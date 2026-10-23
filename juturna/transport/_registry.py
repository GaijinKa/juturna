import importlib
import inspect

from juturna.transport._base import TransportBackend
from juturna.transport.threads import ThreadingTransport
from juturna.transport.browser import BrowserTransport


_TRANSPORTS: dict[str, type[TransportBackend]] = {
    'threading': ThreadingTransport,
    'browser': BrowserTransport,
}

# imported on first use, so that their dependencies stay optional
_LAZY_TRANSPORTS: dict[str, tuple[str, str]] = {
    'grpc': ('juturna.transport.grpc', 'GrpcTransport'),
}

_DEFAULT_TRANSPORT = 'threading'


def _split_spec(spec: str | dict | None) -> tuple[str, dict]:
    if isinstance(spec, dict):
        options = dict(spec)
        name = options.pop('name', None)
    elif spec is None or isinstance(spec, str):
        options, name = dict(), spec
    else:
        raise ValueError(
            f'transport must be a name or a dict, got {type(spec).__name__}'
        )

    if name is not None and not isinstance(name, str):
        raise ValueError(f'transport name must be a string, got {name!r}')

    return name or _DEFAULT_TRANSPORT, options


def get_transport(spec: str | dict | None = None) -> TransportBackend:
    """
    Resolve a transport backend from its configuration.

    Parameters
    ----------
    spec : str | dict | None
        Either the name of the backend, as registered in `_TRANSPORTS` or
        `_LAZY_TRANSPORTS`, or a dictionary with its ``name`` and the options
        of the backend, that are passed to its constructor, like
        ``{'name': 'browser', 'max_payload_bytes': 4000000}``. Defaults to the
        threading backend if not provided.

    Returns
    -------
    TransportBackend
        A new instance of the requested backend.

    Raises
    ------
    ValueError
        If the name does not match any registered backend, or the backend
        does not accept one of the options.

    """
    name, options = _split_spec(spec)
    if name in _LAZY_TRANSPORTS:
        module, attribute = _LAZY_TRANSPORTS[name]

        try:
            transport = getattr(importlib.import_module(module), attribute)
        except ImportError as exc:
            raise ValueError(
                f'the {name!r} transport needs the warp extra: {exc}'
            ) from exc
    elif name in _TRANSPORTS:
        transport = _TRANSPORTS[name]
    else:
        raise ValueError(
            f'unknown transport backend: {name!r}, '
            f'available: {list(_TRANSPORTS) + list(_LAZY_TRANSPORTS)}'
        )

    try:
        inspect.signature(transport).bind(**options)
    except TypeError as exc:
        raise ValueError(
            f'invalid options for the {name!r} transport: {exc}'
        ) from exc

    return transport(**options)
