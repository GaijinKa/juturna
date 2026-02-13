"""
Neuspell

@author: Paolo Saviano
@email: psaviano@meetecho.com
@created_at: 2026-02-13 10:46:11


"""

import re

from juturna.components import Node
from juturna.components import Message

from juturna.payloads import ObjectPayload, Draft

from transformers import pipeline, BertTokenizer


class BertSpellcheck(Node[ObjectPayload, ObjectPayload]):
    """Node implementation class"""

    def __init__(
        self,
        model_name: str,
        device: str,
        whitelist: list[str] | None,
        confidence_threshold: float,
        top_k: int,
        **kwargs,
    ):
        """
        Initialization of the BertSpellcheck node.

        Parameters
        ----------
        model_name : str
            Name of the model to use.
        device : str
            Device to run the model on (e.g., 'cpu' or 'cuda').
        whitelist : list[str] | None, optional
            List of whitelisted terms that should not be corrected.
        top_k : int
            Number of top predictions to consider for corrections.
        confidence_threshold : float
            Confidence threshold for applying corrections.
        kwargs : dict
            Supernode arguments.

        """
        super().__init__(**kwargs)
        self._model_name = model_name
        self._device = device
        self._whitelist = whitelist or []
        self._top_k = top_k
        self._confidence_threshold = confidence_threshold
        self._checker = None
        self._temp_history = []

    def warmup(self):
        """Warmup the node"""
        self._pipe = pipeline(
            'fill-mask',
            model=self._model_name,
            device=0 if self._device == 'cuda' else -1,
        )
        self._tokenizer = BertTokenizer.from_pretrained(self._model_name)

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

        if not suggestion or silence or hallucination:
            self.logger.debug(
                'No suggestion or silence/hallucination detected'
                ', skipping correction.'
            )
            return

        words = suggestion.split()
        corrected_words = list(words)

        for i, word in enumerate(words):
            match = re.match(r'(\W*)(\w+)(\W*)', word)
            if not match:
                corrected_words.append(word)
                continue

            prefix, core, suffix = match.groups()
            if core in self._whitelist:
                self.logger.debug(
                    f'Word "{word}" is whitelisted, skipping correction.'
                )
                continue

            if not core.isalpha() or len(core) <= 3:
                self.logger.debug(
                    f'Word "{word}" is not a candidate for correction, skipping'
                )
                continue

            is_correct, best_alternative, confidence = self.test_word(
                suggestion, i
            )

            if not is_correct and confidence >= self._confidence_threshold:
                self.logger.debug(
                    f'Word "{word}" is incorrect. '
                    f'Replacing with "{best_alternative}" '
                    f'(confidence: {confidence:.4f}).'
                )
                corrected_words[i] = f'{prefix}{best_alternative}{suffix}'

        corrected_suggestion = ' '.join(corrected_words)
        to_send.payload['suggestion'] = corrected_suggestion

        self.transmit(to_send)

    def test_word(self, text, word_position) -> tuple[bool, str, float]:
        """
        Returns:
            (is_correct, best_alternative, confidence)

        """
        words = text.split()
        target_word = words[word_position]

        masked_words = words.copy()
        masked_words[word_position] = self._tokenizer.mask_token
        masked_text = ' '.join(masked_words)

        predictions = self._pipe(masked_text, top_k=self._top_k)

        target_lower = target_word.lower()

        for i, pred in enumerate(predictions):
            self.logger.debug(
                f'Prediction {i}: '
                f"'{pred['token_str'].strip()}' with score {pred['score']:.4f}"
            )
            pred_word = pred['token_str'].strip().lower()

            if pred_word == target_lower:
                return True, target_word, pred['score']

        best = predictions[0]
        return False, best['token_str'].strip(), best['score']
