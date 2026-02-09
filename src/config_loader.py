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
    except (IOError, PermissionError) as e:
        raise ConfigError(f"Error reading configuration file: {e}")

    # Validate required sections
    required_sections = ['ai', 'wecom', 'tasks', 'logging']
    for section in required_sections:
        if section not in config:
            raise ConfigError(f"Missing required configuration section: {section}")

    # Validate required fields in each section
    required_fields = {
        'ai': ['base_url', 'api_key', 'model'],
        'wecom': ['webhook_url'],
        'tasks': ['daily_limit', 'weekly_limit', 'daily_hour', 'weekly_day', 'weekly_hour'],
        'logging': ['level', 'file']
    }

    for section, fields in required_fields.items():
        for field in fields:
            if field not in config[section]:
                raise ConfigError(f"Missing required field '{field}' in section '{section}'")

    # Validate data types and ranges
    tasks = config['tasks']
    if not isinstance(tasks.get('daily_limit'), int) or tasks['daily_limit'] < 1:
        raise ConfigError("tasks.daily_limit must be a positive integer")
    if not isinstance(tasks.get('weekly_limit'), int) or tasks['weekly_limit'] < 1:
        raise ConfigError("tasks.weekly_limit must be a positive integer")
    if not isinstance(tasks.get('daily_hour'), int) or not (0 <= tasks['daily_hour'] <= 23):
        raise ConfigError("tasks.daily_hour must be an integer between 0 and 23")
    if not isinstance(tasks.get('weekly_day'), int) or not (0 <= tasks['weekly_day'] <= 6):
        raise ConfigError("tasks.weekly_day must be an integer between 0 (Monday) and 6 (Sunday)")
    if not isinstance(tasks.get('weekly_hour'), int) or not (0 <= tasks['weekly_hour'] <= 23):
        raise ConfigError("tasks.weekly_hour must be an integer between 0 and 23")

    return config
