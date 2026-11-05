"""
Tests for the theme editor: preset persistence, validation and live styling.

Covers the theme store in ``desktop_app.themes`` (custom presets, atomic
writes, hex validation) and the theme editor wiring in the settings window.
GUI is exercised through the shared ``qapp`` fixture only where needed.
"""

import json
import os
from pathlib import Path

import pytest

from desktop_app import themes
from desktop_app.settings_window import CATEGORIES


@pytest.fixture
def store_path(tmp_path):
    """Isolated themes.json path for each test."""
    return tmp_path / "themes.json"


class TestHexValidation:
    """Validation of user-supplied colour values."""

    def test_accepts_six_digit_hex(self):
        assert themes.validate_hex("#f59e0b") is True

    def test_accepts_three_digit_hex(self):
        assert themes.validate_hex("#abc") is True

    def test_accepts_uppercase(self):
        assert themes.validate_hex("#F59E0B") is True

    def test_rejects_named_colour(self):
        assert themes.validate_hex("red") is False

    def test_rejects_wrong_length(self):
        assert themes.validate_hex("#12345") is False

    def test_rejects_non_hex_digits(self):
        assert themes.validate_hex("#gggggg") is False

    def test_rejects_empty(self):
        assert themes.validate_hex("") is False

    def test_rejects_rgba(self):
        assert themes.validate_hex("rgba(245, 158, 11, 0.15)") is False

    def test_normalise_expands_short_hex(self):
        assert themes.normalise_hex("#abc") == "#aabbcc"


class TestPresetPersistence:
    """Saving, loading and deleting custom presets."""

    def test_save_creates_json_file(self, store_path):
        themes.save_custom_preset("Моя тема", {"accent_primary": "#ff0000"},
                                  path=store_path)
        data = json.loads(store_path.read_text(encoding="utf-8"))
        assert "Моя тема" in data["custom_presets"]

    def test_save_stores_only_editable_keys(self, store_path):
        themes.save_custom_preset(
            "Моя тема",
            {"accent_primary": "#ff0000", "success": "#00ff00"},
            path=store_path,
        )
        data = json.loads(store_path.read_text(encoding="utf-8"))
        stored = data["custom_presets"]["Моя тема"]["colors"]
        assert "accent_primary" in stored
        assert "success" not in stored

    def test_save_rejects_invalid_hex(self, store_path):
        with pytest.raises(ValueError):
            themes.save_custom_preset("Моя тема", {"accent_primary": "red"},
                                      path=store_path)

    def test_save_rejects_empty_name(self, store_path):
        with pytest.raises(ValueError):
            themes.save_custom_preset("   ", {"accent_primary": "#ff0000"},
                                      path=store_path)

    def test_save_rejects_builtin_name(self, store_path):
        builtin = next(iter(themes.BUILTIN_THEMES))
        with pytest.raises(ValueError):
            themes.save_custom_preset(builtin, {"accent_primary": "#ff0000"},
                                      path=store_path)

    def test_save_overwrites_existing_preset(self, store_path):
        themes.save_custom_preset("Моя тема", {"accent_primary": "#ff0000"},
                                  path=store_path)
        themes.save_custom_preset("Моя тема", {"accent_primary": "#00ff00"},
                                  path=store_path)
        colors = themes.get_theme_colors("Моя тема", path=store_path)
        assert colors["accent_primary"] == "#00ff00"

    def test_save_normalises_short_hex(self, store_path):
        themes.save_custom_preset("Моя тема", {"accent_primary": "#f0a"},
                                  path=store_path)
        colors = themes.get_theme_colors("Моя тема", path=store_path)
        assert colors["accent_primary"] == "#ff00aa"

    def test_load_missing_file_returns_defaults(self, store_path):
        store = themes.load_theme_store(path=store_path)
        assert store["custom_presets"] == {}
        assert store["active_theme"] == themes.DEFAULT_THEME_NAME

    def test_load_corrupt_json_returns_defaults(self, store_path):
        store_path.write_text("{not valid json", encoding="utf-8")
        store = themes.load_theme_store(path=store_path)
        assert store["custom_presets"] == {}

    def test_preset_roundtrip_merges_over_base(self, store_path):
        base = themes.get_theme_colors(themes.DEFAULT_THEME_NAME)
        themes.save_custom_preset("Моя тема", {"accent_primary": "#123456"},
                                  path=store_path)
        colors = themes.get_theme_colors("Моя тема", path=store_path)
        assert colors["accent_primary"] == "#123456"
        assert colors["text_primary"] == base["text_primary"]

    def test_delete_custom_preset(self, store_path):
        themes.save_custom_preset("Моя тема", {"accent_primary": "#ff0000"},
                                  path=store_path)
        assert themes.delete_custom_preset("Моя тема", path=store_path) is True
        assert themes.load_theme_store(path=store_path)["custom_presets"] == {}

    def test_delete_builtin_returns_false(self, store_path):
        builtin = next(iter(themes.BUILTIN_THEMES))
        assert themes.delete_custom_preset(builtin, path=store_path) is False

    def test_delete_missing_returns_false(self, store_path):
        assert themes.delete_custom_preset("Немає такої", path=store_path) is False

    def test_list_theme_names_includes_custom(self, store_path):
        themes.save_custom_preset("Моя тема", {"accent_primary": "#ff0000"},
                                  path=store_path)
        names = themes.list_theme_names(path=store_path)
        assert next(iter(themes.BUILTIN_THEMES)) in names
        assert "Моя тема" in names


