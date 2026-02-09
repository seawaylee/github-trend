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
