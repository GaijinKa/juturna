import json
import uuid

from juturna.remotizer.c_protos.payloads_pb2 import ProtoEnvelope


PROTOCOL_VERSION = 1
ARGS_KEY = 'args'


def encode_args(args: dict) -> str:
    """Encode command arguments as JSON, which keeps ints as ints."""
    return json.dumps(args)


def decode_args(text: str) -> dict:
    """Decode the arguments written by `encode_args`."""
    return json.loads(text) if text else dict()


def make_envelope(
    command: str, args: dict, response_to: str = ''
) -> ProtoEnvelope:
    """Build a control message carrying a command or the answer to one."""
    return ProtoEnvelope(
        id=str(uuid.uuid4()),
        request_type=command,
        response_to=response_to,
        metadata={ARGS_KEY: encode_args(args)},
    )


def envelope_args(envelope: ProtoEnvelope) -> dict:
    """Read the arguments of a control message."""
    return decode_args(envelope.metadata[ARGS_KEY])