class TestAtomicWrite:
    """Preset store writes must be atomic (temp file + os.replace)."""

    def test_save_uses_temp_then_replace(self, store_path, monkeypatch):
        calls = []
        real_replace = os.replace

        def fake_replace(src, dst):
            calls.append((Path(src), Path(dst)))
            real_replace(src, dst)

        monkeypatch.setattr(themes.os, "replace", fake_replace)
        themes.save_theme_store(
            {"active_theme": themes.DEFAULT_THEME_NAME, "custom_presets": {}},
            path=store_path,
        )
        assert len(calls) == 1
        src, dst = calls[0]
        assert dst == store_path
        assert src != dst
        assert src.parent == dst.parent
        assert not src.exists()

    def test_save_leaves_no_temp_files(self, store_path):
        themes.save_custom_preset("Моя тема", {"accent_primary": "#ff0000"},
                                  path=store_path)
        leftovers = [p for p in store_path.parent.iterdir() if p != store_path]
        assert leftovers == []


class TestActiveTheme:
    """Active theme selection persists across load/save cycles."""

    def test_set_active_theme_persists(self, store_path):
        themes.set_active_theme("Смарагдова", path=store_path)
        assert themes.get_active_theme_name(path=store_path) == "Смарагдова"

    def test_active_theme_survives_preset_save(self, store_path):
        themes.set_active_theme("Смарагдова", path=store_path)
        themes.save_custom_preset("Моя тема", {"accent_primary": "#ff0000"},
                                  path=store_path)
        assert themes.get_active_theme_name(path=store_path) == "Смарагдова"


class TestStylesheetGeneration:
    """Live stylesheet generation from edited colours."""

    def test_builtin_theme_overrides_accent(self):
        colors = themes.get_theme_colors("Смарагдова")
        assert colors["accent_primary"] != themes.COLORS["accent_primary"]

    def test_unknown_theme_falls_back_to_base(self):
        colors = themes.get_theme_colors("неіснуюча тема")
        assert colors == themes.COLORS

    def test_build_stylesheet_replaces_accent(self):
        colors = dict(themes.COLORS)
        colors["accent_primary"] = "#ff0000"
        css = themes.build_stylesheet(colors)
        assert "#ff0000" in css
        assert themes.COLORS["accent_primary"] not in css

    def test_build_stylesheet_keeps_untouched_colors(self):
        colors = dict(themes.COLORS)
        colors["accent_primary"] = "#ff0000"
        css = themes.build_stylesheet(colors)
        assert themes.COLORS["bg_primary"] in css

    def test_build_stylesheet_derives_glow(self):
        colors = dict(themes.COLORS)
        colors["accent_primary"] = "#ff0000"
        css = themes.build_stylesheet(colors)
        assert "rgba(255, 0, 0, 0.15)" in css


class TestApplyTheme:
    """apply_theme stays backward compatible and accepts custom colours."""

    def test_default_call_unchanged(self, qapp):
        from PyQt6.QtWidgets import QWidget
        w = QWidget()
        themes.apply_theme(w)
        assert themes.COLORS["accent_primary"] in w.styleSheet()

    def test_custom_colors_call(self, qapp):
        from PyQt6.QtWidgets import QWidget
        w = QWidget()
        colors = dict(themes.COLORS)
        colors["accent_primary"] = "#ff0000"
        themes.apply_theme(w, colors=colors)
        assert "#ff0000" in w.styleSheet()


class TestUkrainianLabels:
    """User-facing theme names are Ukrainian, without em dashes."""

    def test_builtin_names_are_ukrainian(self):
        for name in themes.BUILTIN_THEMES:
            assert any("\u0400" <= ch <= "\u04ff" for ch in name), name

    def test_color_labels_are_ukrainian(self):
        for label in themes.THEME_COLOR_LABELS.values():
            assert any("\u0400" <= ch <= "\u04ff" for ch in label), label

    def test_no_em_dash_in_labels(self):
        for label in themes.THEME_COLOR_LABELS.values():
            assert "\u2014" not in label


class TestSettingsWindowIntegration:
    """The settings window exposes the appearance category."""

    def test_appearance_category_registered(self):
        keys = [key for key, _ in CATEGORIES]
        assert "appearance" in keys

    def test_appearance_label_is_ukrainian(self):
        label = dict(CATEGORIES)["appearance"]
        assert any("\u0400" <= ch <= "\u04ff" for ch in label)
