"""
Configuration loader for GitHub AI Trend Tracker.
Loads and validates YAML configuration files.
"""

import yaml
from pathlib import Path
from typing import Dict, Any


class ConfigError(Exception):
    """Custom exception for configuration errors"""
    pass


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load and validate configuration from YAML file.

    Args:
        config_path: Path to the configuration YAML file

    Returns:
        Dictionary containing configuration values

    Raises:
        ConfigError: If config file doesn't exist or is invalid
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in configuration file: {e}")
    except Exception as e:
        raise ConfigError(f"Error reading configuration file: {e}")

    # Validate required sections
    required_sections = ['ai', 'wecom', 'tasks', 'logging']
    for section in required_sections:
        if section not in config:
            raise ConfigError(f"Missing required configuration section: {section}")

    return config
