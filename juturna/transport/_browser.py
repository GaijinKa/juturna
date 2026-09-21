"""
Browser transport backend (Pyodide), based on `SharedArrayBuffer` +
`Atomics`, made concurrent by JSPI (JavaScript Promise Integration /
stack switching).

## Deployment requirement

This backend only works under all of the following:

- Pyodide **>= v314.0.0**, loaded in a **module-type** Worker
  (`new Worker(url, { type: 'module' })`) via a **dynamic** `import()` of
  `pyodide.mjs` (not `pyodide.js` - classic `importScripts()` loading was
  dropped in this Pyodide line). Older builds (validated down to
  `v0.27.7`) crash on nested `callPromising()` with `RuntimeError: memory
  access out of bounds` - a genuine Pyodide bug (changelog #6260), fixed
  in 314.0.0; a related contextvars-isolation fix landed in 314.0.5. Do
  not deploy against anything older than 314.0.0.
- The Python entry point that ultimately drives a node (`Node.start()`
  and everything it transitively calls) must be invoked from JS via
  `.callPromising()`, never a plain call/`runPython`. Every blocking
  primitive in this module (`_BrowserQueue`, `_BrowserLock`,
  `_BrowserCondition`, `_BrowserWorker.join()`) requires this and raises
  a clear `RuntimeError` (via `_require_stack_switching()`) if it isn't
  met, rather than surfacing a raw pyodide stack-switching error.

This module is meant to be imported unconditionally by
`juturna.transport._registry` even outside a Pyodide runtime (e.g. on a
normal desktop Python interpreter, where `import juturna` must keep
working). Every `js`/`pyodide.ffi` import is therefore deferred to inside
the methods that actually need it, never at module scope - importing this
module, or defining/instantiating `BrowserTransport`, must never require
`js` to exist. `contextvars` (stdlib) is the only exception and sits at
module scope.

Design and validation trail: `design/browser-transport/` (local, not
tracked by git). What is implemented here follows, unmodified in its
mechanics, these validated spikes:

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
- `spike/jspi/worker3-new.js`, `worker5-new.js`: nested `callPromising()`
  (a spawned task itself blocking on another primitive while other
  spawned tasks are live) on Pyodide 314.0.6 - no crash, real
  cooperative concurrency confirmed, 3 independent reproductions.
- `spike/jspi/worker6-lockcond.js`: `_BrowserLock`/`_BrowserCondition`
  under real contention (Lock: exact mutual exclusion over 60 contested
  increments; Condition: wait/notify_all within ~2ms of the expected
  delay).
- `spike/jspi/worker7-iscurrent.js`: the `contextvars.ContextVar`-based
  `is_current()` mechanism - identity survives a real stack-switch
  suspend/resume and stays correctly isolated between two concurrently
  spawned tasks.

## Why `Atomics.wait` (synchronous) must never appear in this module

Every blocking wait here uses `run_sync(Atomics.waitAsync(...))`, never
the synchronous `Atomics.wait(...)`. Under JSPI, a node's `_worker`,
`_update`, `_source` and `_handle_control` loops all run cooperatively in
the *same* interpreter/event loop (there is no real OS thread per
`spawn()` - Pyodide confirmed **no real thread support at all**,
`RuntimeError: can't start new thread`). A synchronous `Atomics.wait`
freezes that entire event loop, starving every other spawned task in the
node - not a slowdown, a deadlock (e.g. `Node.join()` waiting on a
`Condition` that only `_update`, sharing the same frozen loop, could ever
notify). `run_sync(Atomics.waitAsync(...))` suspends only the current
stack-switched task and lets the others keep running - this is the
mechanism every JSPI spike above validated and the reason `spawn()`
works at all under a single Pyodide instance per node.

## `is_current()` and worker identity

There is no OS thread identity to compare against under JSPI, so
`_BrowserWorker` identity is tracked with a module-level
`contextvars.ContextVar`, set at the start of the wrapped target and read
back by `BrowserTransport.is_current()`. Validated
(`spike/jspi/worker7-iscurrent.js`) to survive a real stack-switch
suspend/resume mid-target and to stay isolated between two concurrently
running spawned targets - this exercises the Pyodide 314.0.5 fix ("A
Python entry point invoked with stack switching enabled now runs with a
copy of the contextvars context").

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
  interpreter). Now that `spawn()` is JSPI-backed (one Pyodide instance
  per node, no per-`spawn()` Worker), `Buffer` never actually crosses a
  real Worker boundary from its `Node` - `_out_queue`'s
  `SharedArrayBuffer` backing is unnecessary overhead there, but not
  incorrect. Left as-is (both call sites share one implementation);
  worth a plain-Python-object fast path for the intra-node case if queue
  overhead ever shows up in profiling, not before.
- `JUTURNA_MAX_QUEUE_SIZE` (999) is `ThreadingTransport`'s default
  `maxsize` and is NOT reused as the ring buffer capacity here: at typical
  video-frame slot sizes that would pre-allocate hundreds of MB per queue.
  `BrowserTransport` uses its own, much smaller, capped default instead
  (see `DEFAULT_QUEUE_CAPACITY` below) - this is a deliberate deviation
  from `ThreadingTransport`'s semantics, not an oversight.

## Aligned to the current `TransportBackend` contract (`_base.py`)

This module was written against an earlier version of the protocol.
`full()`/`qsize()`/`put(timeout=...)` on `Queue`, `wait(timeout=...)` on
`Signal`, and `timeout` on `Condition.wait_for()` were added to `_base.py`
by `dd4185a` (node draining fix) without a matching update here; `Event`/
`new_event()` were added by `19fe90a`, also without an implementation in
either backend (`ThreadingTransport` does not implement `Event` either as
of this writing). Brought in line with `_base.py` as follows:

- `_BrowserQueue.put(item, timeout=...)` reuses the same deadline-loop
  shape already used by `_reserve_read()`; on timeout it raises stdlib
  `queue.Full`, mirroring `_ThreadQueue.put()` (which lets `queue.Full`
  leak through from `queue.Queue.put()` unwrapped - `_base.py` declares
  no backend-agnostic `Full` type, unlike `Empty`, so matching the
  reference backend's actual behaviour is the correct alignment here,
  not inventing a new exception type).
- `_BrowserQueue.full()`/`qsize()` read the existing `_COUNT` cell -  no
  new state, same one `_reserve_write()`/`_reserve_read()` already use.
- `_BrowserSignal.wait()` required a real fix, not just an addition:
  `set()` never called `Atomics.notify()`, harmless while nothing waited
  on the cell, but a `wait()` built on `_atomics_wait_async()` would
  otherwise block until its timeout even when `set()` had already run.
  `set()` now notifies, matching `_BrowserLock`/`_BrowserCondition`'s
  existing store-then-notify pattern.
- `_BrowserEvent` is a plain subclass of `_BrowserSignal` with no
  overrides: the two protocols in `_base.py` are structurally identical
  (`set`/`clear`/`is_set`/`wait`), differing only in `wait()`'s declared
  return annotation (`bool` for `Signal`, `None` for `Event`), which
  Python does not enforce at runtime. A second independent
  implementation of the same Atomics-cell mechanism would be pure
  duplication for no behavioural difference.
"""

