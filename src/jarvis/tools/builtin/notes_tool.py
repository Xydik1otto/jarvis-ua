"""notesTool: voice notes, to-do tasks and a shopping list.

Backed by a single JSON file on disk (same mechanism as the dictation
history: ``~/.local/share/jarvis/notes.json``). Every mutation reloads
from disk first so external consumers (e.g. the desktop app) are picked
up, then writes atomically (temp file + ``os.replace``) under a
``threading.Lock`` so concurrent voice turns never corrupt the file.

User-facing console lines are Ukrainian; ``reply_text`` stays English
raw text that the chat model rephrases for the user, mirroring
``timer_tool``.
"""

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...debug import debug_log
from ..base import Tool, ToolContext
from ..types import ToolExecutionResult

# Caps bound memory use and nonsense model output.
MAX_ITEMS = 200
MAX_TEXT_LEN = 500

VALID_LIST_NAMES = ("shopping", "todos")


def _default_notes_path() -> Path:
    """Return the default storage path, mirroring the dictation history."""
    base = Path.home() / ".local" / "share" / "jarvis"
    base.mkdir(parents=True, exist_ok=True)
    return base / "notes.json"


class NotesStore:
    """Thread-safe, file-backed store of notes, to-dos and shopping items."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or _default_notes_path()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_note(self, text: str) -> Dict[str, Any]:
        return self.add("notes", text)

    def list_notes(self) -> List[Dict[str, Any]]:
        return self.snapshot("notes")

    def delete_note(self, note_id: str) -> bool:
        return self.remove("notes", note_id)

    def add_todo(self, text: str) -> Dict[str, Any]:
        return self.add("todos", text, extra={"done": False})

    def list_todos(self) -> List[Dict[str, Any]]:
        return self.snapshot("todos")

    def complete_todo(self, todo_id: str) -> bool:
        with self._lock:
            data = self._load()
            for entry in data["todos"]:
                if entry["id"] == todo_id:
                    if entry.get("done"):
                        return False  # already done, nothing to change
                    entry["done"] = True
                    self._save(data)
                    return True
            return False

    def add_shopping(self, text: str) -> Dict[str, Any]:
        return self.add("shopping", text)

    def list_shopping(self) -> List[Dict[str, Any]]:
        return self.snapshot("shopping")

    def remove_shopping(self, item_id: str) -> bool:
        return self.remove("shopping", item_id)

    def clear_list(self, list_name: str) -> int:
        """Delete every entry of one list; returns how many were removed."""
        if list_name not in VALID_LIST_NAMES:
            raise ValueError(f"unknown list name: {list_name}")
        with self._lock:
            data = self._load()
            count = len(data[list_name])
            data[list_name] = []
            self._save(data)
            return count

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def add(self, key: str, text: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Append an entry to one of the three lists and persist it."""
        text = (text or "").strip()
        if not text:
            raise ValueError("text must not be empty")
        if len(text) > MAX_TEXT_LEN:
            raise ValueError(f"text exceeds {MAX_TEXT_LEN} characters")
        entry: Dict[str, Any] = {"id": uuid.uuid4().hex[:8], "text": text}
        if extra:
            entry.update(extra)
        with self._lock:
            data = self._load()
            if len(data[key]) >= MAX_ITEMS:
                raise ValueError(f"{key} limit reached ({MAX_ITEMS} entries)")
            data[key].append(entry)
            self._save(data)
        debug_log(f"notesTool: {key} added {entry['id']}", "tools")
        return entry

    def snapshot(self, key: str) -> List[Dict[str, Any]]:
        """Return a copy of one list; callers may mutate it freely."""
        with self._lock:
            return [dict(entry) for entry in self._load()[key]]

    def remove(self, key: str, entry_id: str) -> bool:
        """Delete the entry with this id; True when something was removed."""
        with self._lock:
            data = self._load()
            before = len(data[key])
            data[key] = [e for e in data[key] if e["id"] != entry_id]
            if len(data[key]) < before:
                self._save(data)
                return True
            return False

    def _load(self) -> Dict[str, List[Dict[str, Any]]]:
        """Read the store from disk, tolerating a missing or corrupt file."""
        empty: Dict[str, List[Dict[str, Any]]] = {
            "notes": [], "todos": [], "shopping": [],
        }
        try:
            if self._path.exists():
                with self._path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for key in empty:
                        if not isinstance(data.get(key), list):
                            data[key] = []
                    return data
        except Exception as exc:
            debug_log(f"notesTool: load failed, starting fresh: {exc}", "tools")
        return empty

    def _save(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        """Atomic write: dump to a temp file, then rename over the target."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path)


# Shared default store, created lazily so importing this module never
# touches the user's home directory (unit tests stay side-effect free).
_DEFAULT_STORE: Optional[NotesStore] = None
_DEFAULT_STORE_LOCK = threading.Lock()


def _default_store() -> NotesStore:
    global _DEFAULT_STORE
    with _DEFAULT_STORE_LOCK:
        if _DEFAULT_STORE is None:
            _DEFAULT_STORE = NotesStore()
        return _DEFAULT_STORE


class NotesTool(Tool):
    """Save notes, manage a to-do list and a shopping list."""

    def __init__(self, store: Optional[NotesStore] = None) -> None:
        self._store = store

    @property
    def name(self) -> str:
        return "notesTool"

    @property
    def description(self) -> str:
        return (
            "Save voice notes, manage a to-do task list and a shopping list. "
            "Use for ANY note-taking, task or shopping request: 'запиши "
            "нотатку', 'додай хліб у список покупок', 'мої задачі', 'відміть "
            "задачу як виконану', 'save a note that I have a meeting at 3', "
            "'what is on my shopping list', 'mark the milk task as done'. "
            "Actions: add_note (text), list_notes, delete_note (note_id), "
            "add_todo (text), list_todos, complete_todo (todo_id), "
            "add_shopping (text), list_shopping, remove_shopping (item_id), "
            "clear_list (list_name='shopping' or 'todos'). Notes are kept "
            "separately from tasks; shopping is its own list."
        )

    @property
    def inputSchema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "add_note", "list_notes", "delete_note",
                        "add_todo", "list_todos", "complete_todo",
                        "add_shopping", "list_shopping", "remove_shopping",
                        "clear_list",
                    ],
                    "description": "Which notes/tasks/shopping operation to perform.",
                },
                "text": {
                    "type": "string",
                    "description": "Note, task or shopping item text (for add_* actions). Keep the user's wording.",
                },
                "note_id": {
                    "type": "string",
                    "description": "Note id to delete (for action='delete_note').",
                },
                "todo_id": {
                    "type": "string",
                    "description": "Task id to mark as done (for action='complete_todo').",
                },
                "item_id": {
                    "type": "string",
                    "description": "Shopping item id to remove (for action='remove_shopping').",
                },
                "list_name": {
                    "type": "string",
                    "enum": ["shopping", "todos"],
                    "description": "Which list to clear (for action='clear_list').",
                },
            },
            "required": ["action"],
        }

    def run(self, args: Optional[Dict[str, Any]], context: ToolContext) -> ToolExecutionResult:
        store = self._store or _default_store()
        action = ""
        if args and isinstance(args, dict):
            action = str(args.get("action") or "").strip().lower()

        handlers = {
            "add_note": (self._run_add, "notes", "note"),
            "list_notes": (self._run_list, "notes", "note"),
            "delete_note": (self._run_delete, "notes", "note"),
            "add_todo": (self._run_add, "todos", "todo"),
            "list_todos": (self._run_list, "todos", "todo"),
            "complete_todo": (self._run_complete, "todos", "todo"),
            "add_shopping": (self._run_add, "shopping", "item"),
            "list_shopping": (self._run_list, "shopping", "item"),
            "remove_shopping": (self._run_remove, "shopping", "item"),
            "clear_list": (self._run_clear, None, "item"),
        }
        if action not in handlers:
            return ToolExecutionResult(
                success=False,
                reply_text=(
                    "Unknown notes action. Use one of: add_note, list_notes, "
                    "delete_note, add_todo, list_todos, complete_todo, "
                    "add_shopping, list_shopping, remove_shopping, clear_list."
                ),
            )
        handler, key, id_label = handlers[action]
        if key is None:
            return handler(args, context, store)  # clear_list needs no list key
        return handler(args, context, store, key, id_label)

    def _run_add(self, args, context, store, key, id_label) -> ToolExecutionResult:
        args = args or {}
        text = str(args.get("text") or "")
        try:
            entry = store.add(key, text)
        except ValueError as exc:
            debug_log(f"notesTool: add rejected: {exc}", "tools")
            return ToolExecutionResult(
                success=False,
                reply_text=f"Entry not saved: {exc}.",
            )
        context.user_print(f"📝 Записано: {entry['text']}")
        return ToolExecutionResult(
            success=True,
            data={id_label: entry},
            reply_text=f"Saved (id {entry['id']}): {entry['text']}",
        )

    def _run_list(self, args, context, store, key, id_label) -> ToolExecutionResult:
        items = store.snapshot(key)
        if not items:
            empty_replies = {
                "notes": "No notes saved yet.",
                "todos": "No to-dos yet.",
                "shopping": "No items on the shopping list.",
            }
            return ToolExecutionResult(success=True, reply_text=empty_replies[key])
        lines = []
        for entry in items:
            marker = "[x] " if entry.get("done") else "[ ] "
            lines.append(f"- {marker}{entry['text']} (id {entry['id']})")
        context.user_print(f"📋 Записів: {len(items)}")
        return ToolExecutionResult(
            success=True,
            reply_text=f"Entries ({len(items)}):\n" + "\n".join(lines),
        )

    def _run_delete(self, args, context, store, key, id_label) -> ToolExecutionResult:
        args = args or {}
        entry_id = str(args.get("note_id") or "").strip()
        if not entry_id:
            return ToolExecutionResult(
                success=False,
                reply_text="No note_id given. Pass the id of the note to delete.",
            )
        if not store.remove(key, entry_id):
            return ToolExecutionResult(
                success=False,
                reply_text=f"No note with id {entry_id}.",
            )
        context.user_print(f"🗑️ Нотатку {entry_id} видалено")
        return ToolExecutionResult(success=True, reply_text=f"Note {entry_id} deleted.")

    def _run_complete(self, args, context, store, key, id_label) -> ToolExecutionResult:
        args = args or {}
        todo_id = str(args.get("todo_id") or "").strip()
        if not todo_id:
            return ToolExecutionResult(
                success=False,
                reply_text="No todo_id given. Pass the id of the task to mark as done.",
            )
        if not store.complete_todo(todo_id):
            return ToolExecutionResult(
                success=False,
                reply_text=(
                    f"No open to-do with id {todo_id} (it may not exist or is already done)."
                ),
            )
        context.user_print(f"✅ Задачу {todo_id} виконано")
        return ToolExecutionResult(success=True, reply_text=f"To-do {todo_id} marked as done.")

    def _run_remove(self, args, context, store, key, id_label) -> ToolExecutionResult:
        args = args or {}
        entry_id = str(args.get("item_id") or "").strip()
        if not entry_id:
            return ToolExecutionResult(
                success=False,
                reply_text="No item_id given. Pass the id of the shopping item to remove.",
            )
        if not store.remove(key, entry_id):
            return ToolExecutionResult(
                success=False,
                reply_text=f"No shopping item with id {entry_id}.",
            )
        context.user_print(f"🗑️ Видалено зі списку покупок: {entry_id}")
        return ToolExecutionResult(success=True, reply_text=f"Shopping item {entry_id} removed.")

    def _run_clear(self, args, context, store) -> ToolExecutionResult:
        args = args or {}
        list_name = str(args.get("list_name") or "shopping").strip().lower()
        if list_name not in VALID_LIST_NAMES:
            return ToolExecutionResult(
                success=False,
                reply_text=(
                    "No valid list_name given. Pass list_name='shopping' or "
                    "list_name='todos' for clear_list."
                ),
            )
        try:
            count = store.clear_list(list_name)
        except ValueError as exc:
            return ToolExecutionResult(success=False, reply_text=f"Could not clear: {exc}.")
        context.user_print(f"🧹 Список очищено ({count} записів)")
        return ToolExecutionResult(
            success=True,
            reply_text=f"Cleared {count} entr{'y' if count == 1 else 'ies'} from '{list_name}'.",
        )
