# agent-core

`agent-core` 是从两个 Agent 项目的重复实现中抽取出的轻量 Python 运行时，统一 OpenAI Function Calling 工具定义、注册与执行事件，不包含数据库、HTTP 框架或具体业务工具。

## 提供能力

- `Tool`：用一份 JSON Schema 同时描述工具和生成 OpenAI `tools` 参数。
- `ToolRegistry`：工具注册、查询、同步/异步执行与结构化错误返回。
- `ToolCallEvent` / `ToolResultEvent`：统一工具调用和结果事件。
- `execute_tool_calls` / `aexecute_tool_calls`：同步和异步工具执行适配器。

## 项目关系

```text
LLM-Agent-From-Scratch
  └─ ReAct 与 Transformer 原理实现
                  ↓ 设计思想演进
              agent-core 0.1.0
             ↙                ↘
ai-agent-platform              wechat-bot
平台/上下文/持久化              音乐工具/记忆/双前端
```

`LLM-Agent-From-Scratch` 保持独立，不导入本包；它用于展示公共运行时之前的原理与最小实现。

## 本地安装

```bash
python3 -m pip install -e ./agent-core
```

当前两个消费者项目按同级目录组织：

```text
求职项目/
├── agent-core/
├── ai-agent-platform/
└── wechat-bot/
```

消费者的 `requirements.txt` 使用 `-e ../agent-core`。若构建环境无法联网下载构建依赖，可先安装 `setuptools>=68`，或在已具备 setuptools 的环境中使用 `pip install --no-build-isolation -e ../agent-core`。

## 使用示例

```python
from agent_core import Tool, ToolRegistry, execute_tool_calls

registry = ToolRegistry([
    Tool(
        name="echo",
        description="Echo text",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        handler=lambda text: text,
    )
])

events = list(execute_tool_calls(
    registry,
    [{"id": "call_1", "name": "echo", "arguments": {"text": "hello"}}],
))
```

## 测试

```bash
PYTHONPATH=src python3 -m pytest tests -q
```

当前版本：`0.1.0`。