import contextvars
import json
import pickle

from collections.abc import Callable
from queue import Full
from typing import Any

from juturna.transport._base import Empty
from juturna.transport._base import WorkerHandle


# Tracks "which spawned target is currently running" for is_current() -
# see the "is_current() and worker identity" section of the module
# docstring. No `js`/`pyodide.ffi` dependency, safe at module scope.
_current_worker: contextvars.ContextVar = contextvars.ContextVar(
    '_current_worker', default=None
)


def _require_stack_switching(op: str) -> None:
    """
    Raises a clear error instead of letting a raw pyodide stack-switching
    error surface from deep inside a wait loop, when `op` is about to
    suspend the current task but the call isn't running inside a
    stack-switching-enabled entry point (i.e. not ultimately invoked via
    `.callPromising()`) - see the module docstring's deployment
    requirement.
    """
    from pyodide.ffi import can_run_sync

    if not can_run_sync():
        raise RuntimeError(
            f'{op} would block, but the current call is not running '
            'inside a stack-switching-enabled entry point. Every code '
            'path that can reach a BrowserTransport Queue/Lock/Condition '
            'wait must ultimately be invoked via '
            '`<callable>.callPromising()` on Pyodide >= v314.0.0, never '
            'via a plain call/`runPython` - see the _browser.py module '
            'docstring.'
        )


