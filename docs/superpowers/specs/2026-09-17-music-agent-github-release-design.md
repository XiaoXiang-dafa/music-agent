# Music Agent GitHub Release Design

## Goal

Publish the existing music AI Agent as a public GitHub repository that an HR reviewer can understand quickly and run from one clone without access to private local files or sibling repositories.

## Repository shape

Use one public repository named `music-agent`.

- Keep the application at the repository root.
- Copy the current shared runtime into `packages/agent-core`.
- Change the Python editable dependency from `../agent-core` to `./packages/agent-core`.
- Keep backend, React/Vite frontend, tests, static assets, and deployment files together.
- Do not use a Git submodule or require a second repository.

## Privacy and source control

The public repository must exclude local and personal state:

- `.env`, API keys, cookies, tokens, and local credentials.
- `project.private.config.json` and editor/OS metadata.
- `data/chat_history.txt`, SQLite databases, traces, logs, caches, dependencies, and build outputs.
- Any generated temporary output.

`config.json` and `config.example.json` may remain only if the security tests confirm that they contain placeholders rather than usable credentials or personal values.

The repository will include an explicit sample chat-history file only if the application needs a path to exist; otherwise runtime code must create the ignored local file as needed.

## Reviewer experience

The README will lead with the interview-relevant story:

1. Natural-language music requests enter a Function Calling Agent loop.
2. The Agent selects music, weather, memory, and playback tools.
3. SSE streams reasoning/tool events to the React UI.
4. Trace and SQLite-backed memory make behavior observable and personalized.
5. `DEMO_MODE=1` provides an offline, credential-free demonstration.

It will provide copy-paste setup, demo startup, test, and frontend build commands from a fresh clone. It will state honestly that Demo mode generates a test tone rather than streaming a copyrighted song.

## Verification

Before publishing:

- Run all Python tests for the application.
- Run all Python tests for the bundled `agent-core`.
- Run the React regression test and production build.
- Scan tracked files and staged changes for credential-like values and private filenames.
- Confirm ignored dependencies/build products are not tracked.
- Confirm the documented setup paths match the single-repository layout.

No successful release claim will be made unless these checks pass. Any environment-only failure will be reported separately from a code failure.

## GitHub publication

Create a public repository named `music-agent` under the GitHub account already signed into the user's browser. Preserve a concise two-commit history where practical: release preparation followed by any verification-only corrections. Push the local `main` branch and verify the public repository page and default branch after upload.

## Out of scope

- Adding unrelated product features or redesigning the UI.
- Deploying a live backend or purchasing hosting.
- Publishing real API credentials, cookies, personal conversations, or generated databases.
- Changing the separate `ai-agent-platform` or `LLM-Agent-From-Scratch` projects.
