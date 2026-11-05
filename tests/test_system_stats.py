"""Unit tests for the systemStats builtin tool."""

import subprocess
import types

import pytest

from jarvis.tools.base import ToolContext
from jarvis.tools.builtin import system_stats as ss
from jarvis.tools.builtin.system_stats import SystemStatsTool


def _ctx():
    return ToolContext(
        db=None,
        cfg=types.SimpleNamespace(),
        system_prompt="",
        original_prompt="",
        redacted_text="",
        max_retries=0,
        user_print=lambda *_: None,
    )


@pytest.mark.unit
def test_run_reports_cpu_and_ram_markers():
    res = SystemStatsTool().run({}, _ctx())
    assert res.success is True
    text = res.reply_text or ""
    assert "CPU" in text
    assert "RAM" in text


@pytest.mark.unit
def test_missing_battery_is_handled(monkeypatch):
    import psutil

    monkeypatch.setattr(psutil, "sensors_battery", lambda: None, raising=False)
    res = SystemStatsTool().run({}, _ctx())
    assert res.success is True
    text = res.reply_text or ""
    assert "Battery" not in text or "unavailable" in text.lower()


@pytest.mark.unit
def test_battery_error_is_handled(monkeypatch):
    import psutil

    def boom():
        raise RuntimeError("no sensors")

    monkeypatch.setattr(psutil, "sensors_battery", boom, raising=False)
    res = SystemStatsTool().run({}, _ctx())
    assert res.success is True


@pytest.mark.unit
def test_gpu_section_omitted_when_nvidia_smi_missing(monkeypatch):
    def boom(*args, **kwargs):
        raise FileNotFoundError("nvidia-smi not found")

    monkeypatch.setattr(ss.subprocess, "run", boom)
    res = SystemStatsTool().run({}, _ctx())
    assert res.success is True
    assert "GPU" not in (res.reply_text or "")


@pytest.mark.unit
def test_gpu_section_present_when_nvidia_smi_works(monkeypatch):
    class FakeProc:
        stdout = "45, 2048, 8192\n"
        returncode = 0

    monkeypatch.setattr(ss.subprocess, "run", lambda *a, **k: FakeProc())
    res = SystemStatsTool().run({}, _ctx())
    assert res.success is True
    text = res.reply_text or ""
    assert "GPU" in text
    assert "45" in text


@pytest.mark.unit
def test_no_exceptions_on_headless_box(monkeypatch):
    """Disk/battery/GPU collection must never raise out of run()."""
    import psutil

    def boom_disk(*a, **k):
        raise RuntimeError("no disk")

    monkeypatch.setattr(psutil, "disk_usage", boom_disk)
    monkeypatch.setattr(psutil, "sensors_battery", None, raising=False)
    monkeypatch.setattr(ss.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(subprocess.SubprocessError("x")))
    res = SystemStatsTool().run({}, _ctx())
    assert res.success is True