def _atomics_wait_async(
    cell, index: int, expected: int, timeout_ms=None
) -> None:
    """
    Cooperative equivalent of the synchronous `Atomics.wait()`: suspends
    only the current stack-switched task via
    `run_sync(Atomics.waitAsync(...))`, never the whole worker/event
    loop. See the module docstring's "Why `Atomics.wait` (synchronous)
    must never appear in this module" section - every blocking wait in
    `_BrowserQueue`, `_BrowserLock` and `_BrowserCondition` goes through
    this helper.
    """
    from js import Atomics
    from pyodide.ffi import run_sync

    result = (
        Atomics.waitAsync(cell, index, expected)
        if timeout_ms is None
        else Atomics.waitAsync(cell, index, expected, timeout_ms)
    )

    if result.async_:
        _require_stack_switching('a BrowserTransport wait')
        run_sync(result.value)


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

_HEADER_INT32_LENGTH = 7
_HEAD, _TAIL, _COUNT, _CLOSED = 0, 1, 2, 3
# The slot geometry is written in the header so that a queue attached from
# another Worker can check it agrees with the creator's: a mismatch would
# otherwise read mid-slot, silently.
_GEOM_CAPACITY, _GEOM_META_BYTES, _GEOM_PAYLOAD_BYTES = 4, 5, 6
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
        Atomics.notify(self._cell, self._CELL)

    def clear(self) -> None:
        from js import Atomics

        Atomics.store(self._cell, self._CELL, 0)

    def is_set(self) -> bool:
        from js import Atomics

        return bool(Atomics.load(self._cell, self._CELL))

    def wait(self, timeout: float | None = None) -> bool:
        deadline = None if timeout is None else _now_ms() + timeout * 1000

        while True:
            if self.is_set():
                return True

            if deadline is not None:
                remaining_ms = deadline - _now_ms()
                if remaining_ms <= 0:
                    return False
                _atomics_wait_async(self._cell, self._CELL, 0, remaining_ms)
            else:
                _atomics_wait_async(self._cell, self._CELL, 0)


