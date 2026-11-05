"""Common types and result classes for tools."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ToolExecutionResult:
    """Result object for tool execution."""
    success: bool
    reply_text: Optional[str]
    error_message: Optional[str] = None
    # Optional structured payload (e.g. the id of an entry a tool created)
    # so callers can chain tool calls without re-parsing reply_text.
    data: Optional[Dict[str, Any]] = None
