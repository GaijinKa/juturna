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

from neuspell import BertChecker, SclstmChecker, available_checkers


class Neuspell(Node[ObjectPayload, ObjectPayload]):
    """Node implementation class"""

    def __init__(
        self,
        model_name: str,
        context_window: int,
        device: str,
        whitelist: list[str] | None,
        confidence_threshold: float,
        **kwargs,
    ):
        """
        Initialization of the Neuspell node.

        Parameters
        ----------
        model_name : str
            Name of the model to use.
        context_window : int
            Size of the context window for the model ('bert' or 'sclstm')
        device : str
            Device to run the model on (e.g., 'cpu' or 'cuda').
        whitelist : list[str] | None, optional
            List of whitelisted terms that should not be corrected.
        confidence_threshold : float
            Confidence threshold for applying corrections.
        kwargs : dict
            Supernode arguments.

        """
        super().__init__(**kwargs)
        self._model_name = model_name
        self._context_window = context_window
        self._device = device
        self._whitelist = whitelist or []
        self._confidence_threshold = confidence_threshold
        self._checker = None
        self._temp_history = []

    def configure(self):
        """Configure the node"""
        self.logger.info(f'available checkers: {available_checkers()}')

        if self._model_name == 'bert':
            self._checker = BertChecker()
        elif self._model_name == 'sclstm':
            self._checker = SclstmChecker()
        else:
            raise ValueError(f'Unsupported model name: {self._model_name}')

    def warmup(self):
        """Warmup the node"""
        self._checker.from_pretrained()

    def stop(self):
        """Stop the node"""
        # after custom stop code, invoke base node stop
        super().stop()

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
            self._temp_history = []
            self.logger.debug(
                'No suggestion to process or silence/hallucination detected,'
                ' skipping correction and cleaning history'
            )
            return

        locked_suggestion = self._lock_whitelist(suggestion)
        context = ' '.join(
            [msg.payload.get('suggestion', '') for msg in self._temp_history]
        )
        full_suggestions = ' '.join([context, locked_suggestion]).strip()

        corrected = self._checker.correct(full_suggestions)

        corrected_words = corrected.split()

        chunk_word_count = len(locked_suggestion.split())
        corrected_chunk_words = corrected_words[-chunk_word_count:]
        corrected = ' '.join(corrected_chunk_words)

        restored_correction = self._restore_whitelist(corrected)
        to_send.payload['suggestion'] = restored_correction

        if len(self._temp_history) >= self._context_window:
            self._temp_history.pop(0)
        self._temp_history.append(message)

        self.transmit(to_send)

    def _lock_whitelist(self, text: str) -> str:
        """Check if a word is in the whitelist"""
        protected = text
        for word in self._whitelist:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            protected = pattern.sub(f'__PROTECTED_{word.upper()}__', protected)

        return protected

    def _restore_whitelist(self, text: str) -> str:
        """Restore whitelisted words in the text"""
        restored = text
        for word in self._whitelist:
            pattern = re.compile(
                f'__PROTECTED_{re.escape(word.upper())}__', re.IGNORECASE
            )
            restored = pattern.sub(word, restored)

        return restored
