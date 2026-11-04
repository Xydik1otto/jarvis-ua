"""Tests for restricted "text" voice normalisation.

Voices with phoneme_type="text" (e.g. uk_UA-ukrainian_tts) map only their bare
alphabet, so capitals, digits, brackets and Latin letters have no phoneme and
get dropped mid-word ("Missing phoneme from id map"). The normaliser folds text
down to the voice's own character set so nothing is swallowed.
"""

import pytest

from src.jarvis.output.tts import (
    normalise_for_restricted_voice,
    _uk_number_to_words,
)


# The real uk_UA-ukrainian_tts-medium character set.
UK_ALLOWED = set("\" !$',-.:;?^_́̆̈"
                 "абвгдежзийклмнопрстуфхцчшщьюяєіїґ—")


class TestUkNumberToWords:
    def test_single_digits(self):
        assert _uk_number_to_words(0) == "нуль"
        assert _uk_number_to_words(4) == "чотири"

    def test_teens_and_tens(self):
        assert _uk_number_to_words(11) == "одинадцять"
        assert _uk_number_to_words(29) == "двадцять дев'ять"
        assert _uk_number_to_words(40) == "сорок"

    def test_hundreds(self):
        assert _uk_number_to_words(150) == "сто п'ятдесят"

    def test_thousands(self):
        assert _uk_number_to_words(2026).startswith("дві тисячі")

    def test_words_use_only_allowed_characters(self):
        # Every number word must itself be pronounceable by the voice.
        for n in list(range(0, 100)) + [150, 365, 1000, 2026, 9999]:
            for ch in _uk_number_to_words(n):
                assert ch == " " or ch in UK_ALLOWED, (
                    f"number {n} produced unpronounceable {ch!r}"
                )


class TestNormaliseForRestrictedVoice:
    def _assert_clean(self, out):
        leftovers = [c for c in out if not c.isspace() and c not in UK_ALLOWED]
        assert not leftovers, f"unpronounceable chars survived: {leftovers}"

    def test_the_phrase_that_broke_playback(self):
        # Straight from the field log that logged one warning per character.
        text = "Сьогодні в Лівонії час 04:29 Фінляндія (літо)."
        out = normalise_for_restricted_voice(text, UK_ALLOWED)
        self._assert_clean(out)

    def test_capitals_are_lowercased_not_dropped(self):
        out = normalise_for_restricted_voice("Привіт", UK_ALLOWED)
        assert "привіт" in out
        self._assert_clean(out)

    def test_digits_become_words(self):
        out = normalise_for_restricted_voice("42 котики", UK_ALLOWED)
        assert "сорок" in out and "два" in out
        assert not any(c.isdigit() for c in out)

    def test_brackets_become_pauses_not_missing_phonemes(self):
        out = normalise_for_restricted_voice("день (літо)", UK_ALLOWED)
        self._assert_clean(out)
        assert "(" not in out and ")" not in out

    def test_latin_is_stripped(self):
        out = normalise_for_restricted_voice("модель gemma працює", UK_ALLOWED)
        self._assert_clean(out)
        assert "працює" in out

    def test_no_runaway_whitespace(self):
        out = normalise_for_restricted_voice("а   б    в", UK_ALLOWED)
        assert "  " not in out

    def test_empty_allowed_set_is_passthrough(self):
        # An espeak voice (no restricted charset) must be left untouched.
        text = "Hello, World! 42"
        assert normalise_for_restricted_voice(text, set()) == text
