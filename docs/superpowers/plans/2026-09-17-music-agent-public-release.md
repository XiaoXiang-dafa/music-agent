# Music Agent Public Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 将已完成安全加固的音乐 Agent 整理为单一、可公开、可离线演示的 GitHub 仓库。

**架构：** 保留 Flask + React/Vite 应用在仓库根目录，将通用 Python 运行时收纳到 `packages/agent-core`，让依赖从同级目录改为仓库内相对路径。公开仓库仅保留脱敏配置和可复现的 Demo 路径。

**技术栈：** Python 3.12、Flask、SQLite、OpenAI-compatible Function Calling、React 18、TypeScript 5.6、Vite 8、pytest、npm audit。

---

### 任务 1：收纳共享运行时

**文件：**
- 创建：`packages/agent-core/pyproject.toml`
- 创建：`packages/agent-core/src/agent_core/*.py`
- 创建：`packages/agent-core/tests/*.py`
- 修改：`requirements.txt:1`
- 测试：`tests/test_release_layout.py`

- [ ] **步骤 1：写失败的单仓布局测试**

```python
def test_agent_core_is_bundled():
    assert Path("packages/agent-core/pyproject.toml").is_file()
    assert "-e ./packages/agent-core" in Path("requirements.txt").read_text()
```

- [ ] **步骤 2：运行布局测试并确认因目录缺失而失败**

`DEMO_MODE=1 /tmp/music-agent-audit/bin/python -m pytest tests/test_release_layout.py -q`

- [ ] **步骤 3：复制当前 `agent-core` 源码、测试和元数据，并修改 editable 依赖路径**

```text
-e ./packages/agent-core
```

- [ ] **步骤 4：运行布局测试与内置核心测试**

`PYTHONPATH=packages/agent-core/src /tmp/music-agent-audit/bin/python -m pytest tests/test_release_layout.py packages/agent-core/tests -q`

### 任务 2：整理公开仓库内容

**文件：**
- 修改：`.gitignore`
- 修改：`README.md`
- 修改：`Dockerfile`
- 修改：`deploy.sh`
- 修改：`config.json`
- 创建：`LICENSE`

- [ ] **步骤 1：确认私有聊天、本地配置、数据库、依赖和构建产物被忽略**

`git check-ignore data/chat_history.txt project.private.config.json .DS_Store web/node_modules web/dist`

- [ ] **步骤 2：将 README 安装路径改为单仓布局，补充安全边界、Demo 启动和验证命令**

- [ ] **步骤 3：让 Docker 在安装 requirements 前复制 `packages/agent-core`，并让部署脚本仅使用环境变量**

- [ ] **步骤 4：添加 MIT License，并扫描已跟踪内容中的密钥特征和私有文件名**

### 任务 3：验证、提交与发布

**文件：**
- 验证：全部 Python/Node 源码与配置
- 提交：Git `main`
- 发布：GitHub 公开仓库 `music-agent`

- [ ] **步骤 1：运行全部应用测试、内置核心测试、前端回归与生产构建**

```bash
DEMO_MODE=1 /tmp/music-agent-audit/bin/python -m pytest -q
PYTHONPATH=packages/agent-core/src /tmp/music-agent-audit/bin/python -m pytest packages/agent-core/tests -q
cd web && node --test tests/*.test.mjs && npm run build
```

- [ ] **步骤 2：运行 `pip-audit`、`npm audit`、Bandit 高危扫描、密钥扫描与 `git diff --check`**

- [ ] **步骤 3：仅在所有门禁通过后提交发布内容**

`git add -A && git commit -m "feat: prepare secure public music agent release"`

- [ ] **步骤 4：通过已登录浏览器创建公开 `music-agent` 仓库，添加远程、推送 `main`，并验证仓库页面**
