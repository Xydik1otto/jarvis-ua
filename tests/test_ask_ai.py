"""Unit tests for the askAi tool (delegate a question to another local model)."""

import types
import pytest

from jarvis.tools.builtin import ask_ai as aa
from jarvis.tools.builtin.ask_ai import AskAiTool, _resolve_model
from jarvis.tools.base import ToolContext


CATALOGUE = [
    {
        "name": "DeepSeek Coder",
        "aliases": ["діпсік", "дипсик", "deepseek", "deepseek coder"],
        "model": "deepseek-coder-v2",
    },
    {
        "name": "Qwen Coder",
        "aliases": ["квін кодер", "qwen coder", "qwen2.5-coder"],
        "model": "qwen2.5-coder:7b",
    },
    {
        "name": "Qwen",
        "aliases": ["квін", "qwen"],
        "model": "qwen2.5:7b-instruct",
    },
]


class FakeBackend:
    """Records chat() calls; returns a canned Ollama-shaped response."""

    def __init__(self, content="RAW ANSWER TEXT", fail=False):
        self.calls = []
        self.content = content
        self.fail = fail

    def chat(self, model, messages, timeout_sec=30.0, extra_options=None, **kwargs):
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "timeout_sec": timeout_sec,
                "extra_options": extra_options,
            }
        )
        if self.fail:
            return None
        return {"message": {"content": self.content}}


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


def _cfg(targets=CATALOGUE, enabled=True):
    return types.SimpleNamespace(ask_ai_targets=targets, ask_ai_enabled=enabled)


@pytest.mark.unit
@pytest.mark.parametrize("spoken,expected", [
    ("діпсік", "DeepSeek Coder"),
    ("deepseek", "DeepSeek Coder"),
    ("qwen coder", "Qwen Coder"),
    ("квін", "Qwen"),
    ("щось невідоме", None),
])
def test_resolver_matches_aliases_and_names(spoken, expected):
    entry = _resolve_model(spoken, CATALOGUE)
    assert (entry.get("name") if entry else None) == expected


@pytest.mark.unit
def test_run_returns_raw_answer(monkeypatch):
    fake = FakeBackend(content="def foo(): pass")
    monkeypatch.setattr(aa, "get_llm_backend", lambda cfg: fake)
    res = AskAiTool().run({"model": "діпсік", "prompt": "напиши foo"}, _ctx(_cfg()))
    assert res.success is True
    # Raw delegated answer, no LLM processing on the tool side.
    assert res.reply_text == "def foo(): pass"


@pytest.mark.unit
def test_run_uses_catalogue_model_and_keep_alive_zero(monkeypatch):
    fake = FakeBackend()
    monkeypatch.setattr(aa, "get_llm_backend", lambda cfg: fake)
    res = AskAiTool().run({"model": "квін кодер", "prompt": "fix this code"}, _ctx(_cfg()))
    assert res.success is True
    call = fake.calls[0]
    # The catalogue's model string is what goes on the wire, not the display name.
    assert call["model"] == "qwen2.5-coder:7b"
    # Unload the second model from VRAM right after the call.
    assert call["extra_options"]["keep_alive"] == 0


@pytest.mark.unit
def test_unknown_model_rejected(monkeypatch):
    fake = FakeBackend()
    monkeypatch.setattr(aa, "get_llm_backend", lambda cfg: fake)
    res = AskAiTool().run({"model": "гпт-4", "prompt": "привіт"}, _ctx(_cfg()))
    assert res.success is False
    assert "DeepSeek Coder" in (res.reply_text or "")
    assert fake.calls == []


@pytest.mark.unit
def test_timeout_returns_failure(monkeypatch):
    fake = FakeBackend(fail=True)
    monkeypatch.setattr(aa, "get_llm_backend", lambda cfg: fake)
    res = AskAiTool().run({"model": "qwen", "prompt": "питання"}, _ctx(_cfg()))
    assert res.success is False
    assert res.reply_text


@pytest.mark.unit
def test_disabled_flag_blocks_call(monkeypatch):
    fake = FakeBackend()
    monkeypatch.setattr(aa, "get_llm_backend", lambda cfg: fake)
    res = AskAiTool().run({"model": "qwen", "prompt": "питання"}, _ctx(_cfg(enabled=False)))
    assert res.success is False
    assert fake.calls == []


@pytest.mark.unit
def test_missing_or_empty_args(monkeypatch):
    fake = FakeBackend()
    monkeypatch.setattr(aa, "get_llm_backend", lambda cfg: fake)
    for args in ({}, {"model": "qwen"}, {"model": "qwen", "prompt": ""}, {"model": "", "prompt": "x"}):
        res = AskAiTool().run(args, _ctx(_cfg()))
        assert res.success is False
    assert fake.calls == []


@pytest.mark.unit
def test_empty_catalogue_guides_user(monkeypatch):
    fake = FakeBackend()
    monkeypatch.setattr(aa, "get_llm_backend", lambda cfg: fake)
    res = AskAiTool().run({"model": "qwen", "prompt": "питання"}, _ctx(_cfg(targets=[])))
    assert res.success is False
    assert "ask_ai_targets" in (res.reply_text or "")


@pytest.mark.unit
def test_config_defaults():
    from jarvis.config import get_default_config

    defaults = get_default_config()
    assert defaults["ask_ai_enabled"] is True
    targets = defaults["ask_ai_targets"]
    models = {t["model"] for t in targets}
    assert models == {"deepseek-coder-v2", "qwen2.5-coder:7b", "qwen2.5:7b-instruct"}
    for t in targets:
        assert set(t.keys()) == {"name", "aliases", "model"}


@pytest.mark.unit
def test_registry_wiring():
    from jarvis.tools.registry import BUILTIN_TOOLS

    tool = BUILTIN_TOOLS.get("askAi")
    assert isinstance(tool, AskAiTool)
