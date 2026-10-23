import queue
import threading

import grpc

from juturna.components import Message
from juturna.remotizer.c_protos.messaging_service_pb2_grpc import (
    MessagingServiceStub,
)
from juturna.remotizer.c_protos.payloads_pb2 import ProtoEnvelope
from juturna.remotizer.utils import message_to_proto
from juturna.utils.log_utils import jt_logger

from juturna.transport.grpc import _options


_END = object()


class _GrpcDestination:
    """
    Stream the messages for one node of another process.

    Messages are serialized on the writer's thread and queued; gRPC drains
    the queue on its own thread into one client-streaming ``Stream`` call,
    opened by the first message.
    """

    def __init__(
        self,
        channel: grpc.Channel,
        address: str,
        node_name: str,
        pipe_id: str,
        worker: str,
        queue_size: int,
    ):
        self._stub = MessagingServiceStub(channel)
        self._address = address
        self._node_name = node_name
        self._pipe_id = pipe_id
        self._worker = worker
        self._queue = queue.Queue(maxsize=queue_size)
        self._lock = threading.Lock()
        self._dead = threading.Event()
        self._done = threading.Event()
        self._call = None
        self._closing = False
        self._warned = False
        self._logger = jt_logger(f'grpc.{node_name}')
        self._header_bytes = ProtoEnvelope(
            pipe_id=pipe_id, receiver=node_name, sender=worker
        ).ByteSize()

    def put(self, message: Message):
        """Queue a message for the remote node; never raises."""
        if self._dead.is_set():
            return

        try:
            envelope = ProtoEnvelope(message=message_to_proto(message))
            size = envelope.ByteSize() + self._header_bytes

            # gRPC would fail the whole stream on it, not just this message
            if size > _options.MAX_MESSAGE_BYTES:
                raise ValueError(
                    f'{size} bytes, more than {_options.MAX_MESSAGE_BYTES}'
                )
        except Exception as exc:
            if not self._warned:
                self._warned = True
                self._logger.warning(
                    f'message for {self._node_name} cannot be sent: {exc}'
                )

            return

        self._open()
        self._enqueue(envelope)

    def close(self):
        """Flush the stream and wait until the receiver has every message."""
        with self._lock:
            if self._call is None:
                self._dead.set()

                return

            closing, self._closing = self._closing, True

        if not closing:
            self._enqueue(_END)

        self._done.wait()

    def cancel(self):
        """Drop the stream now, unblocking every writer."""
        self._dead.set()

        with self._lock:
            call = self._call

        if call is not None:
            call.cancel()

    def _open(self):
        with self._lock:
            if self._call is not None or self._dead.is_set():
                return

            self._call = self._stub.Stream.future(self._requests())

        self._call.add_done_callback(self._finished)

    def _enqueue(self, item):
        while not self._dead.is_set():
            try:
                self._queue.put(item, timeout=0.1)

                return
            except queue.Full:
                continue

    def _requests(self):
        first = True

        # polled: gRPC's request thread must leave once the link is dead
        while not self._dead.is_set():
            try:
                envelope = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if envelope is _END:
                return

            if first:
                first = False
                envelope.pipe_id = self._pipe_id
                envelope.receiver = self._node_name
                envelope.sender = self._worker

            yield envelope

    def _finished(self, call):
        lost = not self._dead.is_set() and not call.cancelled()
        self._dead.set()

        if lost and call.exception() is not None:
            self._logger.warning(
                f'link to {self._node_name} at {self._address} lost: '
                f'{call.exception().code()}'
            )

        self._done.set()
