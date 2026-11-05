"""
Tests for the shared desktop theme module (regression guard).

The theme editor lives in tests/test_theme_editor.py; this file keeps the
original module contract covered: default stylesheet application and the
indicator icon generation.
"""

from desktop_app import themes


class TestApplyThemeBackwardCompat:
    """apply_theme must keep working for existing callers."""

    def test_applies_default_stylesheet(self, qapp):
        from PyQt6.QtWidgets import QWidget
        w = QWidget()
        themes.apply_theme(w)
        css = w.styleSheet()
        assert themes.COLORS["bg_primary"] in css
        assert themes.COLORS["accent_primary"] in css

    def test_stylesheet_contains_icon_rules(self, qapp):
        from PyQt6.QtWidgets import QWidget
        w = QWidget()
        themes.apply_theme(w)
        assert "QCheckBox::indicator:checked" in w.styleSheet()

    def test_module_exports_unchanged(self):
        assert themes.JARVIS_THEME_STYLESHEET
        assert set(themes.COLORS) >= {
            "bg_primary", "accent_primary", "text_primary", "border",
        }
