"""Stable data contracts shared by the Agent projects."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        return str(value)


@dataclass(frozen=True)
class ToolCallEvent:
    name: str
    arguments: dict[str, Any]
    call_id: str
    type: str = "tool_call"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "name": self.name,
            "arguments": _json_safe(self.arguments),
            "id": self.call_id,
        }


@dataclass(frozen=True)
class ToolResultEvent:
    name: str
    result: Any
    call_id: str
    type: str = "tool_result"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "name": self.name,
            "result": _json_safe(self.result),
            "id": self.call_id,
        }