class _BrowserEvent(_BrowserSignal):
    """
    Event primitive required by `TransportBackend.new_event()`. No
    overrides: `Signal` and `Event` in `_base.py` are structurally
    identical (`set`/`clear`/`is_set`/`wait`), differing only in
    `wait()`'s declared return annotation, which Python does not enforce
    at runtime - see the module docstring's "Aligned to the current
    `TransportBackend` contract" section.
    """


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

    A queue can be shared with another Worker: `handle()` gives what has to
    be posted to it, and passing that `sab` to a new `_BrowserQueue` there
    attaches to the same ring. The ring has a single producer and a single
    consumer: `put()` reserves the head slot without a compare-and-swap, so
    it is safe for any number of producers only while they all run in the
    same Worker (cooperative scheduling), never from two Workers at once.
    """

    def __init__(
        self,
        capacity: int = DEFAULT_QUEUE_CAPACITY,
        max_meta_json_bytes: int = DEFAULT_MAX_META_JSON_BYTES,
        max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
        sab=None,
    ):
        """
        Parameters
        ----------
        capacity : int
            Number of slots.
        max_meta_json_bytes : int
            Room for the JSON metadata of each slot.
        max_payload_bytes : int
            Room for the payload of each slot.
        sab : SharedArrayBuffer, optional
            The buffer of a queue created elsewhere, to attach to it. The
            three sizes above must be those the creator used.

        Raises
        ------
        ValueError
            If ``sab`` was not created with the same geometry.

        """
        from js import Atomics
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

        size = _HEADER_INT32_LENGTH * 4 + capacity * self._slot_bytes
        geometry = (capacity, max_meta_json_bytes, max_payload_bytes)

        if sab is None:
            sab = SharedArrayBuffer.new(size)
            header = Int32Array.new(sab, 0, _HEADER_INT32_LENGTH)

            for index, value in zip(
                (_GEOM_CAPACITY, _GEOM_META_BYTES, _GEOM_PAYLOAD_BYTES),
                geometry,
                strict=True,
            ):
                Atomics.store(header, index, value)
        else:
            header = Int32Array.new(sab, 0, _HEADER_INT32_LENGTH)
            found = tuple(
                int(Atomics.load(header, index))
                for index in (
                    _GEOM_CAPACITY,
                    _GEOM_META_BYTES,
                    _GEOM_PAYLOAD_BYTES,
                )
            )

            if sab.byteLength != size or found != geometry:
                raise ValueError(
                    'cannot attach to the queue: it was created with '
                    f'(capacity, max_meta_json_bytes, max_payload_bytes) = '
                    f'{found}, not {geometry}'
                )

        self._sab = sab
        self._header = header

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

    def handle(self):
        """
        What another Worker needs to attach to this queue: a JS object
        ``{sab, capacity, max_meta_json_bytes, max_payload_bytes}``, meant to
        be posted to it (the buffer is shared, not copied).
        """
        from js import Object
        from pyodide.ffi import to_js

        return to_js(
            {
                'sab': self._sab,
                'capacity': self._capacity,
                'max_meta_json_bytes': self._max_meta_json_bytes,
                'max_payload_bytes': self._max_payload_bytes,
            },
            dict_converter=Object.fromEntries,
        )

    def put(self, item: Any, timeout: float | None = None) -> None:
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

        slot = self._reserve_write(timeout)
        if slot == -1:
            raise Full

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

    def full(self) -> bool:
        from js import Atomics

        return int(Atomics.load(self._header, _COUNT)) >= self._capacity

    def qsize(self) -> int:
        from js import Atomics

        return int(Atomics.load(self._header, _COUNT))

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

    def _reserve_write(self, timeout: float | None = None) -> int:
        from js import Atomics

        # Blocks indefinitely when timeout is None, matching
        # queue.Queue.put()'s default (block=True, timeout=None) semantics
        # used by ThreadingTransport. Returns -1 on timeout, mirroring
        # _reserve_read()'s sentinel - put() turns it into Full.
        deadline = None if timeout is None else _now_ms() + timeout * 1000

        while True:
            count = int(Atomics.load(self._header, _COUNT))

            if count < self._capacity:
                return int(Atomics.load(self._header, _HEAD))

            if timeout is not None:
                remaining_ms = deadline - _now_ms()
                if remaining_ms <= 0:
                    return -1
                _atomics_wait_async(self._header, _COUNT, count, remaining_ms)
            else:
                _atomics_wait_async(self._header, _COUNT, count)

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
                _atomics_wait_async(self._header, _COUNT, count, remaining_ms)
            else:
                _atomics_wait_async(self._header, _COUNT, count)

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
    Mutual-exclusion primitive: a single Int32 cell in a SharedArrayBuffer,
    `Atomics.compareExchange` for the uncontended fast path,
    `_atomics_wait_async` (cooperative, JSPI-backed) for the contended
    path. NOT reentrant, unlike the `RLock` behind `threading.Condition` -
    `Node`/`Buffer` never nest lock acquisition, so this is a deliberate
    simplification, not a gap.

    Validated in `design/browser-transport/spike/jspi/worker6-lockcond.js`
    (exact mutual exclusion over 60 contested increments).
    """

    _CELL = 0

    def __init__(self):
        from js import Int32Array
        from js import SharedArrayBuffer

        sab = SharedArrayBuffer.new(4)
        self._cell = Int32Array.new(sab)

    def __enter__(self):
        from js import Atomics

        while True:
            prev = int(Atomics.compareExchange(self._cell, self._CELL, 0, 1))

            if prev == 0:
                return self

            _atomics_wait_async(self._cell, self._CELL, 1)

    def __exit__(self, *exc_info) -> None:
        from js import Atomics

        Atomics.store(self._cell, self._CELL, 0)
        Atomics.notify(self._cell, self._CELL, 1)


