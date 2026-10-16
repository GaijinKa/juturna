import contextlib
import csv
import pathlib

from typing import ClassVar

from juturna.meta import JUTURNA_THREAD_JOIN_TIMEOUT
from juturna.telemetry._base import TELEMETRY_FIELDS
from juturna.telemetry._base import TelemetryContext
from juturna.telemetry._base import tag_records
from juturna.transport import Empty
from juturna.transport import Full
from juturna.transport import WorkerHandle
from juturna.utils.log_utils import jt_logger

DEFAULT_MAX_PENDING = 10000


class CsvTelemetry:
    """Write the telemetry records on a CSV file, from a worker of its own"""

    requires: ClassVar[frozenset[str]] = frozenset({'shared_fs'})

    def __init__(
        self,
        ctx: TelemetryContext,
        target: str,
        max_pending: int = DEFAULT_MAX_PENDING,
    ):
        """
        Parameters
        ----------
        ctx : TelemetryContext
            The context of the pipeline.
        target : str
            Name of the CSV file, relative to the folder of the pipeline.
        max_pending : int
            Batches waiting to be written. When the writer cannot keep up, the
            new batches are dropped (see `dropped`): the nodes never wait.

        """
        if not isinstance(max_pending, int) or max_pending < 1:
            raise ValueError(
                f'max_pending must be a positive integer, got {max_pending}'
            )

        self._target = pathlib.Path(ctx.pipe_path, target)
        self._worker = ctx.worker
        self._transport = ctx.transport

        # batches are lists, which a cross-worker ring queue does not accept
        self._queue = ctx.transport.new_queue(maxsize=max_pending, local=True)
        self._evt = ctx.transport.new_event()
        self._logger = jt_logger('telemetry')

        self._thread: WorkerHandle | None = None

        # approximate: `+=` from several threads may miss a count
        self.dropped = 0

    def start(self):
        """Start the worker that writes the file"""
        if self._thread is not None:
            self._logger.info('telemetry already running')

            return

        self._thread = self._transport.spawn(
            target=self._read_telemetry,
            name='telemetry',
            daemon=True,
        )

        self._thread.start()

    def stop(self):
        """Write what is left and stop the worker"""
        if self._thread is not None and self._thread.is_alive():
            self._evt.set()

            # an empty batch wakes up the reader blocked on get(); if the
            # queue is full the reader is busy and sees the event by itself
            with contextlib.suppress(Full):
                self._queue.put_nowait(list())

            self._thread.join()

        if self.dropped:
            self._logger.warning(f'{self.dropped} telemetry records dropped')

    def record_telemetry(self, record_batch: list[tuple]):
        """Queue a batch to be written, or drop it if the writer is behind"""
        # the telemetry must never slow a node down
        try:
            self._queue.put_nowait(tag_records(record_batch, self._worker))
        except Full:
            self.dropped += len(record_batch)

    def records(self) -> list[tuple]:
        """The records written so far, parsed, oldest first"""
        try:
            with open(self._target, newline='') as f:
                rows = list(csv.reader(f))
        except FileNotFoundError:
            return []

        # the header is repeated at every start, and the last row may be partial
        return [
            _parse(row)
            for row in rows
            if len(row) == len(TELEMETRY_FIELDS) and row[0] != 'ts'
        ]

    def _read_telemetry(self):
        self._logger.info(f'telemetry started, writing on {self._target}')

        with open(self._target, 'a', newline='', buffering=1) as f:
            _writer = csv.writer(f)
            _writer.writerow(TELEMETRY_FIELDS)

            while not self._evt.is_set():
                try:
                    telemetry_batch = self._queue.get(
                        timeout=JUTURNA_THREAD_JOIN_TIMEOUT
                    )
                except Empty:
                    continue

                _writer.writerows(telemetry_batch)

            while True:
                try:
                    telemetry_batch = self._queue.get_nowait()
                except Empty:
                    break

                _writer.writerows(telemetry_batch)


def _parse(row: list[str]) -> tuple:
    ts, evt, node, origin, msg_id, src_id, size, worker = row

    return (
        float(ts),
        evt,
        node,
        origin,
        int(msg_id),
        int(src_id) if src_id else None,
        int(size),
        worker,
    )
