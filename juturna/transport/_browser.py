"""
Browser transport backend (Pyodide), based on `SharedArrayBuffer` +
`Atomics`.

STATUS: PARTIAL, see the "open architectural question" note below before
touching `_BrowserLock`/`_BrowserCondition`/`spawn`/`is_current`.

This module is meant to be imported unconditionally by
`juturna.transport._registry` even outside a Pyodide runtime (e.g. on a
normal desktop Python interpreter, where `import juturna` must keep
working). Every `js`/`pyodide` import is therefore deferred to inside the
methods that actually need it, never at module scope - importing this
module, or defining `BrowserTransport`, must never require `js` to exist.
Only *instantiating* the not-yet-implemented pieces raises.

Design and validation trail: `design/browser-transport/` (local, not
tracked by git). What is implemented here follows, unmodified in its
mechanics, three validated spikes:

- `spike/getbuffer/`: bulk bytes numpy/bytes -> SharedArrayBuffer write via
  `PyProxy.getBuffer()` + a JS-to-JS `TypedArray.set()` (never a `bytes`
  argument crossing `pyodide.ffi`, which measured ~125ms/frame - too slow);
  read via a FRESH `.to_py()` call every time, never cached (a cached
  `to_py()` view does not alias real shared memory - confirmed broken,
  see `spike/zerocopy/`).
- `spike/message/`: the same mechanism extended to a real
  `juturna.components.Message` with `ImagePayload`/`AudioPayload` (JSON
  metadata blob + dtype-agnostic byte-reinterpretation of the array, so a
  `float32` audio payload isn't silently corrupted by a `uint8`
  destination view).
- `spike/pyfunction/`: the `getBuffer()`+`.set()` JS helper can be built
  entirely from Python via `from js import Function; Function.new(...)`,
  so this module needs no separate `.js` asset file to ship.

## Open architectural question (not resolved by any spike so far)

`Node.start()` calls `transport.spawn()` up to four times per node
(`_worker`, `_update`, `_source`, and `_handle_control` for control
messages), expecting the spawned callables to run concurrently with each
other. Pyodide in the pinned build (`v0.26.4`) has confirmed **no real
thread support at all** (`RuntimeError: can't start new thread`, §3.4 of
the design doc), including inside a dedicated Worker. This means:

- A literal "one real `new Worker()` per `spawn()` call" implementation
  (as originally sketched for `_BrowserWorker` in the design doc) would
  create ~4 separate Pyodide instances per node, not the "one Pyodide
  instance per node" the design intended - and `Node`/`Buffer` state
  (the buffer dict, its `Lock`, the synchroniser closure, `Node.update()`'s
  live state) cannot be transparently shared across genuinely separate
  Pyodide interpreters the way it is across real OS threads.
- `Node.join()`'s `self._pending_condition.wait_for(...)` blocking while
  `_update` - in the same interpreter - is what notifies it, would
  deadlock under naive cooperative single-interpreter scheduling.
- A promising newer option (Pyodide >= 0.27.7 with JSPI/stack-switching,
  `pyodide.ffi.run_sync`) may let synchronous-looking blocking calls
  cooperatively yield without rewriting `Node`'s loop bodies as
  generators - but this is unverified, requires Chrome 137+, and is a
  different Pyodide version than every spike so far.

`_BrowserLock`, `_BrowserCondition`, `spawn()` and `is_current()` are left
unimplemented (raise `NotImplementedError`) until this is resolved -
implementing them against a guess would mean throwing the work away.
`_BrowserQueue`/`_BrowserSignal` do not depend on this question: they are
correct, independently testable units usable today (and are exactly what
`spike/getbuffer/` and `spike/message/` already validated end-to-end,
across two real separate Workers).

## Known simplifications / open items in `_BrowserQueue`

- Only `Message` items are supported (`put()` raises for anything else).
  Confirmed by inspection: a bare `ControlSignal` is never passed to
  `Node.put()` anywhere in this codebase - it is always wrapped in
  `Message(payload=ControlPayload(...))`.
- Fast binary path: `ControlPayload`, `ImagePayload`, `AudioPayload`,
  `BytesPayload`. Everything else (`VideoPayload`, `Batch`,
  `ObjectPayload`, custom payload types) falls back to `pickle`, exactly
  as planned in the original design doc (§5.1) - correct, not optimized.
  `Buffer._consume()` does emit `Batch` payloads for multi-input nodes, so
  this fallback is on a real, exercised path, not just a hypothetical.
- A `SharedArrayBuffer`-backed slot has a fixed maximum size
  (`max_meta_json_bytes` + `max_payload_bytes`), unlike `queue.Queue`
  which holds arbitrary Python objects. `put()` raises `ValueError` if a
  serialized message does not fit, rather than truncating or blocking
  forever - this is a real behavioural difference from
  `ThreadingTransport` that callers need to be aware of.
- `new_queue(maxsize=...)` cannot tell apart the two real call sites:
  `Node.__init__` (receives messages that, under a real multi-Worker
  deployment, would cross from another node's Worker) and `Buffer.__init__`
  (`_out_queue`, purely intra-node, `_worker` -> `_update` in the same
  interpreter). Both currently get the same `SharedArrayBuffer`-backed
  implementation; for the intra-node case this is unnecessary overhead
  (no real cross-Worker boundary to cross) but not incorrect. Revisit once
  the spawn()/threading question above is settled and it's clear whether
  `Buffer` ever actually lives in a different Worker than its `Node`.
- `JUTURNA_MAX_QUEUE_SIZE` (999) is `ThreadingTransport`'s default
  `maxsize` and is NOT reused as the ring buffer capacity here: at typical
  video-frame slot sizes that would pre-allocate hundreds of MB per queue.
  `BrowserTransport` uses its own, much smaller, capped default instead
  (see `DEFAULT_QUEUE_CAPACITY` below) - this is a deliberate deviation
  from `ThreadingTransport`'s semantics, not an oversight.
"""

