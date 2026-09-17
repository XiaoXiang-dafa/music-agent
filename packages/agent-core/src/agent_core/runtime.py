"""Adapters that turn tool calls into stable runtime events."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from .contracts import ToolCallEvent, ToolResultEvent
from .registry import ToolRegistry


def _call_parts(call: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    call_id = str(call.get("id", ""))
    name = str(call.get("name", ""))
    arguments = call.get("arguments", {})
    function = call.get("function")
    if isinstance(function, dict):
        name = str(function.get("name", name))
        arguments = function.get("arguments", arguments)
    if not isinstance(arguments, dict):
        arguments = {}
    return call_id, name, arguments


def execute_tool_calls(
    registry: ToolRegistry, calls: list[dict[str, Any]]
) -> Iterator[ToolCallEvent | ToolResultEvent]:
    for call in calls:
        call_id, name, arguments = _call_parts(call)
        yield ToolCallEvent(name=name, arguments=arguments, call_id=call_id)
        yield ToolResultEvent(
            name=name,
            result=registry.run(name, arguments),
            call_id=call_id,
        )


async def aexecute_tool_calls(
    registry: ToolRegistry, calls: list[dict[str, Any]]
) -> AsyncIterator[ToolCallEvent | ToolResultEvent]:
    for call in calls:
        call_id, name, arguments = _call_parts(call)
        yield ToolCallEvent(name=name, arguments=arguments, call_id=call_id)
        yield ToolResultEvent(
            name=name,
            result=await registry.arun(name, arguments),
            call_id=call_id,
        )
