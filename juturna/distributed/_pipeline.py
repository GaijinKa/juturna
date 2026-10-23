import copy
import threading
import time

from collections.abc import Iterable
from collections.abc import Mapping

from juturna.components import Pipeline
from juturna.components import layered_stop
from juturna.components import pipeline_layers
from juturna.components._pipeline import DEFAULT_WORKER
from juturna.components._pipeline import _TRANSITION_RULES
from juturna.components.exceptions import PipelineBusyError
from juturna.names import PipelineStatus
from juturna.transport.grpc import DataServer
from juturna.utils.log_utils import jt_logger

from juturna.distributed._registry import RemoteWorker
from juturna.distributed._registry import WorkerRegistry


class DistributionError(RuntimeError):
    """A pipeline cannot be placed on its workers."""


class RemoteParticipant:
    """The part of a pipeline on a worker, as `layered_stop` drives it."""

    def __init__(self, worker: RemoteWorker, pipe_id: str):
        self._worker = worker
        self._pipe_id = pipe_id

    @property
    def alive(self) -> bool:
        return self._worker.alive

    def _call(self, command: str, **args) -> dict | None:
        try:
            return self._worker.call(
                command, {'pipe_id': self._pipe_id, **args}
            )
        except ConnectionError:
            # a lost worker counts as done, so the stop never hangs on it
            return None

    def begin_stop(self) -> bool:
        answer = self._call('begin_stop')

        return bool(answer and answer['began'])

    def close_remote(self, nodes: Iterable[str]):
        self._call('close_remote', nodes=list(nodes))

    def stop_nodes(self, nodes: Iterable[str]):
        self._call('stop_nodes', nodes=list(nodes))

    def end_stop(self):
        self._call('end_stop')

    def abort_stop(self):
        # must not hide the error that made layered_stop abort
        try:
            self._call('abort_stop')
        except Exception:
            jt_logger('distributed').warning(
                f'abort_stop of {self._pipe_id} on {self._worker.name} failed',
                exc_info=True,
            )


