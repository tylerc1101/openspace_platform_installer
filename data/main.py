#!/usr/bin/env python3
"""
Simple Installer Runner
-----------------------
Runs installation steps from a profile YAML file.
Each step can be an Ansible playbook, Python script, or shell script.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
import yaml


# Where everything lives
BASE_DIR = Path("/install")
DATA_DIR = BASE_DIR / "data"
ENV_DIR = BASE_DIR / "usr_home"
LOG_DIR = BASE_DIR / "logs"
STATE_FILE = LOG_DIR / "state.json"


def load_yaml_file(file_path):
    """Load a YAML file and return its contents."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def replace_placeholders(text, env_name, profile_name, profile_kind):
    """Replace {env}, {profile}, {profile_kind} in text with actual values."""
    text = text.replace("{env}", env_name)
    text = text.replace("{profile}", profile_name)
    text = text.replace("{profile_kind}", profile_kind)
    return text


def find_step_file(file_path):
    """
    Convert step file paths to absolute paths.
    - Relative paths are relative to /install/data
    - /data/... gets converted to /install/data/...
    """
    path = Path(file_path)
    
    # If it starts with /data/, remap it
    if str(path).startswith("/data/"):
        return DATA_DIR / str(path)[6:]  # skip "/data/"
    
    # If it's already absolute, use as-is
    if path.is_absolute():
        return path
    
    # Otherwise it's relative to DATA_DIR
    return DATA_DIR / path


def load_state():
    """Load the state file that tracks which steps completed."""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_state(state):
    """Save progress to the state file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def run_command(command, log_file):
    """
    Run a command and save output to a log file.
    Returns the exit code (0 = success).
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Running: {' '.join(command)}")
    
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
        
        return process.wait()


def build_command(step, step_file, inventory_file, rendered_args):
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


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run installation steps")
    parser.add_argument("--env", required=True, help="Environment name")
    parser.add_argument("--profile", required=True, help="Profile type (basekit/baremetal/aws)")
    parser.add_argument("--resume", action="store_true", help="Skip already completed steps")
    args = parser.parse_args()

    env_name = args.env
    profile_kind = args.profile

    # Find config files
    env_path = ENV_DIR / env_name
    inventory_file = env_path / "config.yml"
    group_vars_file = env_path / "group_vars" / f"{profile_kind}.yml"

    # Check if files exist
    if not env_path.exists():
        print(f"ERROR: Environment directory not found: {env_path}")
        return 2
    
    if not inventory_file.exists():
        print(f"ERROR: Config file not found: {inventory_file}")
        return 2
    
    if not group_vars_file.exists():
        print(f"ERROR: Group vars file not found: {group_vars_file}")
        return 2

    # Load the profile name from group_vars
    group_vars = load_yaml_file(group_vars_file)
    profile_name = group_vars.get("profile", "default")
    
    # Find the profile file
    profile_file = DATA_DIR / "profiles" / profile_kind / f"{profile_name}.yml"
    if not profile_file.exists():
        print(f"ERROR: Profile file not found: {profile_file}")
        return 2

    # Load the steps from the profile
    profile_data = load_yaml_file(profile_file)
    
    # Profile can be a list directly, or a dict with a "steps" key
    if isinstance(profile_data, dict):
        steps = profile_data.get("steps", [])
    else:
        steps = profile_data

    if not steps:
        print("ERROR: No steps found in profile")
        return 2

    # Load or initialize state tracking
    state = load_state()
    state["env"] = env_name
    state["profile_kind"] = profile_kind
    state["profile_name"] = profile_name
    
    if "steps" not in state:
        state["steps"] = {}

    # Run each step
    for index, step in enumerate(steps, start=1):
        step_id = str(step.get("id", index))
        description = step.get("description") or step.get("desc") or "No description"
        kind = step.get("kind", "")
        file_path = step.get("file")
        args = step.get("args") or []

        # Skip if no kind or file
        if not kind or not file_path:
            print(f"[{step_id}] SKIPPING: Missing kind or file")
            state["steps"][step_id] = {"status": "skipped"}
            save_state(state)
            continue

        # Skip if already completed (when using --resume)
        if args.resume and state["steps"].get(step_id, {}).get("status") == "ok":
            print(f"[{step_id}] SKIPPING: Already completed - {description}")
            continue

        # Find the step file
        step_file = find_step_file(file_path)
        if not step_file.exists():
            print(f"[{step_id}] ERROR: File not found: {step_file}")
            state["steps"][step_id] = {"status": "failed", "error": "file not found"}
            save_state(state)
            return 3

        # Replace placeholders in arguments
        rendered_args = [
            replace_placeholders(arg, env_name, profile_name, profile_kind)
            for arg in args
        ]

        # Build the command
        try:
            command = build_command(step, step_file, inventory_file, rendered_args)
        except ValueError as e:
            print(f"[{step_id}] ERROR: {e}")
            state["steps"][step_id] = {"status": "failed", "error": str(e)}
            save_state(state)
            return 4

        # Create log file name
        safe_desc = description.replace(" ", "_")
        log_file = LOG_DIR / f"{step_id}-{safe_desc}.log"

        # Update state to "running"
        print(f"\n[{step_id}] {description}")
        state["steps"][step_id] = {
            "status": "running",
            "log": str(log_file),
            "kind": kind,
            "file": str(step_file)
        }
        save_state(state)

        # Run the command
        exit_code = run_command(command, log_file)

        # Update state based on result
        if exit_code == 0:
            print(f"[{step_id}] ✅ SUCCESS")
            state["steps"][step_id]["status"] = "ok"
            state["steps"][step_id]["exit_code"] = 0
        else:
            print(f"[{step_id}] ❌ FAILED (exit code: {exit_code})")
            print(f"    See log: {log_file}")
            state["steps"][step_id]["status"] = "failed"
            state["steps"][step_id]["exit_code"] = exit_code
            save_state(state)
            return exit_code

        save_state(state)

    print("\n✅ All steps completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())