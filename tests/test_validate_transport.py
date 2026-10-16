import pytest

from juturna.cli.commands._validation_tools import ValidationError
from juturna.cli.commands.validate import _check_transport


@pytest.mark.parametrize(
    'pipeline',
    [
        {},
        {'transport': None},
        {'transport': 'threading'},
        {'transport': 'browser'},
        {'transport': {'name': 'browser', 'queue_capacity': 4}},
    ],
)
def test_valid_transports(pipeline):
    _check_transport(pipeline)


@pytest.mark.parametrize(
    'pipeline',
    [
        {'transport': 'nope'},
        {'transport': {'name': 'nope'}},
    ],
)
def test_unknown_transport_is_a_validation_error(pipeline):
    with pytest.raises(ValidationError, match='nope'):
        _check_transport(pipeline)
