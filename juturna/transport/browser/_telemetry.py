"""
Telemetry manager of the browser transport.

The CSV of the default manager would live in the memory file system of one
Worker, never merged with the others and growing without bound. This one keeps
the latest records in memory and posts every batch to the page, tagged with
the name of its Worker (the message ids are counters of one interpreter, so
they collide across Workers).
"""

from collections import deque

from juturna.utils.log_utils import jt_logger

DEFAULT_MAX_RECORDS = 10000


class BrowserTelemetryManager:
    """Keep the latest telemetry records and post each batch to the page"""

    def __init__(
        self,
        worker: str,
        max_records: int = DEFAULT_MAX_RECORDS,
        post=None,
    ):
        """
        Parameters
        ----------
        worker : str
            Name of the Worker, added as the last field of every record.
        max_records : int
            Records kept for `records()`; the oldest are dropped first.
        post : Callable[[dict], None] | None
            Delivers a ``{type, worker, records}`` message to the page.
            Defaults to `postMessage`, which only exists inside a Worker.

        """
        self._worker = worker
        self._records: deque = deque(maxlen=max_records)
        self._post = post or _post_to_page
        self._logger = jt_logger('telemetry')

    def start(self):
        """Nothing to start: records are handled where they are produced"""

    def stop(self):
        """Nothing to flush: every batch is posted as it arrives"""

    def record_telemetry(self, record_batch: list):
        """Store a batch and post it to the page"""
        if not record_batch:
            return

        batch = [[*record, self._worker] for record in record_batch]
        self._records.extend(batch)

        try:
            self._post(
                {'type': 'telemetry', 'worker': self._worker, 'records': batch}
            )
        except Exception:
            # telemetry must never take a node down
            self._logger.error('cannot post telemetry', exc_info=True)

    def records(self) -> list:
        """The records kept so far, oldest first"""
        return list(self._records)


def _post_to_page(message: dict):
    from js import Object
    from js import postMessage
    from pyodide.ffi import to_js

    postMessage(to_js(message, dict_converter=Object.fromEntries))
