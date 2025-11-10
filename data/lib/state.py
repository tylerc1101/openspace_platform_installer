"""
State file management for tracking installation progress.
Simplified format without exit codes.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional


class StateManager:
    """
    Manages state persistence for deployment progress.
    Tracks which steps have completed, failed, or are running.
    Simplified format: just status, no exit codes.
    
    Example:
        >>> state = StateManager(Path("/config/prod/.cache/state.json"), Path("/config/prod/.cache/logs"))
        >>> state.mark_running("step1", log="/config/prod/.cache/logs/step1.log")
        >>> state.mark_success("step1")
        >>> if state.is_completed("step1"):
        ...     print("Step already done!")
    """
    
    def __init__(self, state_file: Path, log_dir: Path, logger: logging.Logger = None):
        """
        Initialize the state manager.
        
        Args:
            state_file: Path to the JSON state file (in .cache directory)
            log_dir: Directory for logs
            logger: Optional logger for messages
        """
        self.state_file = state_file
        self.log_dir = log_dir
        self.logger = logger or logging.getLogger(__name__)
        self.state: Dict[str, Any] = self._load()
        
    def _load(self) -> Dict[str, Any]:
        """Load the state file that tracks which steps completed."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Could not load state file: {e}. Starting fresh.")
        return {"steps": {}}
    
    def save(self) -> None:
        """Save progress to the state file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
    
    def initialize(self, env_name: str, deployment_type: str, deployment_plan: str) -> None:
        """
        Initialize state with environment information.
        
        Args:
            env_name: Environment name
            deployment_type: Deployment type (basekit/baremetal/aws)
            deployment_plan: Deployment plan name
        """
        self.state["env"] = env_name
        self.state["deployment_type"] = deployment_type
        self.state["deployment_plan"] = deployment_plan
        if "steps" not in self.state:
            self.state["steps"] = {}
        self.save()
    
    def mark_running(self, step_id: str, **kwargs) -> None:
        """
        Mark a step as currently running.
        
        Args:
            step_id: Step identifier
            **kwargs: Additional metadata (log path, description, etc.)
        """
        self.state["steps"][step_id] = {"status": "running", **kwargs}
        self.save()
    
    def mark_success(self, step_id: str) -> None:
        """
        Mark a step as successfully completed.
        
        Args:
            step_id: Step identifier
        """
        if step_id in self.state["steps"]:
            self.state["steps"][step_id]["status"] = "ok"
        self.save()
    
    def mark_failed(self, step_id: str) -> None:
        """
        Mark a step as failed.
        
        Args:
            step_id: Step identifier
        """
        if step_id in self.state["steps"]:
            self.state["steps"][step_id]["status"] = "failed"
        self.save()
    
    def mark_skipped(self, step_id: str, reason: str = "") -> None:
        """
        Mark a step as skipped.
        
        Args:
            step_id: Step identifier
            reason: Optional reason for skipping
        """
        self.state["steps"][step_id] = {"status": "skipped"}
        if reason:
            self.state["steps"][step_id]["reason"] = reason
        self.save()
    
    def is_completed(self, step_id: str) -> bool:
        """
        Check if a step has completed successfully.
        
        Args:
            step_id: Step identifier
            
        Returns:
            True if step completed successfully
        """
        return self.state.get("steps", {}).get(step_id, {}).get("status") == "ok"
    
    def get_step_status(self, step_id: str) -> Optional[str]:
        """
        Get the status of a step.
        
        Args:
            step_id: Step identifier
            
        Returns:
            Status string (ok/failed/running/skipped) or None
        """
        return self.state.get("steps", {}).get(step_id, {}).get("status")