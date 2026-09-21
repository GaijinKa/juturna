"""
AudioMicBrowser

Source node reading the microphone from inside a browser tab.

``getUserMedia``/``AudioWorklet`` only exist on the page's main thread, while
the node runs inside a Pyodide Worker: the main thread captures audio and
writes it into a float32 ring buffer on a ``SharedArrayBuffer``, this node
reads it from there. Requires the browser transport (Pyodide >= 314.0.0,
module Worker, entry point invoked via ``.callPromising()``).

Ring layout (shared with the main-thread capture code):

    int32[4] header: WRITTEN, READ, CLOSED, OVERRUNS  (sample counters)
    float32[capacity] samples
"""

import numpy as np

from juturna.components import Node
from juturna.components import Message

from juturna.payloads import AudioPayload
from juturna.payloads import ControlPayload
from juturna.payloads import ControlSignal

_WRITTEN, _READ, _CLOSED, _OVERRUNS = 0, 1, 2, 3
_HEADER_BYTES = 16
_POLL_MS = 200


class AudioMicBrowser(Node[AudioPayload, AudioPayload]):
    """
    Chunk the microphone audio captured by the page into fixed-length
    messages, as soon as each block is available.
    """

    def __init__(
        self, ring_name: str, block_size: int, audio_rate: int, **kwargs
    ):
        """
        Parameters
        ----------
        ring_name : str
            Name of the ``globalThis`` property holding the ring buffer
            ``SharedArrayBuffer`` (set by the worker bootstrap).
        block_size : int
            Time length in seconds of each produced audio chunk.
        audio_rate : int
            Sampling rate of the ring; the capture side must use the same.
        kwargs : dict
            Superclass arguments.

        """
        super().__init__(**kwargs)

        self._ring_name = ring_name
        self._block_size = block_size
        self._rate = audio_rate

        self._block_samples = block_size * audio_rate
        self._header = None
        self._samples = None
        self._capacity = 0
        self._read = 0
        self._copy_out = None

    def warmup(self):  # noqa: D102
        from js import Float32Array
        from js import Function
        from js import Int32Array
        from js import globalThis

        ring = getattr(globalThis, self._ring_name, None)

        if ring is None:
            raise RuntimeError(
                f'no ring buffer in globalThis.{self._ring_name}: the page '
                'must start the capture and hand it over before warmup'
            )

        self._header = Int32Array.new(ring, 0, 4)
        self._capacity = (ring.byteLength - _HEADER_BYTES) // 4
        self._samples = Float32Array.new(ring, _HEADER_BYTES, self._capacity)

        # wrap-aware copy into a fresh array, kept on the JS side so that
        # only one contiguous buffer crosses into Python
        self._copy_out = Function.new(
            'samples',
            'start',
            'count',
            'const out = new Float32Array(count); '
            'const cap = samples.length; '
            'const first = Math.min(count, cap - start); '
            'out.set(samples.subarray(start, start + first), 0); '
            'if (first < count) '
            '{ out.set(samples.subarray(0, count - first), first); } '
            'return out;',
        )

        self.set_source(self._read_block, by=0, mode='pre')

        self.logger.info(
            f'mic ring attached: {self._capacity} samples @ {self._rate}Hz'
        )

    def _read_block(self) -> Message[AudioPayload | ControlPayload]:
        from js import Atomics
        from pyodide.ffi import run_sync

        needed = self._block_samples

        while True:
            written = Atomics.load(self._header, _WRITTEN)

            if written - self._read > self._capacity:
                # the reader fell behind by more than the ring: drop the
                # oldest audio rather than replaying overwritten samples
                self._read = written - self._capacity
                self.logger.warning('mic ring overrun, dropped audio')

            if written - self._read >= needed:
                break

            if (
                Atomics.load(self._header, _CLOSED)
                or self._stop_source_event.is_set()
            ):
                return Message[ControlPayload](
                    creator=self.name,
                    payload=ControlPayload(signal=ControlSignal.STOP),
                )

            result = Atomics.waitAsync(
                self._header, _WRITTEN, written, _POLL_MS
            )

            if result.async_:
                run_sync(result.value)

        start = self._read
        block = self._copy_out(self._samples, start % self._capacity, needed)
        chunk = np.array(block.to_py(), dtype=np.float32)
        self._read += needed
        Atomics.store(self._header, _READ, self._read)

        return Message[AudioPayload](
            creator=self.name,
            payload=AudioPayload(
                audio=chunk,
                sampling_rate=self._rate,
                channels=1,
                start=start / self._rate,
                end=self._read / self._rate,
            ),
        )

    def update(self, message: Message[AudioPayload | ControlPayload], **kwargs):  # noqa: D102
        message.meta['session_id'] = self.pipe_id

        self.transmit(message)
