#!/usr/bin/env python3
"""
Simple Installer Runner
-----------------------
Runs installation steps from a profile YAML file.
Each step can be an Ansible playbook, Python script, or shell script.
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml


# Where everything lives
BASE_DIR = Path("/install")
DATA_DIR = BASE_DIR / "data"
ENV_DIR = BASE_DIR / "usr_home"
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
    
    # Create logger
    logger = logging.getLogger("onboarder")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Console handler with colors (if supported)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    
    # File handler with detailed info
    file_handler = logging.FileHandler(log_dir / "onboarder.log")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
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


def replace_placeholders(text: str, env_name: str, profile_name: str, 
                        profile_kind: str, group_vars: Dict[str, Any]) -> str:
    """
    Replace placeholders in text with actual values.
    Supports:
    - {env} - environment name
    - {profile} - profile name  
    - {profile_kind} - profile kind
    - {variable_name} - any variable from group_vars
    """
    result = (text
              .replace("{env}", env_name)
              .replace("{profile}", profile_name)
              .replace("{profile_kind}", profile_kind))
    
    # Replace any group_vars variables (like {onboarder}, {basekit}, etc.)
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
    
    # Don't allow absolute paths in profiles (except for custom usr_home scripts)
    if path.is_absolute():
        if str(path).startswith("/install/usr_home/"):
            return path
        raise ValueError(
            f"Use relative paths in profiles (relative to /install/data): {file_path}"
        )
    
    # Relative to DATA_DIR
    return DATA_DIR / path


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


def run_command(command: List[str], log_file: Path, timeout: Optional[int] = None) -> int:
    """
    Run a command and save output to a log file.
    Returns the exit code (0 = success).
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    logging.info(f"Running: {' '.join(command)}")
    
    try:
        with open(log_file, 'w') as log:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(BASE_DIR)
            )
            
            # Print and log output line by line
            for line in process.stdout:
                print(line, end='')
                log.write(line)
            
            exit_code = process.wait(timeout=timeout)
            return exit_code
            
    except subprocess.TimeoutExpired:
        logging.error(f"Command timed out after {timeout} seconds")
        process.kill()
        return 124  # Standard timeout exit code
    except Exception as e:
        logging.error(f"Failed to run command: {e}")
        return 1


def build_command(step: Dict[str, Any], step_file: Path, 
                 inventory_file: Path, rendered_args: List[str]) -> List[str]:
    """Build the command to run based on step type."""
    kind = step.get("kind", "").lower()
    
    if kind == "ansible":
        return ["ansible-playbook", "-i", str(inventory_file), str(step_file)] + rendered_args
    
    elif kind in ("python", "python3"):
        return ["python3", str(step_file)] + rendered_args
    
    elif kind in ("shell", "bash", "sh"):
        shell = "/bin/bash" if kind in ("bash", "shell") else "/bin/sh"
        return [shell, str(step_file)] + rendered_args
    
    else:
        raise ValueError(f"Unknown step kind: {kind}")


