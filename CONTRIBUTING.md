# Contributing to jarvis-ua

[English](CONTRIBUTING.md) | [Українська](CONTRIBUTING.uk.md)

## Welcome

This is the Ukrainian-localised fork of [isair/jarvis](https://github.com/isair/jarvis): a 100% local AI voice assistant whose voice pipeline, desktop UI, setup wizard and LLM prompt layer are localised to Ukrainian.

If you want to contribute to Jarvis itself (features, upstream architecture, non-Ukrainian fixes), please contribute upstream at [isair/jarvis](https://github.com/isair/jarvis). This fork tracks upstream and exists to ship and maintain the Ukrainian build.

## Getting started

1. Fork this repository, then clone your fork:

   ```bash
   git clone https://github.com/<your-username>/jarvis-ua.git
   cd jarvis-ua
   ```

2. Create a Python 3.11 virtual environment (or use the helper scripts in `scripts/`):

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. [Ollama](https://ollama.com) is required: Jarvis runs its LLMs through it locally.

4. Run from source:

   ```bash
   bash scripts/run_macos.sh    # macOS
   bash scripts/run_linux.sh    # Linux
   pwsh -ExecutionPolicy Bypass -File scripts/run_windows.ps1  # Windows
   ```

## Development rules

- **TDD**: write the failing test first, then implement the fix. Tests should verify **behaviours**, not implementation details.
- **Specs**: every code change either adheres to the `*.spec.md` spec file next to the code, or updates that spec in the same change. Search for related spec files before starting any work.
- **Prompt changes need an eval case**: any change to LLM prompts (system prompts, tool incentives, constraints) must be verified against a relevant eval case. If no eval exists for the behaviour being changed, write one first; it should demonstrate the improvement.
- **Commit style**: [Conventional Commits](https://www.conventionalcommits.org/) (e.g. `feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- **Branches**: target the repository's default branch with your feature branches and PRs.

## Ukrainian localisation rules

- User-facing strings are in Ukrainian, informal «ти», and contain **no em dashes** (use a comma, full stop, colon, or parentheses instead).
- Code comments and identifiers are in **British English** (e.g. "colour" not "color", "behaviour" not "behavior").
- Never hardcode language patterns beyond the deliberate Ukrainian-first prompt layer: the assistant is designed to support any number of languages, so keep detection and routing language-agnostic.

## Testing

Run the unit suite locally:

```bash
pytest -q -m unit
```

CI runs on `ubuntu-24.04` with Python 3.11 and a PulseAudio daemon (the headless runner has no audio server; tests that import `sounddevice` need PulseAudio started before pytest).

Two recent gotchas worth knowing before you open a PR:

- **pydantic must stay `<2.14`** for `mcp 1.13.1`: mcp imports a pydantic-internal symbol removed in pydantic 2.14. CI installs fresh dependency versions, so a pin that works locally can still break CI when transitive deps advance; pin the breaking dependency in `requirements.txt` rather than upgrading mcp.
- **Do not commit files containing literal secret-looking strings** (e.g. real-format AWS example keys). GitHub secret scanning will block the push. Where tests need such values, assemble them at runtime from fragments instead; see `tests/test_redact_extended.py` for the pattern.

## PR checklist

- [ ] Tests pass (`pytest -q -m unit` locally; CI is green)
- [ ] New tools have a spec file (`*.spec.md` next to the code) and tests
- [ ] README(s) updated for any user-facing change (both [README.md](README.md) and [README.uk.md](README.uk.md) when the change affects Ukrainian users)
- [ ] Ukrainian copy reviewed: informal «ти», no em dashes, natural technical wording
