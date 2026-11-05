# timerTool

## Purpose

Countdown timers with audible announcements, per upstream isair/jarvis
issue #303: "set a timer for 10 minutes", optional label ("pasta"),
concurrent timers, cancellation ("cancel the pasta timer", "cancel all"),
and listing ("what timers do I have running?").

## Schema

| Field | Type | Meaning |
|---|---|---|
| `action` | `set` \| `list` \| `cancel` | required |
| `duration_seconds` | number | duration for `set`; the model converts the user's phrase to seconds |
| `duration` | string | OPTIONAL raw phrase fallback (`"10 хвилин"`, `"1h30m"`) when the model could not compute seconds |
| `label` | string | OPTIONAL short name (e.g. `pasta`); defaults to "таймер" |
| `timer_id` | string | id to cancel, or `all` to cancel everything |

## Registry

Module-level `TimerRegistry` singleton (`REGISTRY`), shared by the tool and
the daemon poller. Thread-safe dict `{id: (label, deadline_monotonic,
duration)}` on a monotonic clock (injectable for tests). Limits: max 16
concurrent timers, max duration 24h; violations raise `ValueError`, which
the tool converts into an honest failure reply.

## Elapsed announcement

`start_polling(speak_fn, poll_sec=1.0)` runs a daemon thread. When a timer
elapses the poller:

1. prints `⏰ Таймер «label» завершився!` to the console,
2. calls `speak_fn("Час вийшов: <label>")`.

The tool itself is NOT invoked again: once `set` returns, the announcement
path never touches the LLM or the tool loop. TTS failures are swallowed
(logged via `debug_log`) so the console line always appears.

The daemon (`daemon.py`) registers the poller right after TTS init with
`tts.speak` as the callback. `tts.speak()` no-ops when TTS is disabled, so
timers still announce on the console without TTS.

## Duration parsing

`parse_duration` handles uk + en free-form phrases language-agnostically:
`10 хвилин`, `2 години`, `90 секунд`, `пів години`, `10m`, `2h`, `1h30m`,
`1 година 30 хвилин`. Unit stems match by prefix so plural/genitive forms
parse without enumerating them. Returns `None` for anything unparseable.

## Result contract

- `set`: `Timer '<label>' set for <N> seconds (id <id>). ...`
- `list`: bullet list, soonest deadline first, or `No timers are running.`
- `cancel`: `Cancelled <N> timer(s).` for `all`, per-id confirmation, or an
  honest failure for a nonexistent id.
- Unknown action / missing duration / missing timer_id: failure reply
  naming the missing argument.

Raw text only; the chat model phrases the final reply in the user's
language. No LLM calls, no network, no persistence (timers live for the
process lifetime only).
