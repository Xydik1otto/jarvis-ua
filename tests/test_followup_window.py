"""
Tests for the follow-up window (v1.2.0).

After Jarvis finishes a voice reply, the follow-up window keeps the
assistant listening for ~15 seconds without requiring the wake word:

- silence / timeout        -> back to wake word mode
- phrase without wake word -> processed as a normal query
- phrase with wake word    -> also works (wake word stripped)
- Jarvis's own TTS audio   -> must NEVER trigger the follow-up (echo guard)

Config knob: ``followup_window_seconds`` (default 15, 0 = disabled).

Tests exercise VoiceListener with real StateManager and EchoDetector
instances — only Whisper, audio, and the intent judge are mocked.
"""

import json
import time
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from jarvis.listening.state_manager import ListeningState
from jarvis.listening.intent_judge import IntentJudgment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_listener(**kwargs):
    """Create a VoiceListener with mocked heavy subsystems.

    Returns (listener, mock_tts) so tests can control TTS state.
    Uses real StateManager and EchoDetector — only Whisper, audio, and
    the intent judge are mocked.
    """
    mock_cfg = MagicMock()
    mock_cfg.whisper_model = "small"
    mock_cfg.whisper_device = "auto"
    mock_cfg.whisper_compute_type = "int8"
    mock_cfg.whisper_backend = "faster-whisper"
    mock_cfg.sample_rate = 16000
    mock_cfg.vad_enabled = False
    mock_cfg.vad_aggressiveness = 2
    mock_cfg.echo_tolerance = kwargs.get("echo_tolerance", 0.05)
    mock_cfg.echo_energy_threshold = 2.0
    mock_cfg.hot_window_seconds = kwargs.get("hot_window_seconds", 3.0)
    mock_cfg.followup_window_seconds = kwargs.get("followup_window_seconds", 15.0)
    mock_cfg.hot_window_enabled = kwargs.get("hot_window_enabled", True)
    mock_cfg.voice_collect_seconds = 2.0
    mock_cfg.voice_max_collect_seconds = 60.0
    mock_cfg.voice_device = None
    mock_cfg.voice_debug = False
    mock_cfg.voice_min_energy = 0.0045
    mock_cfg.tune_enabled = False
    mock_cfg.wake_word = kwargs.get("wake_word", "джарвіс")
    mock_cfg.wake_aliases = kwargs.get("wake_aliases", ["джарвіс"])
    mock_cfg.wake_fuzzy_ratio = 0.78
    mock_cfg.stop_commands = ["стоп", "тихо"]
    mock_cfg.tts_rate = 200
    mock_cfg.transcript_buffer_duration_sec = 120.0
    mock_cfg.intent_judge_model = "gemma4:e2b"
    mock_cfg.ollama_base_url = "http://127.0.0.1:11434"
    mock_cfg.intent_judge_timeout_sec = 3.0
    mock_db = MagicMock()
    mock_tts = MagicMock()
    mock_tts.enabled = True
    mock_tts.is_speaking.return_value = kwargs.get("tts_speaking", False)
    mock_dialogue_memory = MagicMock()

    with patch("jarvis.listening.listener.webrtcvad", None), \
         patch("jarvis.listening.listener.sd", None), \
         patch("jarvis.listening.listener.np", None), \
         patch("jarvis.listening.listener.create_intent_judge", return_value=None):
        from jarvis.listening.listener import VoiceListener
        listener = VoiceListener(mock_db, mock_cfg, mock_tts, mock_dialogue_memory)

    _created_listeners.append(listener)
    return listener, mock_tts


def _make_judgment(directed=True, query="", stop=False, confidence="high", reasoning="test"):
    """Build an IntentJudgment."""
    return IntentJudgment(
        directed=directed, query=query, stop=stop,
        confidence=confidence, reasoning=reasoning,
    )


def _install_intent_judge(listener, judgment=None):
    """Replace the listener's intent judge with a mock.

    ``judgment=None`` means the judge exists but returns no verdict
    (simulating an unavailable judge) — the hot-window fallback then
    decides.
    """
    mock_judge = MagicMock()
    mock_judge.available = True
    mock_judge.judge.return_value = judgment
    listener._intent_judge = mock_judge
    return mock_judge


