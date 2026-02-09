import pytest
import tempfile
import os
from pathlib import Path
from src.config_loader import load_config, ConfigError


def test_load_valid_config():
    """Test loading valid configuration"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.yaml"
        config_file.write_text("""
ai:
  base_url: "http://127.0.0.1:8045"
  api_key: "sk-test"
  model: "gemini-3-pro-high"
wecom:
  webhook_url: "https://qyapi.weixin.qq.com/test"
tasks:
  daily_limit: 5
  weekly_limit: 25
  daily_hour: 10
  weekly_day: 5
  weekly_hour: 16
logging:
  level: "INFO"
  file: "logs/app.log"
""")
        config = load_config(str(config_file))
        assert config['ai']['model'] == 'gemini-3-pro-high'
        assert config['tasks']['daily_limit'] == 5


def test_missing_config_file():
    """Test error when config file doesn't exist"""
    with pytest.raises(ConfigError):
        load_config("/nonexistent/config.yaml")


def test_invalid_yaml():
    """Test error on malformed YAML"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.yaml"
        config_file.write_text("invalid: yaml: content:")
        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_config(str(config_file))


def test_missing_section():
    """Test error when required section is missing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.yaml"
        config_file.write_text("""
ai:
  base_url: "http://localhost"
  api_key: "test"
  model: "test"
# Missing wecom, tasks, logging sections
""")
        with pytest.raises(ConfigError, match="Missing required.*section"):
            load_config(str(config_file))


def test_missing_required_field():
    """Test error when required field is missing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.yaml"
        config_file.write_text("""
ai:
  base_url: "http://localhost"
  # Missing api_key and model
wecom:
  webhook_url: "https://test.com"
tasks:
  daily_limit: 5
  weekly_limit: 25
  daily_hour: 10
  weekly_day: 5
  weekly_hour: 16
logging:
  level: "INFO"
  file: "logs/app.log"
""")
        with pytest.raises(ConfigError, match="Missing required field.*api_key"):
            load_config(str(config_file))


def test_invalid_daily_hour():
    """Test error when daily_hour is out of range"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.yaml"
        config_file.write_text("""
ai:
  base_url: "http://localhost"
  api_key: "test"
  model: "test"
wecom:
  webhook_url: "https://test.com"
tasks:
  daily_limit: 5
  weekly_limit: 25
  daily_hour: 25  # Invalid!
  weekly_day: 5
  weekly_hour: 16
logging:
  level: "INFO"
  file: "logs/app.log"
""")
        with pytest.raises(ConfigError, match="daily_hour.*between 0 and 23"):
            load_config(str(config_file))
