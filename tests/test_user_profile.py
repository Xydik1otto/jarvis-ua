"""Unit tests for the explicit user-profile personalisation block."""

import types
import pytest

from jarvis.reply.engine import build_user_profile_block


@pytest.mark.unit
def test_empty_or_missing_profile_returns_none():
    assert build_user_profile_block(types.SimpleNamespace()) is None
    assert build_user_profile_block(types.SimpleNamespace(user_profile={})) is None
    assert build_user_profile_block(
        types.SimpleNamespace(user_profile={"communication_style": "", "goals": "  "})
    ) is None


@pytest.mark.unit
def test_style_only_block():
    cfg = types.SimpleNamespace(user_profile={"communication_style": "Коротко, на «ти»"})
    block = build_user_profile_block(cfg)
    assert block is not None
    assert "Як спілкуватися з користувачем: Коротко, на «ти»" in block
    assert "задач" not in block


@pytest.mark.unit
def test_style_and_goals_block():
    cfg = types.SimpleNamespace(
        user_profile={"communication_style": "S", "goals": "Ship the UK build"}
    )
    block = build_user_profile_block(cfg)
    assert "авторитетних" in block
    assert "Як спілкуватися з користувачем: S" in block
    assert "Поточні задачі та цілі користувача: Ship the UK build" in block


@pytest.mark.unit
def test_non_dict_profile_is_safe():
    assert build_user_profile_block(types.SimpleNamespace(user_profile="oops")) is None
