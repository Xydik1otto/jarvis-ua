"""Tests for the unified persona system prompt.

The persona should match the user's configured wake word so renaming the
wake word to e.g. "Friday" produces a butler named Friday, not one still
hardcoded to Jarvis.

The prompt text is Ukrainian (personal UA build), so the name is rendered
as «на ім'я {name}».
"""

from jarvis.system_prompt import build_system_prompt


class TestBuildSystemPrompt:
    def test_default_name_is_jarvis(self):
        prompt = build_system_prompt()
        assert "на ім'я Jarvis" in prompt

    def test_custom_name_replaces_jarvis(self):
        prompt = build_system_prompt("Friday")
        assert "на ім'я Friday" in prompt
        assert "на ім'я Jarvis" not in prompt

    def test_lowercase_wake_word_is_capitalised(self):
        prompt = build_system_prompt("friday".capitalize())
        assert "на ім'я Friday" in prompt

    def test_blank_name_falls_back_to_jarvis(self):
        assert "на ім'я Jarvis" in build_system_prompt("")
        assert "на ім'я Jarvis" in build_system_prompt("   ")
        assert "на ім'я Jarvis" in build_system_prompt(None)  # type: ignore[arg-type]

    def test_prompt_is_ukrainian(self):
        """The persona prompt must be Ukrainian: qwen2.5:7b-instruct
        garbles Ukrainian replies when it reads a long English system
        prompt (invented words, Chinese phrases leaking in). A Ukrainian
        system prompt produces clean Ukrainian from the same model."""
        prompt = build_system_prompt()
        assert "дворецький" in prompt
        assert "Заборонені формулювання" in prompt
        # Long English instruction prose must be gone; only the wake-word
        # name itself may remain Latin.
        assert "British butler" not in prompt
        assert "Banned phrasings" not in prompt

    def test_prompt_has_no_em_dashes(self):
        prompt = build_system_prompt()
        assert "\u2014" not in prompt
