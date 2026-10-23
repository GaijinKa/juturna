from collections.abc import Sequence
from typing import Any


def layered_stop(participants: Sequence[Any], layers: list[list[str]]) -> None:
    """
    Stop a pipeline spread over several workers, layer by layer.

    Every worker only sees its own links, so the links into a layer are closed
    on all of them (each close waits for the messages in flight) before any
    node of that layer is stopped. A participant whose ``alive`` attribute is
    False is skipped; one whose ``begin_stop`` returns False (already stopped)
    takes no further part.

    Parameters
    ----------
    participants : Sequence[Any]
        The pipeline instances, one per worker, or anything with their
        ``begin_stop``, ``close_remote``, ``stop_nodes``, ``end_stop`` and
        ``abort_stop`` methods.
    layers : list[list[str]]
        The layers of the global graph, see `pipeline_layers`.

    Raises
    ------
    Exception
        Whatever a participant raises, after ``abort_stop`` has been called on
        every participant that claimed the stop.

    """
    claimed = list()

    def _alive():
        return [p for p in claimed if getattr(p, 'alive', True)]

    try:
        for participant in participants:
            if getattr(participant, 'alive', True) and participant.begin_stop():
                claimed.append(participant)

        for layer in layers:
            for participant in _alive():
                participant.close_remote(layer)

            for participant in _alive():
                participant.stop_nodes(layer)

        for participant in _alive():
            participant.end_stop()
    except Exception:
        for participant in claimed:
            participant.abort_stop()

        raise
