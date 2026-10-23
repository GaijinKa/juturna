"""In-process stand-in for the links between workers, for tests only."""

import queue
import threading
import time

from juturna.transport import ThreadingTransport
from juturna.utils.log_utils import jt_logger


_END = object()


class LoopbackDestination:
    """
    Deliver messages to a node of another `Pipeline` of this process.

    One queue and one drain thread per link keep the order of the stream.
    """

    def __init__(self, peers: dict, node_name: str, delay: float):
        self._peers = peers
        self._node_name = node_name
        self._delay = delay
        self._queue = queue.Queue(maxsize=4)
        self._logger = jt_logger(f'loopback.{node_name}')
        self.dead = False
        self._warned = False
        self._thread = threading.Thread(target=self._drain, daemon=True)
        self._thread.start()

    def _drain(self):
        while not self.dead:
            try:
                message = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if message is _END:
                return

            time.sleep(self._delay)
            self._peers[self._node_name]._nodes[self._node_name].put(message)

    def put(self, message):
        while not self.dead:
            try:
                self._queue.put(message, timeout=0.1)

                return
            except queue.Full:
                continue

        if not self._warned:
            self._warned = True
            self._logger.warning(f'link to {self._node_name} is dead')

    def close(self):
        self.put(_END)
        self._thread.join()

    def kill_link(self):
        self.dead = True

    def cancel(self):
        # no join: the thread may be blocked on a peer that is not killed yet
        self.dead = True


class LoopbackTransport(ThreadingTransport):
    """Reach the nodes of `peers` (node name -> pipeline) in this process."""

    def __init__(self, peers: dict, delay: float = 0):
        super().__init__()

        self.peers = peers
        self.delay = delay
        self.destinations: dict[str, LoopbackDestination] = dict()

    def remote_destination(self, node_name):
        destination = LoopbackDestination(self.peers, node_name, self.delay)
        self.destinations[node_name] = destination

        return destination
