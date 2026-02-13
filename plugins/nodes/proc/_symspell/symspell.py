"""
Symspell

@author: Paolo Saviano
@email: psaviano@meetecho.com
@created_at: 2026-02-12 16:03:28

This nodes implement symspell spell correction algorithm.
"""

import re
from symspellpy import SymSpell, Verbosity
from pathlib import Path

from juturna.components import Node
from juturna.components import Message

from juturna.payloads import ObjectPayload, Draft


class Symspell(Node[ObjectPayload, ObjectPayload]):
    """Node implementation class"""

    def __init__(
        self,
        dictionary_path: str,
        min_frequency_threshold: int,
        min_edit_distance: int,
        max_edit_distance: int,
        min_confidence_threshold: float,
        frequency_ratio_threshold: int,
        custom_dictionary: list[str] | None,
        whitelist: list[str] | None,
        **kwargs,
    ):
        """
        Parameters
        ----------
        dictionary_path : str
            Path to the dictionary file (https://github.com/wolfgarbe/SymSpell/blob/master/SymSpell.FrequencyDictionary).
        min_frequency_threshold : int
            Minimum frequency threshold for terms.
        min_edit_distance : int
            Minimum edit distance for corrections.
        max_edit_distance : int
            Maximum edit distance for corrections.
        min_confidence_threshold : float
            Minimum confidence threshold for applying corrections.
        frequency_ratio_threshold : int
            Frequency ratio threshold required for corrections.
        custom_dictionary : list[str] | None, optional
            Custom dictionary entries.
        whitelist : list[str] | None, optional
            List of whitelisted terms that should not be corrected.
        kwargs : dict
            Supernode arguments.

        """
        super().__init__(**kwargs)
        self._dictionary_path = dictionary_path
        self._custom_dictionary = custom_dictionary or []
        self._whitelist = whitelist or []
        self._min_frequency_threshold = min_frequency_threshold
        self._min_confidence_threshold = min_confidence_threshold
        self._min_edit_distance = min_edit_distance
        self._max_edit_distance = max_edit_distance
        self._frequency_ratio_threshold = frequency_ratio_threshold

    def warmup(self):
        """Warmup the node"""
        self._sym_spell = SymSpell(
            max_dictionary_edit_distance=self._max_edit_distance,
            prefix_length=7,
        )
        self._sym_spell.load_dictionary(
            Path(self._dictionary_path),
            term_index=0,
            count_index=1,
        )

        for term, freq in self._custom_dictionary:
            self._sym_spell.create_dictionary_entry(term, freq)

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
            words = suggestion.split()
            corrected_words = []

            for word in words:
                match = re.match(r'(\W*)(\w+)(\W*)', word)
                if not match:
                    corrected_words.append(word)
                    continue

                prefix, core, suffix = match.groups()

                is_suspicious, original_freq = self._is_word_suspicious(core)
                if not is_suspicious:
                    corrected_words.append(word)
                    continue

                corrected, confidence, orig_freq, corr_freq = (
                    self._propose_corrections(core)
                )

                if confidence > self._min_confidence_threshold:
                    if core[0].isupper():
                        corrected = corrected.capitalize()

                    corrected_word = prefix + corrected + suffix
                    corrected_words.append(corrected_word)
                    self.logger.debug(
                        f"Corrected '{core}' to '{corrected}' "
                        f'conf: {confidence:.2f}, '
                        f'freq: {orig_freq} → {corr_freq}'
                    )
                else:
                    corrected_words.append(word)

            to_send.payload['suggestion'] = ' '.join(corrected_words)

        self.transmit(to_send)

    def _is_word_suspicious(self, word: str) -> tuple[bool, float]:
        normalized_word = word.lower()

        if normalized_word in self._whitelist:
            return False, float('inf')

        if len(word) <= 2:
            return False, float('inf')

        if not word.isalpha():
            return False, float('inf')

        lookup_result = self._sym_spell.lookup(
            normalized_word,
            Verbosity.TOP,
            max_edit_distance=0,
            include_unknown=True,
        )

        if not lookup_result:
            return True, 0.0

        frequency = lookup_result[0].count
        return frequency < self._min_frequency_threshold, frequency

    def _propose_corrections(
        self, word: str
    ) -> tuple[list[str], float, int, int]:
        normalized_word = word.lower()

        suggestions = self._sym_spell.lookup(
            normalized_word,
            Verbosity.ALL,
            max_edit_distance=self._max_edit_distance,
            include_unknown=False,
        )

        if not suggestions or len(suggestions) == 0:
            return word, 0.0, 0, 0

        original_freq = 0
        for suggestion in suggestions:
            if suggestion.term.lower() == normalized_word:
                original_freq = suggestion.count
                break

        candidates = []

        for suggestion in suggestions:
            if suggestion.term.lower() == normalized_word:
                continue

            if suggestion.distance > self._max_edit_distance:
                continue

            if suggestion.count < self._min_frequency_threshold * original_freq:
                continue

            candidates.append(suggestion)

        if not candidates:
            return word, 0.0, original_freq, original_freq

        best_suggestion = max(candidates, key=lambda s: s.count)

        freq_score = (
            min(best_suggestion.count / max(original_freq, 1), 100) / 100
        )

        dist_score = 1.0 - (best_suggestion.distance / self._max_edit_distance)

        confidence = (freq_score * 0.7) + (dist_score * 0.3)

        return (
            best_suggestion.term,
            confidence,
            best_suggestion.distance,
            best_suggestion.count,
        )
