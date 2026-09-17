from pathlib import Path


def test_agent_core_is_bundled_in_public_repository():
    assert Path("packages/agent-core/pyproject.toml").is_file()
    assert Path("packages/agent-core/src/agent_core/runtime.py").is_file()


def test_requirements_use_repository_local_agent_core():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    assert "-e ./packages/agent-core" in requirements
    assert "-e ../agent-core" not in requirements


def test_docker_copies_bundled_agent_core_before_dependency_install():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.index("COPY packages/agent-core") < dockerfile.index(
        "pip install --no-cache-dir -r requirements.txt"
    )
