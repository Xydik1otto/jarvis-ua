"""Unit tests for the timerTool builtin tool and its TimerRegistry."""

import time
import types

import pytest

from jarvis.tools.base import ToolContext
from jarvis.tools.builtin import timer_tool as tt
from jarvis.tools.builtin.timer_tool import TimerRegistry, TimerTool, parse_duration


def _ctx():
    return ToolContext(
        db=None,
        cfg=types.SimpleNamespace(),
        system_prompt="",
        original_prompt="",
        redacted_text="",
        max_retries=0,
        user_print=lambda *_: None,
    )


def _fresh_registry(clock=time.monotonic):
    return TimerRegistry(clock=clock)


# --- Duration parsing -------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("phrase,expected", [
    ("10 хвилин", 600),
    ("10 хвилини", 600),
    ("5 хвилин", 300),
    ("2 години", 7200),
    ("90 секунд", 90),
    ("1 секунда", 1),
    ("пів години", 1800),
    ("10m", 600),
    ("2h", 7200),
    ("45s", 45),
    ("1h30m", 5400),
    ("1 година 30 хвилин", 5400),
])
def test_parse_duration_uk_and_en_forms(phrase, expected):
    assert parse_duration(phrase) == expected


@pytest.mark.unit
@pytest.mark.parametrize("phrase", ["", "  ", "щось невідоме", "5 років"])
def test_parse_duration_rejects_unknown(phrase):
    assert parse_duration(phrase) is None


# --- Registry semantics -----------------------------------------------------


@pytest.mark.unit
def test_create_and_list():
    reg = _fresh_registry()
    tid = reg.create("pasta", 60)
    items = reg.list()
    assert len(items) == 1
    assert items[0]["id"] == tid
    assert items[0]["label"] == "pasta"
    assert items[0]["duration_seconds"] == 60
    assert 0 < items[0]["remaining_seconds"] <= 60


@pytest.mark.unit
def test_cancel_existing_and_missing():
    reg = _fresh_registry()
    tid = reg.create("pasta", 60)
    assert reg.cancel(tid) is True
    assert reg.cancel(tid) is False  # already gone
    assert reg.list() == []


@pytest.mark.unit
def test_cancel_all_returns_count():
    reg = _fresh_registry()
    reg.create("a", 60)
    reg.create("b", 120)
    assert reg.cancel_all() == 2
    assert reg.cancel_all() == 0
    assert reg.list() == []


@pytest.mark.unit
def test_concurrent_timers_and_elapsed_firing():
    reg = _fresh_registry()
    reg.create("a", 10)
    reg.create("b", 100)
    assert len(reg.list()) == 2
    # Advance past the first deadline only (fake clock).
    reg._now = lambda: reg._clock() + 15
    fired = reg.poll_once()
    assert [label for label, _tid in fired] == ["a"]
    assert len(reg.list()) == 1
    assert reg.list()[0]["label"] == "b"


@pytest.mark.unit
def test_concurrency_cap_16():
    reg = _fresh_registry()
    for i in range(16):
        reg.create(f"t{i}", 60)
    with pytest.raises(ValueError):
        reg.create("t17", 60)


@pytest.mark.unit
def test_max_duration_24h():
    reg = _fresh_registry()
    with pytest.raises(ValueError):
        reg.create("too long", 24 * 3600 + 1)
    # Exactly 24h is fine.
    tid = reg.create("max", 24 * 3600)
    assert tid


# --- Poller / speak callback ------------------------------------------------


@pytest.mark.unit
def test_poller_speaks_on_elapse():
    reg = _fresh_registry()
    spoken = []
    reg.create("pasta", 0.05)
    reg.start_polling(lambda text: spoken.append(text), poll_sec=0.01)
    deadline = time.monotonic() + 2.0
    while not spoken and time.monotonic() < deadline:
        time.sleep(0.01)
    assert spoken, "speak callback never fired"
    assert "pasta" in spoken[0]
    assert reg.list() == []


@pytest.mark.unit
def test_elapsed_announcement_goes_through_callback_not_tool():
    """The tool itself must not be invoked again: firing is the poller's job."""
    reg = _fresh_registry()
    calls = []

    def speak(text):
        calls.append(text)

    reg.create("tea", 0.05)
    reg.start_polling(speak, poll_sec=0.01)
    deadline = time.monotonic() + 2.0
    while not calls and time.monotonic() < deadline:
        time.sleep(0.01)
    # Exactly one callback, and the registry is empty afterwards.
    assert len(calls) == 1
    assert "Час вийшов" in calls[0]


# --- Tool behaviour ---------------------------------------------------------


@pytest.mark.unit
def test_tool_set_accepts_duration_seconds():
    tool = TimerTool()
    res = tool.run({"action": "set", "duration_seconds": 300, "label": "pasta"}, _ctx())
    assert res.success is True
    assert "pasta" in (res.reply_text or "")
    assert "300" in (res.reply_text or "")
    tt.REGISTRY.cancel_all()


@pytest.mark.unit
def test_tool_set_accepts_free_form_phrase():
    tool = TimerTool()
    res = tool.run({"action": "set", "duration": "10 хвилин", "label": "чай"}, _ctx())
    assert res.success is True
    assert "600" in (res.reply_text or "")
    tt.REGISTRY.cancel_all()


@pytest.mark.unit
def test_tool_set_without_duration_fails():
    tool = TimerTool()
    res = tool.run({"action": "set", "label": "pasta"}, _ctx())
    assert res.success is False
    tt.REGISTRY.cancel_all()


@pytest.mark.unit
def test_tool_list_shows_running_timers():
    tt.REGISTRY.cancel_all()
    tt.REGISTRY.create("pasta", 600)
    tool = TimerTool()
    res = tool.run({"action": "list"}, _ctx())
    assert res.success is True
    assert "pasta" in (res.reply_text or "")
    tt.REGISTRY.cancel_all()


@pytest.mark.unit
def test_tool_cancel_by_id_and_all():
    tt.REGISTRY.cancel_all()
    tid = tt.REGISTRY.create("pasta", 600)
    tool = TimerTool()
    res = tool.run({"action": "cancel", "timer_id": tid}, _ctx())
    assert res.success is True
    res_all = tool.run({"action": "cancel", "timer_id": "all"}, _ctx())
    assert res_all.success is True


@pytest.mark.unit
def test_tool_cancel_nonexistent_id_fails():
    tt.REGISTRY.cancel_all()
    tool = TimerTool()
    res = tool.run({"action": "cancel", "timer_id": "nope"}, _ctx())
    assert res.success is False


@pytest.mark.unit
def test_tool_unknown_action_rejected():
    tool = TimerTool()
    res = tool.run({"action": "restart"}, _ctx())
    assert res.success is False


@pytest.mark.unit
def test_tool_set_over_cap_fails():
    tt.REGISTRY.cancel_all()
    for i in range(16):
        tt.REGISTRY.create(f"t{i}", 600)
    tool = TimerTool()
    res = tool.run({"action": "set", "duration_seconds": 60}, _ctx())
    assert res.success is False
    tt.REGISTRY.cancel_all()
