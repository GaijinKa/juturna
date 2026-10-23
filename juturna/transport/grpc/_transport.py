import grpc

from juturna.transport.threads import ThreadingTransport

from juturna.transport.grpc._destination import _GrpcDestination
from juturna.transport.grpc._options import KEEPALIVE_OPTIONS


class GrpcTransport(ThreadingTransport):
    """
    Threading transport that reaches the nodes of other processes over gRPC.

    Local queues and workers are the threading ones. A link to a node of
    another process streams to the `DataServer` at its address in ``peers``,
    one stream per destination node.
    """

    def __init__(
        self,
        worker: str,
        pipe_id: str,
        peers: dict[str, str],
        queue_size: int = 64,
    ):
        """
        Parameters
        ----------
        worker : str
            The worker this process runs as, sent to the receivers.
        pipe_id : str
            The pipeline the links belong to.
        peers : dict[str, str]
            Data address (``host:port``) of each node of another process.
        queue_size : int
            Messages buffered per link before a writer blocks.

        """
        self._worker = worker
        self._pipe_id = pipe_id
        self._peers = dict(peers)
        self._queue_size = queue_size
        self._channels: dict[str, grpc.Channel] = dict()
        self._destinations: dict[str, _GrpcDestination] = dict()

    def remote_destination(self, node_name: str) -> _GrpcDestination:
        if node_name not in self._peers:
            raise ValueError(
                f'node {node_name} runs in another worker, but the grpc '
                'transport has no data address for it'
            )

        if node_name not in self._destinations:
            address = self._peers[node_name]

            if address not in self._channels:
                self._channels[address] = grpc.insecure_channel(
                    address, options=KEEPALIVE_OPTIONS
                )

            self._destinations[node_name] = _GrpcDestination(
                self._channels[address],
                address,
                node_name,
                self._pipe_id,
                self._worker,
                self._queue_size,
            )

        return self._destinations[node_name]
