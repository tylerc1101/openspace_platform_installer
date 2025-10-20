"""
Configuration and logging management.
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any
import yaml

from .exceptions import ConfigurationError


def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    """
    Setup logging to both file and console with proper formatting.
    
    Args:
        log_dir: Directory for log files
        verbose: Enable debug-level logging
        
    Returns:
        Configured logger instance
        
    Example:
        >>> logger = setup_logging(Path("/var/log"), verbose=True)
        >>> logger.info("Starting deployment")
    """
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


def load_yaml_file(file_path: Path, logger: logging.Logger = None) -> Dict[str, Any]:
    """
    Load a YAML file and return its contents.
    
    Args:
        file_path: Path to YAML file
        logger: Optional logger for error messages
        
    Returns:
        Parsed YAML as dictionary
        
    Raises:
        ConfigurationError: If file cannot be read or parsed
        
    Example:
        >>> config = load_yaml_file(Path("config.yml"))
        >>> print(config['deployment_type'])
    """
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        msg = f"Invalid YAML in {file_path}: {e}"
        if logger:
            logger.error(msg)
        raise ConfigurationError(msg)
    except FileNotFoundError:
        msg = f"File not found: {file_path}"
        if logger:
            logger.error(msg)
        raise ConfigurationError(msg)
    except Exception as e:
        msg = f"Cannot read {file_path}: {e}"
        if logger:
            logger.error(msg)
        raise ConfigurationError(msg)


def replace_placeholders(text: str, env_name: str, deployment_plan: str, 
                        deployment_type: str, group_vars: Dict[str, Any]) -> str:
    """
    Replace placeholders in text with actual values.
    
    Supports: {env}, {deployment}, {deployment_type}, {variable_name}
    
    Args:
        text: Text containing placeholders
        env_name: Environment name
        deployment_plan: Deployment plan name
        deployment_type: Deployment type (basekit/baremetal/aws)
        group_vars: Dictionary of variables to replace
        
    Returns:
        Text with placeholders replaced
        
    Example:
        >>> result = replace_placeholders(
        ...     "{env}-{deployment_type}",
        ...     "prod", "default", "basekit", {}
        ... )
        >>> print(result)
        prod-basekit
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