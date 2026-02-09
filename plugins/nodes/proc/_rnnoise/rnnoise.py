"""
RnnNoise

@author: Paolo Saviano
@email: psaviano@meetecho.com
@created_at: 2026-02-09 11:56:01

Use the RNNoise library to perform noise suppression on audio content.
"""

from juturna.components import Node
from juturna.components import Message

from juturna.payloads import AudioPayload

from .rnnoise_wrapper import RNNoiseWrapper


class RnnNoise(Node[AudioPayload, AudioPayload]):
    """Node implementation class"""

    def __init__(
        self,
        lib_path: str,
        **kwargs,
    ):
        """
        Parameters
        ----------
        lib_path : str, optional
            Custom path to the RNNoise library.
            If None, searches in standard paths.
        kwargs : dict
            Supernode arguments.

        """
        super().__init__(**kwargs)
        self._lib_path = lib_path

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
        ...

    def update(self, message: Message[AudioPayload]):
        """Receive data from upstream, transmit data downstream"""
        assert self.denoiser is not None

        audio_frame = message.payload.audio

        output_buffer = []
        vad_probs = []

        # this works under the assumption that input audio is already resampled
        # to 48kHz and framed into 10ms (480 samples) chunks by upstream nodes.
        # If not, additional buffering and resampling logic would be needed here
        while len(audio_frame) >= RNNoiseWrapper.FRAME_SIZE:
            frame = audio_frame[: RNNoiseWrapper.FRAME_SIZE]
            audio_frame = audio_frame[RNNoiseWrapper.FRAME_SIZE :]
            cleaned_audio, vad_prob = self.denoiser.process_frame(frame)
            vad_probs.append(vad_prob)
            output_buffer.append(cleaned_audio)

        to_send = Message[AudioPayload](
            creator=self.name,
            version=message.version,
            payload=AudioPayload(
                audio=cleaned_audio,
                sample_rate=message.payload.sample_rate,
                sampling_rate=message.payload.sampling_rate,
                audio_format=message.payload.audio_format,
                channels=message.payload.channels,
                start=message.payload.start,
                end=message.payload.end,
            ),
            timers_from=message,
        )

        to_send.meta = dict(message.meta)

        to_send.meta['silence'] = False
        to_send.meta['sequence_number'] = message.version
        to_send.meta['original_audio'] = message.payload.audio
        to_send.meta['vad_probs'] = sum(vad_probs) / len(vad_probs)

        self.dump_json(message, f'{self.name}_{message.version}.json')
        self.transmit(to_send)

    # uncomment next_batch to design custom synchronisation policy
    # def next_batch(sources: dict[str, list[Message]]) -> dict[str, list[int]]:
    #     ...