def _activate_followup_window(listener):
    """Simulate a completed reply: schedule the follow-up window and wait."""
    listener.activate_hot_window()
    deadline = time.time() + 1.0
    while time.time() < deadline:
        if listener.state_manager.is_hot_window_active():
            return True
        time.sleep(0.01)
    return False


# Listeners created by tests in this module; the autouse fixture below stops
# their state managers so no expiry timer leaks prints into a later test.
_created_listeners: list = []


@pytest.fixture(autouse=True)
def _stop_pending_state_managers():
    yield
    for listener in _created_listeners:
        try:
            listener.state_manager.stop()
        except Exception:
            pass
    _created_listeners.clear()


def _read_captured_until(capsys, needle: str, timeout: float = 2.0) -> str:
    """Accumulate captured stdout until *needle* appears (or timeout).

    The activation/expiry messages are printed from a timer thread that
    sets the listening state *before* printing, so a single readouterr()
    can race ahead of the print. Polling until the needle shows up keeps
    the assertion deterministic.
    """
    out_all = ""
    deadline = time.time() + timeout
    while time.time() < deadline:
        out_all += capsys.readouterr().out
        if needle in out_all:
            return out_all
        time.sleep(0.02)
    return out_all


def _wait_for_state(listener, state, timeout=2.0):
    """Wait until the state manager reaches *state*."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if listener.state_manager.get_state() == state:
            return True
        time.sleep(0.02)
    return False


def _pending_query(listener) -> str:
    """Return the accepted (pending) query text, empty when rejected."""
    return listener.state_manager.get_pending_query()


# ---------------------------------------------------------------------------
# Config: followup_window_seconds
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFollowupWindowConfig:

    def test_default_config_has_15_second_followup_window(self):
        """The shipped default follow-up window is 15 seconds."""
        from jarvis.config import get_default_config
        assert get_default_config()["followup_window_seconds"] == 15.0

    def test_settings_field_exists_with_default_15(self, tmp_path, monkeypatch):
        """Settings carries the followup_window_seconds field (default 15)."""
        from jarvis.config import load_settings
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text("{}", encoding="utf-8")
        monkeypatch.setenv("JARVIS_CONFIG_PATH", str(cfg_file))
        settings = load_settings()
        assert settings.followup_window_seconds == 15.0

    def test_load_settings_parses_zero_as_disabled(self, tmp_path, monkeypatch):
        """followup_window_seconds = 0 in config.json disables the window."""
        from jarvis.config import load_settings
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"followup_window_seconds": 0}), encoding="utf-8")
        monkeypatch.setenv("JARVIS_CONFIG_PATH", str(cfg_file))
        settings = load_settings()
        assert settings.followup_window_seconds == 0.0

    def test_negative_value_clamped_to_zero(self, tmp_path, monkeypatch):
        """Negative followup_window_seconds values are clamped to 0 (off)."""
        from jarvis.config import load_settings
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"followup_window_seconds": -5}), encoding="utf-8")
        monkeypatch.setenv("JARVIS_CONFIG_PATH", str(cfg_file))
        settings = load_settings()
        assert settings.followup_window_seconds == 0.0


# ---------------------------------------------------------------------------
# Listener wiring: the follow-up window drives the hot-window duration
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFollowupWindowWiring:

    def test_listener_uses_followup_window_seconds(self):
        """The listener sizes its follow-up window from the config field."""
        listener, _ = _create_listener(followup_window_seconds=15.0)
        assert listener.state_manager.hot_window_seconds == 15.0

    def test_listener_falls_back_to_hot_window_seconds(self):
        """Configs without the new field keep the legacy hot window length."""
        cfg = SimpleNamespace(
            sample_rate=16000,
            vad_enabled=False,
            echo_tolerance=0.3,
            echo_energy_threshold=2.0,
            hot_window_seconds=3.0,
            voice_collect_seconds=2.0,
            voice_max_collect_seconds=60.0,
            tune_enabled=False,
        )
        with patch("jarvis.listening.listener.webrtcvad", None), \
             patch("jarvis.listening.listener.sd", None), \
             patch("jarvis.listening.listener.np", None), \
             patch("jarvis.listening.listener.create_intent_judge", return_value=None):
            from jarvis.listening.listener import VoiceListener
            listener = VoiceListener(MagicMock(), cfg, MagicMock(), MagicMock())
        assert listener.state_manager.hot_window_seconds == 3.0


# ---------------------------------------------------------------------------
# Activation gating: 0 = disabled
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFollowupWindowActivation:

    def test_zero_followup_window_stays_in_wake_word(self):
        """followup_window_seconds = 0: after a reply, no follow-up opens."""
        listener, _ = _create_listener(followup_window_seconds=0.0)
        listener.activate_hot_window()
        time.sleep(0.15)
        assert listener.state_manager.get_state() == ListeningState.WAKE_WORD
        assert not listener.state_manager.is_hot_window_active()

    def test_hot_window_enabled_false_disables_followup(self):
        """hot_window_enabled = False keeps the follow-up off regardless."""
        listener, _ = _create_listener(hot_window_enabled=False)
        listener.activate_hot_window()
        time.sleep(0.15)
        assert listener.state_manager.get_state() == ListeningState.WAKE_WORD
        assert not listener.state_manager.is_hot_window_active()

    def test_activate_hot_window_opens_15s_followup(self):
        """A completed reply opens a 15-second follow-up listening window."""
        listener, _ = _create_listener(followup_window_seconds=15.0)
        assert _activate_followup_window(listener) is True
        assert listener.state_manager.hot_window_seconds == 15.0
        assert listener.state_manager.get_state() == ListeningState.HOT_WINDOW


# ---------------------------------------------------------------------------
# Behaviour inside the window
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFollowupWindowBehaviour:

    def test_phrase_without_wake_word_accepted(self):
        """A phrase with no wake word is processed as a normal query."""
        listener, _ = _create_listener()
        assert _activate_followup_window(listener) is True
        _install_intent_judge(listener, _make_judgment(query="яка погода у Києві"))

        now = time.time()
        listener._process_transcript("яка погода у Києві", 0.01, now, now + 0.5)

        assert "яка погода" in _pending_query(listener)

    def test_phrase_with_wake_word_accepted(self):
        """A phrase that includes the wake word also works inside the window."""
        listener, _ = _create_listener()
        assert _activate_followup_window(listener) is True
        _install_intent_judge(listener, _make_judgment(query="який день сьогодні"))

        now = time.time()
        listener._process_transcript("джарвіс, який день сьогодні", 0.01, now, now + 0.5)

        query = _pending_query(listener)
        assert "який день" in query
        assert "джарвіс" not in query

    def test_wake_word_phrase_works_without_intent_judge(self):
        """With no judge available, the wake-word path still handles phrases."""
        listener, _ = _create_listener()
        assert _activate_followup_window(listener) is True
        listener._intent_judge = None

        now = time.time()
        listener._process_transcript("джарвіс скільки часу", 0.01, now, now + 0.5)

        query = _pending_query(listener)
        assert "скільки часу" in query
        assert "джарвіс" not in query

    def test_non_echo_phrase_accepted_via_fallback(self):
        """When the judge is unavailable, non-echo speech is still accepted."""
        listener, _ = _create_listener()
        assert _activate_followup_window(listener) is True
        _install_intent_judge(listener, None)

        now = time.time()
        listener._process_transcript("а що скажеш про завтра", 0.01, now, now + 0.5)

        assert "завтра" in _pending_query(listener)

    def test_phrase_after_window_expiry_requires_wake_word(self):
        """After the window expires, only the wake word re-engages Jarvis."""
        listener, _ = _create_listener()
        assert _activate_followup_window(listener) is True
        listener.state_manager.expire_hot_window()
        time.sleep(0.05)
        judge = _install_intent_judge(listener, _make_judgment(query="яка погода"))

        now = time.time()
        listener._process_transcript("яка погода", 0.01, now, now + 0.5)

        assert _pending_query(listener) == ""
        judge.judge.assert_not_called()

    def test_silence_timeout_returns_to_wake_word_state(self):
        """Silence past the window duration returns to wake word mode."""
        listener, _ = _create_listener(followup_window_seconds=0.3)
        assert _activate_followup_window(listener) is True

        assert _wait_for_state(listener, ListeningState.WAKE_WORD, timeout=1.5) is True


# ---------------------------------------------------------------------------
# Echo guard: Jarvis's own TTS must not trigger the follow-up
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFollowupWindowEchoGuard:

    def test_tts_echo_rejected_in_followup_window(self):
        """Echo of the reply inside the window is rejected, judge untouched."""
        listener, mock_tts = _create_listener()
        mock_tts.is_speaking.return_value = False
        listener.echo_detector.track_tts_start("Також я знайшов прогноз погоди на тиждень", 0.004)
        assert _activate_followup_window(listener) is True
        judge = _install_intent_judge(listener, _make_judgment(query="прогноз"))

        now = time.time()
        listener._process_transcript("також я знайшов прогноз погоди на тиждень", 0.004, now, now + 0.5)

        assert _pending_query(listener) == ""
        judge.judge.assert_not_called()

    def test_echo_does_not_extend_followup_window(self):
        """Rejected echo neither collects a query nor keeps the window alive."""
        listener, mock_tts = _create_listener(followup_window_seconds=0.4)
        mock_tts.is_speaking.return_value = False
        listener.echo_detector.track_tts_start("Ось що я знайшов у мережі сьогодні", 0.004)
        assert _activate_followup_window(listener) is True

        now = time.time()
        listener._process_transcript("ось що я знайшов у мережі сьогодні", 0.004, now, now + 0.5)
        assert _pending_query(listener) == ""

        # The window must still expire on its original schedule.
        assert _wait_for_state(listener, ListeningState.WAKE_WORD, timeout=2.0) is True

    def test_echo_during_tts_does_not_activate_followup(self):
        """Echo captured while TTS plays is dropped and opens no window."""
        listener, mock_tts = _create_listener()
        mock_tts.is_speaking.return_value = True
        listener.echo_detector.track_tts_start("Дозвольте я підкажу відповідь на це питання", 0.004)

        now = time.time()
        listener._process_transcript(
            "дозвольте я підкажу відповідь на це питання", 0.004, now, now + 0.5
        )

        assert _pending_query(listener) == ""
        assert not listener.state_manager.is_hot_window_active()
        assert listener.state_manager.get_state() == ListeningState.WAKE_WORD

    def test_similar_but_different_phrase_not_rejected_as_echo(self):
        """A real follow-up that merely mentions similar words is accepted."""
        listener, mock_tts = _create_listener()
        mock_tts.is_speaking.return_value = False
        listener.echo_detector.track_tts_start("Я знайшов кілька варіантів для тебе", 0.004)
        assert _activate_followup_window(listener) is True
        _install_intent_judge(listener, _make_judgment(query="розкажи докладніше про перший варіант"))

        now = time.time()
        listener._process_transcript(
            "розкажи докладніше про перший варіант", 0.01, now, now + 0.5
        )

        assert "варіант" in _pending_query(listener)


# ---------------------------------------------------------------------------
# User-facing output (Ukrainian)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFollowupWindowMessages:

    def test_activation_and_expiry_messages_in_ukrainian(self, capsys):
        """Window open/close messages are shown in Ukrainian."""
        listener, _ = _create_listener(followup_window_seconds=15.0)
        assert _activate_followup_window(listener) is True
        out = _read_captured_until(capsys, "Слухаю продовження (15 с)")
        assert "Слухаю продовження (15 с)" in out

        listener.state_manager.expire_hot_window()
        out = _read_captured_until(capsys, "Повертаюсь до режиму слова-активатора")
        assert "Повертаюсь до режиму слова-активатора" in out