class DistributedPipeline:
    """
    A pipeline whose nodes run on the host (``main``) and on workers, driven
    from the host over the workers' control streams.
    """

    # same lifecycle rules and exceptions as a local pipeline
    _begin_transition = Pipeline._begin_transition
    _end_transition = Pipeline._end_transition
    _abort_transition = Pipeline._abort_transition

    def __init__(
        self,
        config: dict,
        registry: WorkerRegistry,
        data_server: DataServer,
        environ: Mapping[str, str] | None = None,
    ):
        """
        Parameters
        ----------
        config : dict
            The whole pipeline configuration; a node runs on the worker named
            by its ``worker`` key, ``main`` (this process) when missing.
        registry : WorkerRegistry
            The workers registered on the host.
        data_server : DataServer
            The started data server of the host, receiving for its nodes.
        environ : Mapping[str, str] | None
            Values of the allowed ``$JT_ENV_*`` variables the configuration
            references, sent to every worker and used by the local part.

        """
        self._config = copy.deepcopy(config)
        self._name = self._config['pipeline']['name']
        self._pipe_id = self._config['pipeline']['id']
        self._pipe_path = self._config['pipeline']['folder']
        self._registry = registry
        self._data_server = data_server
        self._environ = dict(environ or dict())
        self._logger = jt_logger(self._name)

        self._placement = {
            node['name']: node.get('worker', DEFAULT_WORKER)
            for node in self._config['pipeline']['nodes']
        }
        self._workers = sorted(set(self._placement.values()) - {DEFAULT_WORKER})

        self._local: Pipeline | None = None
        self._remotes: dict[str, RemoteWorker] = dict()
        self._reservations: list[tuple[RemoteWorker | DataServer, int]] = []

        self._status = PipelineStatus.NEW
        self._status_lock = threading.Lock()
        self._transitioning = False

        self.created_at = time.time()

    @property
    def pipe_id(self) -> str:
        return self._pipe_id

    @property
    def pipe_path(self) -> str:
        return self._pipe_path

    @property
    def name(self) -> str:
        return self._name

    @property
    def _telemetry(self) -> bool:
        return self._local._telemetry if self._local else False

    @property
    def _telemetry_manager(self):
        return self._local._telemetry_manager if self._local else None

    @property
    def status(self) -> dict:
        """The local status and the liveness of each worker, never asked."""
        local = self._local
        workers = dict()

        for name in self._workers:
            remote = self._remotes.get(name) or self._registry.get(name)
            workers[name] = 'alive' if remote and remote.alive else 'lost'

        return {
            'pipe_id': self.pipe_id,
            'folder': self.pipe_path,
            'self': self._status,
            'workers': workers,
            'nodes': local.status['nodes'] if local else dict(),
        }

    def warmup(self):
        """
        Reserve the incoming streams of every process, then warm up the
        workers and the local part.

        If anything fails, the workers already warmed up are destroyed and
        the reservations released: the pipeline stays NEW and warmup() can be
        retried.

        Raises
        ------
        DistributionError
            If a worker is not registered, or cannot take the streams.

        """
        if not self._begin_transition('warmup', _TRANSITION_RULES):
            return

        try:
            self._warmup()
        except BaseException:
            self._abort_transition(self._rollback_warmup)

            raise
        else:
            self._end_transition(PipelineStatus.READY)

    def _warmup(self):
        pipeline_layers(self._config)

        workers = dict()

        for name in self._workers:
            remote = self._registry.get(name)

            if remote is None or not remote.alive:
                raise DistributionError(f'worker {name} is not registered')

            workers[name] = remote

        inbound: dict[str, set] = dict()

        for link in self._config['pipeline']['links']:
            sender = self._placement[link['from']]
            receiver = self._placement[link['to']]

            if sender != receiver:
                inbound.setdefault(receiver, set()).add((sender, link['to']))

        for process, pairs in sorted(inbound.items()):
            holder = workers.get(process, self._data_server)

            if not holder.reserve(len(pairs)):
                raise DistributionError(
                    f'worker {process} cannot accept {len(pairs)} more streams'
                )

            self._reservations.append((holder, len(pairs)))

        addresses = {
            name: remote.data_address for name, remote in workers.items()
        }
        addresses[DEFAULT_WORKER] = self._data_server.address

        for name, remote in workers.items():
            remote.call(
                'warmup',
                {
                    'config': self._process_config(name, addresses),
                    'environ': self._environ,
                },
            )
            self._remotes[name] = remote

        if DEFAULT_WORKER in self._placement.values():
            self._local = Pipeline(
                self._process_config(DEFAULT_WORKER, addresses),
                worker=DEFAULT_WORKER,
                environ=self._environ,
            )
            self._local.warmup()
            self._data_server.register(self._pipe_id, self._local._nodes)

    def _process_config(self, worker: str, addresses: dict) -> dict:
        config = copy.deepcopy(self._config)
        config['pipeline']['transport'] = {
            'name': 'grpc',
            'worker': worker,
            'pipe_id': self._pipe_id,
            'peers': {
                node: addresses[where]
                for node, where in self._placement.items()
                if where != worker
            },
        }

        return config

    def _rollback_warmup(self):
        for name, remote in self._remotes.items():
            try:
                remote.call('destroy', {'pipe_id': self._pipe_id})
            except Exception:
                self._logger.warning(
                    f'cannot destroy {self._pipe_id} on {name}', exc_info=True
                )

        self._remotes = dict()
        # the local part rolled itself back, nothing left to release in it
        self._local = None
        self._release()

    def _release(self):
        reservations, self._reservations = self._reservations, list()

        for holder, n in reservations:
            holder.release(n)

    def start(self):
        """
        Start the workers, then the local part.

        If one fails, those already started go back to READY with
        ``abort_start``, and so does the pipeline.
        """
        if not self._begin_transition('start', _TRANSITION_RULES):
            return

        started = list()

        def _rollback():
            for remote in started:
                try:
                    remote.call('abort_start', {'pipe_id': self._pipe_id})
                except Exception:
                    self._logger.warning(
                        f'cannot abort start on {remote.name}', exc_info=True
                    )

        try:
            for remote in self._remotes.values():
                remote.call('start', {'pipe_id': self._pipe_id})
                started.append(remote)

            if self._local:
                self._local.start()
        except BaseException:
            self._abort_transition(_rollback)

            raise
        else:
            self._end_transition(PipelineStatus.RUNNING)

    def stop(self):
        """
        Stop every part layer by layer on the global graph, so no message in
        flight between processes is lost; lost workers are skipped.
        """
        if not self._begin_transition('stop', _TRANSITION_RULES):
            return

        try:
            self._stop()
        except Exception:
            self._abort_transition()

            raise
        else:
            self._end_transition(PipelineStatus.STOPPED)

    def _stop(self):
        participants = [self._local] if self._local else list()
        participants += [
            RemoteParticipant(remote, self._pipe_id)
            for remote in self._remotes.values()
        ]

        layered_stop(participants, pipeline_layers(self._config))

    def kill(self):
        """Kill every alive worker part, then the local part."""
        if not self._begin_transition('kill', _TRANSITION_RULES):
            return

        try:
            self._each_worker('kill')

            if self._local:
                self._local.kill()
        except Exception:
            self._abort_transition()

            raise
        else:
            self._end_transition(PipelineStatus.STOPPED)

    def _each_worker(self, command: str):
        # one worker failing must not keep the others, or the local part,
        # running
        for name, remote in self._remotes.items():
            if not remote.alive:
                continue

            try:
                remote.call(command, {'pipe_id': self._pipe_id})
            except Exception:
                self._logger.warning(
                    f'{command} of {self._pipe_id} on {name} failed',
                    exc_info=True,
                )

    def destroy(self):
        """
        Stop the pipeline if running, then destroy it everywhere and release
        its streams. A no-op once DESTROYED.
        """
        with self._status_lock:
            if self._status == PipelineStatus.DESTROYED:
                return

            if self._transitioning:
                raise PipelineBusyError(
                    self.name,
                    f'pipeline {self.name} is already processing another '
                    'lifecycle operation, cannot destroy() concurrently',
                )

            was_running = self._status == PipelineStatus.RUNNING
            self._transitioning = True

        try:
            if was_running:
                self._stop()

            self._each_worker('destroy')
            self._remotes = dict()
            # unregister kills the receiving nodes: only once they are stopped
            self._data_server.unregister(self._pipe_id)

            if self._local:
                self._local.destroy()

            self._release()
        except Exception:
            self._abort_transition()

            raise

        self._end_transition(PipelineStatus.DESTROYED)
