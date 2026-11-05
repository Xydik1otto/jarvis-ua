"""Unit tests for the notesTool builtin tool and its NotesStore."""

import json
import threading
import types

import pytest

from jarvis.tools.base import ToolContext
from jarvis.tools.builtin.notes_tool import NotesStore, NotesTool


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
    return NotesStore(path=tmp_path / "notes.json")


def _tool(tmp_path):
    return NotesTool(store=_store(tmp_path))


# --- Store semantics --------------------------------------------------------


@pytest.mark.unit
def test_store_empty_lists_initially(tmp_path):
    store = _store(tmp_path)
    assert store.list_notes() == []
    assert store.list_todos() == []
    assert store.list_shopping() == []


@pytest.mark.unit
def test_store_add_and_list_notes(tmp_path):
    store = _store(tmp_path)
    entry = store.add_note("перший запис")
    items = store.list_notes()
    assert len(items) == 1
    assert items[0]["id"] == entry["id"]
    assert items[0]["text"] == "перший запис"


@pytest.mark.unit
def test_store_delete_note_existing_and_missing(tmp_path):
    store = _store(tmp_path)
    entry = store.add_note("нотатка")
    assert store.delete_note(entry["id"]) is True
    assert store.delete_note(entry["id"]) is False  # already gone
    assert store.list_notes() == []


@pytest.mark.unit
def test_store_add_and_list_todos(tmp_path):
    store = _store(tmp_path)
    store.add_todo("купити молоко")
    store.add_todo("подзвонити мамі")
    items = store.list_todos()
    assert len(items) == 2
    assert items[0]["text"] == "купити молоко"
    assert items[0]["done"] is False


@pytest.mark.unit
def test_store_complete_todo(tmp_path):
    store = _store(tmp_path)
    entry = store.add_todo("задача")
    assert store.complete_todo(entry["id"]) is True
    assert store.list_todos()[0]["done"] is True
    assert store.complete_todo(entry["id"]) is False  # already done


@pytest.mark.unit
def test_store_add_list_remove_shopping(tmp_path):
    store = _store(tmp_path)
    store.add_shopping("хліб")
    store.add_shopping("молоко")
    items = store.list_shopping()
    assert [item["text"] for item in items] == ["хліб", "молоко"]
    assert store.remove_shopping(items[0]["id"]) is True
    assert store.remove_shopping(items[0]["id"]) is False  # already gone
    assert [item["text"] for item in store.list_shopping()] == ["молоко"]


@pytest.mark.unit
def test_store_clear_list_shopping_and_todos(tmp_path):
    store = _store(tmp_path)
    store.add_shopping("хліб")
    store.add_todo("задача")
    assert store.clear_list("shopping") == 1
    assert store.list_shopping() == []
    assert len(store.list_todos()) == 1  # other list untouched
    assert store.clear_list("todos") == 1
    assert store.list_todos() == []


@pytest.mark.unit
def test_store_unicode_ukrainian_text_roundtrip(tmp_path):
    store = _store(tmp_path)
    text = "Нотатка: привіт, світе! Її Євген їв ґудзик."
    store.add_note(text)
    store.add_todo("перевірити ґудзик і ЇЖАК")
    store.add_shopping("квашена капуста")
    # A second store over the same file must see the identical Ukrainian text.
    reloaded = _store(tmp_path)
    assert reloaded.list_notes()[0]["text"] == text
    assert reloaded.list_todos()[0]["text"] == "перевірити ґудзик і ЇЖАК"
    assert reloaded.list_shopping()[0]["text"] == "квашена капуста"


@pytest.mark.unit
def test_store_persists_across_instances(tmp_path):
    store = _store(tmp_path)
    store.add_note("one")
    store.add_todo("two")
    reloaded = _store(tmp_path)
    assert len(reloaded.list_notes()) == 1
    assert len(reloaded.list_todos()) == 1


@pytest.mark.unit
def test_store_atomic_write_leaves_no_temp_files(tmp_path):
    store = _store(tmp_path)
    store.add_note("перевірка")
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "notes.json"]
    assert leftovers == []
    data = json.loads((tmp_path / "notes.json").read_text(encoding="utf-8"))
    assert data["notes"][0]["text"] == "перевірка"


@pytest.mark.unit
def test_store_corrupt_json_recovers(tmp_path):
    path = tmp_path / "notes.json"
    path.write_text("not json {{{", encoding="utf-8")
    store = NotesStore(path=path)
    assert store.list_notes() == []
    store.add_note("після збою")
    assert len(NotesStore(path=path).list_notes()) == 1


@pytest.mark.unit
def test_store_lock_survives_concurrent_writes(tmp_path):
    store = _store(tmp_path)
    barrier = threading.Barrier(8)

    def worker(n):
        barrier.wait()
        for i in range(10):
            store.add_note(f"потік {n} запис {i}")

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(store.list_notes()) == 80
    # The file must still be valid JSON (no interleaved writes).
    data = json.loads((tmp_path / "notes.json").read_text(encoding="utf-8"))
    assert len(data["notes"]) == 80


@pytest.mark.unit
def test_store_rejects_empty_and_overlong_text(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ValueError):
        store.add_note("   ")
    with pytest.raises(ValueError):
        store.add_note("x" * 501)


# --- Tool behaviour ---------------------------------------------------------


