# themes.spec.md

## Purpose

Shared theme module for all desktop windows: the base colour palette
(`COLORS`), the full Qt stylesheet (`JARVIS_THEME_STYLESHEET`), SVG-based
indicator icons, and the theme store (built-in themes plus the user's
custom presets). Every window must theme itself through `apply_theme()`
from this module.

## Theme store

- Storage: `~/.local/share/jarvis/themes.json` (mirrors the notes store
  path convention); `JARVIS_THEMES_PATH` env var overrides it for tests.
- Format: `{"active_theme": str, "custom_presets": {name: {"base": str,
  "colors": {key: hex}}}}`. Presets store only `EDITABLE_COLOR_KEYS`,
  merged over `COLORS` on read.
- Writes are atomic: temp file in the same directory, then `os.replace`.
- Corrupt or missing JSON degrades softly to the default store; it is
  never fatal and never overwrites the file until the next save.
- Custom presets may not shadow built-in theme names; deleting a built-in
  or unknown name is refused (`delete_custom_preset` returns False).
- Deleting the active preset resets `active_theme` to
  `DEFAULT_THEME_NAME`.

## Colour validation

- `validate_hex` accepts `#rgb` and `#rrggbb` only; named colours, rgba
  strings and wrong lengths are rejected.
- `normalise_hex` lower-cases and expands `#abc` to `#aabbcc` so stored
  values are uniform.

## Built-in themes

`BUILTIN_THEMES` maps Ukrainian names to sparse override dicts (only the
colours they change). The base theme is `DEFAULT_THEME_NAME`. Names are
user-facing: Ukrainian, no em dashes.

## Live restyle

- `build_stylesheet(colors)` regenerates the stylesheet by substituting
  the literal base hexes in `JARVIS_THEME_STYLESHEET` with the requested
  values; untouched colours keep their base values. The amber rgba glows
  are re-derived from `accent_primary`.
- Limitation: colours that share a base hex in the stylesheet (e.g.
  `accent_primary` and `warning`) move together, because the stylesheet
  stores literal values and they cannot be addressed separately.
- `apply_theme(widget, colors=None)` keeps the original single-argument
  contract for existing callers; passing `colors` restyles the widget
  immediately, without a restart.

## Settings window integration

The `appearance` category ("🎨 Вигляд і тема") renders a custom page
(like `mcps`): theme combo (built-ins plus `★`-marked custom presets),
colour-picker swatches for `THEME_COLOR_LABELS`, and apply/save/delete
preset actions. Applying re-runs `apply_theme` on the live window and
persists the active theme; other windows pick the theme up on open.
