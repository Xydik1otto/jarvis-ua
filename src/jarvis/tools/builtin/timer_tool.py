"""timerTool: countdown timers with audible elapsed announcements.

Supports concurrent named timers ("set a 10 minute pasta timer"), listing
("what timers do I have running?") and cancellation ("cancel the pasta
timer", "cancel all timers"). Elapsed timers are announced by a background
poller through a speak callback, NOT by a second tool call: once the tool
returns, the announcement path never touches the LLM again.

The registry is a module-level singleton (``REGISTRY``) so the tool and the
daemon's poller share one source of truth. Durations are tracked on a
monotonic clock; tests can inject their own clock.
"""

import re
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from ...debug import debug_log
from ..base import Tool, ToolContext
from ..types import ToolExecutionResult

# Maximum number of timers that may run at once, and the longest single
# duration accepted. Caps bound memory use and nonsense model output.
MAX_TIMERS = 16
MAX_DURATION_SECONDS = 24 * 3600

# Duration words for uk + en, language-agnostic enough for Whisper output.
# Each unit maps to its multiplier; plural/genitive forms all funnel into
# the same stem prefix so "хвилина/хвилини/хвилин", "minute/minutes" parse.
_UNIT_WORDS: List[Tuple[str, float]] = [
    ("секунд", 1.0), ("секунд", 1.0),
    ("сек", 1.0),
    ("с", 1.0),
    ("second", 1.0),
    ("sec", 1.0),
    ("s", 1.0),
    ("хвилин", 60.0),
    ("хв", 60.0),
    ("minute", 60.0),
    ("min", 60.0),
    ("m", 60.0),
    ("годин", 3600.0),
    ("год", 3600.0),
    ("hour", 3600.0),
    ("hr", 3600.0),
    ("h", 3600.0),
]

_PHRASE_RE = re.compile(
    r"(\d+[\d.,]*)\s*([a-zA-Zа-яА-ЯІіЇїЄєҐґ]+)",
    re.UNICODE,
)

# Longest unit word first so "годин" wins over "год" and "хвилин" over "хв".
_ORDERED_UNITS = sorted(
    [(stem, mult) for stem, mult in _UNIT_WORDS if len(stem) > 1],
    key=lambda item: -len(item[0]),
)


def _unit_multiplier(word: str) -> Optional[float]:
    word = word.lower()
    for stem, mult in _ORDERED_UNITS:
        if word.startswith(stem):
            return mult
    # Single-letter unit shorthand (m / s / h), checked after long forms so
    # Ukrainian words are never swallowed by a one-letter stem.
    for stem, mult in _UNIT_WORDS:
        if len(stem) == 1 and word == stem:
            return mult
    return None


def parse_duration(phrase: str) -> Optional[float]:
    """Parse a free-form duration phrase into seconds.

    Accepts Ukrainian and English forms: "10 хвилин", "2 години", "90
    секунд", "пів години", "10m", "1h30m". Returns None when nothing
    duration-like is found. Never raises.
    """
    if not phrase or not isinstance(phrase, str):
        return None
    text = phrase.strip().lower().replace(",", ".")
    if not text:
        return None

    # "пів години" / "half an hour"-style half-unit prefix: normalise to a
    # numeric 0.5 before the unit so the generic number+unit pass handles it.
    text = re.sub(r"пів\s*(?=сек|хв|год)", "0.5 ", text)
    text = re.sub(r"половин\w*\s*(?=сек|хв|год)", "0.5 ", text)
    text = re.sub(r"half an?\s+(?=second|sec|minute|min|hour|hr)", "0.5 ", text)

    total = 0.0
    matched = False
    for number, unit in _PHRASE_RE.findall(text):
        mult = _unit_multiplier(unit)
        if mult is None:
            continue
        try:
            value = float(number)
        except ValueError:
            continue
        total += value * mult
        matched = True

    if not matched:
        return None
    return total


