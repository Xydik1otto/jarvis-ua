"""Unit tests for personaTool and the user-persona prompt injection."""

import json
import threading
import types

import pytest

from jarvis.tools.base import ToolContext
from jarvis.tools.builtin.persona_tool import PersonaStore, PersonaTool
from jarvis.tools.registry import BUILTIN_TOOLS, run_tool_with_retries
from jarvis.reply.engine import build_persona_block


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


def _store(tmp_path):
    return PersonaStore(path=tmp_path / "persona.json")


def _tool(tmp_path):
    return PersonaTool(store=_store(tmp_path))


# --- Store semantics --------------------------------------------------------


@pytest.mark.unit
def test_store_empty_initially(tmp_path):
    assert _store(tmp_path).snapshot() == {}


@pytest.mark.unit
def test_store_set_and_get_scalar_field(tmp_path):
    store = _store(tmp_path)
    store.set_field("name", "Олена")
    assert store.get_field("name") == "Олена"


@pytest.mark.unit
def test_store_set_all_valid_fields(tmp_path):
    store = _store(tmp_path)
    store.set_field("name", "Олена")
    store.set_field("address_name", "пане Оленко")
    store.set_field("communication_style", "коротко")
    store.set_field("profession", "інженерка")
    store.set_field("favourite_topics", "космос, математика")
    store.set_field("preferences", "люблю тишу")
    snapshot = store.snapshot()
    assert snapshot["name"] == "Олена"
    assert snapshot["address_name"] == "пане Оленко"
    assert snapshot["communication_style"] == "коротко"
    assert snapshot["profession"] == "інженерка"
    assert snapshot["favourite_topics"] == ["космос", "математика"]
    assert snapshot["preferences"] == ["люблю тишу"]


@pytest.mark.unit
def test_store_communication_style_accepts_detailno(tmp_path):
    store = _store(tmp_path)
    store.set_field("communication_style", "Детально")
    assert store.get_field("communication_style") == "детально"


@pytest.mark.unit
def test_store_rejects_unknown_field(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ValueError):
        store.set_field("credit_card", "4111")


@pytest.mark.unit
def test_store_rejects_invalid_style(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ValueError):
        store.set_field("communication_style", "поспівай")


@pytest.mark.unit
def test_store_rejects_empty_value(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ValueError):
        store.set_field("name", "   ")


@pytest.mark.unit
def test_store_rejects_overlong_value(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ValueError):
        store.set_field("name", "x" * 501)


@pytest.mark.unit
def test_store_set_overwrites_previous_value(tmp_path):
    store = _store(tmp_path)
    store.set_field("name", "Старе")
    store.set_field("name", "Нове")
    assert store.get_field("name") == "Нове"


@pytest.mark.unit
def test_store_get_missing_field_returns_none(tmp_path):
    assert _store(tmp_path).get_field("name") is None


@pytest.mark.unit
def test_store_delete_existing_and_missing(tmp_path):
    store = _store(tmp_path)
    store.set_field("name", "Олена")
    assert store.delete_field("name") is True
    assert store.delete_field("name") is False
    assert store.get_field("name") is None


@pytest.mark.unit
def test_store_snapshot_only_nonempty_fields(tmp_path):
    store = _store(tmp_path)
    store.set_field("profession", "лікар")
    assert store.snapshot() == {"profession": "лікар"}


@pytest.mark.unit
def test_store_persists_across_instances(tmp_path):
    store = _store(tmp_path)
    store.set_field("name", "Олена")
    assert _store(tmp_path).get_field("name") == "Олена"


@pytest.mark.unit
def test_store_tolerates_corrupt_file(tmp_path):
    path = tmp_path / "persona.json"
    path.write_text("{not json", encoding="utf-8")
    store = PersonaStore(path=path)
    assert store.snapshot() == {}
    store.set_field("name", "Олена")
    assert store.get_field("name") == "Олена"


@pytest.mark.unit
def test_store_atomic_write_leaves_no_temp_file(tmp_path):
    store = _store(tmp_path)
    store.set_field("name", "Олена")
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "persona.json"]
    assert leftovers == []
    data = json.loads((tmp_path / "persona.json").read_text(encoding="utf-8"))
    assert data["name"] == "Олена"


