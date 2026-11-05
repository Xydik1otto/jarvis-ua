# mediaControl

## Purpose

Voice control of media playback and volume on the user's computer:
play/pause, next/previous track, volume up/down, mute. Sends OS media key
events via pynput, so it works with any active media session (Spotify, a
browser player, the system player) without targeting a specific player.

## Schema

| Field | Type | Meaning |
|---|---|---|
| `action` | `play_pause` \| `next` \| `previous` \| `volume_up` \| `volume_down` \| `mute` | required |
| `steps` | integer | OPTIONAL, volume actions only: number of volume presses (default 5) |

## Key mapping

| Action | pynput `Key` | Steps |
|---|---|---|
| `play_pause` | `media_play_pause` | 1 |
| `next` | `media_next` | 1 |
| `previous` | `media_previous` | 1 |
| `volume_up` | `media_volume_up` | `steps` (default 5) |
| `volume_down` | `media_volume_down` | `steps` (default 5) |
| `mute` | `media_volume_mute` | 1 |

The controller is obtained through `_get_controller()` (kept as a function
so tests can inject a fake); the `Key` enum is referenced through module
attribute `_KEYS` for the same reason.

## Result contract

- Success: `Sent <action> (xN) to the media session.`
- Unknown or missing action: honest failure listing the valid actions.
- Press failure (no media session, OS error): `success=False` with the
  reason in the reply; never raises out of `run()`.
- pynput not importable (headless environment): honest failure, no crash.

Raw text only; no LLM calls, no network.
