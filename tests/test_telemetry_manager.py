import csv

from juturna.components._telemetry_manager import TelemetryManager
from juturna.transport import ThreadingTransport


class _LocalOnlyTransport(ThreadingTransport):
    def new_queue(self, maxsize: int = 0, local: bool = False):
        assert local, 'telemetry batches must go on a local queue'

        return super().new_queue(maxsize, local)


def test_telemetry_batches_go_on_a_local_queue(tmp_path):
    target = tmp_path / 'tele.csv'
    manager = TelemetryManager(str(target), transport=_LocalOnlyTransport())

    manager.start()
    manager.record_telemetry([(1.0, 'tx', 'in', 'in', 0, 0, 10)])
    manager.stop()

    with open(target, newline='') as f:
        rows = list(csv.reader(f))

    assert len(rows) == 2, f'Expected header and 1 record, got {rows}'
    assert rows[1][1:3] == ['tx', 'in'], f'Unexpected record {rows[1]}'
