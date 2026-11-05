"""systemStats tool: report the local machine's CPU, RAM, disk, battery, and
GPU state as raw text for the chat model to phrase.

Everything is collected locally via psutil and an optional nvidia-smi
subprocess. No cloud calls, no LLM calls.
"""

import os
import subprocess
from typing import Any, Dict, Optional

import psutil

from ...debug import debug_log
from ..base import Tool, ToolContext
from ..types import ToolExecutionResult

# nvidia-smi can hang on driver hiccups; cap the subprocess wait.
_GPU_TIMEOUT_SEC = 5.0


def _query_gpu() -> Optional[str]:
    """Return a GPU summary line via nvidia-smi, or None when unavailable."""
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=_GPU_TIMEOUT_SEC,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        debug_log(f"systemStats: nvidia-smi unavailable: {exc}", "tools")
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    parts = [p.strip() for p in proc.stdout.strip().splitlines()[0].split(",")]
    if len(parts) != 3:
        return None
    util, used, total = parts
    return f"GPU: {util} util, {used} / {total} VRAM"


def _battery_line() -> Optional[str]:
    """Return a battery summary, or None on desktops / missing sensors."""
    try:
        battery = psutil.sensors_battery()
    except (AttributeError, RuntimeError, OSError, TypeError):
        return None
    if battery is None:
        return None
    percent = round(battery.percent)
    plugged = "charging" if battery.power_plugged else "on battery"
    return f"Battery: {percent}% ({plugged})"


def _disk_line() -> Optional[str]:
    """Disk usage for the system drive; tolerates exotic mounts."""
    try:
        usage = psutil.disk_usage(os.path.abspath(os.sep))
    except (RuntimeError, OSError) as exc:
        debug_log(f"systemStats: disk usage unavailable: {exc}", "tools")
        return None
    drive = os.path.splitdrive(os.path.abspath(os.sep))[0].rstrip("\\/") or "/"
    total_gb = usage.total / (1024 ** 3)
    free_gb = usage.free / (1024 ** 3)
    percent = usage.percent
    return f"Disk {drive}: {free_gb:.1f} / {total_gb:.1f} GB free ({percent}% used)"


class SystemStatsTool(Tool):
    """Report local system status: CPU, RAM, disk, battery, GPU."""

    @property
    def name(self) -> str:
        return "systemStats"

    @property
    def description(self) -> str:
        return (
            "Report the current state of the user's computer: CPU load, RAM "
            "usage, disk space, battery level, and GPU utilisation / VRAM "
            "when an NVIDIA GPU is present. Use for 'how is my system', "
            "'яке навантаження на процесор', 'скільки вільної пам'яті', "
            "'system stats', 'battery level' requests. Takes no arguments."
        )

    @property
    def inputSchema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    def run(self, args, context: ToolContext) -> ToolExecutionResult:
        context.user_print("📊 Збираю статистику системи")

        sections: list = []

        cpu_percent = psutil.cpu_percent(interval=0.3)
        sections.append(f"CPU: {cpu_percent}%")

        mem = psutil.virtual_memory()
        used_gb = mem.used / (1024 ** 3)
        total_gb = mem.total / (1024 ** 3)
        sections.append(
            f"RAM: {used_gb:.1f} / {total_gb:.1f} GB ({mem.percent}%)"
        )

        disk = _disk_line()
        if disk:
            sections.append(disk)

        battery = _battery_line()
        if battery:
            sections.append(battery)

        gpu = _query_gpu()
        if gpu:
            sections.append(gpu)

        debug_log("systemStats: collected local system status", "tools")
        return ToolExecutionResult(success=True, reply_text="\n".join(sections))
