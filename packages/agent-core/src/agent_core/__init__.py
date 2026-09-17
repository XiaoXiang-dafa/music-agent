"""Shared runtime primitives for the Agent projects."""

from .contracts import ToolCallEvent, ToolResultEvent
from .registry import Tool, ToolRegistry
from .runtime import aexecute_tool_calls, execute_tool_calls

__version__ = "0.1.0"

__all__ = [
    "Tool",
    "ToolRegistry",
    "ToolCallEvent",
    "ToolResultEvent",
    "execute_tool_calls",
    "aexecute_tool_calls",
]