class TimerRegistry:
    """Thread-safe store of running timers with an elapsed-timer poller."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        # id -> (label, deadline_monotonic, duration_seconds)
        self._timers: Dict[str, Tuple[str, float, float]] = {}
        self._poller: Optional[threading.Thread] = None

    def _now(self) -> float:
        return self._clock()

    def create(self, label: str, duration_seconds: float) -> str:
        """Register a timer and return its id. Raises ValueError on limits."""
        duration = float(duration_seconds)
        if duration <= 0:
            raise ValueError("duration must be positive")
        if duration > MAX_DURATION_SECONDS:
            raise ValueError("duration exceeds 24h limit")
        label = (label or "").strip() or "таймер"
        timer_id = uuid.uuid4().hex[:8]
        with self._lock:
            if len(self._timers) >= MAX_TIMERS:
                raise ValueError(f"timer limit reached ({MAX_TIMERS} concurrent)")
            self._timers[timer_id] = (label, self._now() + duration, duration)
        debug_log(f"timer created: {timer_id} '{label}' {duration}s", "tools")
        return timer_id

    def list(self) -> List[Dict[str, Any]]:
        """Snapshot of running timers, soonest deadline first."""
        now = self._now()
        with self._lock:
            items = [
                {
                    "id": tid,
                    "label": label,
                    "duration_seconds": duration,
                    "remaining_seconds": max(0, round(deadline - now, 1)),
                }
                for tid, (label, deadline, duration) in self._timers.items()
            ]
        items.sort(key=lambda item: item["remaining_seconds"])
        return items

    def cancel(self, timer_id: str) -> bool:
        with self._lock:
            return self._timers.pop(timer_id, None) is not None

    def cancel_all(self) -> int:
        with self._lock:
            count = len(self._timers)
            self._timers.clear()
        return count

    def poll_once(self, now: Optional[float] = None) -> List[Tuple[str, str]]:
        """Fire every elapsed timer; returns [(label, timer_id), ...]."""
        now = self._now() if now is None else now
        fired: List[Tuple[str, str]] = []
        with self._lock:
            for tid, (label, deadline, _duration) in list(self._timers.items()):
                if deadline <= now:
                    del self._timers[tid]
                    fired.append((label, tid))
        return fired

    def start_polling(self, speak_fn: Callable[[str], None], poll_sec: float = 1.0) -> None:
        """Start a daemon thread that announces elapsed timers via speak_fn.

        The announcement never re-enters the LLM: the poller prints a
        user-facing line and speaks directly. TTS failures are swallowed so
        the console line still appears.
        """

        def _loop() -> None:
            while True:
                time.sleep(poll_sec)
                try:
                    fired = self.poll_once()
                except Exception as exc:
                    debug_log(f"timer poll error: {exc}", "tools")
                    continue
                for label, _tid in fired:
                    print(f"⏰ Таймер «{label}» завершився!", flush=True)
                    try:
                        speak_fn(f"Час вийшов: {label}")
                    except Exception as exc:
                        debug_log(f"timer speak failed: {exc}", "tools")

        thread = threading.Thread(target=_loop, daemon=True, name="timer-poller")
        self._poller = thread
        thread.start()


# Shared registry: the tool and the daemon poller must see the same timers.
REGISTRY = TimerRegistry()


class TimerTool(Tool):
    """Set, list, and cancel countdown timers with audible announcements."""

    @property
    def name(self) -> str:
        return "timerTool"

    @property
    def description(self) -> str:
        return (
            "Set countdown timers, list running timers, or cancel them. Use "
            "for ANY timer request: 'set a timer for 10 minutes', 'нагадай "
            "мені через 5 хвилин поставити таймер', 'cancel the pasta "
            "timer', 'cancel all timers', 'what timers do I have running?'. "
            "Pass action='set' with duration_seconds (number) and an "
            "optional short label (e.g. 'pasta'); the model may also pass "
            "the raw duration phrase via duration. Timers run in the "
            "background and announce themselves when they finish."
        )

    @property
    def inputSchema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["set", "list", "cancel"],
                    "description": "set a new timer, list running timers, or cancel one/all.",
                },
                "duration_seconds": {
                    "type": "number",
                    "description": "Timer duration in seconds (for action='set'). Convert the user's phrase to seconds yourself.",
                },
                "duration": {
                    "type": "string",
                    "description": "OPTIONAL raw duration phrase (e.g. '10 хвилин', '1h30m') if you could not compute duration_seconds.",
                },
                "label": {
                    "type": "string",
                    "description": "OPTIONAL short name for the timer (e.g. 'pasta').",
                },
                "timer_id": {
                    "type": "string",
                    "description": "Timer id to cancel (for action='cancel'), or 'all' to cancel every running timer.",
                },
            },
            "required": ["action"],
        }

    def run(self, args: Optional[Dict[str, Any]], context: ToolContext) -> ToolExecutionResult:
        action = ""
        if args and isinstance(args, dict):
            action = str(args.get("action") or "").strip().lower()

        if action == "set":
            return self._run_set(args, context)
        if action == "list":
            return self._run_list(context)
        if action == "cancel":
            return self._run_cancel(args, context)
        return ToolExecutionResult(
            success=False,
            reply_text=(
                "Unknown timer action. Use action='set', 'list', or 'cancel'."
            ),
        )

    def _run_set(self, args, context: ToolContext) -> ToolExecutionResult:
        args = args or {}
        label = str(args.get("label") or "").strip()
        duration: Optional[float] = None
        raw_duration = args.get("duration_seconds")
        if raw_duration is not None:
            try:
                duration = float(raw_duration)
            except (TypeError, ValueError):
                duration = None
        if duration is None:
            phrase = str(args.get("duration") or "").strip()
            duration = parse_duration(phrase)
        if duration is None:
            return ToolExecutionResult(
                success=False,
                reply_text=(
                    "No timer duration was given. Pass duration_seconds "
                    "(a number) or duration (a phrase like '10 хвилин')."
                ),
            )

        try:
            timer_id = REGISTRY.create(label, duration)
        except ValueError as exc:
            debug_log(f"timerTool: create rejected: {exc}", "tools")
            return ToolExecutionResult(
                success=False,
                reply_text=f"Timer not set: {exc}.",
            )

        shown_label = label or "таймер"
        context.user_print(f"⏲️ Таймер «{shown_label}» на {int(duration)} с запущено")
        debug_log(f"timerTool: set {timer_id} '{label}' {duration}s", "tools")
        return ToolExecutionResult(
            success=True,
            reply_text=(
                f"Timer '{shown_label}' set for {int(duration)} seconds "
                f"(id {timer_id}). It will announce itself when it finishes."
            ),
        )

    def _run_list(self, context: ToolContext) -> ToolExecutionResult:
        items = REGISTRY.list()
        if not items:
            return ToolExecutionResult(
                success=True,
                reply_text="No timers are running.",
            )
        lines = [
            (
                f"- {item['label']} (id {item['id']}): "
                f"{int(item['remaining_seconds'])}s remaining of "
                f"{int(item['duration_seconds'])}s"
            )
            for item in items
        ]
        context.user_print(f"⏲️ Активних таймерів: {len(items)}")
        return ToolExecutionResult(
            success=True,
            reply_text="Running timers:\n" + "\n".join(lines),
        )

    def _run_cancel(self, args, context: ToolContext) -> ToolExecutionResult:
        args = args or {}
        timer_id = str(args.get("timer_id") or "").strip()
        if not timer_id:
            return ToolExecutionResult(
                success=False,
                reply_text=(
                    "No timer_id given. Pass the timer id, or 'all' to "
                    "cancel every running timer."
                ),
            )
        if timer_id.lower() == "all":
            count = REGISTRY.cancel_all()
            context.user_print(f"⏲️ Скасовано таймерів: {count}")
            return ToolExecutionResult(
                success=True,
                reply_text=f"Cancelled {count} timer(s).",
            )
        if REGISTRY.cancel(timer_id):
            context.user_print(f"⏲️ Таймер {timer_id} скасовано")
            return ToolExecutionResult(
                success=True,
                reply_text=f"Timer {timer_id} cancelled.",
            )
        return ToolExecutionResult(
            success=False,
            reply_text=f"No running timer with id {timer_id}.",
        )
