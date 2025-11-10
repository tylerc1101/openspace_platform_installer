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
    #log_dir: Path = None  # Will be set to <env>/.cache/logs
    
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
    
    def __post_init__(self):
        """Validate required fields after initialization."""
        if not self.env_name:
            raise ValueError("env_name is required")
        if not self.deployment_type:
            raise ValueError("deployment_type is required")