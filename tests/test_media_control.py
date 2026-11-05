"""Unit tests for the mediaControl builtin tool."""

import types

import pytest

from jarvis.tools.base import ToolContext
from jarvis.tools.builtin import media_control as mc
from jarvis.tools.builtin.media_control import MediaControlTool


class FakeKey:
    media_play_pause = "<play_pause>"
    media_next = "<next>"
    media_previous = "<previous>"
    media_volume_up = "<vol_up>"
    media_volume_down = "<vol_down>"
    media_volume_mute = "<mute>"


class FakeController:
    def __init__(self):
        self.taps = []

    def tap(self, key):
        self.taps.append(key)


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


@pytest.fixture()
def fake_controller(monkeypatch):
    ctrl = FakeController()
    monkeypatch.setattr(mc, "_get_controller", lambda: ctrl)
    monkeypatch.setattr(mc, "_KEYS", FakeKey)
    # Headless CI (no X display) fails the pynput import, leaving the module
    # flag False; the tool checks it before reaching the patched controller.
    monkeypatch.setattr(mc, "_PYNPUT_AVAILABLE", True)
    return ctrl


@pytest.mark.unit
@pytest.mark.parametrize("action,expected_key", [
    ("play_pause", "<play_pause>"),
    ("next", "<next>"),
    ("previous", "<previous>"),
    ("mute", "<mute>"),
])
def test_action_presses_correct_key(fake_controller, action, expected_key):
    res = MediaControlTool().run({"action": action}, _ctx())
    assert res.success is True
    assert fake_controller.taps == [expected_key]


@pytest.mark.unit
def test_volume_up_default_steps(fake_controller):
    res = MediaControlTool().run({"action": "volume_up"}, _ctx())
    assert res.success is True
    assert fake_controller.taps == ["<vol_up>"] * 5


@pytest.mark.unit
def test_volume_down_custom_steps(fake_controller):
    res = MediaControlTool().run({"action": "volume_down", "steps": 10}, _ctx())
    assert res.success is True
    assert fake_controller.taps == ["<vol_down>"] * 10


@pytest.mark.unit
def test_steps_ignored_for_playback_actions(fake_controller):
    res = MediaControlTool().run({"action": "next", "steps": 9}, _ctx())
    assert res.success is True
    assert fake_controller.taps == ["<next>"]


@pytest.mark.unit
def test_unknown_action_rejected(fake_controller):
    res = MediaControlTool().run({"action": "rewind"}, _ctx())
    assert res.success is False
    assert fake_controller.taps == []


@pytest.mark.unit
def test_missing_action_rejected(fake_controller):
    res = MediaControlTool().run({}, _ctx())
    assert res.success is False


@pytest.mark.unit
def test_press_failure_reports_honest_failure(fake_controller, monkeypatch):
    def boom(key):
        raise RuntimeError("no media session")

    monkeypatch.setattr(fake_controller, "tap", boom)
    res = MediaControlTool().run({"action": "play_pause"}, _ctx())
    assert res.success is False
    assert (res.reply_text or "") != ""