import json
import pickle

from collections.abc import Callable
from typing import Any

from juturna.transport._base import Empty
from juturna.transport._base import WorkerHandle


# --- wire format -----------------------------------------------------------
#
# Per-slot layout inside a queue's SharedArrayBuffer (mirrors
# design/browser-transport/spike/message/message_ring_buffer.js exactly):
#
#   [0..32)                          8x int32 header:
#                                       metaJsonLen, dtypeCode, ndim,
#                                       shape0, shape1, shape2, shape3,
#                                       payloadLen
#   [32..32+max_meta_json_bytes)     UTF-8 JSON metadata blob
#   [32+max_meta_json_bytes..end)    raw payload bytes (uint8
#                                    byte-reinterpretation of the array,
#                                    or pickled bytes for the fallback path)
#
# Global (queue-level) header, 4x int32: HEAD, TAIL, COUNT, CLOSED.

_HEADER_INT32_LENGTH = 4
_HEAD, _TAIL, _COUNT, _CLOSED = 0, 1, 2, 3
_SLOT_META_INT32_LENGTH = 8

_DTYPE_CODES = {
    'uint8': 1,
    'float32': 2,
    'int16': 3,
    'float64': 4,
    'int32': 5,
}
_DTYPE_BY_CODE = {code: name for name, code in _DTYPE_CODES.items()}

_KIND_CONTROL = 'control'
_KIND_IMAGE = 'image'
_KIND_AUDIO = 'audio'
_KIND_BYTES = 'bytes'
_KIND_PICKLE = 'pickle'

DEFAULT_QUEUE_CAPACITY = 8
DEFAULT_MAX_META_JSON_BYTES = 4096
DEFAULT_MAX_PAYLOAD_BYTES = (
    2_000_000  # ~2MB, comfortably above one 1080p-ish uint8 frame
)


def _get_buffer_write_fn():
    """
    Builds, from Python, the JS helper that does the validated fast write:
    `npProxy.getBuffer('u8')` (Python->JS zero-copy) + a JS-to-JS
    `TypedArray.set()` (never a `bytes` argument crossing `pyodide.ffi`,
    which is what made `BinaryRingBuffer` slow - see module docstring).

    Constructed via the standard JS `Function` constructor
    (`from js import Function; Function.new(...)`), validated in
    `design/browser-transport/spike/pyfunction/`. No separate `.js` file.
    """
    from js import Function

    return Function.new(
        'destView',
        'srcBufferProtocolObj',
        'const buf = srcBufferProtocolObj.getBuffer("u8"); '
        'try { destView.set(buf.data); } finally { buf.release(); }',
    )


