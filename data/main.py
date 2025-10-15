#!/usr/bin/env python3
"""
Simple Installer Runner
-----------------------
Runs installation steps from a profile YAML file.
Each step can be an Ansible playbook or a direct command.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml


# Where everything lives
BASE_DIR = Path("/install")
DATA_DIR = BASE_DIR / "data"
ENV_DIR = Path("/docker-workspace/config")
IMAGES_DIR = BASE_DIR / "images"
LOG_DIR = BASE_DIR / "logs"
STATE_FILE = LOG_DIR / "state.json"

# Exit codes
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 2
EXIT_FILE_NOT_FOUND = 3
EXIT_UNSUPPORTED_KIND = 4
EXIT_STEP_FAILED = 5
EXIT_VALIDATION_FAILED = 6


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


def get_host_from_inventory(inventory_file: Path, host_or_group: str) -> Dict[str, Any]:
    """
    Get connection info for a host from inventory.
    Returns dict with ansible_host, ansible_user, ansible_ssh_pass, etc.
    """
    try:
        inventory = load_yaml_file(inventory_file)
    except Exception as e:
        raise ValueError(f"Failed to load inventory: {e}")
    
    def find_host(data: Dict, target: str, parent_vars: Dict = None) -> Optional[Dict]:
        """Recursively search for host in inventory."""
        parent_vars = parent_vars or {}
        
        # Merge parent vars
        current_vars = parent_vars.copy()
        if 'vars' in data:
            current_vars.update(data['vars'])
        
        # Check hosts at this level
        if 'hosts' in data and isinstance(data['hosts'], dict):
            if target in data['hosts']:
                host_data = data['hosts'][target].copy() if isinstance(data['hosts'][target], dict) else {}
                host_data.update(current_vars)
                return host_data
        
        # Check children
        if 'children' in data and isinstance(data['children'], dict):
            # Check if target is a group name
            if target in data['children']:
                group_data = data['children'][target]
                # Return first host in this group
                if 'hosts' in group_data and isinstance(group_data['hosts'], dict):
                    first_host_name = list(group_data['hosts'].keys())[0]
                    host_data = group_data['hosts'][first_host_name].copy()
                    if 'vars' in group_data:
                        host_data.update(group_data['vars'])
                    host_data.update(current_vars)
                    return host_data
            
            # Recurse into children
            for child_name, child_data in data['children'].items():
                result = find_host(child_data, target, current_vars)
                if result:
                    return result
        
        return None
    
    # Special case: localhost
    if host_or_group == 'localhost':
        return {'ansible_host': 'localhost', 'ansible_user': os.getenv('USER', 'root')}
    
    host_info = find_host(inventory.get('all', {}), host_or_group)
    
    if not host_info:
        raise ValueError(f"Host or group '{host_or_group}' not found in inventory")
    
    return host_info


def replace_placeholders(text: str, env_name: str, profile_name: str, 
                        profile_kind: str, group_vars: Dict[str, Any]) -> str:
    """
    Replace placeholders in text with actual values.
    Supports: {env}, {profile}, {profile_kind}, {variable_name}
    """
    result = (text
              .replace("{env}", env_name)
              .replace("{profile}", profile_name)
              .replace("{profile_kind}", profile_kind))
    
    # Replace any group_vars variables
    for key, value in group_vars.items():
        if isinstance(value, (str, int, float, bool)):
            result = result.replace(f"{{{key}}}", str(value))
    
    return result


def find_step_file(file_path: str) -> Path:
    """
    Convert step file paths to absolute paths.
    All paths in profiles should be relative to /install/data.
    """
    path = Path(file_path)
    
    if path.is_absolute():
        if str(path).startswith("/docker-workspace/config/"):
            return path
        raise ValueError(
            f"Use relative paths in profiles (relative to /install/data): {file_path}"
        )
    
    return DATA_DIR / path


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
                 env_name: str, profile_name: str, profile_kind: str,
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
            command, env_name, profile_name, profile_kind, group_vars
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


def run_command(command: List[str], log_file: Path, timeout: Optional[int] = None) -> int:
    """
    Run a command and save output to a log file.
    Returns the exit code (0 = success).
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    logging.info(f"Running: {' '.join(command)}")
    
    # Set up environment for ansible
    env = os.environ.copy()
    env["ANSIBLE_CONFIG"] = str(DATA_DIR / "ansible.cfg")
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
                cwd=str(BASE_DIR),
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


