"""Business-agnostic tool registration and invocation."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    handler: Callable[..., Any] = field(default=lambda **_: "")

    def to_openai(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def run(self, arguments: dict[str, Any]) -> Any:
        try:
            return self.handler(**(arguments if isinstance(arguments, dict) else {}))
        except TypeError as exc:
            return {
                "error": "invalid_arguments",
                "message": str(exc),
                "tool": self.name,
            }
        except Exception as exc:  # noqa: BLE001 - surface tool failures to the Agent
            return {
                "error": "tool_execution_error",
                "message": str(exc),
                "tool": self.name,
            }

    async def arun(self, arguments: dict[str, Any]) -> Any:
        try:
            result = self.handler(**(arguments if isinstance(arguments, dict) else {}))
            if inspect.isawaitable(result):
                return await result
            return result
        except TypeError as exc:
            return {
                "error": "invalid_arguments",
                "message": str(exc),
                "tool": self.name,
            }
        except Exception as exc:  # noqa: BLE001 - surface tool failures to the Agent
            return {
                "error": "tool_execution_error",
                "message": str(exc),
                "tool": self.name,
            }


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def openai_defs(self) -> list[dict[str, Any]]:
        return [tool.to_openai() for tool in self._tools.values()]

    def public_descriptions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self._tools.values()
        ]

    def run(self, name: str, arguments: dict[str, Any]) -> Any:
        tool = self.get(name)
        if tool is None:
            return {
                "error": "unknown_tool",
                "message": f"Unknown tool: {name}",
                "tool": name,
                "available": self.names(),
            }
        return tool.run(arguments)

    async def arun(self, name: str, arguments: dict[str, Any]) -> Any:
        tool = self.get(name)
        if tool is None:
            return {
                "error": "unknown_tool",
                "message": f"Unknown tool: {name}",
                "tool": name,
                "available": self.names(),
            }
        return await tool.arun(arguments)
