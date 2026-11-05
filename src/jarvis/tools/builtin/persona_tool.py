"""personaTool: user personalisation presets, per the ua-build v1.2.0 roadmap.

Backed by a single JSON file on disk (same mechanism as notesTool:
``~/.local/share/jarvis/persona.json``). Every mutation reloads from
disk first so external consumers are picked up, then writes atomically
(temp file + ``os.replace``) under a ``threading.Lock`` so concurrent
voice turns never corrupt the file.

The active profile is injected into the system prompt by
``jarvis.reply.engine.build_persona_block``.

User-facing console lines are Ukrainian; ``reply_text`` stays English
raw text that the chat model rephrases for the user, mirroring
``notes_tool``.
"""

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Union

from ...debug import debug_log
from ..base import Tool, ToolContext
from ..types import ToolExecutionResult

# Caps bound memory use and nonsense model output.
MAX_VALUE_LEN = 500
MAX_LIST_ITEMS = 20
MAX_LIST_ITEM_LEN = 100

VALID_FIELDS = (
    "name",
    "address_name",
    "favourite_topics",
    "communication_style",
    "profession",
    "preferences",
)
LIST_FIELDS = ("favourite_topics", "preferences")
VALID_STYLES = ("коротко", "детально")


def _default_persona_path() -> Path:
    """Return the default storage path, mirroring notesTool."""
    base = Path.home() / ".local" / "share" / "jarvis"
    base.mkdir(parents=True, exist_ok=True)
    return base / "persona.json"


def _normalise_list_value(raw: Union[str, list]) -> list:
    """Split a comma-separated string (or pass through a list) into items."""
    if isinstance(raw, list):
        items = [str(item).strip() for item in raw]
    else:
        items = [part.strip() for part in str(raw).split(",")]
    return [item for item in items if item]


class PersonaStore:
    """Thread-safe, file-backed store of user-persona facts."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or _default_persona_path()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_field(self, field: str, value: Union[str, list]) -> Any:
        """Validate, store and persist one persona field; returns the value."""
        field = (field or "").strip()
        if field not in VALID_FIELDS:
            raise ValueError(f"unknown field: {field}")
        if field == "communication_style":
            value = _normalise_list_value(value)
            value = value[0].lower() if value else ""
            if value not in VALID_STYLES:
                raise ValueError(
                    f"communication_style must be one of: {', '.join(VALID_STYLES)}"
                )
        elif field in LIST_FIELDS:
            items = _normalise_list_value(value)
            if not items:
                raise ValueError("value must not be empty")
            if len(items) > MAX_LIST_ITEMS:
                raise ValueError(f"too many items (limit {MAX_LIST_ITEMS})")
            for item in items:
                if len(item) > MAX_LIST_ITEM_LEN:
                    raise ValueError(
                        f"item exceeds {MAX_LIST_ITEM_LEN} characters: {item[:40]}…"
                    )
            value = items
        else:
            value = str(value or "").strip()
            if not value:
                raise ValueError("value must not be empty")
            if len(value) > MAX_VALUE_LEN:
                raise ValueError(f"value exceeds {MAX_VALUE_LEN} characters")
        with self._lock:
            data = self._load()
            data[field] = value
            self._save(data)
        debug_log(f"personaTool: set {field}", "tools")
        return value

    def get_field(self, field: str) -> Optional[Any]:
        """Return the stored value for one field, or None when unset."""
        if (field or "").strip() not in VALID_FIELDS:
            raise ValueError(f"unknown field: {field}")
        with self._lock:
            return self._load().get(field)

    def delete_field(self, field: str) -> bool:
        """Remove one field; True when something was removed."""
        if (field or "").strip() not in VALID_FIELDS:
            raise ValueError(f"unknown field: {field}")
        with self._lock:
            data = self._load()
            if field not in data:
                return False
            del data[field]
            self._save(data)
        debug_log(f"personaTool: deleted {field}", "tools")
        return True

    def snapshot(self) -> Dict[str, Any]:
        """Return a copy of the non-empty fields; callers may mutate freely."""
        with self._lock:
            return dict(self._load())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load(self) -> Dict[str, Any]:
        """Read the store from disk, tolerating a missing or corrupt file."""
        try:
            if self._path.exists():
                with self._path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    # Drop anything that is not one of the known fields so a
                    # hand-edited file cannot smuggle prompt content in.
                    return {
                        key: value
                        for key, value in data.items()
                        if key in VALID_FIELDS
                        and (
                            isinstance(value, str) if key not in LIST_FIELDS
                            else isinstance(value, list)
                        )
                    }
        except Exception as exc:
            debug_log(f"personaTool: load failed, starting fresh: {exc}", "tools")
        return {}

    def _save(self, data: Dict[str, Any]) -> None:
        """Atomic write: dump to a temp file, then rename over the target."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path)


# Shared default store, created lazily so importing this module never
# touches the user's home directory (unit tests stay side-effect free).
_DEFAULT_STORE: Optional[PersonaStore] = None
_DEFAULT_STORE_LOCK = threading.Lock()


