"""launchApp tool: open a program, launch a game, play music, or open a
website / YouTube search from a user-configurable catalogue.

Security model: the model never supplies a raw command. It only picks a
``target`` name, which is fuzzy-matched against the catalogue in
``cfg.launch_targets``. Only catalogue commands are ever executed, so an
utterance cannot inject an arbitrary shell command. The optional ``query`` is
URL-encoded before being substituted into a ``{query}`` placeholder, so it can
only ever land inside a URL, never as a separate argument.
"""

import os
import sys
import subprocess
from urllib.parse import quote
from typing import Dict, Any, Optional, List

from rapidfuzz import fuzz

from ...debug import debug_log
from ..base import Tool, ToolContext
from ..types import ToolExecutionResult


# Fuzzy score (0-100) a target name must reach against a catalogue entry's
# name or one of its aliases to count as a match. High enough to avoid
# launching the wrong app on a loose word, low enough to tolerate Whisper
# mishearings and case/spacing noise.
_MATCH_THRESHOLD = 78


def _resolve_target(name: str, targets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the best catalogue entry for a spoken target name, or None.

    Matches against each entry's ``name`` plus every alias, taking the higher
    of full-ratio and partial-ratio so both "стім" == "Steam-alias" and
    substring hits ("відкрий стім будь ласка" already trimmed upstream) work.
    """
    query = (name or "").strip().lower()
    if not query:
        return None

    best: Optional[Dict[str, Any]] = None
    best_score = 0.0
    for entry in targets:
        candidates = [entry.get("name", "")] + list(entry.get("aliases", []) or [])
        for cand in candidates:
            cand = (cand or "").strip().lower()
            if not cand:
                continue
            score = max(fuzz.ratio(query, cand), fuzz.partial_ratio(query, cand))
            if score > best_score:
                best_score = score
                best = entry

    if best is not None and best_score >= _MATCH_THRESHOLD:
        return best
    return None


def _open(command: str) -> None:
    """Open a path, folder, file, URI, or protocol with the OS default handler.

    Raises on failure so the caller can report a clean error to the user.
    """
    if sys.platform == "win32":
        # Handles .exe paths, documents, folders, and registered protocols
        # (steam://, spotify:, https://, mailto:, ...).
        os.startfile(command)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", command])
    else:
        subprocess.Popen(["xdg-open", command])


class LaunchAppTool(Tool):
    """Open apps, games, music, or websites from the user's launch catalogue."""

    @property
    def name(self) -> str:
        return "launchApp"

    @property
    def description(self) -> str:
        return (
            "Open a program, launch a game, play music, or open a website / "
            "YouTube video on the user's computer. Use for ANY 'open X', "
            "'launch X', 'play X', 'start X' request (e.g. open Steam, launch "
            "the game, play my music, open YouTube). Pass target='<what to "
            "open, as the user named it>'. For a YouTube/web search, also pass "
            "query='<what to search or watch>'. Only catalogued targets can be "
            "opened; never invent a file path."
        )

    @property
    def inputSchema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "What to open, as the user named it (e.g. 'Steam', 'YouTube', 'my music', a game name). Matched against the user's launch catalogue.",
                },
                "query": {
                    "type": "string",
                    "description": "OPTIONAL. Only for search/watch targets like YouTube or Google: what to search for or watch (e.g. 'lofi hip hop', 'Dune trailer').",
                },
            },
            "required": ["target"],
        }

    def run(self, args: Optional[Dict[str, Any]], context: ToolContext) -> ToolExecutionResult:
        target = ""
        query = ""
        if args and isinstance(args, dict):
            target = str(args.get("target") or "").strip()
            query = str(args.get("query") or "").strip()

        if not target:
            return ToolExecutionResult(
                success=False,
                reply_text="No target was given. Tell me what to open (e.g. Steam, YouTube, my music).",
            )

        targets: List[Dict[str, Any]] = list(getattr(context.cfg, "launch_targets", []) or [])
        if not targets:
            return ToolExecutionResult(
                success=False,
                reply_text=(
                    "The launch catalogue is empty. Add entries under "
                    "'launch_targets' in config.json (name, aliases, command) "
                    "so I can open apps, games, and music."
                ),
            )

        entry = _resolve_target(target, targets)
        if entry is None:
            known = ", ".join(str(t.get("name", "")) for t in targets if t.get("name"))
            return ToolExecutionResult(
                success=False,
                reply_text=f"I don't have '{target}' in the launch catalogue. Known targets: {known}.",
            )

        command = str(entry.get("command", "")).strip()
        label = str(entry.get("name", target))
        if not command:
            return ToolExecutionResult(
                success=False,
                reply_text=f"'{label}' has no command configured in the launch catalogue.",
            )

        # Substitute the query into a URL template, URL-encoding it so it stays
        # confined to the query string.
        if "{query}" in command:
            command = command.replace("{query}", quote(query))

        context.user_print(f"🚀 Відкриваю: {label}")
        try:
            _open(command)
        except FileNotFoundError:
            debug_log(f"launchApp: path not found for '{label}': {command}", "tools")
            return ToolExecutionResult(
                success=False,
                reply_text=f"Couldn't open '{label}' — the file or path was not found. Check its command in config.json.",
            )
        except OSError as e:
            debug_log(f"launchApp: OS error opening '{label}': {e}", "tools")
            return ToolExecutionResult(
                success=False,
                reply_text=f"Couldn't open '{label}': {e}.",
            )

        debug_log(f"launchApp: opened '{label}' via {command}", "tools")
        detail = f" ({query})" if query else ""
        return ToolExecutionResult(success=True, reply_text=f"Opened {label}{detail}.")
