import inspect

from typing import Any

from juturna.telemetry._base import TelemetryContext
from juturna.telemetry._base import TelemetryManager
from juturna.telemetry.memory import MemoryTelemetry
from juturna.transport import TransportBackend


# Any: every manager has options of its own, which no common constructor
# signature can express
_MANAGERS: dict[str, Any] = {
    'memory': MemoryTelemetry,
}


def _resolve(
    spec: dict | None, transport_cls: type[TransportBackend]
) -> tuple[type[TelemetryManager], dict] | None:
    if spec is None:
        return None

    if not isinstance(spec, dict):
        raise ValueError(
            f'telemetry must be a dict with a "name", got '
            f'{type(spec).__name__}: use {{"name": "csv", "target": "..."}}'
        )

    options = dict(spec)
    name = options.pop('name', None)

    if not isinstance(name, str):
        raise ValueError(
            f'telemetry needs a name, available: {list(_MANAGERS)}'
        )

    if name not in _MANAGERS:
        raise ValueError(
            f'unknown telemetry manager: {name!r}, available: {list(_MANAGERS)}'
        )

    manager_cls = _MANAGERS[name]

    try:
        # None stands for the context, which the pipeline provides
        inspect.signature(manager_cls).bind(None, **options)
    except TypeError as exc:
        raise ValueError(
            f'invalid options for the {name!r} telemetry: {exc}'
        ) from exc

    missing = manager_cls.requires - transport_cls.capabilities

    if missing:
        raise ValueError(
            f'the {name!r} telemetry requires {sorted(missing)}, which the '
            f'{transport_cls.__name__} transport does not offer'
        )

    return manager_cls, options


def check_telemetry(
    spec: dict | None, transport_cls: type[TransportBackend]
) -> None:
    """
    Check a telemetry configuration against a transport, building nothing.

    Raises
    ------
    ValueError
        If the configuration does not ask for a registered manager with
        options it accepts, or the manager needs something the transport
        does not offer.

    """
    _resolve(spec, transport_cls)


def get_telemetry(
    spec: dict | None, ctx: TelemetryContext
) -> TelemetryManager | None:
    """
    Build the telemetry manager a pipeline asks for.

    Parameters
    ----------
    spec : dict | None
        The ``telemetry`` entry of the pipeline configuration: a dictionary
        with the ``name`` of the manager and its options. ``None`` means the
        telemetry is off.
    ctx : TelemetryContext
        The context of the pipeline.

    Returns
    -------
    TelemetryManager | None
        A new manager, or ``None`` if the telemetry is off.

    Raises
    ------
    ValueError
        See `check_telemetry`.

    """
    resolved = _resolve(spec, type(ctx.transport))

    if resolved is None:
        return None

    manager_cls, options = resolved

    return manager_cls(ctx, **options)
