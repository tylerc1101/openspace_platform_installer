"""
Execution context that holds all shared state and configuration.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any


@dataclass
class ExecutionContext:
    """
    Shared context for the entire deployment execution.
    Reduces parameter passing and centralizes configuration.
    """
    # Directory paths
    base_dir: Path = Path("/docker-workspace")
    data_dir: Path = Path("/docker-workspace/data")
    env_dir: Path = Path("/docker-workspace/config")
    images_dir: Path = Path("/docker-workspace/images")
    log_dir: Path = field(default=None)
    
    # Environment configuration
    env_name: str = ""
    deployment_type: str = ""
    deployment_plan: str = ""
    
    # Configuration data
    group_vars: Dict[str, Any] = field(default_factory=dict)
    inventory_file: Path = None
    
    # Runtime
    logger: logging.Logger = None
    verbose: bool = False
    resume: bool = False
    
    @property
    def state_file(self) -> Path:
        """Path to the state file (in .cache directory)."""
        return self.env_path / ".cache" / "state.json"
    
    @property
    def env_path(self) -> Path:
        """Path to the environment directory."""
        return self.env_dir / self.env_name
    
    @property
    def cache_dir(self) -> Path:
        """Path to the .cache directory."""
        return self.env_path / ".cache"
    
    @property
    def log_path(self) -> Path:
        """Path to the logs directory (derived from env_name if log_dir not set)."""
        if self.log_dir:
            return self.log_dir
        return self.cache_dir / "logs"
    
    def __post_init__(self):
        """Validate required fields after initialization."""
        if not self.env_name:
            raise ValueError("env_name is required")
        if not self.deployment_type:
            raise ValueError("deployment_type is required")