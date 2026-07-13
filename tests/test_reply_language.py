"""
Unit tests for reply-language resolution.

The reply must be pronounceable by the active TTS voice: a Ukrainian voice has
no phonemes for Latin script and a British one has none for Cyrillic, so a
mismatch synthesises as silence or noise. These tests verify the engine derives
the reply language from the configured voice instead of pinning every install
to English.

No Ollama, no Piper runtime — the voice is represented by its sidecar config,
exactly as Piper ships it.
"""

import json
from types import SimpleNamespace

import pytest

from jarvis.output.tts import get_piper_voice_language
from jarvis.reply.engine import build_reply_language_guidance, resolve_reply_language


# =============================================================================
# Helpers
# =============================================================================

def _write_voice(tmp_path, filename: str, name_english: str):
    """Write a Piper voice sidecar and return the .onnx path it describes."""
    onnx = tmp_path / filename
    onnx.write_bytes(b"")  # the model itself is never read here
    sidecar = tmp_path / f"{filename}.json"
    sidecar.write_text(
        json.dumps({"language": {"code": "xx_XX", "name_english": name_english}}),
        encoding="utf-8",
    )
    return str(onnx)


def _cfg(**overrides):
    base = dict(tts_enabled=True, tts_engine="piper", tts_piper_model_path=None)
    base.update(overrides)
    return SimpleNamespace(**base)


# =============================================================================
# get_piper_voice_language
# =============================================================================

class TestGetPiperVoiceLanguage:
    """The voice's own sidecar is the source of truth for what it can say."""

    def test_reads_language_from_sidecar(self, tmp_path):
        path = _write_voice(tmp_path, "uk_UA-ukrainian_tts-medium.onnx", "Ukrainian")
        assert get_piper_voice_language(path) == "Ukrainian"

    def test_reads_english_voice(self, tmp_path):
        path = _write_voice(tmp_path, "en_GB-alan-medium.onnx", "English")
        assert get_piper_voice_language(path) == "English"

    def test_missing_sidecar_is_unknown(self, tmp_path):
        onnx = tmp_path / "hand-rolled.onnx"
        onnx.write_bytes(b"")
        assert get_piper_voice_language(str(onnx)) is None

    def test_corrupt_sidecar_is_unknown(self, tmp_path):
        onnx = tmp_path / "broken.onnx"
        onnx.write_bytes(b"")
        (tmp_path / "broken.onnx.json").write_text("{not json", encoding="utf-8")
        assert get_piper_voice_language(str(onnx)) is None


# =============================================================================
# resolve_reply_language
# =============================================================================

class TestResolveReplyLanguage:
    """The reply language follows the voice, with English as the safe default."""

    def test_ukrainian_voice_yields_ukrainian(self, tmp_path):
        path = _write_voice(tmp_path, "uk_UA-ukrainian_tts-medium.onnx", "Ukrainian")
        assert resolve_reply_language(_cfg(tts_piper_model_path=path)) == "Ukrainian"

    def test_unknown_voice_falls_back_to_english(self, tmp_path):
        onnx = tmp_path / "mystery.onnx"
        onnx.write_bytes(b"")
        cfg = _cfg(tts_piper_model_path=str(onnx))
        assert resolve_reply_language(cfg) == "English"

    def test_chatterbox_is_english_only(self, tmp_path):
        # Even with a Ukrainian Piper voice on disk, Chatterbox cannot speak it.
        path = _write_voice(tmp_path, "uk_UA-ukrainian_tts-medium.onnx", "Ukrainian")
        cfg = _cfg(tts_engine="chatterbox", tts_piper_model_path=path)
        assert resolve_reply_language(cfg) == "English"

    def test_disabled_tts_leaves_language_unconstrained(self, tmp_path):
        # Nothing is spoken aloud, so the model may answer in the user's language.
        assert resolve_reply_language(_cfg(tts_enabled=False)) is None

    def test_unrecognised_engine_leaves_language_unconstrained(self):
        # We only constrain the reply for engines we actually speak through.
        assert resolve_reply_language(_cfg(tts_engine="espeak")) is None

    def test_non_path_model_setting_does_not_raise(self):
        # A stubbed or malformed config must not take the reply engine down.
        cfg = _cfg(tts_piper_model_path=object())
        assert resolve_reply_language(cfg) == "English"


# =============================================================================
# build_reply_language_guidance
# =============================================================================

class TestBuildReplyLanguageGuidance:
    """The system-prompt line must name the language the voice speaks."""

    def test_guidance_names_the_voice_language(self, tmp_path):
        path = _write_voice(tmp_path, "uk_UA-ukrainian_tts-medium.onnx", "Ukrainian")
        guidance = build_reply_language_guidance(_cfg(tts_piper_model_path=path))
        assert guidance is not None
        assert "Ukrainian" in guidance
        assert "English" not in guidance

    def test_default_install_still_says_english(self, tmp_path):
        onnx = tmp_path / "not-downloaded-yet.onnx"
        guidance = build_reply_language_guidance(_cfg(tts_piper_model_path=str(onnx)))
        assert guidance is not None
        assert "English" in guidance

    def test_no_guidance_when_tts_disabled(self):
        assert build_reply_language_guidance(_cfg(tts_enabled=False)) is None