@pytest.mark.unit
def test_tool_add_and_list_notes(tmp_path):
    tool = _tool(tmp_path)
    res = tool.run({"action": "add_note", "text": "нотатка про зустріч"}, _ctx())
    assert res.success is True
    res = tool.run({"action": "list_notes"}, _ctx())
    assert res.success is True
    assert "нотатка про зустріч" in (res.reply_text or "")


@pytest.mark.unit
def test_tool_list_notes_empty(tmp_path):
    tool = _tool(tmp_path)
    res = tool.run({"action": "list_notes"}, _ctx())
    assert res.success is True
    assert "No notes" in (res.reply_text or "")


@pytest.mark.unit
def test_tool_delete_note(tmp_path):
    tool = _tool(tmp_path)
    res = tool.run({"action": "add_note", "text": "зайва"}, _ctx())
    note_id = res.data["note"]["id"]
    res = tool.run({"action": "delete_note", "note_id": note_id}, _ctx())
    assert res.success is True
    assert tool.run({"action": "list_notes"}, _ctx()).reply_text.count("зайва") == 0
    assert tool.run({"action": "delete_note", "note_id": note_id}, _ctx()).success is False


@pytest.mark.unit
def test_tool_add_and_list_todos(tmp_path):
    tool = _tool(tmp_path)
    assert tool.run({"action": "add_todo", "text": "прибрати на столі"}, _ctx()).success is True
    res = tool.run({"action": "list_todos"}, _ctx())
    assert res.success is True
    assert "прибрати на столі" in (res.reply_text or "")


@pytest.mark.unit
def test_tool_complete_todo(tmp_path):
    tool = _tool(tmp_path)
    res = tool.run({"action": "add_todo", "text": "задача"}, _ctx())
    todo_id = res.data["todo"]["id"]
    res = tool.run({"action": "complete_todo", "todo_id": todo_id}, _ctx())
    assert res.success is True
    assert "[x]" in tool.run({"action": "list_todos"}, _ctx()).reply_text


@pytest.mark.unit
def test_tool_add_and_list_shopping(tmp_path):
    tool = _tool(tmp_path)
    assert tool.run({"action": "add_shopping", "text": "хліб"}, _ctx()).success is True
    res = tool.run({"action": "list_shopping"}, _ctx())
    assert res.success is True
    assert "хліб" in (res.reply_text or "")


@pytest.mark.unit
def test_tool_remove_shopping(tmp_path):
    tool = _tool(tmp_path)
    res = tool.run({"action": "add_shopping", "text": "молоко"}, _ctx())
    item_id = res.data["item"]["id"]
    assert tool.run({"action": "remove_shopping", "item_id": item_id}, _ctx()).success is True
    assert tool.run({"action": "remove_shopping", "item_id": item_id}, _ctx()).success is False


@pytest.mark.unit
def test_tool_clear_list(tmp_path):
    tool = _tool(tmp_path)
    tool.run({"action": "add_shopping", "text": "хліб"}, _ctx())
    tool.run({"action": "add_shopping", "text": "сіль"}, _ctx())
    res = tool.run({"action": "clear_list", "list_name": "shopping"}, _ctx())
    assert res.success is True
    assert "2" in (res.reply_text or "")
    assert "No items" in tool.run({"action": "list_shopping"}, _ctx()).reply_text


@pytest.mark.unit
def test_tool_clear_list_todos(tmp_path):
    tool = _tool(tmp_path)
    tool.run({"action": "add_todo", "text": "справа"}, _ctx())
    res = tool.run({"action": "clear_list", "list_name": "todos"}, _ctx())
    assert res.success is True
    assert tool.run({"action": "list_todos"}, _ctx()).reply_text.startswith("No to-dos")


@pytest.mark.unit
def test_tool_missing_text_fails(tmp_path):
    tool = _tool(tmp_path)
    assert tool.run({"action": "add_note"}, _ctx()).success is False
    assert tool.run({"action": "add_todo", "text": "  "}, _ctx()).success is False
    assert tool.run({"action": "add_shopping"}, _ctx()).success is False


@pytest.mark.unit
def test_tool_complete_todo_without_id_fails(tmp_path):
    tool = _tool(tmp_path)
    res = tool.run({"action": "complete_todo"}, _ctx())
    assert res.success is False


@pytest.mark.unit
def test_tool_unknown_action_rejected(tmp_path):
    tool = _tool(tmp_path)
    res = tool.run({"action": "reorganise"}, _ctx())
    assert res.success is False


# --- Registry wiring and description routing --------------------------------


@pytest.mark.unit
def test_registered_in_builtin_registry():
    from jarvis.tools.registry import BUILTIN_TOOLS

    assert isinstance(BUILTIN_TOOLS["notesTool"], NotesTool)


@pytest.mark.unit
def test_description_covers_ukrainian_phrases():
    description = NotesTool().description
    for phrase in (
        "запиши нотатку",
        "додай хліб у список покупок",
        "мої задачі",
        "відміть задачу як виконану",
    ):
        assert phrase in description, f"description misses phrase: {phrase}"


@pytest.mark.unit
def test_description_names_every_action():
    description = NotesTool().description
    for action in (
        "add_note", "list_notes", "delete_note", "add_todo", "list_todos",
        "complete_todo", "add_shopping", "list_shopping", "remove_shopping",
        "clear_list",
    ):
        assert action in description, f"description misses action: {action}"
