"""
🎨 Jarvis UI Themes

Shared stylesheets for Qt interfaces, matching the Memory Viewer's
deep space theme with amber accents.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

# Color palette
COLORS = {
    "bg_primary": "#0a0b0f",
    "bg_secondary": "#12141a",
    "bg_tertiary": "#1a1d26",
    "bg_card": "#161920",
    "bg_hover": "#1e222c",
    
    "accent_primary": "#f59e0b",
    "accent_secondary": "#fbbf24",
    "accent_glow": "rgba(245, 158, 11, 0.15)",
    "accent_muted": "#92400e",
    
    "text_primary": "#f4f4f5",
    "text_secondary": "#a1a1aa",
    "text_muted": "#71717a",
    
    "border": "#27272a",
    "border_glow": "rgba(245, 158, 11, 0.3)",
    
    "success": "#22c55e",
    "success_light": "#4ade80",
    "warning": "#f59e0b",
    "warning_light": "#fbbf24",
    "error": "#ef4444",
    "error_light": "#f87171",
}


# Comprehensive Qt stylesheet matching the Memory Viewer's design
JARVIS_THEME_STYLESHEET = """
    QMainWindow, QDialog, QWizard, QWizardPage {
        background-color: #0a0b0f;
    }
    
    QWidget {
        background-color: #0a0b0f;
        color: #f4f4f5;
        font-family: '.AppleSystemUIFont', 'Segoe UI', sans-serif;
    }
    
    QLabel {
        color: #f4f4f5;
        background: transparent;
    }
    
    QLabel#title {
        font-size: 18px;
        font-weight: 600;
        color: #f4f4f5;
    }
    
    QLabel#subtitle {
        font-size: 12px;
        color: #71717a;
    }
    
    QLabel#section_title {
        font-size: 16px;
        font-weight: bold;
        color: #fbbf24;
    }
    
    QTextEdit, QPlainTextEdit {
        background-color: #12141a;
        color: #f4f4f5;
        border: 1px solid #27272a;
        border-radius: 10px;
        padding: 12px;
        selection-background-color: rgba(245, 158, 11, 0.3);
        selection-color: #fbbf24;
    }
    
    QTextEdit:focus, QPlainTextEdit:focus {
        border-color: #f59e0b;
    }
    
    QLineEdit {
        background-color: #12141a;
        color: #f4f4f5;
        border: 1px solid #27272a;
        border-radius: 8px;
        padding: 8px 12px;
        selection-background-color: rgba(245, 158, 11, 0.3);
    }
    
    QLineEdit:focus {
        border-color: #f59e0b;
    }
    
    QLineEdit::placeholder {
        color: #71717a;
    }
    
    QPushButton {
        background-color: #1a1d26;
        color: #f4f4f5;
        border: 1px solid #27272a;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 500;
    }
    
    QPushButton:hover {
        background-color: #1e222c;
        border-color: #f59e0b;
        color: #fbbf24;
    }
    
    QPushButton:pressed {
        background-color: rgba(245, 158, 11, 0.15);
    }
    
    QPushButton:disabled {
        background-color: #12141a;
        color: #71717a;
        border-color: #1a1d26;
    }
    
    QPushButton#primary {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #f59e0b, stop:1 #d97706);
        color: #0a0b0f;
        border: none;
        font-weight: 600;
    }
    
    QPushButton#primary:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #fbbf24, stop:1 #f59e0b);
    }
    
    QPushButton#primary:disabled {
        background: #27272a;
        color: #71717a;
    }
    
    QPushButton#danger {
        background-color: #1a1d26;
        border-color: #ef4444;
        color: #ef4444;
    }
    
    QPushButton#danger:hover {
        background-color: rgba(239, 68, 68, 0.15);
        border-color: #f87171;
        color: #f87171;
    }
    
    QComboBox {
        background-color: #12141a;
        color: #f4f4f5;
        border: 1px solid #27272a;
        border-radius: 8px;
        padding: 8px 12px;
        min-width: 120px;
    }
    
    QComboBox:hover {
        border-color: #f59e0b;
    }
    
    QComboBox::drop-down {
        border: none;
        width: 24px;
    }
    
    QComboBox::down-arrow {
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid #71717a;
        margin-right: 8px;
    }
    
    QComboBox QAbstractItemView {
        background-color: #161920;
        color: #f4f4f5;
        border: 1px solid #27272a;
        border-radius: 8px;
        selection-background-color: rgba(245, 158, 11, 0.15);
        selection-color: #fbbf24;
    }
    
    QCheckBox {
        color: #f4f4f5;
        spacing: 8px;
        background: transparent;
    }
    
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border: 1px solid #27272a;
        border-radius: 4px;
        background-color: transparent;
    }
    
    QCheckBox::indicator:hover {
        border-color: #f59e0b;
    }
    
    QCheckBox::indicator:checked {
        background-color: #f59e0b;
        border-color: #f59e0b;
    }
    
    QRadioButton {
        color: #f4f4f5;
        spacing: 8px;
        background: transparent;
    }
    
    QRadioButton::indicator {
        width: 18px;
        height: 18px;
        border: 1px solid #27272a;
        border-radius: 9px;
        background-color: #12141a;
    }
    
    QRadioButton::indicator:hover {
        border-color: #f59e0b;
    }
    
    QRadioButton::indicator:checked {
        background-color: #f59e0b;
        border-color: #f59e0b;
    }
    
    QProgressBar {
        background-color: #12141a;
        border: 1px solid #27272a;
        border-radius: 6px;
        height: 8px;
        text-align: center;
    }
    
    QProgressBar::chunk {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #f59e0b, stop:1 #fbbf24);
        border-radius: 5px;
    }
    
    QScrollArea {
        background: transparent;
        border: none;
    }
    
    QScrollBar:vertical {
        background-color: #12141a;
        width: 10px;
        border-radius: 5px;
        margin: 0;
    }
    
    QScrollBar::handle:vertical {
        background-color: #27272a;
        border-radius: 5px;
        min-height: 30px;
    }
    
    QScrollBar::handle:vertical:hover {
        background-color: #f59e0b;
    }
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
    
    QScrollBar:horizontal {
        background-color: #12141a;
        height: 10px;
        border-radius: 5px;
    }
    
    QScrollBar::handle:horizontal {
        background-color: #27272a;
        border-radius: 5px;
        min-width: 30px;
    }
    
    QScrollBar::handle:horizontal:hover {
        background-color: #f59e0b;
    }
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0;
    }
    
    QGroupBox {
        background-color: #161920;
        border: 1px solid #27272a;
        border-radius: 12px;
        margin-top: 12px;
        padding: 16px;
        padding-top: 24px;
        font-weight: 500;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 16px;
        padding: 0 8px;
        color: #a1a1aa;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    QTabWidget::pane {
        background-color: #161920;
        border: 1px solid #27272a;
        border-radius: 12px;
        top: -1px;
    }
    
    QTabBar::tab {
        background-color: #12141a;
        color: #a1a1aa;
        border: 1px solid #27272a;
        border-bottom: none;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        padding: 10px 20px;
        margin-right: 2px;
    }
    
    QTabBar::tab:selected {
        background-color: #161920;
        color: #fbbf24;
        border-color: #27272a;
        border-bottom-color: #161920;
    }
    
    QTabBar::tab:hover:!selected {
        background-color: #1a1d26;
        color: #f4f4f5;
    }
    
    QSpinBox, QDoubleSpinBox {
        background-color: #12141a;
        color: #f4f4f5;
        border: 1px solid #27272a;
        border-radius: 8px;
        padding: 8px 12px;
    }
    
    QSpinBox:focus, QDoubleSpinBox:focus {
        border-color: #f59e0b;
    }
    
    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {
        background-color: #1a1d26;
        border: none;
        width: 20px;
    }

    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
        background-color: #f59e0b;
    }

    
    QListWidget {
        background-color: #12141a;
        color: #f4f4f5;
        border: 1px solid #27272a;
        border-radius: 10px;
        padding: 8px;
    }
    
    QListWidget::item {
        padding: 8px 12px;
        border-radius: 6px;
    }
    
    QListWidget::item:selected {
        background-color: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
    }
    
    QListWidget::item:hover:!selected {
        background-color: #1e222c;
    }
    
    QMessageBox {
        background-color: #0a0b0f;
    }
    
    QMessageBox QLabel {
        color: #f4f4f5;
    }
    
    QToolTip {
        background-color: #161920;
        color: #f4f4f5;
        border: 1px solid #27272a;
        border-radius: 6px;
        padding: 6px 10px;
    }
    
    QMenu {
        background-color: #161920;
        color: #f4f4f5;
        border: 1px solid #27272a;
        border-radius: 8px;
        padding: 4px;
    }
    
    QMenu::item {
        padding: 8px 24px;
        border-radius: 4px;
    }
    
    QMenu::item:selected {
        background-color: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
    }
    
    QMenu::separator {
        height: 1px;
        background-color: #27272a;
        margin: 4px 8px;
    }
    
    /* Wizard-specific styles */
    QWizard QPushButton {
        min-width: 100px;
    }
    
    QWizard QLabel#qt_watermark_label {
        background: transparent;
    }
    
    /* Card-style container */
    QFrame#card {
        background-color: #161920;
        border: 1px solid #27272a;
        border-radius: 12px;
        padding: 16px;
    }