class _BrowserSignal:
    """Signal primitive backed by a single Int32 cell in a SharedArrayBuffer."""

    _CELL = 0

    def __init__(self):
        from js import Int32Array
        from js import SharedArrayBuffer

        sab = SharedArrayBuffer.new(4)
        self._cell = Int32Array.new(sab)

    def set(self) -> None:
        from js import Atomics

        Atomics.store(self._cell, self._CELL, 1)

    def clear(self) -> None:
        from js import Atomics

        Atomics.store(self._cell, self._CELL, 0)

    def is_set(self) -> bool:
        from js import Atomics

        return bool(Atomics.load(self._cell, self._CELL))


def _serialize_message(msg) -> tuple[bytes, int, int, tuple[int, ...], Any]:
    """
    Returns (meta_json_bytes, dtype_code, ndim, shape, payload_buf).

    payload_buf is any buffer-protocol Python object (a numpy array for
    the fast paths, plain `bytes` for `BytesPayload`/the pickle fallback) -
    both are accepted as-is by the getBuffer()-based write helper.
    dtype_code == 0 means "no array interpretation", payload_buf is either
    empty (ControlPayload) or raw pickled bytes (fallback path).
    """
    import numpy as np

    from juturna.payloads import AudioPayload
    from juturna.payloads import BytesPayload
    from juturna.payloads import ControlPayload
    from juturna.payloads import ImagePayload

    payload = msg.payload

    meta = {
        'id': msg.id,
        'created_at': msg.created_at,
        'creator': msg.creator,
        'version': msg.version,
        'meta': dict(msg.meta),
        'timers': dict(msg.timers),
    }

    if isinstance(payload, ControlPayload):
        meta['kind'] = _KIND_CONTROL
        meta['payload_meta'] = {'signal': int(payload.signal)}

        return json.dumps(meta).encode('utf-8'), 0, 0, (), b''

    if isinstance(payload, ImagePayload):
        arr = payload.image
        meta['kind'] = _KIND_IMAGE
        meta['payload_meta'] = {
            'width': payload.width,
            'height': payload.height,
            'depth': payload.depth,
            'pixel_format': payload.pixel_format,
            'timestamp': payload.timestamp,
        }
        dtype_code, ndim, shape, payload_buf = _array_wire(arr, np)

        return (
            json.dumps(meta).encode('utf-8'),
            dtype_code,
            ndim,
            shape,
            payload_buf,
        )

    if isinstance(payload, AudioPayload):
        arr = payload.audio
        meta['kind'] = _KIND_AUDIO
        meta['payload_meta'] = {
            'sampling_rate': payload.sampling_rate,
            'audio_format': payload.audio_format,
            'channels': payload.channels,
            'start': payload.start,
            'end': payload.end,
        }
        dtype_code, ndim, shape, payload_buf = _array_wire(arr, np)

        return (
            json.dumps(meta).encode('utf-8'),
            dtype_code,
            ndim,
            shape,
            payload_buf,
        )

    if isinstance(payload, BytesPayload):
        meta['kind'] = _KIND_BYTES
        meta['payload_meta'] = {}
        payload_buf = payload.cnt

        return (
            json.dumps(meta).encode('utf-8'),
            _DTYPE_CODES['uint8'],
            1,
            (len(payload_buf),),
            payload_buf,
        )

    # VideoPayload, Batch, ObjectPayload, or any custom payload type: no
    # known binary layout, fall back to pickle (README §5.1). Correct,
    # not on the fast path - Buffer._consume() emits Batch for multi-input
    # nodes, so this is a real path, not a hypothetical.
    meta['kind'] = _KIND_PICKLE
    meta['payload_meta'] = {}
    payload_buf = pickle.dumps(payload)

    return json.dumps(meta).encode('utf-8'), 0, 0, (), payload_buf


