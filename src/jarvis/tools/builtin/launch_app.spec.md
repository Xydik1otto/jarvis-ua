# launchApp tool

## Purpose

Open a program, launch a game, play music, or open a website / YouTube search
on the user's machine in response to "open X" / "launch X" / "play X" / "start
X" utterances.

## Security model

The model never supplies a raw command. It only picks a `target` name, which is
fuzzy-matched against the catalogue in `cfg.launch_targets`. Only a catalogued
command is ever executed, so an utterance cannot inject an arbitrary shell
command. The optional `query` is URL-encoded before substitution into a
`{query}` placeholder, so it can only land inside a URL.

## Catalogue (`cfg.launch_targets`)

A list of entries:

- `name` — canonical display name (used in replies and as a match candidate).
- `aliases` — spoken variants, including Ukrainian and common Whisper
  mishearings.
- `command` — an OS-openable path, folder, file, or protocol/URI. Examples:
  an `.exe` path, `steam://rungameid/<id>`, `steam://open/main`, `spotify:`,
  `https://...`. May contain `{query}` for search targets.
- `needs_query` — advisory only (documents that the command expects a query);
  not enforced.

Defaults seed `YouTube` and `Google` (work everywhere). Local apps/games/music
are per-machine and added by the user.

## Resolution

`_resolve_target` takes the higher of `fuzz.ratio` and `fuzz.partial_ratio`
across each entry's name and aliases; a match needs score >= 78. Language
agnostic (works for Cyrillic and Latin). Returns None below threshold so the
tool reports the target as unknown rather than opening the wrong thing.

## Launch

`_open` uses `os.startfile` on Windows (handles paths, folders, files, and
registered protocols) and `open` / `xdg-open` on macOS / Linux.

## Result contract

- Success: `Opened <name>[ (<query>)].`
- Empty catalogue: guidance to populate `launch_targets`.
- Unknown target: lists the known target names.
- Missing path / OS error: honest failure naming the target.

Raw text only; the chat model phrases the final reply in the user's language.
No LLM calls, no network (beyond whatever the opened URL/app does).