"""


_CHECKMARK_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18">'
    '<path d="M4 9l3.5 3.5L14 5" stroke="#0a0b0f" stroke-width="2.5" '
    'stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>'
)

_RADIO_DOT_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18">'
    '<circle cx="9" cy="9" r="4" fill="#0a0b0f"/></svg>'
)

_ARROW_UP_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12">'
    '<path d="M2.5 7.5L6 4l3.5 3.5" stroke="#a1a1aa" stroke-width="1.5" '
    'stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>'
)

_ARROW_DOWN_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12">'
    '<path d="M2.5 4.5L6 8l3.5-3.5" stroke="#a1a1aa" stroke-width="1.5" '
    'stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>'
)

# Cached icon paths (created once per process)
_icon_dir: str | None = None


_ICON_STYLESHEET_TEMPLATE = """
    QCheckBox::indicator:checked {{
        image: url({check});
    }}
    QRadioButton::indicator:checked {{
        image: url({radio});
    }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
        image: url({arrow_up});
        width: 10px;
        height: 10px;
    }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        image: url({arrow_down});
        width: 10px;
        height: 10px;
    }}
"""


def _ensure_icons() -> dict[str, str]:
    """Write indicator SVGs to a temp directory, return {name: path} mapping."""
    global _icon_dir
    if _icon_dir is None:
        _icon_dir = tempfile.mkdtemp(prefix="jarvis_theme_")

    icons = {
        "check": _CHECKMARK_SVG,
        "radio": _RADIO_DOT_SVG,
        "arrow_up": _ARROW_UP_SVG,
        "arrow_down": _ARROW_DOWN_SVG,
    }
    paths: dict[str, str] = {}
    for name, svg in icons.items():
        path = os.path.join(_icon_dir, f"{name}.svg")
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write(svg)
        paths[name] = path.replace("\\", "/")
    return paths


def apply_theme(widget, colors: dict | None = None) -> None:
    """Apply the Jarvis theme to a Qt widget, including SVG-based indicator icons.

    When ``colors`` is given, the stylesheet is regenerated from those
    colours so a theme change applies immediately, without a restart.
    """
    icons = _ensure_icons()
    icon_css = _ICON_STYLESHEET_TEMPLATE.format(**icons)
    if colors is None:
        widget.setStyleSheet(JARVIS_THEME_STYLESHEET + icon_css)
    else:
        widget.setStyleSheet(build_stylesheet(colors) + icon_css)


# ---------------------------------------------------------------------------
# Theme store: built-in themes and user presets
# ---------------------------------------------------------------------------

DEFAULT_THEME_NAME = "Jarvis (базова)"

# Built-in presets: {name: {color key: override}}. Overrides are merged over
# COLORS, so a preset only lists the colours it changes. Names are Ukrainian
# (user-facing). Do not edit these names: user presets may not shadow them.
BUILTIN_THEMES: dict[str, dict[str, str]] = {
    DEFAULT_THEME_NAME: {},
    "Смарагдова": {
        "accent_primary": "#10b981",
        "accent_secondary": "#34d399",
        "accent_muted": "#065f46",
    },
    "Багряна ніч": {
        "accent_primary": "#f43f5e",
        "accent_secondary": "#fb7185",
        "accent_muted": "#9f1239",
    },
    "Лазурна": {
        "accent_primary": "#38bdf8",
        "accent_secondary": "#7dd3fc",
        "accent_muted": "#075985",
    },
}

# Colour keys the theme editor exposes (single hex values only; the rgba
# glow entries are derived from accent_primary at stylesheet build time).
EDITABLE_COLOR_KEYS = (
    "accent_primary",
    "accent_secondary",
    "bg_primary",
    "bg_secondary",
    "bg_tertiary",
    "bg_card",
    "bg_hover",
    "text_primary",
    "text_secondary",
    "text_muted",
    "border",
)

# Ukrainian labels for the colour pickers (no em dashes, per house style).
THEME_COLOR_LABELS = {
    "accent_primary": "Акцент",
    "accent_secondary": "Світлий акцент",
    "bg_primary": "Фон",
    "bg_secondary": "Фон панелей",
    "bg_card": "Фон карток",
    "text_primary": "Текст",
    "text_secondary": "Другорядний текст",
    "border": "Межі",
}

# Base hex of every solid colour, used for substitution when rebuilding
# the stylesheet. Shared values (accent_primary also drives warning) move
# together: the stylesheet stores literal hexes, so they cannot be split.
_BASE_HEX = {key: value for key, value in COLORS.items() if not value.startswith("rgba")}

_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

_GLOW_ALPHA_15 = "rgba(245, 158, 11, 0.15)"
_GLOW_ALPHA_30 = "rgba(245, 158, 11, 0.3)"


def _default_themes_path() -> Path:
    """Return the default preset store path, mirroring the notes store."""
    return Path.home() / ".local" / "share" / "jarvis" / "themes.json"


def get_themes_path() -> Path:
    """Resolve the themes.json path; JARVIS_THEMES_PATH overrides it (tests)."""
    env_path = os.environ.get("JARVIS_THEMES_PATH")
    if env_path:
        return Path(env_path)
    return _default_themes_path()


def validate_hex(value: object) -> bool:
    """True when ``value`` is a #rgb or #rrggbb colour literal."""
    if not isinstance(value, str):
        return False
    return bool(_HEX_RE.match(value.strip()))


