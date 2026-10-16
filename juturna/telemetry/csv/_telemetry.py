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
from juturna.utils import jt_utils
from juturna.utils.log_utils import jt_logger

DEFAULT_MAX_PENDING = 10000

# written by the pipeline in the same folder
_RESERVED_NAMES = frozenset({'config.json'})


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
        # the target becomes a path under the pipeline folder
        jt_utils.check_name(target, 'telemetry file')

        if target in _RESERVED_NAMES:
            raise ValueError(
                f'invalid telemetry file name {target!r}: reserved for the '
                'pipeline configuration'
            )

        if (
            isinstance(max_pending, bool)
            or not isinstance(max_pending, int)
            or max_pending < 1
        ):
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
        self._file = None

        # approximate: `+=` from several threads may miss a count
        self.dropped = 0

    def start(self):
        """Start the worker that writes the file"""
        if self._thread is not None:
            self._logger.info('telemetry already running')

            return

        # opened here, not by the writer: a target that cannot be written
        # fails the start of the pipeline instead of killing a worker
        self._file = open(self._target, 'a', newline='', buffering=1)  # noqa: SIM115

        try:
            # on a restart the file already has its header
            if self._file.tell() == 0:
                csv.writer(self._file).writerow(TELEMETRY_FIELDS)

            self._thread = self._transport.spawn(
                target=self._read_telemetry,
                name='telemetry',
                daemon=True,
            )

            self._thread.start()
        except BaseException:
            self._file.close()
            self._thread = None

            raise

    def stop(self):
        """Write what is left and stop the worker"""
        if self._thread is not None:
            if self._thread.is_alive():
                self._evt.set()

                # an empty batch wakes up the reader blocked on get(); if the
                # queue is full the reader is busy and sees the event itself
                with contextlib.suppress(Full):
                    self._queue.put_nowait(list())

                self._thread.join()

            # a stopped manager can be started again, as after a failed start
            self._thread = None
            self._evt.clear()

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

        # the header is repeated at every start, and a row may be partial or
        # corrupted: those are skipped
        records = []

        for row in rows:
            if len(row) != len(TELEMETRY_FIELDS) or row[0] == 'ts':
                continue

            try:
                records.append(_parse(row))
            except ValueError:
                continue

        return records

    def _read_telemetry(self):
        self._logger.info(f'telemetry started, writing on {self._target}')

        with self._file as f:
            _writer = csv.writer(f)

            while not self._evt.is_set():
                try:
                    telemetry_batch = self._queue.get(
                        timeout=JUTURNA_THREAD_JOIN_TIMEOUT
                    )
                except Empty:
                    continue

                self._write(_writer, telemetry_batch)

            while True:
                try:
                    telemetry_batch = self._queue.get_nowait()
                except Empty:
                    break

                self._write(_writer, telemetry_batch)

    def _write(self, writer, batch: list[tuple]):
        try:
            writer.writerows(batch)
        except Exception:
            # a batch that cannot be written must not kill the writer
            self.dropped += len(batch)
            self._logger.error('cannot write telemetry', exc_info=True)


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