class _BrowserCondition:
    """
    Condition variable: a generation-counter Int32 cell plus an associated
    `_BrowserLock`, mirroring `threading.Condition` (`__enter__`/
    `__exit__` delegate to the lock; `wait_for`/`notify_all` use the
    counter).

    Validated in `design/browser-transport/spike/jspi/worker6-lockcond.js`
    (waiter woke within ~2ms of the notifier's delay).
    """

    _GEN = 0

    def __init__(self):
        from js import Int32Array
        from js import SharedArrayBuffer

        sab = SharedArrayBuffer.new(4)
        self._gen_cell = Int32Array.new(sab)
        self._lock = _BrowserLock()

    def __enter__(self):
        self._lock.__enter__()
        return self

    def __exit__(self, *exc_info) -> None:
        self._lock.__exit__(*exc_info)

    def wait_for(
        self, predicate: Callable[[], bool], timeout: float | None = None
    ) -> None:
        from js import Atomics

        if predicate():
            return

        # Guarded here, before the lock is ever released: a raise from
        # inside _atomics_wait_async (the guard lives there too) would
        # otherwise leave the lock released but not reacquired, and the
        # enclosing `with condition:` would then release/notify a lock
        # it no longer holds on the way out.
        _require_stack_switching('_BrowserCondition.wait_for()')

        # One deadline for the whole call, matching
        # threading.Condition.wait_for() - not reset per iteration.
        deadline = None if timeout is None else _now_ms() + timeout * 1000

        while not predicate():
            remaining_ms = None
            if deadline is not None:
                remaining_ms = deadline - _now_ms()
                if remaining_ms <= 0:
                    return

            # The generation MUST be read before releasing the lock: if a
            # notifier bumps it in the window between release and the
            # wait call, waitAsync returns immediately (value mismatch)
            # and the loop just rechecks the predicate instead of missing
            # the wakeup. This closes the lost-wakeup race - not
            # redundant bookkeeping.
            gen = int(Atomics.load(self._gen_cell, self._GEN))
            self._lock.__exit__(None, None, None)
            _atomics_wait_async(self._gen_cell, self._GEN, gen, remaining_ms)
            self._lock.__enter__()

    def notify_all(self) -> None:
        from js import Atomics

        Atomics.add(self._gen_cell, self._GEN, 1)
        Atomics.notify(self._gen_cell, self._GEN)


def _get_js_spawn_fn():
    """
    Builds, from Python, the JS helper that starts a JSPI stack-switching
    task from a proxied Python callable: `pyCallableProxy.callPromising()`
    must be invoked from JS (not called directly from Python) for the
    target to actually run with stack switching enabled - see
    `design/browser-transport/spike/jspi/worker7-iscurrent.js`.
    """
    from js import Function

    return Function.new(
        'pyCallableProxy',
        'return pyCallableProxy.callPromising();',
    )