def normalise_hex(value: str) -> str:
    """Lower-case a hex colour and expand #abc to #aabbcc."""
    trimmed = value.strip().lower()
    if len(trimmed) == 4:
        trimmed = "#" + "".join(ch * 2 for ch in trimmed[1:])
    return trimmed


def load_theme_store(path: Path | str | None = None) -> dict:
    """Load {active_theme, custom_presets} from themes.json, tolerating
    missing or corrupt files by returning the empty default store."""
    path = Path(path) if path else get_themes_path()
    store: dict = {"active_theme": DEFAULT_THEME_NAME, "custom_presets": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return store
    if not isinstance(data, dict):
        return store
    presets = data.get("custom_presets")
    if isinstance(presets, dict):
        store["custom_presets"] = {
            str(name): entry for name, entry in presets.items() if isinstance(entry, dict)
        }
    active = data.get("active_theme")
    if isinstance(active, str) and active:
        store["active_theme"] = active
    return store


def save_theme_store(store: dict, path: Path | str | None = None) -> None:
    """Persist the store atomically: temp file in the same dir, os.replace."""
    path = Path(path) if path else get_themes_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def get_theme_colors(name: str, path: Path | str | None = None) -> dict:
    """Return the full colour palette for a built-in or custom theme."""
    if name in BUILTIN_THEMES:
        colors = dict(COLORS)
        colors.update(BUILTIN_THEMES[name])
        return colors
    preset = load_theme_store(path=path)["custom_presets"].get(name)
    if isinstance(preset, dict):
        colors = dict(COLORS)
        colors.update({
            key: value for key, value in preset.get("colors", {}).items()
            if key in _BASE_HEX
        })
        return colors
    return dict(COLORS)


def list_theme_names(path: Path | str | None = None) -> list:
    """Built-in theme names followed by the user's custom presets."""
    custom = sorted(load_theme_store(path=path)["custom_presets"])
    return list(BUILTIN_THEMES) + custom


def save_custom_preset(
    name: str, colors: dict, path: Path | str | None = None
) -> str:
    """Save a user preset under ``name``; returns the normalised name.

    Only editable colour keys are stored, hex values are validated and
    normalised. Raises ValueError on an empty name, a name that shadows a
    built-in theme, or an invalid hex value.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("Введи назву пресету.")
    if name in BUILTIN_THEMES:
        raise ValueError(f"Назва «{name}» вже зайнята вбудованою темою.")
    clean: dict[str, str] = {}
    for key in EDITABLE_COLOR_KEYS:
        if key in colors and colors[key]:
            value = str(colors[key]).strip()
            if not validate_hex(value):
                raise ValueError(f"Некоректний колір для «{key}»: {value}")
            clean[key] = normalise_hex(value)
    store = load_theme_store(path=path)
    store["custom_presets"][name] = {"base": DEFAULT_THEME_NAME, "colors": clean}
    save_theme_store(store, path=path)
    return name


def delete_custom_preset(name: str, path: Path | str | None = None) -> bool:
    """Remove a user preset; built-in and unknown names are refused."""
    if name in BUILTIN_THEMES:
        return False
    store = load_theme_store(path=path)
    if name not in store["custom_presets"]:
        return False
    del store["custom_presets"][name]
    if store["active_theme"] == name:
        store["active_theme"] = DEFAULT_THEME_NAME
    save_theme_store(store, path=path)
    return True


def set_active_theme(name: str, path: Path | str | None = None) -> None:
    """Persist the active theme selection."""
    store = load_theme_store(path=path)
    store["active_theme"] = name
    save_theme_store(store, path=path)


def get_active_theme_name(path: Path | str | None = None) -> str:
    """Return the persisted active theme name."""
    return load_theme_store(path=path)["active_theme"]


def _derive_glow(hex_value: str, alpha: str) -> str:
    """Build an rgba(...) glow string from a hex colour."""
    digits = hex_value.lstrip("#")
    r, g, b = int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def build_stylesheet(colors: dict) -> str:
    """Regenerate the theme stylesheet for the given colours.

    Literal base hexes in JARVIS_THEME_STYLESHEET are substituted with the
    requested values; untouched colours keep their base values. The amber
    rgba glows are re-derived from accent_primary.
    """
    css = JARVIS_THEME_STYLESHEET
    accent = normalise_hex(str(colors.get("accent_primary", COLORS["accent_primary"])))
    for key, base in _BASE_HEX.items():
        value = colors.get(key, base)
        if value != base:
            css = css.replace(base, value)
    if accent != COLORS["accent_primary"]:
        css = css.replace(_GLOW_ALPHA_15, _derive_glow(accent, "0.15"))
        css = css.replace(_GLOW_ALPHA_30, _derive_glow(accent, "0.3"))
    return css

