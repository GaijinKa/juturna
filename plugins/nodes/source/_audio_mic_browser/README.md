# audio_mic_browser

Source node reading the microphone from inside a browser tab, for
browser-only pipelines (Pyodide + `BrowserTransport`).

## Node type: source

## Node class name: AudioMicBrowser

## Node name: audio_mic_browser

## How it works

`getUserMedia` and `AudioWorklet` exist only on the page's main thread,
while the node runs inside a Pyodide Worker. The page therefore captures
the audio (`AudioContext({sampleRate: audio_rate})` + an `AudioWorklet`)
and writes it into a float32 ring buffer on a `SharedArrayBuffer`; the node
reads `block_size` seconds at a time from it, waiting on
`Atomics.waitAsync` when the block is not complete yet. If the reader falls
behind by more than the ring capacity, the oldest audio is dropped (logged
as a warning) instead of replayed corrupted.

Ring layout, to be respected by the capture code on the page:

- `int32[4]` header (16 bytes): `WRITTEN`, `READ`, `CLOSED`, `OVERRUNS`
  (sample counters; `CLOSED` != 0 asks the node to stop)
- `float32[capacity]` samples, mono, range [-1, 1]

The `SharedArrayBuffer` must be exposed to the Worker as
`globalThis[ring_name]` before `warmup()`.

Requirements: Pyodide >= 314.0.0, module Worker, `BrowserTransport`, entry
point invoked via `.callPromising()`, page served with COOP/COEP headers.

## Arguments

- `ring_name`: name of the `globalThis` property holding the ring
- `block_size`: seconds of audio per message
- `audio_rate`: sampling rate of the ring (must match the page's
  `AudioContext`)

## Input message

None: this is a source node, data comes from the ring buffer. The
`update()` method only receives the messages the node generated itself.

## Output message

`Message[AudioPayload]`, one per `block_size` seconds of audio.

Payload (`AudioPayload`):

- `audio`: `np.float32`, shape `(block_size * audio_rate,)`, mono
- `sampling_rate`: `audio_rate`
- `channels`: `1`
- `start` / `end`: block boundaries in **seconds** since the capture
  started (note: `audio_file` uses sample offsets instead)
- `audio_format`: left at the default (`''`)

Meta:

- `session_id`: set to `pipe_id` (`None` if the node runs outside a
  `Pipeline`)

At end of stream (`CLOSED` set, or node stopped) a
`Message[ControlPayload]` with `ControlSignal.STOP` is emitted instead.
