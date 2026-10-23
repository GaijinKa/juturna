import queue
import secrets
import threading

from concurrent.futures import ThreadPoolExecutor

import grpc

from juturna.remotizer.c_protos.messaging_service_pb2_grpc import (
    MessagingServiceServicer,
    add_MessagingServiceServicer_to_server,
)
from juturna.remotizer.c_protos.payloads_pb2 import ProtoEnvelope
from juturna.transport.grpc._options import SERVER_OPTIONS
from juturna.utils.log_utils import jt_logger

from juturna.distributed._protocol import PROTOCOL_VERSION
from juturna.distributed._protocol import envelope_args
from juturna.distributed._protocol import make_envelope


class RemoteWorker:
    """The host's handle on a registered worker and its control stream."""

    def __init__(self, name: str, data_address: str, max_streams: int):
        self.name = name
        self.data_address = data_address
        self.max_streams = max_streams
        self.alive = True
        self._reserved = 0
        self._pending: dict[str, dict] = dict()
        self._outbound: queue.Queue[ProtoEnvelope | None] = queue.Queue()
        self._lock = threading.Lock()

    def call(self, command: str, args: dict, timeout: float | None = None):
        """
        Run a command on the worker and wait for its answer.

        Parameters
        ----------
        command : str
            The command name, one of the worker's handlers.
        args : dict
            JSON-serialisable arguments of the command.
        timeout : float | None
            Seconds to wait for the answer; ``None`` waits until the worker
            answers or goes away.

        Returns
        -------
        dict
            The answer of the worker.

        Raises
        ------
        RuntimeError
            If the worker answers with an error.
        ConnectionError
            If the control stream is closed, or closes before the answer.
        TimeoutError
            If no answer arrives within ``timeout``.

        """
        request = make_envelope(command, args)
        slot = {'done': threading.Event()}

        with self._lock:
            if not self.alive:
                raise ConnectionError(f'worker {self.name} is not connected')

            self._pending[request.id] = slot

        self._outbound.put(request)

        if not slot['done'].wait(timeout):
            with self._lock:
                self._pending.pop(request.id, None)

            raise TimeoutError(f'worker {self.name} did not answer {command}')

        if 'answer' not in slot:
            raise ConnectionError(f'worker {self.name} disconnected')

        if not isinstance(slot['answer'], dict):
            raise RuntimeError(f'worker {self.name} answered {slot["answer"]}')

        if 'error' in slot['answer']:
            raise RuntimeError(slot['answer']['error'])

        return slot['answer']

    def reserve(self, n: int) -> bool:
        """Promise n incoming streams of the worker, if they fit."""
        with self._lock:
            if self._reserved + n > self.max_streams:
                return False

            self._reserved += n

            return True

    def release(self, n: int):
        """Give back streams promised by `reserve`."""
        with self._lock:
            self._reserved = max(0, self._reserved - n)

    def _answer(self, envelope: ProtoEnvelope):
        with self._lock:
            slot = self._pending.pop(envelope.response_to, None)

        if slot is not None:
            slot['answer'] = envelope_args(envelope)
            slot['done'].set()

    def _close(self):
        with self._lock:
            self.alive = False
            pending, self._pending = self._pending, dict()

        self._outbound.put(None)

        for slot in pending.values():
            slot['done'].set()

    def _outgoing(self):
        while (envelope := self._outbound.get()) is not None:
            yield envelope


class WorkerRegistry(MessagingServiceServicer):
    """
    Accept the registration of workers on the host, and keep their control
    streams open to send them commands.
    """

    def __init__(self, token: str | None = None, max_workers: int = 64):
        """
        Parameters
        ----------
        token : str | None
            The service token a worker must present; ``None`` accepts any.
        max_workers : int
            Control streams served at once.

        """
        self._token = token
        self._max_workers = max_workers
        self._workers: dict[str, RemoteWorker] = dict()
        self._lock = threading.Lock()
        self._server: grpc.Server | None = None
        self._logger = jt_logger('distributed.registry')

    def start(self, address: str) -> str:
        """
        Bind and start the control server.

        Parameters
        ----------
        address : str
            ``HOST:PORT`` to bind; port 0 picks a free one.

        Returns
        -------
        str
            ``HOST:PORT`` with the port actually bound.

        """
        self._server = grpc.server(
            ThreadPoolExecutor(max_workers=self._max_workers),
            options=SERVER_OPTIONS,
            maximum_concurrent_rpcs=self._max_workers,
        )
        add_MessagingServiceServicer_to_server(self, self._server)
        port = self._server.add_insecure_port(address)
        self._server.start()

        return f'{address.rpartition(":")[0]}:{port}'

    def stop(self, grace: float = 0):
        """Stop the server, closing every control stream."""
        if self._server is not None:
            self._server.stop(grace).wait()

        with self._lock:
            workers = list(self._workers.values())

        for worker in workers:
            worker._close()

    def get(self, name: str) -> RemoteWorker | None:
        """The worker registered with that name, if any."""
        with self._lock:
            return self._workers.get(name)

    def _admit(self, args: dict) -> RemoteWorker | str:
        name = args.get('name', '')

        if self._token is not None and not secrets.compare_digest(
            str(args.get('token', '')), self._token
        ):
            return 'invalid service token'

        if args.get('protocol') != PROTOCOL_VERSION:
            return (
                f'protocol {args.get("protocol")} not supported, the host '
                f'speaks {PROTOCOL_VERSION}'
            )

        if not name or name == 'main':
            return f'invalid worker name {name!r}'

        with self._lock:
            current = self._workers.get(name)

            if current is not None and current.alive:
                return f'worker {name} already registered'

            worker = RemoteWorker(
                name, args['data_address'], int(args['max_streams'])
            )
            self._workers[name] = worker

        return worker

    def Control(self, request_iterator, context):  # noqa: D102
        try:
            first = next(request_iterator)
        except (StopIteration, grpc.RpcError):
            return

        worker = self._admit(envelope_args(first))

        if isinstance(worker, str):
            self._logger.warning(f'registration refused: {worker}')
            yield make_envelope('error', {'error': worker}, first.id)

            return

        if not context.add_callback(worker._close):
            worker._close()

        threading.Thread(
            target=self._read,
            args=(worker, request_iterator),
            name=f'control-{worker.name}',
            daemon=True,
        ).start()

        self._logger.info(f'worker {worker.name} registered')
        yield make_envelope('registered', dict(), first.id)
        yield from worker._outgoing()

    def _read(self, worker: RemoteWorker, request_iterator):
        try:
            for envelope in request_iterator:
                worker._answer(envelope)
        except grpc.RpcError:
            pass
        finally:
            worker._close()
            self._logger.warning(f'worker {worker.name} disconnected')
