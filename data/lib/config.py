"""
Configuration and logging management.
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any
import yaml


def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    """Setup logging to both file and console with proper formatting."""
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger("onboarder")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    if logger.handlers:
        return logger
    
    # Console handler - simple format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_format = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_format)
    
    # File handler with detailed info
    file_handler = logging.FileHandler(log_dir / "onboarder.log")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    
    return logger


def load_yaml_file(file_path: Path) -> Dict[str, Any]:
    """Load a YAML file and return its contents."""
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {file_path}: {e}")
    except Exception as e:
        raise IOError(f"Cannot read {file_path}: {e}")


def replace_placeholders(text: str, env_name: str, deployment_plan: str, 
                        deployment_type: str, group_vars: Dict[str, Any]) -> str:
    """
    Replace placeholders in text with actual values.
    Supports: {env}, {deployment}, {deployment_type}, {variable_name}
    """
    result = (text
              .replace("{env}", env_name)
              .replace("{deployment}", deployment_plan)
              .replace("{deployment_type}", deployment_type))
    
    # Replace any group_vars variables
    for key, value in group_vars.items():
        if isinstance(value, (str, int, float, bool)):
            result = result.replace(f"{{{key}}}", str(value))
    
    return result