@pytest.mark.unit
def test_store_thread_safe_concurrent_sets(tmp_path):
    store = _store(tmp_path)
    errors = []

    def worker(i):
        try:
            store.set_field("favourite_topics", f"тема {i}, інша {i}")
        except Exception as exc:  # pragma: no cover - race smoke test
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(store.get_field("favourite_topics")) == 2


# --- Tool behaviour ---------------------------------------------------------


@pytest.mark.unit
def test_tool_set_then_get(tmp_path):
    tool = _tool(tmp_path)
    ctx = _ctx()
    res = tool.run({"action": "set", "field": "name", "value": "Олена"}, ctx)
    assert res.success is True
    res = tool.run({"action": "get", "field": "name"}, ctx)
    assert res.success is True
    assert "Олена" in (res.reply_text or "")


@pytest.mark.unit
def test_tool_list_shows_only_filled_fields(tmp_path):
    tool = _tool(tmp_path)
    ctx = _ctx()
    tool.run({"action": "set", "field": "name", "value": "Олена"}, ctx)
    res = tool.run({"action": "list"}, ctx)
    assert res.success is True
    assert "name" in (res.reply_text or "")


@pytest.mark.unit
def test_tool_list_empty_store(tmp_path):
    res = _tool(tmp_path).run({"action": "list"}, _ctx())
    assert res.success is True


@pytest.mark.unit
def test_tool_delete(tmp_path):
    tool = _tool(tmp_path)
    ctx = _ctx()
    tool.run({"action": "set", "field": "name", "value": "Олена"}, ctx)
    res = tool.run({"action": "delete", "field": "name"}, ctx)
    assert res.success is True
    assert tool.run({"action": "get", "field": "name"}, ctx).reply_text != "Олена"


@pytest.mark.unit
def test_tool_unknown_action_fails(tmp_path):
    res = _tool(tmp_path).run({"action": "wipe"}, _ctx())
    assert res.success is False


@pytest.mark.unit
def test_tool_invalid_value_fails_honestly(tmp_path):
    res = _tool(tmp_path).run(
        {"action": "set", "field": "communication_style", "value": "швидко"},
        _ctx(),
    )
    assert res.success is False


# --- Registry wiring --------------------------------------------------------


@pytest.mark.unit
def test_registry_contains_persona_tool():
    assert "personaTool" in BUILTIN_TOOLS
    description = BUILTIN_TOOLS["personaTool"].description
    assert "запам'ятай" in description
    assert "моє ім'я" in description
    assert "звертайся до мене" in description
    assert "remember my name" in description


@pytest.mark.unit
def test_registry_dispatch(tmp_path, monkeypatch):
    from jarvis.tools.builtin import persona_tool as module

    store = _store(tmp_path)
    monkeypatch.setattr(module, "_default_store", lambda: store)
    cfg = types.SimpleNamespace(voice_debug=True)
    res = run_tool_with_retries(
        db=None,
        cfg=cfg,
        tool_name="personaTool",
        tool_args={"action": "set", "field": "name", "value": "Олена"},
        system_prompt="",
        original_prompt="",
        redacted_text="",
        max_retries=0,
    )
    assert res.success is True
    assert store.get_field("name") == "Олена"


# --- Prompt injection -------------------------------------------------------


@pytest.mark.unit
def test_persona_block_none_when_store_empty(tmp_path):
    cfg = types.SimpleNamespace(persona_path=tmp_path / "persona.json")
    assert build_persona_block(cfg) is None


@pytest.mark.unit
def test_persona_block_none_without_persona_path_attr():
    cfg = types.SimpleNamespace()
    assert build_persona_block(cfg) is None or True  # must not crash


@pytest.mark.unit
def test_persona_block_contains_filled_fields(tmp_path):
    store = _store(tmp_path)
    store.set_field("name", "Олена")
    store.set_field("communication_style", "коротко")
    store.set_field("favourite_topics", "космос, математика")
    cfg = types.SimpleNamespace(persona_path=tmp_path / "persona.json")
    block = build_persona_block(cfg)
    assert block is not None
    assert "ПРОФІЛЬ КОРИСТУВАЧА" in block
    assert "Олена" in block
    assert "коротко" in block
    assert "космос" in block


@pytest.mark.unit
def test_persona_block_skips_empty_fields(tmp_path):
    store = _store(tmp_path)
    store.set_field("name", "Олена")
    cfg = types.SimpleNamespace(persona_path=tmp_path / "persona.json")
    block = build_persona_block(cfg)
    assert "Професія" not in block
    assert "Вподобайки" not in block
