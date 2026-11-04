"""Game mode: keep the GPU free for games.

When a game is running, a resident chat model (several GB of VRAM) starves the
game. This module detects a running game and flips Jarvis into a low-footprint
mode where Ollama models unload from VRAM immediately after each use
(``keep_alive: 0``) instead of staying resident. Whisper already runs on CPU,
so once the chat model is evicted the GPU is free for the game.

Detection is best-effort and language/title agnostic: it looks for any process
whose executable lives under a known game-platform install root (Steam, Epic,
GOG, ...) plus any extra process names the user lists in
``cfg.game_process_names``. The Steam/Epic *clients* themselves are ignored —
only actual games under ``steamapps/common`` (etc.) count.

The public surface is tiny and thread-safe:

- ``is_active()`` -> bool
- ``keep_alive(default)`` -> the keep-alive value Ollama calls should use
- ``GameModeMonitor`` -> background thread the daemon starts
"""

from __future__ import annotations

import threading
from typing import Optional, List

import requests

try:
    import psutil
except Exception:  # pragma: no cover - psutil is a declared dependency
    psutil = None  # type: ignore

from .debug import debug_log


# Substrings (lower-case) that mark an executable path as an actual game rather
# than a launcher/client. Matching a game *under* these roots avoids treating
# the Steam/Epic client itself as a game.
_GAME_PATH_MARKERS = (
    "steamapps\\common",
    "steamapps/common",
    "epic games\\",
    "epic games/",
    "gog galaxy\\games",
    "gog galaxy/games",
    "riot games\\",
    "ea games\\",
    "origin games\\",
    "battle.net\\games",
)


_lock = threading.Lock()
_active = False


def is_active() -> bool:
    """True when a game is currently detected."""
    with _lock:
        return _active


def _set_active(value: bool) -> bool:
    """Set the flag; return True if it changed."""
    global _active
    with _lock:
        if _active == value:
            return False
        _active = value
        return True


def keep_alive(default: str = "30m") -> str:
    """Keep-alive value Ollama calls should use right now.

    ``"0"`` while a game is active (unload immediately after each call) so the
    GPU stays free; the caller's normal value otherwise.
    """
    return "0" if is_active() else default


def detect_game(cfg) -> Optional[str]:
    """Return the process name of a running game, or None.

    Pure and synchronous so it can be unit-tested without the monitor thread.
    """
    if psutil is None:
        return None

    extra_names = {
        str(n).strip().lower()
        for n in (getattr(cfg, "game_process_names", []) or [])
        if str(n).strip()
    }

    for proc in psutil.process_iter(["name", "exe"]):
        try:
            info = proc.info
            name = (info.get("name") or "").lower()
            exe = (info.get("exe") or "").lower()
        except (psutil.Error, Exception):
            continue

        if name and name in extra_names:
            return info.get("name") or name
        if exe and any(marker in exe for marker in _GAME_PATH_MARKERS):
            return info.get("name") or exe
    return None


def _post(base_url: str, payload: dict, timeout: float = 10.0) -> None:
    try:
        requests.post(f"{base_url}/api/generate", json=payload, timeout=timeout)
    except Exception:
        pass


def _models_for(cfg) -> List[str]:
    names = [
        getattr(cfg, "llm_chat_model", "") or getattr(cfg, "ollama_chat_model", ""),
        getattr(cfg, "intent_judge_model", ""),
    ]
    seen, out = set(), []
    for n in names:
        n = (n or "").strip()
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _unload_models(cfg) -> None:
    """Evict the chat/intent models from VRAM right now (keep_alive: 0)."""
    base_url = getattr(cfg, "ollama_base_url", "") or ""
    if not base_url:
        return
    for model in _models_for(cfg):
        _post(base_url, {"model": model, "prompt": "", "keep_alive": 0})
        debug_log(f"game mode: unloaded '{model}' from VRAM", "game")


def _rewarm_models(cfg) -> None:
    """Page the chat model back into VRAM after a game closes."""
    base_url = getattr(cfg, "ollama_base_url", "") or ""
    if not base_url:
        return
    for model in _models_for(cfg):
        _post(
            base_url,
            {"model": model, "prompt": "", "keep_alive": "30m", "options": {"num_predict": 1}},
            timeout=60.0,
        )
        debug_log(f"game mode: re-warmed '{model}'", "game")


class GameModeMonitor(threading.Thread):
    """Poll for a running game and toggle game mode, evicting/re-warming VRAM.

    Prints a Ukrainian status line on each transition. Best-effort: any error
    in a poll is swallowed so the monitor never takes down the daemon.
    """

    def __init__(self, cfg):
        super().__init__(daemon=True, name="game-mode-monitor")
        self.cfg = cfg
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        if not getattr(self.cfg, "game_mode_enabled", True):
            return
        poll = float(getattr(self.cfg, "game_mode_poll_sec", 5.0) or 5.0)
        while not self._stop.wait(poll):
            try:
                game = detect_game(self.cfg)
            except Exception as e:  # pragma: no cover - defensive
                debug_log(f"game mode poll error: {e}", "game")
                continue

            if game and _set_active(True):
                print(f"🎮 Виявлено гру ({game}) — звільняю відеопам'ять для неї", flush=True)
                _unload_models(self.cfg)
            elif not game and _set_active(False):
                print("🎮 Гру закрито — повертаю швидкий режим", flush=True)
                _rewarm_models(self.cfg)
