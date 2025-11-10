"""
Step execution orchestration.
Handles the execution of individual deployment steps.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional

from .config import replace_placeholders
from .context import ExecutionContext
from .exceptions import ExecutionError
from .executor import build_command, run_command
from .inventory import find_step_file
from .state import StateManager


class StepExecutor:
    """
    Orchestrates the execution of deployment steps.
    Handles step validation, command building, and execution.
    
    Example:
        >>> executor = StepExecutor(ctx, state_mgr)
        >>> for idx, step in enumerate(steps, 1):
        ...     if not executor.execute_step(step, idx, len(steps)):
        ...         break
    """
    
    def __init__(self, ctx: ExecutionContext, state_mgr: StateManager):
        """
        Initialize the step executor.
        
        Args:
            ctx: Execution context
            state_mgr: State manager for tracking progress
        """
        self.ctx = ctx
        self.state_mgr = state_mgr
        self.logger = ctx.logger
    
    def execute_step(self, step: Dict[str, Any], index: int, total: int) -> bool:
        """
        Execute a single deployment step.
        
        Args:
            step: Step configuration dictionary
            index: Current step number (1-based)
            total: Total number of steps
            
        Returns:
            True if successful or should continue, False if should stop
        """
        step_id = str(step.get("id", index))
        description = step.get("description") or step.get("desc") or "No description"
        kind = step.get("kind", "")
        on_failure = step.get("on_failure", "fail")
        
        # Skip if no kind
        if not kind:
            self.logger.warning(f"[{step_id}] SKIPPING: Missing kind")
            self.state_mgr.mark_skipped(step_id, "missing kind")
            return True
        
        # Skip if already completed (when using --resume)
        if self.ctx.resume and self.state_mgr.is_completed(step_id):
            self.logger.info(f"[{step_id}] SKIPPING: Already completed - {description}")
            return True
        
        # Check for iteration
        if self._should_iterate(step):
            return self._execute_iterated(step, index, total)
        else:
            return self._execute_single(step, index, total, "")
    
    def _should_iterate(self, step: Dict[str, Any]) -> bool:
        """Determine if step should be executed multiple times (once per host)."""
        kind = step.get("kind", "").lower()
        hosts = step.get("hosts", "localhost")
        iterate = step.get("iterate", False)
        
        return (kind == "command" and iterate and 
                isinstance(hosts, list) and len(hosts) > 1)
    
    def _execute_iterated(self, step: Dict[str, Any], index: int, total: int) -> bool:
        """Execute a step once for each host in the hosts list."""
        hosts = step.get("hosts", [])
        
        for host_idx, host in enumerate(hosts, 1):
            # Create modified step for single host
            step_for_host = step.copy()
            step_for_host["hosts"] = host
            suffix = f"_{host}"
            
            if not self._execute_single(step_for_host, index, total, suffix, host_idx, len(hosts)):
                return False
        
        return True
    
    def _execute_single(
        self, 
        step: Dict[str, Any], 
        index: int, 
        total: int,
        suffix: str = "",
        host_idx: Optional[int] = None,
        host_total: Optional[int] = None
    ) -> bool:
        """Execute a single step (non-iterated or one iteration)."""
        step_id = str(step.get("id", index))
        description = step.get("description") or step.get("desc") or "No description"
        kind = step.get("kind", "")
        timeout = step.get("timeout")
        on_failure = step.get("on_failure", "fail")
        
        # Adjust description for iterated steps
        if suffix:
            current_host = step.get("hosts")
            description = f"{description} (on {current_host})"
        
        # Get or build the step file
        step_file = None
        rendered_args = []
        
        if kind == "command":
            command_text = step.get("command")
            if not command_text:
                self.logger.error(f"[{step_id}] ERROR: 'command' kind requires 'command' field")
                self.state_mgr.mark_skipped(step_id + suffix, "missing command")
                return on_failure == "continue"
        else:
            # File-based kinds
            file_path = step.get("file")
            if not file_path:
                self.logger.warning(f"[{step_id}] SKIPPING: Missing file")
                self.state_mgr.mark_skipped(step_id + suffix, "missing file")
                return True
            
            try:
                step_file = find_step_file(file_path, self.ctx.data_dir)
            except Exception as e:
                self.logger.error(f"[{step_id}] ERROR: {e}")
                self.state_mgr.mark_skipped(step_id + suffix, str(e))
                return False
            
            if not step_file.exists():
                self.logger.error(f"[{step_id}] ERROR: File not found: {step_file}")
                self.state_mgr.mark_skipped(step_id + suffix, "file not found")
                return False
            
            # Render arguments
            step_args = step.get("args") or []
            rendered_args = [
                replace_placeholders(
                    arg, 
                    self.ctx.env_name, 
                    self.ctx.deployment_plan, 
                    self.ctx.deployment_type, 
                    self.ctx.group_vars
                )
                for arg in step_args
            ]
        
        # Build command
        try:
            command = build_command(step, step_file, self.ctx, rendered_args)
        except ExecutionError as e:
            self.logger.error(f"[{step_id}] ERROR: {e}")
            self.state_mgr.mark_skipped(step_id + suffix, str(e))
            return False
        
        # Create log file
        safe_desc = description.replace(" ", "_").replace("/", "-").replace("(", "").replace(")", "")
        log_file = self.ctx.log_path / f"{step_id}{suffix}-{safe_desc}.log"
        
        # Print step header
        print()  # Blank line
        self.logger.info("=" * 70)
        if host_idx:
            self.logger.info(f"STEP {index}/{total}.{host_idx}: {description}")
        else:
            self.logger.info(f"STEP {index}/{total}: {description}")
        self.logger.info("=" * 70)
        if step.get("hosts"):
            self.logger.info(f"Target: {step.get('hosts')}")
        if timeout:
            self.logger.info(f"Timeout: {timeout}s")
        self.logger.info("")  # Blank line
        
        # Update state to running
        state_key = step_id + suffix
        self.state_mgr.mark_running(
            state_key,
            log=str(log_file),
            kind=kind,
            description=description
        )
        
        # Execute command
        exit_code = run_command(command, log_file, self.ctx, timeout)
        
        # Update state based on result
        print()  # Blank line
        if exit_code == 0:
            self.logger.info("✅ SUCCESS")
            self.logger.info("")
            self.state_mgr.mark_success(state_key)
            return True
        else:
            self.logger.error("❌ FAILED")
            self.logger.error(f"Exit code: {exit_code}")
            self.logger.error(f"Log: {log_file}")
            self.logger.error("")
            self.state_mgr.mark_failed(state_key)
            
            if on_failure == "continue":
                self.logger.warning("⚠️  Continuing despite failure")
                return True
            else:
                return False