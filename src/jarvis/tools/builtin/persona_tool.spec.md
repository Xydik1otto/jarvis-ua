# personaTool

## Purpose

User personalisation presets, per the ua-build v1.2.0 roadmap: «запам'ятай,
що мене звати…», «звертайся до мене», «відповідай коротко», «що ти про мене
знаєш». The user tells Jarvis facts about itself once; Jarvis keeps them and
applies them to every reply. All data stays in a local JSON file, never
leaves the machine.

## Storage

Single JSON file `~/.local/share/jarvis/persona.json` (same mechanism as
notesTool). Structure: a flat dict of active fields only:

```json
{
  "name": "Олена",
  "address_name": "пане Оленко",
  "favourite_topics": ["космос", "математика"],
  "communication_style": "коротко",
  "profession": "інженерка",
  "preferences": ["любить тишу"]
}
```

- `PersonaStore(path=None)` — path injectable for tests; default mirrors
  the notesTool path.
- Every mutation reloads from disk first (external consumers are picked
  up), then saves atomically: dump to `persona.json.tmp`, then
  `os.replace` over the target — a crash mid-write never leaves a
  truncated store.
- All access is serialised with a `threading.Lock` (concurrent voice
  turns).
- A missing or corrupt file falls back to an empty profile.
- `_load` keeps only known fields with the right value types, so a
  hand-edited file cannot smuggle arbitrary prompt content in.

## Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | the user's name |
| `address_name` | string | how to address the user («звертайся до мене») |
| `favourite_topics` | list of strings | set with a comma-separated value |
| `communication_style` | enum | `коротко` or `детально` (case-insensitive) |
| `profession` | string | what the user does |
| `preferences` | list of strings | arbitrary likes («довільні вподобайки») |

Validation limits: scalar values 500 chars, list items 100 chars, 20 items
max. Unknown fields, empty values and an invalid style raise `ValueError`,
which the tool surfaces as an honest failure reply.

## Tool contract

`PersonaTool` exposes one `action` parameter: `get`, `set`, `list`,
`delete` (list needs no field; the others take `field`, set also takes
`value`). `delete` on an unset field is a failure, not a fake success.
The tool returns raw data; the chat model rephrases for the user
(`reply_text` stays English, `user_print` lines are Ukrainian with an
emoji, mirroring notesTool). No LLM calls inside the tool.

## Prompt injection

`jarvis.reply.engine.build_persona_block(cfg)` renders the active
profile as a Ukrainian «ПРОФІЛЬ КОРИСТУВАЧА» block. It reads the store
once per reply turn (so a personaTool set takes effect from the next
turn) and is appended to the system prompt right after the explicit
`user_profile` block, before the learned warm profile: user-asked facts
outrank anything learned from the graph. Empty store → no block at all.
`cfg.persona_path` overrides the file path for tests.
