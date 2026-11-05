# notesTool

## Purpose

Voice notes, a to-do task list and a shopping list, per the ua-build v1.2.0
roadmap: «запиши нотатку», «додай хліб у список покупок», «мої задачі»,
«відміть задачу як виконану». All data stays in a local JSON file, never
leaves the machine.

## Storage

Single JSON file `~/.local/share/jarvis/notes.json` (same mechanism as the
dictation history: `jarvis.dictation.history._default_history_path`).
Structure:

```json
{
  "notes":    [{"id": "...", "text": "..."}],
  "todos":    [{"id": "...", "text": "...", "done": false}],
  "shopping": [{"id": "...", "text": "..."}]
}
```

- `NotesStore(path=None)` — path injectable for tests; default mirrors the
  dictation history path.
- Every mutation reloads from disk first (external consumers, e.g. the
  desktop app, are picked up), then saves atomically: dump to
  `notes.json.tmp`, then `os.replace` over the target — a crash mid-write
  never leaves a truncated store.
- All access is serialised with a `threading.Lock` (concurrent voice turns).
- A missing or corrupt file resets to three empty lists; the next save
  overwrites the bad file. Unicode text round-trips (`ensure_ascii=False`).
- Caps: 200 entries per list, 500 characters per text. Violations raise
  `ValueError`, which the tool converts into an honest failure reply.

## Schema

| Field | Type | Meaning |
|---|---|---|
| `action` | see below | required |
| `text` | string | note/task/item text for `add_*`; keep the user's wording |
| `note_id` | string | note to delete (`delete_note`) |
| `todo_id` | string | task to mark done (`complete_todo`) |
| `item_id` | string | shopping item to remove (`remove_shopping`) |
| `list_name` | `shopping` \| `todos` | which list to wipe (`clear_list`) |

Actions: `add_note`, `list_notes`, `delete_note`, `add_todo`, `list_todos`,
`complete_todo`, `add_shopping`, `list_shopping`, `remove_shopping`,
`clear_list`.

## Result contract

- `add_*`: `Saved (id <id>): <text>`; the entry rides in `result.data`
  (`note` / `todo` / `item` key) so callers can chain without parsing text.
- `list_*`: bullet list with `[x]`/`[ ]` done markers for to-dos, or an
  honest empty reply (`No notes saved yet.` / `No to-dos yet.` / `No items
  on the shopping list.`).
- `delete_note` / `complete_todo` / `remove_shopping`: per-id confirmation,
  or a failure naming the missing/unknown id. `complete_todo` on an
  already-done task fails honestly instead of pretending success.
- `clear_list`: `Cleared <N> entries from '<list_name>'.`
- Unknown action / missing `text` / missing id: failure reply naming the
  missing argument.

Raw English `reply_text` only; the chat model phrases the final Ukrainian
reply. Console lines via `context.user_print` are Ukrainian (📝 notes,
✅ tasks, 🛒 shopping, 🧹 clears), no em-dashes.

## Registry wiring

Registered as `"notesTool"` in `BUILTIN_TOOLS`
(`src/jarvis/tools/registry.py`). The description embeds the Ukrainian
phrases above so the tool router matches them; the tool name and argument
identifiers stay English (contract strings the model emits).

## Tests

`tests/test_notes_tool.py` (28 tests): store semantics for every action,
empty lists, Ukrainian unicode round-trip, persistence across instances,
atomic-write leftovers, corrupt-file recovery, concurrent writes under the
lock, cap validation, tool behaviour per action, registry wiring and
description routing.
