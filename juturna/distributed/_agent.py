import queue
import threading

from collections.abc import Callable

import grpc

from juturna.components import Pipeline
from juturna.names import PipelineStatus
from juturna.remotizer.c_protos.messaging_service_pb2_grpc import (
    MessagingServiceStub,
)
from juturna.remotizer.c_protos.payloads_pb2 import ProtoEnvelope
from juturna.transport.grpc import DataServer
from juturna.transport.grpc._options import CHANNEL_OPTIONS
from juturna.utils.log_utils import jt_logger

from juturna.distributed._protocol import PROTOCOL_VERSION
from juturna.distributed._protocol import envelope_args
from juturna.distributed._protocol import make_envelope


class WorkerAgent:
    """
    The worker side of the control stream: register on the host, then run the
    commands it sends.
    """

    def __init__(
        self,
        host_address: str,
        name: str,
        data_address: str,
        folder: str,
        max_streams: int = 16,
        token: str | None = None,
    ):
        """
        Parameters
        ----------
        host_address : str
            ``HOST:PORT`` of the host's worker registry.
        name : str
            The worker name, unique among the workers of the host.
        data_address : str
            ``HOST:PORT`` of the data server, see `DataServer`.
        folder : str
            Base folder of the pipelines run by this worker.
        max_streams : int
            Incoming data streams served at once.
        token : str | None
            The service token of the host.

        """
        self.name = name
        self.folder = folder
        self.data_address = data_address
        self.handlers: dict[str, Callable[[dict], dict]] = dict()
        self._host_address = host_address
        self._max_streams = max_streams
        self._token = token
        self._data = DataServer(data_address, max_streams)
        self._pipelines: dict[str, Pipeline] = dict()
        self._lock = threading.Lock()
        self._outbound: queue.Queue[ProtoEnvelope | None] = queue.Queue()
        self._channel: grpc.Channel | None = None
        self._responses = None
        self._logger = jt_logger(f'distributed.{name}')

    def connect(self):
        """
        Start the data server and register on the host.

        Raises
        ------
        PermissionError
            If the host refuses the registration.
        ConnectionError
            If the host cannot be reached.

        """
        self.data_address = self._data.start()
        self._channel = grpc.insecure_channel(
            self._host_address, options=CHANNEL_OPTIONS
        )
        self._responses = MessagingServiceStub(self._channel).Control(
            self._requests()
        )
        self._outbound.put(
            make_envelope(
                'register',
                {
                    'name': self.name,
                    'data_address': self.data_address,
                    'max_streams': self._max_streams,
                    'protocol': PROTOCOL_VERSION,
                    'token': self._token or '',
                },
            )
        )

        try:
            answer = envelope_args(next(self._responses))
        except (grpc.RpcError, StopIteration) as exc:
            self.close()

            raise ConnectionError(
                f'cannot register on {self._host_address}: {exc}'
            ) from exc

        if 'error' in answer:
            self.close()

            raise PermissionError(answer['error'])

    def serve_forever(self):
        """
        Run the commands of the host until the control stream closes, then
        drop the pipelines, see `on_host_lost`.
        """
        try:
            for envelope in self._responses:
                # a command blocked in close() must not hide the host loss
                threading.Thread(
                    target=self._run, args=(envelope,), daemon=True
                ).start()
        except grpc.RpcError as exc:
            self._logger.warning(f'control stream closed: {exc.code()}')

        self.on_host_lost()

    def close(self):
        """Close the control stream, drop the pipelines, stop the server."""
        self._outbound.put(None)

        if self._responses is not None:
            self._responses.cancel()

        if self._channel is not None:
            self._channel.close()

        self.on_host_lost()
        self._data.stop(0)

    def on_host_lost(self):
        """
        Kill and destroy every pipeline held: an ordered stop could block on
        a stream towards another worker doing the same.
        """
        while True:
            with self._lock:
                if not self._pipelines:
                    return

                pipe_id, pipeline = self._pipelines.popitem()

            self._drop(pipe_id, pipeline)

    def _drop(self, pipe_id: str, pipeline: Pipeline):
        for step in ('abort_stop', 'kill', 'destroy'):
            if (
                step == 'kill'
                and pipeline.status['self'] != PipelineStatus.RUNNING
            ):
                continue

            try:
                getattr(pipeline, step)()
            except Exception:
                self._logger.warning(
                    f'{step} of pipeline {pipe_id} failed', exc_info=True
                )

        self._data.unregister(pipe_id)

    def _requests(self):
        while (envelope := self._outbound.get()) is not None:
            yield envelope

    def _run(self, envelope: ProtoEnvelope):
        handler = self.handlers.get(envelope.request_type)

        try:
            if handler is None:
                raise LookupError(f'unknown command {envelope.request_type}')

            answer = handler(envelope_args(envelope))
        except Exception as exc:
            self._logger.warning(
                f'command {envelope.request_type} failed: {exc}'
            )
            answer = {'error': str(exc)}

        self._outbound.put(make_envelope('answer', answer, envelope.id))
