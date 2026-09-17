import json
from pathlib import Path

import pytest

from modules import common
from modules.common import resolve_api_keys


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.json"


def test_repository_config_contains_no_live_credentials():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["qqmusic"]["cookie"] == "请设置环境变量 QQMUSIC_COOKIE"
    assert config["deepseek"]["api_key"] == "请设置环境变量 DEEPSEEK_API_KEY"


def test_environment_variables_override_placeholders(monkeypatch):
    config = {
        "deepseek": {"api_key": "请设置环境变量 DEEPSEEK_API_KEY"},
        "weather": {"api_key": "请设置环境变量 WEATHER_API_KEY"},
        "qqmusic": {"cookie": "请设置环境变量 QQMUSIC_COOKIE"},
    }
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv("WEATHER_API_KEY", "test-weather-key")
    monkeypatch.setenv("QQMUSIC_COOKIE", "test-cookie")

    resolve_api_keys(config)

    assert config["deepseek"]["api_key"] == "test-deepseek-key"
    assert config["weather"]["api_key"] == "test-weather-key"
    assert config["qqmusic"]["cookie"] == "test-cookie"


def test_missing_deepseek_api_key_is_rejected():
    config = {"deepseek": {"api_key": "请设置环境变量 DEEPSEEK_API_KEY"}}

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        common.require_deepseek_api_key(config)


@pytest.mark.parametrize(
    "value",
    ["", "MISSING_API_KEY", "你的和风天气API_KEY", "请设置环境变量 WEATHER_API_KEY"],
)
def test_placeholder_is_not_treated_as_configured_secret(value):
    assert common.is_configured_secret(value) is False


def test_real_environment_value_is_treated_as_configured_secret():
    assert common.is_configured_secret("injected-test-value") is True
