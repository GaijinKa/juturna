from juturna.transport import BrowserTransport
from juturna.transport.browser._telemetry import BrowserTelemetryManager


def _record(i):
    return (float(i), 'tx', 'in', 'in', i, i, 10)


def test_batch_is_tagged_with_the_worker_and_posted():
    posted = []
    manager = BrowserTelemetryManager('w1', post=posted.append)

    manager.record_telemetry([_record(0), _record(1)])

    assert len(posted) == 1, f'Expected 1 message, got {len(posted)}'
    assert posted[0]['type'] == 'telemetry', f'Unexpected {posted[0]}'
    assert posted[0]['worker'] == 'w1', f'Unexpected {posted[0]}'
    assert posted[0]['records'][1][-1] == 'w1', (
        f'The worker must be the last field, got {posted[0]["records"][1]}'
    )
    assert posted[0]['records'][1][:-1] == list(_record(1)), (
        f'The record must keep its fields, got {posted[0]["records"][1]}'
    )


def test_oldest_records_are_dropped_beyond_the_limit():
    manager = BrowserTelemetryManager('w1', max_records=3, post=lambda m: None)

    manager.record_telemetry([_record(i) for i in range(5)])

    ids = [r[4] for r in manager.records()]
    assert ids == [2, 3, 4], f'Expected the latest 3 records, got {ids}'


def test_empty_batch_is_not_posted():
    posted = []
    manager = BrowserTelemetryManager('w1', post=posted.append)

    manager.record_telemetry([])

    assert not posted, f'Expected nothing posted, got {posted}'


def test_failing_post_keeps_the_records_and_does_not_raise():
    def post(message):
        raise RuntimeError('no page')

    manager = BrowserTelemetryManager('w1', post=post)

    manager.record_telemetry([_record(0)])

    assert len(manager.records()) == 1, 'the record must be kept'


def test_transport_builds_the_manager_of_its_worker():
    manager = BrowserTransport().new_telemetry_manager('w2')

    assert isinstance(manager, BrowserTelemetryManager), (
        f'Expected a BrowserTelemetryManager, got {type(manager)}'
    )
    assert manager._worker == 'w2', f'Unexpected worker {manager._worker}'
