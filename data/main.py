#!/usr/bin/env python3
"""
Simple Installer Runner
-----------------------
Runs installation steps from a deployment YAML file.
Each step can be an Ansible playbook or a direct command.
"""

import argparse
import logging
import sys
from pathlib import Path

# Import our modules
from lib import (
    EXIT_SUCCESS, EXIT_CONFIG_ERROR, EXIT_FILE_NOT_FOUND,
    EXIT_UNSUPPORTED_KIND, EXIT_STEP_FAILED, EXIT_VALIDATION_FAILED
)
from lib.config import setup_logging, load_yaml_file, replace_placeholders
from lib.inventory import find_step_file
from lib.executor import build_command, run_command
from lib.state import load_state, save_state
from lib.installer import install_rpms
from lib.validator import validate_deployment


# Where everything lives
BASE_DIR = Path("/install")
DATA_DIR = BASE_DIR / "data"
ENV_DIR = BASE_DIR / "environments"
IMAGES_DIR = BASE_DIR / "images"
LOG_DIR = BASE_DIR / "logs"
STATE_FILE = LOG_DIR / "state.json"


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run installation steps")
    parser.add_argument("--env", required=True, help="Environment name")
    parser.add_argument("--deployment", required=True, help="Deployment type (basekit/baremetal/aws)")
    parser.add_argument("--resume", action="store_true", help="Skip already completed steps")
    parser.add_argument("--validate-only", action="store_true", help="Only validate, don't run")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    cli_args = parser.parse_args()

    env_name = cli_args.env
    deployment_type = cli_args.deployment

    # Setup logging
    logger = setup_logging(LOG_DIR, cli_args.verbose)
    logger.info("=" * 60)
    logger.info("OpenSpace Onboarder Starting")
    logger.info("=" * 60)
    logger.info(f"Environment: {env_name}")
    logger.info(f"Deployment Type: {deployment_type}")
    logger.info(f"Resume mode: {cli_args.resume}")
    logger.info("=" * 60)

    # Find config files
    env_path = ENV_DIR / env_name
    inventory_file = env_path / "config.yml"
    group_vars_file = env_path / "group_vars" / "deployment.yml"

    if not inventory_file.exists():
        logger.error(f"Config file not found: {inventory_file}")
        return EXIT_CONFIG_ERROR
    
    if not group_vars_file.exists():
        logger.error(f"Deployment configuration file not found: {group_vars_file}")
        logger.error(f"Expected: group_vars/deployment.yml")
        return EXIT_CONFIG_ERROR

    # Load the deployment plan from group_vars
    try:
        group_vars = load_yaml_file(group_vars_file)
    except Exception as e:
        logger.error(f"Failed to load group vars: {e}")
        return EXIT_CONFIG_ERROR
    
    if "deployment_type" not in group_vars:
        logger.error(f"Missing 'deployment_type' in {group_vars_file}")
        return EXIT_CONFIG_ERROR
    
    if "deployment_plan" not in group_vars:
        logger.error(f"Missing 'deployment_plan' in {group_vars_file}")
        return EXIT_CONFIG_ERROR
    
    deployment_plan = group_vars["deployment_plan"]
    
    # Find the deployment file
    deployment_file = DATA_DIR / "deployments" / deployment_type / f"{deployment_plan}.yml"
    if not deployment_file.exists():
        logger.error(f"Deployment file not found: {deployment_file}")
        return EXIT_CONFIG_ERROR

    logger.info(f"Using deployment file: {deployment_file}")

    # Load the steps from the deployment
    try:
        deployment_data = load_yaml_file(deployment_file)
    except Exception as e:
        logger.error(f"Failed to load deployment: {e}")
        return EXIT_CONFIG_ERROR
    
    # Validate deployment structure
    if not validate_deployment(deployment_file, deployment_data, group_vars, DATA_DIR, logger):
        return EXIT_VALIDATION_FAILED
    
    # If validate-only mode, stop here
    if cli_args.validate_only:
        logger.info("\n✅ Validation complete. Exiting (--validate-only mode)")
        return EXIT_SUCCESS
    
    # Install RPMs before running steps
    if not install_rpms(IMAGES_DIR, LOG_DIR, DATA_DIR, logger):
        logger.error("Failed to install required RPMs")
        return EXIT_CONFIG_ERROR
    
    # Extract steps from deployment
    steps = deployment_data.get("steps", [])
    
    if not steps:
        logger.error("No steps found in deployment")
        return EXIT_CONFIG_ERROR

    # Load or initialize state tracking
    state = load_state(STATE_FILE)
    state["env"] = env_name
    state["deployment_type"] = deployment_type
    state["deployment_plan"] = deployment_plan
    
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
            save_state(state, STATE_FILE, LOG_DIR)
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
                    save_state(state, STATE_FILE, LOG_DIR)
                    return EXIT_CONFIG_ERROR
                
                step_file = None
                rendered_args = []
            else:
                # Handle file-based kinds
                file_path = step_for_exec.get("file")
                if not file_path:
                    logger.warning(f"[{step_id}] SKIPPING: Missing file")
                    state["steps"][step_id] = {"status": "skipped"}
                    save_state(state, STATE_FILE, LOG_DIR)
                    continue
                
                # Find the step file
                try:
                    step_file = find_step_file(file_path, DATA_DIR)
                except ValueError as e:
                    logger.error(f"[{step_id}] ERROR: {e}")
                    state["steps"][step_id] = {"status": "failed", "error": str(e)}
                    save_state(state, STATE_FILE, LOG_DIR)
                    return EXIT_FILE_NOT_FOUND
                
                if not step_file.exists():
                    logger.error(f"[{step_id}] ERROR: File not found: {step_file}")
                    state["steps"][step_id] = {"status": "failed", "error": "file not found"}
                    save_state(state, STATE_FILE, LOG_DIR)
                    return EXIT_FILE_NOT_FOUND
                
                # Replace placeholders in arguments
                step_args = step_for_exec.get("args") or []
                rendered_args = [
                    replace_placeholders(arg, env_name, deployment_plan, deployment_type, group_vars)
                    for arg in step_args
                ]

            # Build the command
            try:
                command = build_command(step_for_exec, step_file, inventory_file, rendered_args,
                                       env_name, deployment_plan, deployment_type, group_vars)
            except ValueError as e:
                logger.error(f"[{step_id}] ERROR: {e}")
                state["steps"][step_id] = {"status": "failed", "error": str(e)}
                save_state(state, STATE_FILE, LOG_DIR)
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
            save_state(state, STATE_FILE, LOG_DIR)

            # Run the command
            exit_code = run_command(command, log_file, LOG_DIR, DATA_DIR, timeout)

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
                save_state(state, STATE_FILE, LOG_DIR)
                
                # Handle failure based on on_failure setting
                if on_failure == "continue":
                    logger.warning("⚠️  Continuing despite failure")
                else:
                    return EXIT_STEP_FAILED

            save_state(state, STATE_FILE, LOG_DIR)

    logger.info("\n" + "=" * 70)
    logger.info("✅ ALL STEPS COMPLETED SUCCESSFULLY!")
    logger.info("=" * 70)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())