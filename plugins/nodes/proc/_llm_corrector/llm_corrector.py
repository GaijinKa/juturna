"""
Vllm

@author: Paolo Saviano
@email: psaviano@meetecho.com
@created_at: 2026-02-13 12:47:25

"""

from juturna.components import Node
from juturna.components import Message

from juturna.payloads import ObjectPayload, Draft

from transformers import AutoTokenizer, AutoModelForCausalLM
import torch


class LLMCorrector(Node[ObjectPayload, ObjectPayload]):
    """Node implementation class"""

    def __init__(
        self,
        prompt: str,
        model_name: str,
        context_window: int,
        temperature: int,
        device: str,
        max_new_tokens: int,
        **kwargs,
    ):
        """
        Parameters
        ----------
        prompt : str
            System prompt to use.
        model_name : str
            Name of the model to use.
        context_window : int
            Number of previous suggestions to include in the prompt.
        device : str
            Device to use for model inference (e.g., 'cuda' or 'cpu').
        temperature : int
            Sampling temperature.
        max_new_tokens : int
            Maximum number of new tokens to generate.
        kwargs : dict
            Supernode arguments.

        """
        self._system_prompt = prompt
        self._model_name = model_name
        self._context_window = context_window
        self._history = []
        self._device = device
        self._temperature = temperature
        self._max_new_tokens = max_new_tokens

        super().__init__(**kwargs)

    def warmup(self):
        """Warmup the node"""
        self._tokenizer = AutoTokenizer.from_pretrained(
            self._model_name, trust_remote_code=True
        )
        self._options = dict(
            temperature=self._temperature,
            max_new_tokens=self._max_new_tokens,
            do_sample=False,
            pad_token_id=self._tokenizer.eos_token_id,
            eos_token_id=self._tokenizer.eos_token_id,
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            self._model_name,
            torch_dtype=torch.float16,
            device_map=self._device,
            trust_remote_code=True,
            attn_implementation='eager',  # Più stabile
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
            context_suggestions = [
                msg.payload['suggestion'] for msg in self._history
            ]

            adhoc_prompt = self._system_prompt

            if len(context_suggestions) > 0:
                adhoc_prompt = (
                    self._system_prompt
                    + '\nQueste sono parti del discorso precedente:'
                    + ' '.join(context_suggestions)
                )

            self.logger.debug(
                f'Full prompt:\n{adhoc_prompt}\nUser input:\n{suggestion}'
            )

            messages = [
                {'role': 'system', 'content': adhoc_prompt},
                {'role': 'user', 'content': f'Correggi: {suggestion}'},
            ]

            full_prompt = self._tokenizer(
                messages, add_generation_prompt=True, tokenize=False
            )

            self.logger.debug(f'Full prompt after tokenization:\n{full_prompt}')

            inputs = self._tokenizer(
                full_prompt, return_tensors='pt', padding=True
            ).to(self._model.device)

            input_length = inputs['input_ids'].shape[1]

            with torch.no_grad():
                output = self._model.generate(**inputs, **self._options)

            generated_response = output[0][input_length:]

            full_output = self._tokenizer.decode(
                generated_response,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True,
            )

            to_send.payload['suggestion'] = full_output.strip()

        if len(self._history) >= self._context_window:
            self._history.pop(0)

        self._history.append(to_send)

        self.transmit(to_send)
