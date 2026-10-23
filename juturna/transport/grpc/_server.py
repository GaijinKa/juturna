import threading

from concurrent.futures import ThreadPoolExecutor

import grpc

from juturna.components import Node
from juturna.remotizer.c_protos.messaging_service_pb2_grpc import (
    MessagingServiceServicer,
    add_MessagingServiceServicer_to_server,
)
from juturna.remotizer.c_protos.payloads_pb2 import ProtoEnvelope
from juturna.remotizer.utils import deserialize_message
from juturna.utils.log_utils import jt_logger

from juturna.transport.grpc._options import SERVER_OPTIONS
from juturna.transport.grpc._options import check_address


class _Pipe:
    """The nodes a pipeline exposes, and the streams feeding them."""

    def __init__(self, nodes: dict[str, Node]):
        self.nodes = dict(nodes)
        self.closed = False
        self.contexts: set[grpc.ServicerContext] = set()


class _Servicer(MessagingServiceServicer):
    def __init__(self, server: 'DataServer'):
        self._server = server

    def Stream(self, request_iterator, context):  # noqa: D102
        return self._server._serve(request_iterator, context)


class DataServer:
    """
    Receive the streams of other processes and put their messages into the
    local nodes they are meant for.

    One server per process, shared by all its pipelines: a stream names its
    pipeline and node in its first envelope.
    """

    def __init__(self, address: str, max_streams: int = 16):
        """
        Parameters
        ----------
        address : str
            ``HOST:PORT`` to bind and advertise; port 0 picks a free one.
        max_streams : int
            Streams served at once; an extra one is refused right away.

        """
        self._address = address
        self.address: str | None = None
        self._max_streams = max_streams
        self._pipes: dict[str, _Pipe] = dict()
        self._reserved = 0
        self._lock = threading.Lock()
        self._server: grpc.Server | None = None
        self._logger = jt_logger('grpc.data_server')

    def start(self) -> str:
        """
        Bind and start the server.

        Returns
        -------
        str
            The ``host:port`` the other processes dial, with the port
            actually bound.

        Raises
        ------
        ValueError
            If the address is malformed or a wildcard.

        """
        host, _ = check_address(self._address)

        self._server = grpc.server(
            ThreadPoolExecutor(max_workers=self._max_streams),
            options=SERVER_OPTIONS,
            maximum_concurrent_rpcs=self._max_streams,
        )
        add_MessagingServiceServicer_to_server(_Servicer(self), self._server)
        port = self._server.add_insecure_port(self._address)
        self._server.start()
        self.address = f'[{host}]:{port}' if ':' in host else f'{host}:{port}'

        return self.address

    def stop(self, grace: float = 0):
        """Stop the server, releasing the handlers blocked on a node."""
        with self._lock:
            pipe_ids = list(self._pipes)

        for pipe_id in pipe_ids:
            self.unregister(pipe_id)

        if self._server is not None:
            self._server.stop(grace).wait()

    def register(self, pipe_id: str, nodes: dict[str, Node]):
        """Expose the local nodes of a pipeline to the other processes."""
        with self._lock:
            self._pipes[pipe_id] = _Pipe(nodes)

    def unregister(self, pipe_id: str):
        """
        Stop serving a pipeline: its streams are cancelled, and its nodes
        signalled so that a handler blocked in ``put()`` returns.
        """
        with self._lock:
            pipe = self._pipes.pop(pipe_id, None)

            if pipe is None:
                return

            pipe.closed = True
            contexts = list(pipe.contexts)

        for context in contexts:
            context.cancel()

        for node in pipe.nodes.values():
            node.signal_kill()

    def reserve(self, n: int) -> bool:
        """Promise n incoming streams to a pipeline, if they fit."""
        with self._lock:
            if self._reserved + n > self._max_streams:
                return False

            self._reserved += n

            return True

    def release(self, n: int):
        """Give back streams promised by `reserve`."""
        with self._lock:
            self._reserved = max(0, self._reserved - n)

    def _attach(self, envelope: ProtoEnvelope, context) -> _Pipe | None:
        with self._lock:
            pipe = self._pipes.get(envelope.pipe_id)

            if pipe is None or envelope.receiver not in pipe.nodes:
                return None

            pipe.contexts.add(context)

            return pipe

    def _serve(self, request_iterator, context) -> ProtoEnvelope:
        pipe, node, received, warned = None, None, 0, False

        try:
            for envelope in request_iterator:
                if pipe is None:
                    pipe = self._attach(envelope, context)

                    if pipe is None:
                        context.abort(
                            grpc.StatusCode.NOT_FOUND,
                            f'no node {envelope.receiver} in pipeline '
                            f'{envelope.pipe_id}',
                        )

                    node = pipe.nodes[envelope.receiver]

                if pipe.closed:
                    break

                try:
                    message = deserialize_message(envelope.message)
                except Exception as exc:
                    if not warned:
                        warned = True
                        self._logger.warning(
                            f'message for {node.name} cannot be read: {exc}'
                        )

                    continue

                message._freeze()
                node.put(message)
                received += 1
        except grpc.RpcError:
            # the sender cancelled the stream or went away
            pass
        finally:
            if pipe is not None:
                with self._lock:
                    pipe.contexts.discard(context)

        return ProtoEnvelope(metadata={'received': received})