def load_state() -> Dict[str, Any]:
    """Load the state file that tracks which steps completed."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"Could not load state file: {e}. Starting fresh.")
    return {}


def save_state(state: Dict[str, Any]) -> None:
    """Save progress to the state file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save state: {e}")


def install_rpms(logger: logging.Logger) -> bool:
    """
    Install any RPMs found in /install/images/rpms/.
    Returns True if successful or no RPMs found, False on failure.
    """
    rpms_dir = IMAGES_DIR / "rpms"
    
    if not rpms_dir.exists():
        logger.info("No rpms directory found, skipping RPM installation")
        return True
    
    rpm_files = list(rpms_dir.glob("*.rpm"))
    
    if not rpm_files:
        logger.info("No RPM files found in rpms directory")
        return True
    
    logger.info("=" * 60)
    logger.info("Installing RPMs from images/rpms/")
    logger.info("=" * 60)
    logger.info(f"Found {len(rpm_files)} RPM(s) to install:")
    
    for rpm in rpm_files:
        logger.info(f"  - {rpm.name}")
    
    rpm_paths = [str(rpm) for rpm in rpm_files]
    command = ["rpm", "-ivh", "--force"] + rpm_paths
    
    log_file = LOG_DIR / "00-install-rpms.log"
    
    logger.info(f"Installing RPMs... (log: {log_file})")
    exit_code = run_command(command, log_file)
    
    if exit_code == 0:
        logger.info("✅ RPMs installed successfully")
        logger.info("=" * 60 + "\n")
        return True
    else:
        logger.error(f"❌ RPM installation failed (exit code: {exit_code})")
        logger.error(f"See log: {log_file}")
        logger.info("=" * 60 + "\n")
        return False


