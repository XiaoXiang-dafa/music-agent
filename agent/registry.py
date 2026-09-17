# -*- coding: utf-8 -*-
"""
工具注册表 — 让 Agent 可访问的工具统一在此登记。

每个工具由三部分组成：
  1. schema  : 给 LLM 看的 Function Calling 声明（name/description/parameters）
  2. handler : 实际执行函数，返回可被 JSON 序列化的结果
  3. meta    : 展示用信息（name/描述），供前端/日志使用

使用方式：
    reg = ToolRegistry()
    reg.register(name="search_songs", schema={...}, handler=fn, description="...")
    reg.get_schemas()   # -> 给 openai 的 tools 参数
    reg.call(name, args)  # -> 执行并返回结果
"""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Callable

from agent_core import Tool, ToolRegistry as CoreToolRegistry


class ToolRegistry:
    def __init__(self):
        self.core = CoreToolRegistry()

    def register(self, name: str, schema: dict, handler: Callable[..., Any], description: str = "") -> None:
        """登记一个工具。schema 里的 name 必须与 name 一致。"""
        if self.core.get(name) is not None:
            raise ValueError(f"工具已存在: {name}")
        function = deepcopy(schema).get("function", {})
        self.core.register(
            Tool(
                name=name,
                description=description or function.get("description", ""),
                parameters=function.get("parameters", {}),
                handler=handler,
            )
        )

    def get_schemas(self) -> list[dict]:
        """返回可传给 openai 的 tools 参数（每个元素含 type/function）。"""
        return self.core.openai_defs()

    def names(self) -> list[str]:
        return self.core.names()

    def call(self, name: str, args: dict) -> Any:
        """执行工具。找不到则返回错误结果，供 Agent 自我修复。"""
        return self.compatible_result(name, self.core.run(name, args))

    def compatible_result(self, name: str, result: Any) -> Any:
        """把 agent-core 的标准错误映射为项目已有的中文响应。"""
        if not isinstance(result, dict) or "error" not in result:
            return result
        error_type = result.get("error")
        message = result.get("message", "")
        if error_type == "unknown_tool":
            return {"error": f"未知工具: {name}", "available": result.get("available", self.names())}
        if error_type == "invalid_arguments":
            return {"error": f"参数错误: {message}"}
        if error_type == "tool_execution_error":
            return {"error": f"工具执行失败: {message}"}
        return result

    def describe(self, name: str) -> dict:
        """返回某工具的展示信息。"""
        tool = self.core.get(name)
        if tool is None:
            return {"name": name, "description": "(未知)"}
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters.get("properties", {}),
        }

    def list_descriptions(self) -> list[dict]:
        return [self.describe(name) for name in self.names()]

    def __contains__(self, name: str) -> bool:
        return self.core.get(name) is not None

    def __repr__(self) -> str:
        return f"<ToolRegistry: {','.join(self.names())}>"


def dumps(obj: Any) -> str:
    """安全地把工具结果转成 LLM 可见的 JSON 字符串。"""
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)
