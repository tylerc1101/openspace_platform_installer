"""
Command building and execution.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from .config import replace_placeholders
from .context import ExecutionContext
from .exceptions import ExecutionError
from .inventory import get_host_from_inventory


def build_ssh_command(host_info: Dict[str, Any], remote_command: str) -> List[str]:
    """
    Build SSH command to execute remote command with real-time output.
    
    Args:
        host_info: Host connection information from inventory
        remote_command: Command to execute remotely
        
    Returns:
        List of command arguments for subprocess
        
    Example:
        >>> cmd = build_ssh_command(
        ...     {'ansible_host': '10.0.0.1', 'ansible_user': 'root'},
        ...     'ls -la /tmp'
        ... )
    """
    ssh_cmd = []
    
    # Use sshpass if password is provided
    if host_info.get('ansible_ssh_pass'):
        ssh_cmd.extend(['sshpass', '-p', host_info['ansible_ssh_pass']])
    
    ssh_cmd.append('ssh')
    
    # SSH options for non-interactive, real-time output
    ssh_cmd.extend([
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'UserKnownHostsFile=/dev/null',
        '-o', 'ConnectTimeout=30',
        '-tt'  # Force TTY allocation for real-time output
    ])
    
    # SSH key if specified
    if host_info.get('ansible_ssh_private_key_file'):
        ssh_cmd.extend(['-i', host_info['ansible_ssh_private_key_file']])
    
    # Port if not default
    port = host_info.get('ansible_port', 22)
    if port != 22:
        ssh_cmd.extend(['-p', str(port)])
    
    # User@host
    user = host_info.get('ansible_user', 'root')
    host = host_info.get('ansible_host', 'localhost')
    ssh_cmd.append(f"{user}@{host}")
    
    # Remote command
    ssh_cmd.append(remote_command)
    
    return ssh_cmd


def build_command(
    step: Dict[str, Any], 
    step_file: Optional[Path],
    ctx: ExecutionContext,
    rendered_args: List[str]
) -> List[str]:
    """
    Build the command to run based on step type.
    
    Args:
        step: Step configuration dictionary
        step_file: Path to step file (for ansible/python/bash)
        ctx: Execution context
        rendered_args: Already-rendered command arguments
        
    Returns:
        List of command arguments for subprocess
        
    Raises:
        ExecutionError: If command cannot be built
        
    Example:
        >>> cmd = build_command(
        ...     {'kind': 'ansible', 'file': 'setup.yml'},
        ...     Path('/install/data/tasks/setup.yml'),
        ...     ctx,
        ...     ['-v']
        ... )
    """
    kind = step.get("kind", "").lower()
    hosts = step.get("hosts", "localhost")
    
    # Handle 'command' kind - direct command execution
    if kind == "command":
        command = step.get("command")
        if not command:
            raise ExecutionError("'command' kind requires 'command' field")
        
        # Replace placeholders in command
        rendered_command = replace_placeholders(
            command, 
            ctx.env_name, 
            ctx.deployment_plan, 
            ctx.deployment_type, 
            ctx.group_vars
        )
        
        # For command kind, we only handle single host
        # (iteration is handled in main loop)
        target_host = hosts
        if isinstance(hosts, list):
            target_host = hosts[0]  # Will be iterated in main loop
        
        if target_host == "localhost":
            # Run locally using shell
            return ["/bin/bash", "-c", rendered_command]
        else:
            # Run via SSH
            host_info = get_host_from_inventory(ctx.inventory_file, target_host, ctx.logger)
            return build_ssh_command(host_info, rendered_command)
    
    # Handle 'ansible' kind - Ansible playbooks
    elif kind == "ansible":
        # Build ansible-playbook command
        cmd = ["ansible-playbook", "-i", str(ctx.inventory_file), str(step_file)]
        
        # Convert hosts to comma-separated string for Ansible
        if hosts and hosts != "localhost":
            if isinstance(hosts, list):
                hosts_str = ",".join(hosts)
            else:
                hosts_str = hosts
            cmd.extend(["-e", f"target_hosts={hosts_str}"])
        
        # Add other arguments
        cmd.extend(rendered_args)
        
        return cmd
    
    # Handle python/bash/shell kinds with 'file'
    elif kind in ("python", "python3"):
        return ["python3", str(step_file)] + rendered_args
    
    elif kind in ("shell", "bash", "sh"):
        shell = "/bin/bash" if kind in ("bash", "shell") else "/bin/sh"
        return [shell, str(step_file)] + rendered_args
    
    else:
        raise ExecutionError(f"Unknown step kind: {kind}")


def run_command(
    command: List[str], 
    log_file: Path, 
    ctx: ExecutionContext,
    timeout: Optional[int] = None
) -> int:
    """
    Run a command and save output to a log file.
    
    Args:
        command: Command and arguments to execute
        log_file: Path to write command output
        ctx: Execution context
        timeout: Optional timeout in seconds
        
    Returns:
        Exit code (0 = success)
        
    Example:
        >>> exit_code = run_command(
        ...     ['ls', '-la'],
        ...     Path('/var/log/step.log'),
        ...     ctx,
        ...     timeout=300
        ... )
    """
    ctx.log_dir.mkdir(parents=True, exist_ok=True)
    
    ctx.logger.info(f"Running: {' '.join(command)}")
    
    # Set up environment for ansible
    env = os.environ.copy()
    env["ANSIBLE_CONFIG"] = str(ctx.data_dir / "ansible.cfg")
    env["ANSIBLE_HOST_KEY_CHECKING"] = "False"
    env["ANSIBLE_SSH_RETRIES"] = "3"
    env["PYTHONUNBUFFERED"] = "1"
    env["ANSIBLE_FORCE_COLOR"] = "true"
    
    try:
        with open(log_file, 'w') as log:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
                cwd=str(ctx.base_dir),
                env=env
            )
            
            # Print and log output line by line with immediate flush
            for line in process.stdout:
                print(line, end='', flush=True)  # Real-time output
                log.write(line)
                log.flush()
            
            exit_code = process.wait(timeout=timeout)
            return exit_code
            
    except subprocess.TimeoutExpired:
        ctx.logger.error(f"Command timed out after {timeout} seconds")
        process.kill()
        return 124  # Standard timeout exit code
    except Exception as e:
        ctx.logger.error(f"Failed to run command: {e}")
        return 1