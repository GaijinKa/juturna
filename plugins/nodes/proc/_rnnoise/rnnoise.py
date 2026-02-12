"""
RnnNoise

@author: Paolo Saviano
@email: psaviano@meetecho.com
@created_at: 2026-02-09 11:56:01

Use the RNNoise library to perform noise suppression on audio content.
"""

import numpy as np
import av

from juturna.components import Node
from juturna.components import Message

from juturna.payloads import AudioPayload

from .rnnoise_wrapper import RNNoiseWrapper


class RnnNoise(Node[AudioPayload, AudioPayload]):
    """Node implementation class"""

    def __init__(
        self,
        lib_path: str,
        keep_original_sr: bool,
        **kwargs,
    ):
        """
        Parameters
        ----------
        lib_path : str, optional
            Custom path to the RNNoise library.
            If None, searches in standard paths.
        keep_original_sr : bool
            Whether to resample the output back to the original sampling rate.
        kwargs : dict
            Supernode arguments.

        """
        super().__init__(**kwargs)
        self._lib_path = lib_path
        self._keep_original_sr = keep_original_sr

        self.denoiser = None

    def warmup(self):
        """Warmup the node"""
        try:
            self.denoiser = RNNoiseWrapper(lib_path=self._lib_path)
            self.logger.info('rnnoise ready')
        except RuntimeError as e:
            self.logger.error(f'Failed to load RNNoise library: {e}')
            raise

    def destroy(self):
        """Destroy the node"""
        if self.denoiser is not None:
            del self.denoiser
            self.denoiser = None

    def update(self, message: Message[AudioPayload]):
        """Receive data from upstream, transmit data downstream"""
        assert self.denoiser is not None

        audio_frame = message.payload.audio

        resampled_frame = self._resample_audio(
            audio_frame,
            from_sr=message.payload.sampling_rate,
            to_sr=RNNoiseWrapper.SAMPLE_RATE,
            channels=message.payload.channels,
        ).astype(np.float32)

        vad_probs = []
        cleaned_audio = []

        # this works under the assumption that input audio is already resampled
        # to 48kHz and framed into 10ms (480 samples) chunks by upstream nodes.
        # If not, additional buffering and resampling logic would be needed here
        while len(resampled_frame) >= RNNoiseWrapper.FRAME_SIZE:
            frame = resampled_frame[: RNNoiseWrapper.FRAME_SIZE]
            resampled_frame = resampled_frame[RNNoiseWrapper.FRAME_SIZE :]
            cleaned_frame, vad_prob = self.denoiser.process_frame(frame)
            vad_probs.append(vad_prob)
            cleaned_audio.append(cleaned_frame)

        filtered_audio = (
            np.concatenate(cleaned_audio)
            if cleaned_audio
            else np.array([], dtype=np.float32)
        )

        cleaned_sampling_rate = RNNoiseWrapper.SAMPLE_RATE

        if (
            self._keep_original_sr
            and message.payload.sampling_rate != RNNoiseWrapper.SAMPLE_RATE
        ):
            filtered_audio = self._resample_audio(
                filtered_audio,
                from_sr=RNNoiseWrapper.SAMPLE_RATE,
                to_sr=message.payload.sampling_rate,
                channels=filtered_audio.shape[0]
                if filtered_audio.ndim > 1
                else 1,
            ).astype(np.float32)
            cleaned_sampling_rate = message.payload.sampling_rate

        to_send = Message[AudioPayload](
            creator=self.name,
            version=message.version,
            payload=AudioPayload(
                audio=filtered_audio,
                sampling_rate=cleaned_sampling_rate,
                audio_format='flt',
                channels=1,
                start=message.payload.start,
                end=message.payload.end,
            ),
            timers_from=message,
        )

        to_send.meta = dict(message.meta)

        to_send.meta['silence'] = False
        to_send.meta['sequence_number'] = message.version
        to_send.meta['original_audio'] = message.payload.audio
        to_send.meta['vad_probs'] = (
            sum(vad_probs) / len(vad_probs) if vad_probs else 0.0
        )

        self.dump_json(message, f'{self.name}_{message.version}.json')
        self.transmit(to_send)

    def _resample_audio(
        self, audio: np.ndarray, from_sr: int, to_sr: int, channels: int
    ) -> np.ndarray:
        if from_sr == to_sr:
            return audio

        if channels > 1:
            audio = audio.mean(axis=1)

        input_frame = av.AudioFrame.from_ndarray(
            audio.astype(np.float32).reshape(1, -1), format='flt', layout='mono'
        )
        input_frame.sample_rate = from_sr

        resampler = av.AudioResampler(format='flt', layout='mono', rate=to_sr)

        output_frames = list(resampler.resample(input_frame))
        output_frames.extend(resampler.resample(None))

        if output_frames:
            chunks = [f.to_ndarray()[0] for f in output_frames]
            return np.concatenate(chunks).astype(np.float32)
        else:
            return np.array([], dtype=np.float32)

    # uncomment next_batch to design custom synchronisation policy
    # def next_batch(sources: dict[str, list[Message]]) -> dict[str, list[int]]:
    #     ...
