"""Unit tests for game mode detection and keep-alive gating."""

import types
import pytest

from jarvis import game_mode as gm


class _Proc:
    def __init__(self, name, exe):
        self.info = {"name": name, "exe": exe}


@pytest.fixture(autouse=True)
def _reset_flag():
    gm._set_active(False)
    yield
    gm._set_active(False)


@pytest.mark.unit
def test_keep_alive_tracks_flag():
    assert gm.is_active() is False
    assert gm.keep_alive("30m") == "30m"
    assert gm._set_active(True) is True
    assert gm.is_active() is True
    assert gm.keep_alive("30m") == "0"
    # No-op when already in that state.
    assert gm._set_active(True) is False


@pytest.mark.unit
def test_detect_game_by_configured_process_name(monkeypatch):
    monkeypatch.setattr(
        gm.psutil, "process_iter",
        lambda attrs=None: [_Proc("MyGame.exe", "C:/x/MyGame.exe"), _Proc("chrome.exe", "C:/chrome.exe")],
    )
    cfg = types.SimpleNamespace(game_process_names=["mygame.exe"])
    assert gm.detect_game(cfg) == "MyGame.exe"


@pytest.mark.unit
def test_detect_game_by_steam_install_path(monkeypatch):
    monkeypatch.setattr(
        gm.psutil, "process_iter",
        lambda attrs=None: [
            _Proc("witcher3.exe", r"D:\SteamLibrary\steamapps\common\The Witcher 3\bin\witcher3.exe"),
        ],
    )
    cfg = types.SimpleNamespace(game_process_names=[])
    assert gm.detect_game(cfg) == "witcher3.exe"


@pytest.mark.unit
def test_steam_client_itself_is_not_a_game(monkeypatch):
    # The Steam client lives outside steamapps/common — must not trip game mode.
    monkeypatch.setattr(
        gm.psutil, "process_iter",
        lambda attrs=None: [
            _Proc("steam.exe", r"C:\Program Files (x86)\Steam\steam.exe"),
            _Proc("explorer.exe", r"C:\Windows\explorer.exe"),
        ],
    )
    cfg = types.SimpleNamespace(game_process_names=[])
    assert gm.detect_game(cfg) is None
