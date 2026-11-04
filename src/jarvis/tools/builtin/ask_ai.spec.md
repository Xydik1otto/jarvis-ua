# askAi tool

## Purpose

Delegate a question to another locally installed AI model (Ollama) in
response to "спитай інший ШІ" / "ask another AI" / "питай <model>"
utterances, typically when the user wants a model that is stronger at a
given domain (e.g. code) than the active chat model.

## Catalogue-only model selection (`cfg.ask_ai_targets`)

The model never supplies a raw model string or endpoint. It only picks a
`model` target name, which is fuzzy-matched against the catalogue in
`cfg.ask_ai_targets`. Each entry:

- `name` — canonical display name (used in replies and as a match
  candidate).
- `aliases` — spoken variants, including Ukrainian and common Whisper
  mishearings.
- `model` — the Ollama model tag sent on the wire (e.g.
  `deepseek-coder-v2`). Offline-first: local Ollama models only; cloud
  APIs are not permitted targets.

Defaults seed three targets: `deepseek-coder-v2` (code questions),
`qwen2.5-coder:7b` (code), `qwen2.5:7b-instruct` (general). The feature
is gated by `ask_ai_enabled` (default true).

## Resolution

`_resolve_model` first tries an exact case-insensitive match on any name
or alias (so "квін" resolves to the entry aliased exactly "квін", not to
a partial hit inside "Qwen Coder"), then falls back to the higher of
`fuzz.ratio` and `fuzz.partial_ratio` across names and aliases with the
same threshold as launchApp (score >= 78). Language agnostic (Cyrillic
and Latin). Returns None below threshold so the tool reports the model
as unknown rather than calling the wrong one.

## The delegated call

Routed through `get_llm_backend(cfg)` (provider-agnostic, see
[src/jarvis/llm/llm.spec.md](../../jarvis/llm/llm.spec.md)). The call is a
plain system+user chat with:

- `keep_alive: 0` — the delegated model is unloaded from VRAM
  immediately after answering. Only one model can stay resident on the
  target hardware (8 GB VRAM): the chat model (~6.25 GB resident) and a
  second ~5 GB model cannot coexist. Trade-off: while the delegated call
  runs, both models briefly compete for VRAM and the cold load adds
  seconds to the first answer. Accepted trade-off; do not "fix" by
  keeping the second model warm.
- A generous timeout (120 s) because a cold load plus a full generation
  is slower than the warm chat path.

## Result contract

- Success: the delegated answer is returned **raw** — no LLM processing,
  no trimming, no formatting on the tool side. The chat model phrases
  the final reply in the user's language (raw-data tool principle).
- Disabled (`ask_ai_enabled: false`): honest refusal, no LLM call.
- Missing/empty `model` or `prompt`: error asking for both.
- Empty catalogue: guidance to populate `ask_ai_targets`.
- Unknown model: lists the known catalogue names, no call is made.
- Timeout / empty response: honest failure naming the target; no
  fabricated answer.

## LLM contexts map

This is a tool-specific LLM call (context #15 in
[docs/llm_contexts.md](../../../docs/llm_contexts.md)): one call per
`askAi` invocation, on the user-chosen catalogue model.