def _array_wire(arr, np) -> tuple[int, int, tuple[int, ...], Any]:
    dtype_code = _DTYPE_CODES.get(str(arr.dtype))

    if dtype_code is None:
        raise ValueError(
            f'unsupported array dtype for BrowserTransport: {arr.dtype!r} '
            f'(supported: {sorted(_DTYPE_CODES)})'
        )

    # Byte-reinterpretation, NOT a value conversion: preserves the exact
    # bytes regardless of the array's real dtype. See module docstring -
    # this is what stops float32 audio from being corrupted by a uint8
    # destination view.
    flat_bytes = arr.reshape(-1).view(np.uint8)

    return dtype_code, len(arr.shape), tuple(arr.shape), flat_bytes


def _deserialize_message(header, meta_json_bytes: bytes, payload_bytes):
    import numpy as np

    from juturna.components._message import Message
    from juturna.payloads import AudioPayload
    from juturna.payloads import BytesPayload
    from juturna.payloads import ControlPayload
    from juturna.payloads import ControlSignal
    from juturna.payloads import ImagePayload

    meta_json_len, dtype_code, ndim, s0, s1, s2, s3, payload_len = (
        int(x) for x in header[:8]
    )
    shape = tuple(int(x) for x in (s0, s1, s2, s3)[:ndim])

    meta = json.loads(meta_json_bytes[:meta_json_len].decode('utf-8'))
    kind = meta['kind']
    pm = meta['payload_meta']
    raw = bytes(payload_bytes[:payload_len])

    if kind == _KIND_CONTROL:
        payload = ControlPayload(signal=ControlSignal(pm['signal']))
    elif kind in (_KIND_IMAGE, _KIND_AUDIO):
        arr = np.frombuffer(raw, dtype=_DTYPE_BY_CODE[dtype_code]).reshape(
            shape
        )
        payload = (
            ImagePayload(image=arr, **pm)
            if kind == _KIND_IMAGE
            else AudioPayload(audio=arr, **pm)
        )
    elif kind == _KIND_BYTES:
        payload = BytesPayload(cnt=raw)
    elif kind == _KIND_PICKLE:
        payload = pickle.loads(raw)
    else:
        raise ValueError(f'unknown payload kind on wire: {kind!r}')

    msg = Message(
        creator=meta['creator'], version=meta['version'], payload=payload
    )
    msg.id = meta['id']
    msg.created_at = meta['created_at']
    msg.meta = dict(meta['meta'])
    msg.timers = dict(meta['timers'])

    return msg


