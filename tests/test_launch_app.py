"""Unit tests for the launchApp tool."""

import types
import pytest

from jarvis.tools.builtin import launch_app as la
from jarvis.tools.builtin.launch_app import LaunchAppTool, _resolve_target
from jarvis.tools.base import ToolContext


CATALOGUE = [
    {
        "name": "YouTube",
        "aliases": ["ютуб", "youtube"],
        "command": "https://www.youtube.com/results?search_query={query}",
        "needs_query": True,
    },
    {"name": "Steam", "aliases": ["стім", "steam"], "command": "steam://open/main"},
]


def _ctx(cfg):
    return ToolContext(
        db=None,
        cfg=cfg,
        system_prompt="",
        original_prompt="",
        redacted_text="",
        max_retries=0,
        user_print=lambda *_: None,
    )


def _cfg(targets=CATALOGUE):
    return types.SimpleNamespace(launch_targets=targets)


@pytest.mark.unit
@pytest.mark.parametrize("spoken,expected", [
    ("ютуб", "YouTube"),
    ("youtube", "YouTube"),
    ("стім", "Steam"),
    ("steam", "Steam"),
    ("щось невідоме", None),
])
def test_resolver_matches_uk_and_latin(spoken, expected):
    entry = _resolve_target(spoken, CATALOGUE)
    assert (entry.get("name") if entry else None) == expected


@pytest.mark.unit
def test_run_opens_target_and_reports(monkeypatch):
    opened = {}
    monkeypatch.setattr(la, "_open", lambda cmd: opened.setdefault("cmd", cmd))
    res = LaunchAppTool().run({"target": "стім"}, _ctx(_cfg()))
    assert res.success is True
    assert opened["cmd"] == "steam://open/main"
    assert "Steam" in (res.reply_text or "")


@pytest.mark.unit
def test_run_substitutes_url_encoded_query(monkeypatch):
    opened = {}
    monkeypatch.setattr(la, "_open", lambda cmd: opened.setdefault("cmd", cmd))
    res = LaunchAppTool().run({"target": "ютуб", "query": "lofi hip hop"}, _ctx(_cfg()))
    assert res.success is True
    # Spaces URL-encoded, confined to the query string.
    assert opened["cmd"] == "https://www.youtube.com/results?search_query=lofi%20hip%20hop"


@pytest.mark.unit
def test_unknown_target_lists_known(monkeypatch):
    monkeypatch.setattr(la, "_open", lambda cmd: (_ for _ in ()).throw(AssertionError("must not open")))
    res = LaunchAppTool().run({"target": "фотошоп"}, _ctx(_cfg()))
    assert res.success is False
    assert "YouTube" in (res.reply_text or "") and "Steam" in (res.reply_text or "")


@pytest.mark.unit
def test_empty_catalogue_guides_user():
    res = LaunchAppTool().run({"target": "ютуб"}, _ctx(_cfg(targets=[])))
    assert res.success is False
    assert "launch_targets" in (res.reply_text or "")


@pytest.mark.unit
def test_missing_target_arg():
    res = LaunchAppTool().run({}, _ctx(_cfg()))
    assert res.success is False