def validate_environment(env_path: Path, profile_kind: str, logger: logging.Logger) -> bool:
    """
    Validate that the environment directory has all required files.
    Returns True if valid, False otherwise.
    """
    logger.info("=" * 60)
    logger.info("VALIDATION: Checking environment configuration")
    logger.info("=" * 60)
    
    errors = []
    
    # Check for config.yml
    inventory_file = env_path / "config.yml"
    if not inventory_file.exists():
        errors.append(f"Missing inventory file: {inventory_file}")
    else:
        logger.info(f"✓ Inventory file exists: {inventory_file}")
        try:
            load_yaml_file(inventory_file)
            logger.info("✓ Inventory is valid YAML")
        except Exception as e:
            errors.append(f"Invalid inventory YAML: {e}")
    
    # Check for group_vars
    group_vars_dir = env_path / "group_vars"
    if not group_vars_dir.exists():
        errors.append(f"Missing group_vars directory: {group_vars_dir}")
    else:
        logger.info(f"✓ Group vars directory exists: {group_vars_dir}")
        
        # Check for profile-specific group_vars
        profile_vars = group_vars_dir / f"{profile_kind}.yml"
        if not profile_vars.exists():
            errors.append(f"Missing group vars for profile: {profile_vars}")
        else:
            logger.info(f"✓ Profile group vars exist: {profile_vars}")
            
            # Validate it has required keys
            try:
                gv = load_yaml_file(profile_vars)
                if "profile_kind" not in gv:
                    errors.append(f"Missing 'profile_kind' in {profile_vars}")
                elif gv["profile_kind"] != profile_kind:
                    errors.append(
                        f"profile_kind mismatch: group_vars says '{gv['profile_kind']}' "
                        f"but using '{profile_kind}'"
                    )
                else:
                    logger.info(f"✓ profile_kind matches: {profile_kind}")
                
                if "profile_name" not in gv:
                    errors.append(f"Missing 'profile_name' in {profile_vars}")
                else:
                    logger.info(f"✓ profile_name: {gv['profile_name']}")
                    
            except Exception as e:
                errors.append(f"Failed to validate group_vars: {e}")
    
    # Check for SSH directory
    ssh_dir = env_path / ".ssh"
    if ssh_dir.exists():
        logger.info(f"✓ SSH directory exists: {ssh_dir}")
        # Check for common SSH keys
        for key_name in ["onboarder_ssh_key", "rancher_ssh_key", "osdc_ssh_key", "osms_ssh_key"]:
            pub_key = ssh_dir / f"{key_name}.pub"
            if pub_key.exists():
                logger.info(f"  ✓ Found: {key_name}.pub")
    else:
        logger.warning(f"⚠ No .ssh directory found (may be needed): {ssh_dir}")
    
    if errors:
        logger.error("\n❌ VALIDATION FAILED:")
        for error in errors:
            logger.error(f"  - {error}")
        return False
    
    logger.info("\n✅ Environment validation passed!")
    logger.info("=" * 60)
    return True


