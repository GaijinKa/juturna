KEEPALIVE_OPTIONS = [
    ('grpc.keepalive_time_ms', 10000),
    ('grpc.keepalive_timeout_ms', 5000),
    ('grpc.keepalive_permit_without_calls', 1),
    ('grpc.http2.max_pings_without_data', 0),
]

# as in the remote service: gRPC's default 4 MB cap refuses an HD frame
MAX_MESSAGE_BYTES = 100 * 1024 * 1024

MESSAGE_SIZE_OPTIONS = [
    ('grpc.max_send_message_length', MAX_MESSAGE_BYTES),
    ('grpc.max_receive_message_length', MAX_MESSAGE_BYTES),
]

CHANNEL_OPTIONS = KEEPALIVE_OPTIONS + MESSAGE_SIZE_OPTIONS

SERVER_OPTIONS = (
    KEEPALIVE_OPTIONS
    + [('grpc.http2.min_ping_interval_without_data_ms', 5000)]
    + MESSAGE_SIZE_OPTIONS
)


def check_address(address: str) -> tuple[str, int]:
    """
    Split a data address into the host and the port it names.

    Parameters
    ----------
    address : str
        A ``HOST:PORT`` address, with an IPv6 host in brackets.

    Returns
    -------
    tuple[str, int]
        The host, without brackets, and the port.

    Raises
    ------
    ValueError
        If the address is malformed, or names a wildcard host that the other
        processes cannot dial.

    """
    host, _, port = address.rpartition(':')
    host = host.removeprefix('[').removesuffix(']')

    if not host or not port.isdigit():
        raise ValueError(f'invalid data address {address!r}, use HOST:PORT')

    if host in ('0.0.0.0', '::'):
        raise ValueError('give an address the other processes can reach')

    return host, int(port)