class _BrowserQueue:
    """
    Queue primitive backed by a `SharedArrayBuffer` ring buffer.

    Validated mechanics (see module docstring): write via
    `PyProxy.getBuffer()` + JS `TypedArray.set()`, read via a fresh
    `.to_py()` call every time (never cached). Only `Message` items are
    supported.
    """

    def __init__(
        self,
        capacity: int = DEFAULT_QUEUE_CAPACITY,
        max_meta_json_bytes: int = DEFAULT_MAX_META_JSON_BYTES,
        max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
    ):
        from js import Int32Array
        from js import SharedArrayBuffer
        from js import Uint8Array

        self._capacity = capacity
        self._max_meta_json_bytes = max_meta_json_bytes
        self._max_payload_bytes = max_payload_bytes
        self._slot_bytes = (
            _SLOT_META_INT32_LENGTH * 4
            + max_meta_json_bytes
            + max_payload_bytes
        )

        sab = SharedArrayBuffer.new(
            _HEADER_INT32_LENGTH * 4 + capacity * self._slot_bytes
        )
        self._sab = sab
        self._header = Int32Array.new(sab, 0, _HEADER_INT32_LENGTH)

        slots_base = _HEADER_INT32_LENGTH * 4
        self._meta_views = []
        self._meta_json_views = []
        self._payload_views = []

        for i in range(capacity):
            slot_offset = slots_base + i * self._slot_bytes
            meta_json_offset = slot_offset + _SLOT_META_INT32_LENGTH * 4
            payload_offset = meta_json_offset + max_meta_json_bytes

            self._meta_views.append(
                Int32Array.new(sab, slot_offset, _SLOT_META_INT32_LENGTH)
            )
            self._meta_json_views.append(
                Uint8Array.new(sab, meta_json_offset, max_meta_json_bytes)
            )
            self._payload_views.append(
                Uint8Array.new(sab, payload_offset, max_payload_bytes)
            )

        self._write_bulk = _get_buffer_write_fn()

    def put(self, item: Any) -> None:
        from juturna.components._message import Message

        if not isinstance(item, Message):
            raise NotImplementedError(
                'BrowserTransport queues only support Message items '
                f'(got {type(item)!r}); a bare ControlSignal is never '
                'used in this codebase, see _browser.py module docstring'
            )

        meta_json_bytes, dtype_code, ndim, shape, payload_buf = (
            _serialize_message(item)
        )

        if len(meta_json_bytes) > self._max_meta_json_bytes:
            raise ValueError(
                f'serialized message metadata ({len(meta_json_bytes)} '
                f"bytes) exceeds this queue's slot capacity "
                f'({self._max_meta_json_bytes} bytes) - increase '
                'max_meta_json_bytes on BrowserTransport'
            )

        payload_len = getattr(payload_buf, 'nbytes', None)
        if payload_len is None:
            payload_len = len(payload_buf)

        if payload_len > self._max_payload_bytes:
            raise ValueError(
                f'serialized message payload ({payload_len} bytes) '
                f"exceeds this queue's slot capacity "
                f'({self._max_payload_bytes} bytes) - increase '
                'max_payload_bytes on BrowserTransport'
            )

        slot = self._reserve_write()
        shape_padded = (list(shape) + [0, 0, 0, 0])[:4]

        meta_view = self._meta_views[slot]
        meta_view[0] = len(meta_json_bytes)
        meta_view[1] = dtype_code
        meta_view[2] = ndim
        meta_view[3] = shape_padded[0]
        meta_view[4] = shape_padded[1]
        meta_view[5] = shape_padded[2]
        meta_view[6] = shape_padded[3]
        meta_view[7] = payload_len

        self._write_bulk(self._meta_json_views[slot], meta_json_bytes)
        if payload_len > 0:
            self._write_bulk(self._payload_views[slot], payload_buf)

        self._publish_write(slot)

    def get(self, timeout: float | None = None) -> Any:
        slot = self._reserve_read(timeout)

        if slot == -1:
            raise Empty

        msg = self._read_slot(slot)
        self._release_read()

        return msg

    def get_nowait(self) -> Any:
        return self.get(timeout=0)

    def empty(self) -> bool:
        from js import Atomics

        return int(Atomics.load(self._header, _COUNT)) == 0

    def close(self) -> None:
        from js import Atomics

        Atomics.store(self._header, _CLOSED, 1)
        Atomics.notify(self._header, _COUNT)

    # -- internals ------------------------------------------------------

    def _read_slot(self, slot: int):
        import numpy as np

        header = np.asarray(self._meta_views[slot].to_py())
        meta_json_len = int(header[0])
        meta_json_raw = bytes(
            np.asarray(self._meta_json_views[slot].to_py())[:meta_json_len]
        )
        payload_len = int(header[7])
        payload_raw = (
            np.asarray(self._payload_views[slot].to_py())[:payload_len]
            if payload_len > 0
            else np.asarray([], dtype='uint8')
        )

        return _deserialize_message(header, meta_json_raw, bytes(payload_raw))

    def _reserve_write(self) -> int:
        from js import Atomics

        while True:
            count = int(Atomics.load(self._header, _COUNT))

            if count < self._capacity:
                return int(Atomics.load(self._header, _HEAD))

            # Blocks indefinitely, matching queue.Queue.put()'s default
            # (block=True, timeout=None) semantics used by ThreadingTransport.
            Atomics.wait(self._header, _COUNT, count)

    def _publish_write(self, slot: int) -> None:
        from js import Atomics

        head = int(Atomics.load(self._header, _HEAD))
        Atomics.store(self._header, _HEAD, (head + 1) % self._capacity)
        Atomics.add(self._header, _COUNT, 1)
        Atomics.notify(self._header, _COUNT)

    def _reserve_read(self, timeout: float | None) -> int:
        from js import Atomics

        deadline = None if timeout is None else _now_ms() + timeout * 1000

        while True:
            count = int(Atomics.load(self._header, _COUNT))

            if count > 0:
                return int(Atomics.load(self._header, _TAIL))

            if int(Atomics.load(self._header, _CLOSED)):
                return -1

            if timeout is not None:
                remaining_ms = deadline - _now_ms()
                if remaining_ms <= 0:
                    return -1
                Atomics.wait(self._header, _COUNT, count, remaining_ms)
            else:
                Atomics.wait(self._header, _COUNT, count)

    def _release_read(self) -> None:
        from js import Atomics

        tail = int(Atomics.load(self._header, _TAIL))
        Atomics.store(self._header, _TAIL, (tail + 1) % self._capacity)
        Atomics.add(self._header, _COUNT, -1)
        Atomics.notify(self._header, _COUNT)