def validate_profile(profile_file: Path, profile_data: Dict[str, Any], 
                     group_vars: Dict[str, Any], logger: logging.Logger) -> bool:
    """Validate profile structure and file existence."""
    logger.info("=" * 60)
    logger.info("VALIDATION: Checking profile configuration")
    logger.info("=" * 60)
    
    errors = []
    
    if "steps" not in profile_data:
        errors.append(f"Profile must have 'steps' key: {profile_file}")
        return False
    
    steps = profile_data.get("steps", [])
    if not isinstance(steps, list):
        errors.append(f"'steps' must be a list: {profile_file}")
        return False
    
    if not steps:
        errors.append(f"Profile has no steps defined: {profile_file}")
        return False
    
    logger.info(f"✓ Profile has {len(steps)} steps")
    
    # Validate metadata if present
    metadata = profile_data.get("metadata", {})
    if metadata:
        logger.info(f"✓ Profile: {metadata.get('name', 'Unknown')}")
        logger.info(f"  Version: {metadata.get('version', 'Unknown')}")
        logger.info(f"  Description: {metadata.get('description', 'N/A')}")
    
    # Validate each step
    logger.info("\nValidating steps...")
    for idx, step in enumerate(steps, 1):
        step_id = step.get("id", f"step_{idx}")
        kind = step.get("kind")
        description = step.get("description", "No description")
        
        logger.info(f"\n  Step {idx}: {step_id}")
        logger.info(f"    Description: {description}")
        
        if not kind:
            errors.append(f"Step '{step_id}' missing 'kind' field")
            continue
        
        logger.info(f"    Kind: {kind}")
        
        # Validate based on kind
        if kind == "command":
            if not step.get("command"):
                errors.append(f"Step '{step_id}' of kind 'command' missing 'command' field")
            else:
                logger.info(f"    Command: {step.get('command')}")
        else:
            file_path = step.get("file")
            if not file_path:
                errors.append(f"Step '{step_id}' missing 'file' field")
                continue
            
            logger.info(f"    File: {file_path}")
            
            # Check if file exists
            try:
                step_file = find_step_file(file_path)
                if not step_file.exists():
                    errors.append(f"Step '{step_id}' file not found: {step_file}")
                else:
                    logger.info(f"    ✓ File exists")
            except ValueError as e:
                errors.append(f"Step '{step_id}': {e}")
        
        # Show hosts if specified
        if step.get("hosts"):
            logger.info(f"    Hosts: {step.get('hosts')}")
    
    if errors:
        logger.error("\n❌ PROFILE VALIDATION FAILED:")
        for error in errors:
            logger.error(f"  - {error}")
        return False
    
    logger.info("\n✅ Profile validation passed!")
    logger.info("=" * 60)
    return True


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run installation steps")
    parser.add_argument("--env", required=True, help="Environment name")
    parser.add_argument("--profile", required=True, help="Profile type (basekit/baremetal/aws)")
    parser.add_argument("--resume", action="store_true", help="Skip already completed steps")
    parser.add_argument("--validate-only", action="store_true", help="Only validate, don't run")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    cli_args = parser.parse_args()

    env_name = cli_args.env
    profile_kind = cli_args.profile

    # Setup logging
    logger = setup_logging(LOG_DIR, cli_args.verbose)
    logger.info("=" * 60)
    logger.info("OpenSpace Onboarder Starting")
    logger.info("=" * 60)
    logger.info(f"Environment: {env_name}")
    logger.info(f"Profile: {profile_kind}")
    logger.info(f"Resume mode: {cli_args.resume}")
    logger.info("=" * 60)

    # Find config files
    env_path = ENV_DIR / env_name
    inventory_file = env_path / "config.yml"
    group_vars_file = env_path / "group_vars" / f"{profile_kind}.yml"

    if not inventory_file.exists():
        logger.error(f"Config file not found: {inventory_file}")
        return EXIT_CONFIG_ERROR
    
    if not group_vars_file.exists():
        logger.error(f"Group vars file not found: {group_vars_file}")
        return EXIT_CONFIG_ERROR

    # Load the profile name from group_vars
    try:
        group_vars = load_yaml_file(group_vars_file)
    except Exception as e:
        logger.error(f"Failed to load group vars: {e}")
        return EXIT_CONFIG_ERROR
    
    if "profile_kind" not in group_vars:
        logger.error(f"Missing 'profile_kind' in {group_vars_file}")
        return EXIT_CONFIG_ERROR
    
    if "profile_name" not in group_vars:
        logger.error(f"Missing 'profile_name' in {group_vars_file}")
        return EXIT_CONFIG_ERROR
    
    profile_name = group_vars["profile_name"]
    
    # Find the profile file
    profile_file = DATA_DIR / "profiles" / profile_kind / f"{profile_name}.yml"
    if not profile_file.exists():
        logger.error(f"Profile file not found: {profile_file}")
        return EXIT_CONFIG_ERROR

    logger.info(f"Using profile file: {profile_file}")

    # Load the steps from the profile
    try:
        profile_data = load_yaml_file(profile_file)
    except Exception as e:
        logger.error(f"Failed to load profile: {e}")
        return EXIT_CONFIG_ERROR
    
    # Validate profile structure
    if not validate_profile(profile_file, profile_data, group_vars, logger):
        return EXIT_VALIDATION_FAILED
    
    # If validate-only mode, stop here
    if cli_args.validate_only:
        logger.info("\n✅ Validation complete. Exiting (--validate-only mode)")
        return EXIT_SUCCESS
    
    # Install RPMs before running steps
    if not install_rpms(logger):
        logger.error("Failed to install required RPMs")
        return EXIT_CONFIG_ERROR
    
    # Extract steps from profile
    steps = profile_data.get("steps", [])
    
    if not steps:
        logger.error("No steps found in profile")
        return EXIT_CONFIG_ERROR

    # Load or initialize state tracking
    state = load_state()
    state["env"] = env_name
    state["profile_kind"] = profile_kind
    state["profile_name"] = profile_name
    
    if "steps" not in state:
        state["steps"] = {}

    logger.info("\n" + "=" * 60)
    logger.info(f"Starting execution of {len(steps)} steps")
    logger.info("=" * 60 + "\n")

    # Run each step
    for index, step in enumerate(steps, start=1):
        step_id = str(step.get("id", index))
        description = step.get("description") or step.get("desc") or "No description"
        kind = step.get("kind", "")
        timeout = step.get("timeout")
        on_failure = step.get("on_failure", "fail")
        hosts = step.get("hosts", "localhost")
        iterate = step.get("iterate", False)  # Whether to run command on each host

        # Skip if no kind
        if not kind:
            logger.warning(f"[{step_id}] SKIPPING: Missing kind")
            state["steps"][step_id] = {"status": "skipped"}
            save_state(state)
            continue

        # Skip if already completed (when using --resume)
        if cli_args.resume and state["steps"].get(step_id, {}).get("status") == "ok":
            logger.info(f"[{step_id}] SKIPPING: Already completed - {description}")
            continue

        # Determine if we need to iterate through hosts
        should_iterate = False
        hosts_list = []
        
        if kind == "command" and iterate and isinstance(hosts, list) and len(hosts) > 1:
            should_iterate = True
            hosts_list = hosts
        
        # If not iterating, treat as single execution
        if not should_iterate:
            hosts_list = [None]  # Single execution

        # Execute for each host (or once if not iterating)
        for host_idx, current_host in enumerate(hosts_list, 1):
            # Update step to use current host if iterating
            if should_iterate:
                step_for_exec = step.copy()
                step_for_exec["hosts"] = current_host
                suffix = f"_{current_host}"
                current_description = f"{description} (on {current_host})"
            else:
                step_for_exec = step
                suffix = ""
                current_description = description

            # Handle command kind
            if kind == "command":
                command = step_for_exec.get("command")
                if not command:
                    logger.error(f"[{step_id}] ERROR: 'command' kind requires 'command' field")
                    state["steps"][step_id] = {"status": "failed", "error": "missing command"}
                    save_state(state)
                    return EXIT_CONFIG_ERROR
                
                step_file = None
                rendered_args = []
            else:
                # Handle file-based kinds
                file_path = step_for_exec.get("file")
                if not file_path:
                    logger.warning(f"[{step_id}] SKIPPING: Missing file")
                    state["steps"][step_id] = {"status": "skipped"}
                    save_state(state)
                    continue
                
                # Find the step file
                try:
                    step_file = find_step_file(file_path)
                except ValueError as e:
                    logger.error(f"[{step_id}] ERROR: {e}")
                    state["steps"][step_id] = {"status": "failed", "error": str(e)}
                    save_state(state)
                    return EXIT_FILE_NOT_FOUND
                
                if not step_file.exists():
                    logger.error(f"[{step_id}] ERROR: File not found: {step_file}")
                    state["steps"][step_id] = {"status": "failed", "error": "file not found"}
                    save_state(state)
                    return EXIT_FILE_NOT_FOUND
                
                # Replace placeholders in arguments
                step_args = step_for_exec.get("args") or []
                rendered_args = [
                    replace_placeholders(arg, env_name, profile_name, profile_kind, group_vars)
                    for arg in step_args
                ]

            # Build the command
            try:
                command = build_command(step_for_exec, step_file, inventory_file, rendered_args,
                                       env_name, profile_name, profile_kind, group_vars)
            except ValueError as e:
                logger.error(f"[{step_id}] ERROR: {e}")
                state["steps"][step_id] = {"status": "failed", "error": str(e)}
                save_state(state)
                return EXIT_UNSUPPORTED_KIND

            # Create log file name
            safe_desc = current_description.replace(" ", "_").replace("/", "-").replace("(", "").replace(")", "")
            log_file = LOG_DIR / f"{step_id}{suffix}-{safe_desc}.log"

            # Update state to "running"
            print()  # Blank line for separation
            logger.info("=" * 70)
            if should_iterate:
                logger.info(f"STEP {index}/{len(steps)}.{host_idx}: {current_description}")
            else:
                logger.info(f"STEP {index}/{len(steps)}: {current_description}")
            logger.info("=" * 70)
            if step_for_exec.get("hosts"):
                logger.info(f"Target: {step_for_exec.get('hosts')}")
            if timeout:
                logger.info(f"Timeout: {timeout}s")
            logger.info("")  # Blank line before output
            
            state_key = f"{step_id}{suffix}" if should_iterate else step_id
            state["steps"][state_key] = {
                "status": "running",
                "log": str(log_file),
                "kind": kind,
                "description": current_description
            }
            save_state(state)

            # Run the command
            exit_code = run_command(command, log_file, timeout)

            # Update state based on result
            if exit_code == 0:
                print()  # Blank line
                logger.info("✅ SUCCESS")
                logger.info("")
                state["steps"][state_key]["status"] = "ok"
                state["steps"][state_key]["exit_code"] = 0
            else:
                print()  # Blank line
                logger.error("❌ FAILED")
                logger.error(f"Exit code: {exit_code}")
                logger.error(f"Log: {log_file}")
                logger.error("")
                state["steps"][state_key]["status"] = "failed"
                state["steps"][state_key]["exit_code"] = exit_code
                save_state(state)
                
                # Handle failure based on on_failure setting
                if on_failure == "continue":
                    logger.warning("⚠️  Continuing despite failure")
                else:
                    return EXIT_STEP_FAILED

            save_state(state)

    logger.info("\n" + "=" * 70)
    logger.info("✅ ALL STEPS COMPLETED SUCCESSFULLY!")
    logger.info("=" * 70)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())