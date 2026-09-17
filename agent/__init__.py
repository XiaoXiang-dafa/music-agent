# -*- coding: utf-8 -*-
"""
Agent 核心包 — 基于 Function Calling 的多步工具调用智能体。

包含：
    registry.py  : 工具注册表（可热插拔）
    loop.py      : 流式/非流式执行循环（ReAct + Function Calling）
    prompts.py   : 系统 Prompt 组装（角色 + 工具说明 + 记忆）
"""
from .registry import ToolRegistry, dumps
from .loop import stream_agent, run_agent, AgentConfig

__all__ = ["ToolRegistry", "dumps", "stream_agent", "run_agent", "AgentConfig"]