def _now_ms() -> float:
    import time

    return time.time() * 1000


class _BrowserLock:
    """
    NOT IMPLEMENTED. Depends on the spawn()/threading-model question in
    the module docstring: `Buffer.__init__` calls `transport.new_lock()`
    unconditionally, so this blocks `Buffer` (and therefore `Node`) from
    working at all under `BrowserTransport`, not just `Node.join()`.
    """

    def __init__(self):
        raise NotImplementedError(
            '_BrowserLock is not implemented yet - see the "open '
            'architectural question" note in juturna/transport/_browser.py'
        )


class _BrowserCondition:
    """NOT IMPLEMENTED. Same open question as `_BrowserLock`."""

    def __init__(self):
        raise NotImplementedError(
            '_BrowserCondition is not implemented yet - see the "open '
            'architectural question" note in juturna/transport/_browser.py'
        )


class _BrowserWorker:
    """NOT IMPLEMENTED. Same open question as `_BrowserLock`."""

    def __init__(
        self, target: Callable[[], None], name: str, daemon: bool = True
    ):
        raise NotImplementedError(
            '_BrowserWorker/spawn() is not implemented yet - see the '
            '"open architectural question" note in '
            'juturna/transport/_browser.py'
        )

    def start(self) -> None: ...

    def join(self, timeout: float | None = None) -> None: ...

    def is_alive(self) -> bool: ...


class BrowserTransport:
    """
    Browser transport backend (Pyodide + `SharedArrayBuffer`/`Atomics`).

    PARTIAL: `new_queue()`/`new_signal()` are implemented and validated
    (see module docstring). `new_lock()`/`new_condition()`/`spawn()`/
    `is_current()` raise `NotImplementedError` pending the open
    architectural question documented at the top of this module.
    """

    def __init__(
        self,
        queue_capacity: int = DEFAULT_QUEUE_CAPACITY,
        max_meta_json_bytes: int = DEFAULT_MAX_META_JSON_BYTES,
        max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
    ):
        self._queue_capacity = queue_capacity
        self._max_meta_json_bytes = max_meta_json_bytes
        self._max_payload_bytes = max_payload_bytes

    def new_queue(self, maxsize: int = 0) -> _BrowserQueue:
        # maxsize=0 (unbounded, queue.Queue convention) has no equivalent
        # for a pre-allocated SharedArrayBuffer ring buffer - falls back
        # to this transport's configured capacity. A positive maxsize
        # smaller than that capacity is honoured as-is; a larger one is
        # NOT (deliberately - see JUTURNA_MAX_QUEUE_SIZE note in the
        # module docstring, capacity directly drives memory pre-allocation).
        capacity = (
            self._queue_capacity
            if not maxsize
            else min(maxsize, self._queue_capacity)
        )

        return _BrowserQueue(
            capacity=capacity,
            max_meta_json_bytes=self._max_meta_json_bytes,
            max_payload_bytes=self._max_payload_bytes,
        )

    def new_signal(self) -> _BrowserSignal:
        return _BrowserSignal()

    def new_lock(self) -> _BrowserLock:
        return _BrowserLock()

    def new_condition(self) -> _BrowserCondition:
        return _BrowserCondition()

    def spawn(
        self, target: Callable[[], None], name: str, daemon: bool = True
    ) -> _BrowserWorker:
        return _BrowserWorker(target, name, daemon)

    def is_current(self, handle: WorkerHandle) -> bool:
        raise NotImplementedError(
            'BrowserTransport.is_current() is not implemented yet - see '
            'the "open architectural question" note in '
            'juturna/transport/_browser.py'
        )
