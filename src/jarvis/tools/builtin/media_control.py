"""mediaControl tool: OS media keys for playback and volume via pynput.

Sends hardware media key events, so it works with any active media session
(Spotify, YouTube in a browser, system player) without shelling out to a
specific player. No LLM calls, no network.
"""

from typing import Any, Dict, Optional

from ...debug import debug_log
from ..base import Tool, ToolContext
from ..types import ToolExecutionResult

# Volume actions repeat the key this many presses by default.
DEFAULT_VOLUME_STEPS = 5

try:  # pragma: no cover - import guard for headless environments
    from pynput.keyboard import Controller as _KeyboardController, Key as _Key

    _KEYS = _Key
    _PYNPUT_AVAILABLE = True
except Exception:  # pragma: no cover
    _KeyboardController = None
    _Key = None
    _KEYS = None
    _PYNPUT_AVAILABLE = False


def _get_controller():
    """Return a fresh pynput keyboard controller (separate fn for tests)."""
    return _KeyboardController()


# action -> (key name on pynput.Key, repeats volume steps?)
_ACTIONS: Dict[str, Any] = {
    "play_pause": "media_play_pause",
    "next": "media_next",
    "previous": "media_previous",
    "volume_up": "media_volume_up",
    "volume_down": "media_volume_down",
    "mute": "media_volume_mute",
}

_VOLUME_ACTIONS = {"volume_up", "volume_down"}

_USER_LABELS = {
    "play_pause": "⏯️ Відтворення / пауза",
    "next": "⏭️ Наступний трек",
    "previous": "⏮️ Попередній трек",
    "volume_up": "🔊 Гучність вище",
    "volume_down": "🔉 Гучність нижче",
    "mute": "🔇 Без звуку",
}


class MediaControlTool(Tool):
    """Send OS media keys: play/pause, next/previous, volume, mute."""

    @property
    def name(self) -> str:
        return "mediaControl"

    @property
    def description(self) -> str:
        return (
            "Control media playback and volume on the user's computer: "
            "play/pause, next or previous track, volume up/down, and mute. "
            "Use for 'pause the music', 'наступна пісня', 'зроби гучніше', "
            "'вимкни звук', 'mute' requests. Sends OS media keys to the "
            "active media session (Spotify, browser, system player). Pass "
            "action; volume actions accept steps (default 5 presses)."
        )

    @property
    def inputSchema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "play_pause",
                        "next",
                        "previous",
                        "volume_up",
                        "volume_down",
                        "mute",
                    ],
                    "description": "Which media action to perform.",
                },
                "steps": {
                    "type": "integer",
                    "description": "OPTIONAL, volume actions only: how many volume presses to send (default 5).",
                },
            },
            "required": ["action"],
        }

    def run(self, args, context: ToolContext) -> ToolExecutionResult:
        args = args or {}
        action = str(args.get("action") or "").strip().lower()
        if not action:
            return ToolExecutionResult(
                success=False,
                reply_text=(
                    "No media action given. Use play_pause, next, previous, "
                    "volume_up, volume_down, or mute."
                ),
            )
        if action not in _ACTIONS:
            return ToolExecutionResult(
                success=False,
                reply_text=(
                    f"Unknown media action '{action}'. Use play_pause, next, "
                    "previous, volume_up, volume_down, or mute."
                ),
            )
        if not _PYNPUT_AVAILABLE:
            debug_log("mediaControl: pynput unavailable", "tools")
            return ToolExecutionResult(
                success=False,
                reply_text="Media keys are unavailable: pynput is not installed.",
            )

        key_name = _ACTIONS[action]
        key = getattr(_KEYS, key_name)
        steps = 1
        if action in _VOLUME_ACTIONS:
            try:
                steps = int(args.get("steps") or DEFAULT_VOLUME_STEPS)
            except (TypeError, ValueError):
                steps = DEFAULT_VOLUME_STEPS
            steps = max(1, steps)

        context.user_print(_USER_LABELS[action])
        try:
            controller = _get_controller()
            for _ in range(steps):
                controller.tap(key)
        except Exception as exc:
            debug_log(f"mediaControl: {action} failed: {exc}", "tools")
            return ToolExecutionResult(
                success=False,
                reply_text=(
                    f"Could not send the {action} media key: {exc}. There may "
                    "be no active media session."
                ),
            )

        debug_log(f"mediaControl: {action} x{steps}", "tools")
        detail = f" (x{steps})" if steps > 1 else ""
        return ToolExecutionResult(
            success=True,
            reply_text=f"Sent {action}{detail} to the media session.",
        )
