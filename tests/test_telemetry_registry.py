import pytest

from juturna.telemetry import TelemetryContext
from juturna.telemetry import check_telemetry
from juturna.telemetry import get_telemetry
from juturna.telemetry.memory import MemoryTelemetry
from juturna.transport import ThreadingTransport


def _ctx():
    return TelemetryContext(ThreadingTransport(), 'main', '/tmp')


def test_no_spec_means_off():
    assert get_telemetry(None, _ctx()) is None, 'None must switch it off'


def test_memory_by_name_with_options():
    manager = get_telemetry({'name': 'memory', 'max_records': 7}, _ctx())

    assert isinstance(manager, MemoryTelemetry), f'Got {type(manager)}'


def test_string_spec_is_refused_with_the_new_form():
    with pytest.raises(ValueError, match='"name"'):
        get_telemetry('tele.csv', _ctx())


@pytest.mark.parametrize('spec', [{}, {'max_records': 5}])
def test_spec_without_name(spec):
    with pytest.raises(ValueError, match='needs a name'):
        get_telemetry(spec, _ctx())


def test_unknown_name():
    with pytest.raises(ValueError, match='unknown telemetry manager'):
        get_telemetry({'name': 'nope'}, _ctx())


def test_unknown_option():
    with pytest.raises(ValueError, match="invalid options for the 'memory'"):
        get_telemetry({'name': 'memory', 'colour': 'red'}, _ctx())


def test_check_does_not_build_anything():
    check_telemetry({'name': 'memory'}, ThreadingTransport)
    check_telemetry(None, ThreadingTransport)

    with pytest.raises(ValueError, match='unknown telemetry manager'):
        check_telemetry({'name': 'nope'}, ThreadingTransport)