def validate_profile(profile_file: Path, profile_data: Dict[str, Any], 
                     group_vars: Dict[str, Any], logger: logging.Logger) -> bool:
    """
    Validate that the profile file is properly structured and all referenced files exist.
    Substitutes variables from group_vars during validation.
    Returns True if valid, False otherwise.
    """
    logger.info("=" * 60)
    logger.info("VALIDATION: Checking profile configuration")
    logger.info("=" * 60)
    
    errors = []
    
    # Check for required top-level keys
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
    
    # Check requirements if present
    requirements = profile_data.get("requirements", {})
    if requirements:
        logger.info("\nChecking requirements...")
        
        # Check required images (substitute variables)
        req_images = requirements.get("images", [])
        for image_template in req_images:
            # Substitute variables like {onboarder}
            image = image_template
            for key, value in group_vars.items():
                if isinstance(value, str):
                    image = image.replace(f"{{{key}}}", value)
            
            image_path = DATA_DIR / "images" / image
            if not image_path.exists():
                errors.append(f"Required image not found: {image_path}")
            else:
                logger.info(f"  ✓ Image exists: {image}")
    
    # Validate each step
    logger.info("\nValidating steps...")
    for idx, step in enumerate(steps, 1):
        step_id = step.get("id", f"step_{idx}")
        kind = step.get("kind")
        file_path = step.get("file")
        description = step.get("description", "No description")
        
        logger.info(f"\n  Step {idx}: {step_id}")
        logger.info(f"    Description: {description}")
        
        # Check required fields
        if not kind:
            errors.append(f"Step '{step_id}' missing 'kind' field")
            continue
        
        if not file_path:
            errors.append(f"Step '{step_id}' missing 'file' field")
            continue
        
        logger.info(f"    Kind: {kind}")
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

    # Check if environment directory exists
    if not env_path.exists():
        logger.error(f"Environment directory not found: {env_path}")
        return EXIT_CONFIG_ERROR
    
    # Validate environment
    if not validate_environment(env_path, profile_kind, logger):
        return EXIT_VALIDATION_FAILED
    
    if not inventory_file.exists():
        logger.error(f"Config file not found: {inventory_file}")
        return EXIT_CONFIG_ERROR
    
    if not group_vars_file.exists():
        logger.error(f"Group vars file not found: {group_vars_file}")
        return EXIT_CONFIG_ERROR

    # Load the profile name and kind from group_vars
    try:
        group_vars = load_yaml_file(group_vars_file)
    except Exception as e:
        logger.error(f"Failed to load group vars: {e}")
        return EXIT_CONFIG_ERROR
    
    # Get profile_kind and profile_name from group_vars
    if "profile_kind" not in group_vars:
        logger.error(f"Missing 'profile_kind' in {group_vars_file}")
        logger.error("Add: profile_kind: basekit  # or baremetal, aws")
        return EXIT_CONFIG_ERROR
    
    if "profile_name" not in group_vars:
        logger.error(f"Missing 'profile_name' in {group_vars_file}")
        logger.error("Add: profile_name: default  # or custom, minimal, etc.")
        return EXIT_CONFIG_ERROR
    
    gv_profile_kind = group_vars["profile_kind"]
    profile_name = group_vars["profile_name"]
    
    # Verify it matches what we're trying to use
    if gv_profile_kind != profile_kind:
        logger.error(
            f"Profile kind mismatch: group_vars declares '{gv_profile_kind}' "
            f"but script is using '{profile_kind}'"
        )
        return EXIT_CONFIG_ERROR
    
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
    state["inventory"] = str(inventory_file)
    state["profile_file"] = str(profile_file)
    
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
        file_path = step.get("file")
        step_args = step.get("args") or []
        timeout = step.get("timeout")
        on_failure = step.get("on_failure", "fail")

        # Skip if no kind or file
        if not kind or not file_path:
            logger.warning(f"[{step_id}] SKIPPING: Missing kind or file")
            state["steps"][step_id] = {"status": "skipped"}
            save_state(state)
            continue

        # Skip if already completed (when using --resume)
        if cli_args.resume and state["steps"].get(step_id, {}).get("status") == "ok":
            logger.info(f"[{step_id}] SKIPPING: Already completed - {description}")
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

        # Replace placeholders in arguments (including group_vars variables)
        rendered_args = [
            replace_placeholders(arg, env_name, profile_name, profile_kind, group_vars)
            for arg in step_args
        ]

        # Build the command
        try:
            command = build_command(step, step_file, inventory_file, rendered_args)
        except ValueError as e:
            logger.error(f"[{step_id}] ERROR: {e}")
            state["steps"][step_id] = {"status": "failed", "error": str(e)}
            save_state(state)
            return EXIT_UNSUPPORTED_KIND

        # Create log file name
        safe_desc = description.replace(" ", "_").replace("/", "-")
        log_file = LOG_DIR / f"{step_id}-{safe_desc}.log"

        # Update state to "running"
        logger.info(f"\n{'=' * 60}")
        logger.info(f"[{step_id}] {description}")
        logger.info(f"{'=' * 60}")
        logger.info(f"Step {index} of {len(steps)}")
        logger.info(f"Log file: {log_file}")
        if timeout:
            logger.info(f"Timeout: {timeout}s")
        
        state["steps"][step_id] = {
            "status": "running",
            "log": str(log_file),
            "kind": kind,
            "file": str(step_file),
            "description": description
        }
        save_state(state)

        # Run the command
        exit_code = run_command(command, log_file, timeout)

        # Update state based on result
        if exit_code == 0:
            logger.info(f"\n✅ [{step_id}] SUCCESS")
            state["steps"][step_id]["status"] = "ok"
            state["steps"][step_id]["exit_code"] = 0
        else:
            logger.error(f"\n❌ [{step_id}] FAILED (exit code: {exit_code})")
            logger.error(f"    See log: {log_file}")
            state["steps"][step_id]["status"] = "failed"
            state["steps"][step_id]["exit_code"] = exit_code
            save_state(state)
            
            # Handle failure based on on_failure setting
            if on_failure == "continue":
                logger.warning(f"    Continuing despite failure (on_failure=continue)")
            else:
                logger.error(f"    Stopping execution (on_failure={on_failure})")
                return EXIT_STEP_FAILED

        save_state(state)

    logger.info("\n" + "=" * 60)
    logger.info("✅ All steps completed successfully!")
    logger.info("=" * 60)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())