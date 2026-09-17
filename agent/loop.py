# -*- coding: utf-8 -*-
"""
Agent 执行循环 — 基于 Function Calling 的「推理 → 调用工具 → 观察 → 再推理」循环。

核心思想：
  1. 把系统 Prompt + 会话历史 + 用户消息发给 LLM，并声明可用的工具。
  2. LLM 可能返回两类内容：
       - 直接回复文本 -> 代表本轮任务完成，结束。
       - tool_calls  -> 代表 LLM 决定调用某个工具，需要执行后把结果喂回去，继续下一轮。
  3. 流式模式：回复文本会 split 成 token 逐片下发（SSE），工具调用作为结构化事件下发。

本模块是「纯 Python，无 IO 强依赖」，只依赖 openai 客户端 + 外部传入的 ToolRegistry。
"""
from __future__ import annotations

from collections import defaultdict
from time import perf_counter_ns
from typing import Any, Iterator

from agent_core import ToolCallEvent, ToolResultEvent, execute_tool_calls

from .registry import ToolRegistry, dumps


class AgentConfig:
    """Agent 运行参数。"""

    def __init__(
        self,
        model: str,
        temperature: float = 0.8,
        max_steps: int = 6,
        max_tokens: int = 800,
    ):
        self.model = model
        self.temperature = temperature
        self.max_steps = max_steps
        self.max_tokens = max_tokens


def _assemble(messages: list[dict], system_prompt: str) -> list[dict]:
    return [{"role": "system", "content": system_prompt}] + list(messages)


def _call_llm(client, msgs, cfg, registry, stream: bool):
    kwargs = dict(
        model=cfg.model,
        messages=msgs,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        stream=stream,
    )
    schemas = registry.get_schemas()
    if schemas:
        kwargs["tools"] = schemas
    return client.chat.completions.create(**kwargs)


def stream_agent(
    client,
    registry: ToolRegistry,
    system_prompt: str,
    messages: list[dict],
    cfg: AgentConfig,
) -> Iterator[dict]:
    """
    流式运行 Agent。

    Yields 事件 dict（可直接转成 SSE）：
      {"type": "reply_chunk", "content": "..."}          # 最终回复的 token 增量
      {"type": "tool_call", "name": "x", "args": {...}, "call_id": "..."}
      {"type": "tool_result", "name": "x", "result": ..., "call_id": "...",
       "status": "success|error", "duration_ms": 0}
      {"type": "done", "reply": "完整回复", "steps": n}       # 结束
    """
    msgs = _assemble(messages, system_prompt)
    steps = 0
    final_reply = ""

    while steps < cfg.max_steps:
        steps += 1

        # 累积本轮的流式增量
        content_parts: list[str] = []
        # index -> {"id","name","args_parts":[]}
        tool_acc: dict[int, dict] = defaultdict(lambda: {"id": None, "name": None, "args_parts": []})
        finish_reason = None

        stream = _call_llm(client, msgs, cfg, registry, stream=True)
        for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if choice.finish_reason:
                finish_reason = choice.finish_reason
            delta = choice.delta
            if delta is None:
                continue
            if delta.content:
                content_parts.append(delta.content)
                yield {"type": "reply_chunk", "content": delta.content}
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    slot = tool_acc[tc.index]
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            slot["name"] = tc.function.name
                        if tc.function.arguments:
                            slot["args_parts"].append(tc.function.arguments)

        # 本轮是否有工具调用
        if tool_acc:
            # 组装 assistant 消息（含 tool_calls）
            assistant_tool_calls = []
            tool_msg_order = []
            for idx in sorted(tool_acc):
                slot = tool_acc[idx]
                args_str = "".join(slot["args_parts"])
                try:
                    args = json_loads(args_str) if args_str else {}
                except Exception:
                    args = {"_raw": args_str}
                assistant_tool_calls.append({
                    "id": slot["id"],
                    "type": "function",
                    "function": {"name": slot["name"], "arguments": args_str},
                })
                runtime_call = {
                    "id": slot["id"] or "",
                    "name": slot["name"] or "",
                    "arguments": args,
                }
                result = None
                runtime_events = iter(execute_tool_calls(registry.core, [runtime_call]))
                while True:
                    event_started_ns = perf_counter_ns()
                    try:
                        runtime_event = next(runtime_events)
                    except StopIteration:
                        break
                    if isinstance(runtime_event, ToolCallEvent):
                        yield {
                            "type": "tool_call",
                            "name": runtime_event.name,
                            "args": runtime_event.arguments,
                            "call_id": runtime_event.call_id,
                        }
                    elif isinstance(runtime_event, ToolResultEvent):
                        result = registry.compatible_result(runtime_event.name, runtime_event.result)
                        duration_ms = max(
                            0,
                            (perf_counter_ns() - event_started_ns) // 1_000_000,
                        )
                        status = (
                            "error"
                            if isinstance(result, dict) and "error" in result
                            else "success"
                        )
                        yield {
                            "type": "tool_result",
                            "name": runtime_event.name,
                            "result": result,
                            "call_id": runtime_event.call_id,
                            "status": status,
                            "duration_ms": duration_ms,
                        }
                tool_msg_order.append({
                    "role": "tool",
                    "tool_call_id": slot["id"],
                    "content": dumps(result),
                })

            msgs.append({
                "role": "assistant",
                "content": "".join(content_parts) or None,
                "tool_calls": assistant_tool_calls,
            })
            msgs.extend(tool_msg_order)
            continue  # 继续下一轮推理

        # 无工具调用 -> 结束
        final_reply = "".join(content_parts).strip()
        yield {"type": "done", "reply": final_reply, "steps": steps}
        return

    yield {"type": "done", "reply": final_reply, "steps": steps, "truncated": True}


def run_agent(
    client,
    registry: ToolRegistry,
    system_prompt: str,
    messages: list[dict],
    cfg: AgentConfig,
) -> dict:
    """
    非流式运行 Agent，返回聚合结果：
      {"reply": str, "steps": int, "tool_calls": [{"name","args"}],
       "tool_results": [{"name","result","call_id","status","duration_ms"}],
       "truncated": bool}
    """
    reply = ""
    steps = 0
    tool_calls = []
    tool_results = []
    truncated = False
    for ev in stream_agent(client, registry, system_prompt, messages, cfg):
        if ev["type"] == "tool_call":
            tool_calls.append({"name": ev["name"], "args": ev["args"]})
        elif ev["type"] == "tool_result":
            tool_results.append({
                "name": ev["name"],
                "result": ev["result"],
                "call_id": ev["call_id"],
                "status": ev["status"],
                "duration_ms": ev["duration_ms"],
            })
        elif ev["type"] == "reply_chunk":
            reply += ev["content"]
        elif ev["type"] == "done":
            steps = ev.get("steps", steps)
            truncated = ev.get("truncated", False)
            reply = ev.get("reply", reply)
    return {
        "reply": reply,
        "steps": steps,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "truncated": truncated,
    }


def json_loads(s: str):
    import json
    return json.loads(s)
