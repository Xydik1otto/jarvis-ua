"""askAi tool: delegate a question to another locally installed model.

The model can only pick a ``model`` name from the catalogue in
``cfg.ask_ai_targets`` — it never supplies a raw model string or an
endpoint. Catalogue entries carry the Ollama model tag; the tool resolves
the spoken/typed name with the same rapidfuzz match used by launchApp and
calls the local server through the pluggable LLM backend factory.

VRAM contract: the call is made with ``keep_alive: 0`` so the delegated
model is unloaded from VRAM immediately after answering. Only the chat
model stays resident (8 GB VRAM cannot hold two 7B models).
"""

from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz

from ...debug import debug_log
from ...llm import get_llm_backend, extract_text_from_response
from ..base import Tool, ToolContext
from ..types import ToolExecutionResult


# Fuzzy score (0-100) a spoken model name must reach against a catalogue
# entry's name or one of its aliases to count as a match. Same threshold
# as launchApp: tolerates Whisper mishearings and case/spacing noise
# without resolving to the wrong model.
_MATCH_THRESHOLD = 78

# Delegated answers come from a cold-loaded model, so they pay a load
# plus a full generation. Give them a generous budget.
_CALL_TIMEOUT_SEC = 120.0

# System prompt for the delegated call: plain and neutral. The answer is
# raw data; the chat model phrases the final reply for the user.
_DELEGATED_SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the question directly and "
    "completely. Reply in the language the question was asked in."
)


def _resolve_model(name: str, targets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the best catalogue entry for a spoken model name, or None.

    Matches against each entry's ``name`` plus every alias, taking the
    higher of full-ratio and partial-ratio (language agnostic, works for
    Cyrillic and Latin).
    """
    query = (name or "").strip().lower()
    if not query:
        return None

    # Exact match wins outright: without this, "квін" ties at 100 between
    # the "Qwen" alias and a partial hit inside "Qwen Coder", and the
    # first catalogue entry would silently win the tie.
    for entry in targets:
        candidates = [entry.get("name", "")] + list(entry.get("aliases", []) or [])
        for cand in candidates:
            if (cand or "").strip().lower() == query:
                return entry

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


class AskAiTool(Tool):
    """Ask a question to another locally installed model from the catalogue."""

    @property
    def name(self) -> str:
        return "askAi"

    @property
    def description(self) -> str:
        return (
            "Ask another locally installed AI model to answer a question the "
            "user's chat model may be weaker at (e.g. code). Use for ANY "
            "'спитай інший ШІ' / 'ask another AI' / 'питай <model>' request "
            "where the user names a different assistant or model. Pass "
            "model='<which AI, as the user named it>' and prompt='<the full "
            "question to delegate>'. Only catalogued models can be used; "
            "never invent a model name."
        )

    @property
    def inputSchema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "Which AI to ask, as the user named it (e.g. 'DeepSeek', 'Qwen Coder'). Matched against the user's ask_ai_targets catalogue.",
                },
                "prompt": {
                    "type": "string",
                    "description": "The full question or task to delegate to that model.",
                },
            },
            "required": ["model", "prompt"],
        }

    def run(self, args: Optional[Dict[str, Any]], context: ToolContext) -> ToolExecutionResult:
        model = ""
        prompt = ""
        if args and isinstance(args, dict):
            model = str(args.get("model") or "").strip()
            prompt = str(args.get("prompt") or "").strip()

        if not getattr(context.cfg, "ask_ai_enabled", False):
            return ToolExecutionResult(
                success=False,
                reply_text="Delegating questions to other models is disabled ('ask_ai_enabled' is false in config.json).",
            )

        if not model or not prompt:
            return ToolExecutionResult(
                success=False,
                reply_text="Both 'model' (which AI to ask) and 'prompt' (the question) are required.",
            )

        targets: List[Dict[str, Any]] = list(getattr(context.cfg, "ask_ai_targets", []) or [])
        if not targets:
            return ToolExecutionResult(
                success=False,
                reply_text=(
                    "The AI catalogue is empty. Add entries under 'ask_ai_targets' "
                    "in config.json (name, aliases, model) so I can delegate "
                    "questions to other local models."
                ),
            )

        entry = _resolve_model(model, targets)
        if entry is None:
            known = ", ".join(str(t.get("name", "")) for t in targets if t.get("name"))
            return ToolExecutionResult(
                success=False,
                reply_text=f"I don't have '{model}' in the AI catalogue. Known models: {known}.",
            )

        ollama_model = str(entry.get("model", "")).strip()
        label = str(entry.get("name", model))
        if not ollama_model:
            return ToolExecutionResult(
                success=False,
                reply_text=f"'{label}' has no model configured in the ask_ai_targets catalogue.",
            )

        context.user_print(f"🤖 Питаю {label}…")
        backend = get_llm_backend(context.cfg)
        response = backend.chat(
            ollama_model,
            messages=[
                {"role": "system", "content": _DELEGATED_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            timeout_sec=_CALL_TIMEOUT_SEC,
            # Unload the delegated model from VRAM right after the call:
            # only one model can stay resident on this hardware.
            extra_options={"keep_alive": 0},
        )

        answer = extract_text_from_response(response) if isinstance(response, dict) else None
        if not answer or not answer.strip():
            debug_log(
                f"askAi: no answer from '{label}' ({ollama_model}) — timeout or empty response",
                "tools",
            )
            return ToolExecutionResult(
                success=False,
                reply_text=f"{label} did not answer (timeout or error). Ask again or try another model.",
            )

        debug_log(f"askAi: delegated to '{label}' ({ollama_model}), {len(answer)} chars", "tools")
        # Raw data return: the delegated answer is passed through untouched;
        # the chat model formats the final reply for the user.
        return ToolExecutionResult(success=True, reply_text=answer)
