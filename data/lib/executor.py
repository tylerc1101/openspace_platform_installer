"""
Command building and execution.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from .config import replace_placeholders
from .inventory import get_host_from_inventory


def build_ssh_command(host_info: Dict[str, Any], remote_command: str) -> List[str]:
    """Build SSH command to execute remote command with real-time output."""
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


def build_command(step: Dict[str, Any], step_file: Path, 
                 inventory_file: Path, rendered_args: List[str],
                 env_name: str, deployment_plan: str, deployment_type: str,
                 group_vars: Dict[str, Any]) -> List[str]:
    """Build the command to run based on step type."""
    kind = step.get("kind", "").lower()
    hosts = step.get("hosts", "localhost")
    
    # Handle 'command' kind - direct command execution
    if kind == "command":
        command = step.get("command")
        if not command:
            raise ValueError("'command' kind requires 'command' field")
        
        # Replace placeholders in command
        rendered_command = replace_placeholders(
            command, env_name, deployment_plan, deployment_type, group_vars
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
            host_info = get_host_from_inventory(inventory_file, target_host)
            return build_ssh_command(host_info, rendered_command)
    
    # Handle 'ansible' kind - Ansible playbooks
    elif kind == "ansible":
        # Build ansible-playbook command
        cmd = ["ansible-playbook", "-i", str(inventory_file), str(step_file)]
        
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
        raise ValueError(f"Unknown step kind: {kind}")


def run_command(command: List[str], log_file: Path, log_dir: Path,
                data_dir: Path, timeout: Optional[int] = None) -> int:
    """
    Run a command and save output to a log file.
    Returns the exit code (0 = success).
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.info(f"Running: {' '.join(command)}")
    
    # Set up environment for ansible
    env = os.environ.copy()
    env["ANSIBLE_CONFIG"] = str(data_dir / "ansible.cfg")
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
                cwd=str(data_dir.parent),
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
        logging.error(f"Command timed out after {timeout} seconds")
        process.kill()
        return 124  # Standard timeout exit code
    except Exception as e:
        logging.error(f"Failed to run command: {e}")
        return 1