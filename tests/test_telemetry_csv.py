import csv
import pathlib
import threading

import pytest

from juturna.telemetry import TELEMETRY_FIELDS
from juturna.telemetry import TelemetryContext
from juturna.telemetry import get_telemetry
from juturna.telemetry.csv import CsvTelemetry
from juturna.transport import BrowserTransport
from juturna.transport import ThreadingTransport


def _ctx(tmp_path, worker='main', transport=None):
    return TelemetryContext(
        transport or ThreadingTransport(), worker, str(tmp_path)
    )


def _record(i, src=None):
    return (float(i), 'tx', 'in', 'in', i, src, 10)


def test_rows_have_the_worker_column(tmp_path):
    manager = CsvTelemetry(_ctx(tmp_path, 'w1'), 'tele.csv')

    manager.start()
    manager.record_telemetry([_record(0), _record(1, 3)])
    manager.stop()

    with open(pathlib.Path(tmp_path, 'tele.csv'), newline='') as f:
        rows = list(csv.reader(f))

    assert rows[0] == list(TELEMETRY_FIELDS), f'Unexpected header {rows[0]}'
    assert len(rows) == 3, f'Expected header and 2 records, got {rows}'
    assert rows[2][-1] == 'w1', f'The worker must be last, got {rows[2]}'


def test_records_read_the_file_back_with_types(tmp_path):
    manager = CsvTelemetry(_ctx(tmp_path, 'w1'), 'tele.csv')

    manager.start()
    manager.record_telemetry([_record(0), _record(1, 3)])
    manager.stop()

    assert manager.records() == [
        (0.0, 'tx', 'in', 'in', 0, None, 10, 'w1'),
        (1.0, 'tx', 'in', 'in', 1, 3, 10, 'w1'),
    ], f'Unexpected {manager.records()}'


def test_records_before_the_file_exists(tmp_path):
    manager = CsvTelemetry(_ctx(tmp_path), 'tele.csv')

    assert manager.records() == [], 'Expected no records'


def test_records_skip_repeated_headers_and_partial_rows(tmp_path):
    target = pathlib.Path(tmp_path, 'tele.csv')
    header = ','.join(TELEMETRY_FIELDS)
    target.write_text(
        f'{header}\n1.0,tx,a,a,1,,5,w\n{header}\n2.0,rx,b,a,2\n'
    )

    records = CsvTelemetry(_ctx(tmp_path), 'tele.csv').records()

    assert records == [(1.0, 'tx', 'a', 'a', 1, None, 5, 'w')], (
        f'Expected only the complete record, got {records}'
    )


def test_full_queue_drops_records_without_blocking(tmp_path):
    manager = CsvTelemetry(_ctx(tmp_path), 'tele.csv', max_pending=2)

    def produce():
        for i in range(5):
            manager.record_telemetry([_record(i)])

    producer = threading.Thread(target=produce, daemon=True)
    producer.start()
    producer.join(timeout=2)

    assert not producer.is_alive(), 'record_telemetry blocked on a full queue'
    assert manager.dropped == 3, f'Expected 3 dropped, got {manager.dropped}'


def test_only_the_records_that_fit_are_written(tmp_path):
    manager = CsvTelemetry(_ctx(tmp_path), 'tele.csv', max_pending=2)

    for i in range(5):
        manager.record_telemetry([_record(i)])

    manager.start()
    manager.stop()

    ids = [r[4] for r in manager.records()]
    assert ids == [0, 1], f'Expected the first 2 records, got {ids}'


def test_stop_does_not_block_on_a_full_queue(tmp_path):
    manager = CsvTelemetry(_ctx(tmp_path), 'tele.csv', max_pending=1)

    manager.start()

    stopper = threading.Thread(target=manager.stop, daemon=True)
    stopper.start()
    stopper.join(timeout=5)

    assert not stopper.is_alive(), 'stop() blocked'


def test_max_pending_must_be_positive(tmp_path):
    with pytest.raises(ValueError, match='max_pending'):
        CsvTelemetry(_ctx(tmp_path), 'tele.csv', max_pending=0)


def test_registry_builds_csv_on_threading(tmp_path):
    manager = get_telemetry(
        {'name': 'csv', 'target': 'tele.csv'}, _ctx(tmp_path)
    )

    assert isinstance(manager, CsvTelemetry), f'Got {type(manager)}'


def test_registry_refuses_csv_on_browser(tmp_path):
    ctx = _ctx(tmp_path, transport=BrowserTransport())

    with pytest.raises(ValueError, match='requires.*shared_fs'):
        get_telemetry({'name': 'csv', 'target': 'tele.csv'}, ctx)


def test_target_is_required(tmp_path):
    with pytest.raises(ValueError, match="invalid options for the 'csv'"):
        get_telemetry({'name': 'csv'}, _ctx(tmp_path))


def test_start_fails_when_the_file_cannot_be_opened(tmp_path):
    manager = CsvTelemetry(_ctx(tmp_path), 'missing/tele.csv')

    with pytest.raises(OSError):
        manager.start()


def test_a_batch_that_cannot_be_written_does_not_kill_the_writer(tmp_path):
    class Unwritable:
        def __str__(self):
            raise RuntimeError('cannot be written')

    manager = CsvTelemetry(_ctx(tmp_path), 'tele.csv')

    manager.start()
    manager.record_telemetry([(1.0, 'tx', 'in', 'in', 0, None, Unwritable())])
    manager.record_telemetry([_record(1)])
    manager.stop()

    ids = [r[4] for r in manager.records()]
    assert ids == [1], f'Expected only the writable record, got {ids}'
    assert manager.dropped == 1, f'Expected 1 dropped, got {manager.dropped}'


def test_records_skip_rows_with_corrupted_numbers(tmp_path):
    target = pathlib.Path(tmp_path, 'tele.csv')
    header = ','.join(TELEMETRY_FIELDS)
    target.write_text(
        f'{header}\n1.0,rx,n,o,1,,,main\n2.0,tx,a,a,2,,5,w\nx,tx,a,a,3,,5,w\n'
    )

    records = CsvTelemetry(_ctx(tmp_path), 'tele.csv').records()

    assert records == [(2.0, 'tx', 'a', 'a', 2, None, 5, 'w')], (
        f'Expected only the valid record, got {records}'
    )


@pytest.mark.parametrize('target', [5, None, '', ['tele.csv']])
def test_target_must_be_a_non_empty_string(tmp_path, target):
    with pytest.raises(ValueError, match='target'):
        CsvTelemetry(_ctx(tmp_path), target)


def test_registry_reports_a_wrong_target_as_a_value_error(tmp_path):
    with pytest.raises(ValueError, match='target'):
        get_telemetry({'name': 'csv', 'target': 5}, _ctx(tmp_path))


@pytest.mark.parametrize('max_pending', [True, False, 1.5, '5', None])
def test_max_pending_must_be_a_real_integer(tmp_path, max_pending):
    with pytest.raises(ValueError, match='max_pending'):
        CsvTelemetry(_ctx(tmp_path), 'tele.csv', max_pending=max_pending)