class _BrowserWorker:
    """
    `WorkerHandle` for `BrowserTransport.spawn()`. There is no real OS
    thread under Pyodide (confirmed: `RuntimeError: can't start new
    thread`) - concurrency between a node's `_worker`/`_update`/
    `_source`/`_control` loops is cooperative, provided by JSPI: `start()`
    invokes a proxied `target` via `.callPromising()`, which lets it
    suspend on `run_sync(...)` (inside `_BrowserQueue`/`_BrowserLock`/
    `_BrowserCondition`) without blocking the other spawned targets
    sharing the same interpreter/event loop.

    A target raising is caught and logged (mirrors
    `threading.Thread`'s default excepthook behaviour: the exception
    terminates the target but never re-raises into `join()`).
    """

    def __init__(
        self, target: Callable[[], None], name: str, daemon: bool = True
    ):
        self._target = target
        self.name = name
        self.daemon = daemon
        self._done = False
        self._proxy = None
        self._promise = None

    def start(self) -> None:
        from pyodide.ffi import create_proxy

        handle = self

        def wrapped():
            token = _current_worker.set(handle)
            try:
                handle._target()
            except BaseException:
                import traceback

                traceback.print_exc()
            finally:
                _current_worker.reset(token)
                handle._done = True
                # Safe to destroy here: JS only needs the proxy to
                # *initiate* the call (already happened by this point),
                # not to hold the already-returned Promise.
                handle._proxy.destroy()

        self._proxy = create_proxy(wrapped)
        js_spawn = _get_js_spawn_fn()
        self._promise = js_spawn(self._proxy)

    def join(self, timeout: float | None = None) -> None:
        from pyodide.ffi import run_sync

        if self._promise is None or self._done:
            return

        _require_stack_switching('_BrowserWorker.join()')

        if timeout is None:
            run_sync(self._promise)
            return

        from js import Function

        # Promise.race against a timer: matches threading.Thread.join()
        # semantics - a timed-out join returns without raising, the
        # caller checks is_alive() afterwards.
        race = Function.new(
            'promise',
            'timeoutMs',
            'return Promise.race(['
            'promise, '
            'new Promise((resolve) => setTimeout(resolve, timeoutMs)),'
            ']);',
        )
        run_sync(race(self._promise, timeout * 1000))

    def is_alive(self) -> bool:
        return self._promise is not None and not self._done


class BrowserTransport:
    """
    Browser transport backend (Pyodide + `SharedArrayBuffer`/`Atomics`,
    made concurrent by JSPI). See the module docstring for the deployment
    requirement (Pyodide >= v314.0.0, module-type Worker, entry point
    invoked via `.callPromising()`).
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

    def queue_handle(self, queue: _BrowserQueue):
        """What to post to another Worker so it can `attach_queue()`."""
        return queue.handle()

    def attach_queue(self, handle) -> _BrowserQueue:
        """
        Attach to a queue created in another Worker, from the ``handle`` it
        posted. The ring has a single producer and a single consumer: attach
        from one Worker only if nothing else in another Worker writes to it.

        Raises
        ------
        ValueError
            If the queue geometry does not match the handle.

        """
        return _BrowserQueue(
            capacity=handle.capacity,
            max_meta_json_bytes=handle.max_meta_json_bytes,
            max_payload_bytes=handle.max_payload_bytes,
            sab=handle.sab,
        )

    def new_signal(self) -> _BrowserSignal:
        return _BrowserSignal()

    def new_event(self) -> _BrowserEvent:
        return _BrowserEvent()

    def new_lock(self) -> _BrowserLock:
        return _BrowserLock()

    def new_condition(self) -> _BrowserCondition:
        return _BrowserCondition()

    def spawn(
        self, target: Callable[[], None], name: str, daemon: bool = True
    ) -> _BrowserWorker:
        return _BrowserWorker(target, name, daemon)

    def is_current(self, handle: WorkerHandle) -> bool:
        return _current_worker.get() is handle