def _default_store() -> PersonaStore:
    global _DEFAULT_STORE
    with _DEFAULT_STORE_LOCK:
        if _DEFAULT_STORE is None:
            _DEFAULT_STORE = PersonaStore()
        return _DEFAULT_STORE


class PersonaTool(Tool):
    """Remember facts about the user: name, address, style, likes."""

    def __init__(self, store: Optional[PersonaStore] = None) -> None:
        self._store = store

    @property
    def name(self) -> str:
        return "personaTool"

    @property
    def description(self) -> str:
        return (
            "Remember personal facts about the user and reuse them in every "
            "reply. Use for ANY personalisation request: 'запам'ятай, що мене "
            "звати Олена', 'моє ім'я', 'звертайся до мене', 'я працюю ', "
            "'відповідай коротко', 'що ти про мене знаєш', 'забудь мою "
            "професію', 'remember my name', 'call me doctor', 'what do you "
            "know about me', 'forget my profession'. Actions: get (field), "
            "set (field, value), list, delete (field). Fields: name, "
            "address_name, favourite_topics, communication_style (коротко or "
            "детально), profession, preferences."
        )

    @property
    def inputSchema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get", "set", "list", "delete"],
                    "description": "Which persona operation to perform.",
                },
                "field": {
                    "type": "string",
                    "enum": list(VALID_FIELDS),
                    "description": (
                        "Which persona field (for get/set/delete). Use "
                        "'preferences' for arbitrary likes."
                    ),
                },
                "value": {
                    "type": "string",
                    "description": (
                        "New value (for set). For favourite_topics and "
                        "preferences pass a comma-separated list. For "
                        "communication_style use 'коротко' or 'детально'."
                    ),
                },
            },
            "required": ["action"],
        }

    def run(self, args: Optional[Dict[str, Any]], context: ToolContext) -> ToolExecutionResult:
        store = self._store or _default_store()
        action = ""
        if args and isinstance(args, dict):
            action = str(args.get("action") or "").strip().lower()

        if action not in ("get", "set", "list", "delete"):
            return ToolExecutionResult(
                success=False,
                reply_text=(
                    "Unknown persona action. Use one of: get, set, list, delete."
                ),
            )
        if action == "list":
            return self._run_list(context, store)
        return getattr(self, f"_run_{action}")(args, context, store)

    def _field_arg(self, args) -> str:
        args = args or {}
        return str(args.get("field") or "").strip()

    def _run_get(self, args, context, store) -> ToolExecutionResult:
        field = self._field_arg(args)
        if not field:
            return ToolExecutionResult(
                success=False,
                reply_text="No field given. Pass field='name' (or another field).",
            )
        try:
            value = store.get_field(field)
        except ValueError as exc:
            return ToolExecutionResult(success=False, reply_text=f"Bad field: {exc}")
        if value is None:
            return ToolExecutionResult(
                success=True,
                reply_text=f"Nothing saved yet for '{field}'.",
            )
        pretty = ", ".join(value) if isinstance(value, list) else str(value)
        return ToolExecutionResult(
            success=True,
            reply_text=f"{field}: {pretty}",
        )

    def _run_set(self, args, context, store) -> ToolExecutionResult:
        args = args or {}
        field = self._field_arg(args)
        value = args.get("value")
        if not field or value is None or str(value).strip() == "":
            return ToolExecutionResult(
                success=False,
                reply_text="No field or value given. Pass field and value for set.",
            )
        try:
            stored = store.set_field(field, value)
        except ValueError as exc:
            debug_log(f"personaTool: set rejected: {exc}", "tools")
            return ToolExecutionResult(
                success=False,
                reply_text=f"Value not saved: {exc}",
            )
        pretty = ", ".join(stored) if isinstance(stored, list) else str(stored)
        context.user_print(f"💾 Запам'ятав: {field} = {pretty}")
        return ToolExecutionResult(
            success=True,
            data={"field": field, "value": stored},
            reply_text=f"Saved {field}: {pretty}",
        )

    def _run_delete(self, args, context, store) -> ToolExecutionResult:
        field = self._field_arg(args)
        if not field:
            return ToolExecutionResult(
                success=False,
                reply_text="No field given. Pass the field to delete.",
            )
        try:
            deleted = store.delete_field(field)
        except ValueError as exc:
            return ToolExecutionResult(success=False, reply_text=f"Bad field: {exc}")
        if not deleted:
            return ToolExecutionResult(
                success=False,
                reply_text=f"Nothing saved for '{field}'.",
            )
        context.user_print(f"🗑️ Забув: {field}")
        return ToolExecutionResult(success=True, reply_text=f"Forgot {field}.")

    def _run_list(self, context, store) -> ToolExecutionResult:
        snapshot = store.snapshot()
        if not snapshot:
            context.user_print("📋 Профіль порожній")
            return ToolExecutionResult(
                success=True,
                reply_text="No persona facts saved yet.",
            )
        lines = []
        for field, value in sorted(snapshot.items()):
            pretty = ", ".join(value) if isinstance(value, list) else str(value)
            lines.append(f"- {field}: {pretty}")
        context.user_print(f"📋 Профіль: {len(snapshot)} полів")
        return ToolExecutionResult(
            success=True,
            reply_text="Saved persona facts:\n" + "\n".join(lines),
        )
