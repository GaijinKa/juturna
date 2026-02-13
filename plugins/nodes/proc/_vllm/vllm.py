"""
Vllm

@author: Paolo Saviano
@email: psaviano@meetecho.com
@created_at: 2026-02-13 12:47:25

"""

from juturna.components import Node
from juturna.components import Message

# BasePayload type is intended to be a placehoder for the input-output types
# you intend to use in the node implementation
from juturna.payloads import ObjectPayload, Draft

from vllm import LLM, SamplingParams


class Vllm(Node[ObjectPayload, ObjectPayload]):
    """Node implementation class"""

    def __init__(self, model_name: str, **kwargs):
        """
        Parameters
        ----------
        model_name : str
            Name of the model to use.
        kwargs : dict
            Supernode arguments.

        """
        self._model_name = model_name
        self._options = SamplingParams(
            temperature=0,
            max_tokens=512,
            stop=['\n'],
        )
        self._system_prompt = (
            'You are a helpful assistant for correcting ASR '
            'transcription errors. '
            'You receive an ASR transcription and you correct any error in it, '
            'without changing the meaning of the text. You only reply with the '
            'corrected text, without any explanation.'
            'Preserve ABSOLUTELY all named entities and technical terms'
        )
        super().__init__(**kwargs)

    def warmup(self):
        """Warmup the node"""
        self._model = LLM(
            model=self._model_name,
            trust_remote_code=True,
            max_model_len=512,  # I chunk sono brevi, non serve 4096
            dtype='float16',  # Standard per velocità su GPU consumer
            gpu_memory_utilization=0.5,
        )

    def update(self, message: Message[ObjectPayload]):
        """Receive data from upstream, transmit data downstream"""
        word_info = message.payload

        suggestion = word_info.get('suggestion')
        silence = word_info.get('silence', False)
        hallucination = word_info.get('hallucination', False)

        to_send = Message[ObjectPayload](
            creator=self.name,
            version=message.version,
            payload=Draft(ObjectPayload),
            timers_from=message,
        )

        to_send.payload['suggestion'] = suggestion
        to_send.payload['silence'] = silence
        to_send.payload['hallucination'] = hallucination

        to_send.meta = dict(message.meta)

        if suggestion:
            full_prompt = f'<|system|>\n{self._system_prompt}<|end|>\n'
            full_prompt += f'<|user|>\n{suggestion}<|end|>\n<|assistant|>\n'
            output = self._model._generate(full_prompt, self._options)
            to_send.payload['suggestion'] = output[0].outputs[0].text.strip()

        self.transmit(to_send)
