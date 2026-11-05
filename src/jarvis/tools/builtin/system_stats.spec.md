# systemStats

## Purpose

Report the local machine's live state in response to system-status requests
("how is my system", "яке навантаження на процесор", "скільки вільної
пам'яті", battery level, GPU load). Fully local: psutil plus an optional
nvidia-smi subprocess. No cloud calls, no LLM calls.

## Schema

No arguments: `{}`.

## Collection

- CPU: `psutil.cpu_percent(interval=0.3)`.
- RAM: `psutil.virtual_memory()` used / total GB and percent.
- Disk: `psutil.disk_usage` on the system drive root; tolerated to fail
  (line omitted) on exotic mounts.
- Battery: `psutil.sensors_battery()`; `None`, missing sensors, or any
  sensor error omit the line (desktops, headless boxes).
- GPU: `nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total
  --format=csv,noheader` with a 5s subprocess timeout; FileNotFoundError /
  non-zero exit / malformed output omit the GPU section entirely.

## Result contract

Raw multi-line text, one section per line:
`CPU: 12%`, `RAM: 6.2 / 16.0 GB (39%)`, `Disk G: ...`, `Battery: 85%
(charging)`, `GPU: 45% util, 2048 / 8192 VRAM`. The chat model formats the
final reply in the user's language. Every collector is individually
wrapped: a failure in one section never fails the tool.
