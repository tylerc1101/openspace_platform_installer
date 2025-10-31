#!/usr/bin/env python3
"""
OpenSpace Onboarder Runner
--------------------------
Detects environment, loads configuration, and runs the onboarder container.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Tuple
import yaml


# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
ENVIRONMENTS_DIR = SCRIPT_DIR / "environments"
IMAGES_DIR = SCRIPT_DIR / "images"

# Known deployment types
KNOWN_DEPLOYMENT_TYPES = ["basekit", "baremetal", "aws"]


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_error(msg: str) -> None:
    """Print error message in red."""
    print(f"{Colors.RED}ERROR: {msg}{Colors.ENDC}", file=sys.stderr)


def print_success(msg: str) -> None:
    """Print success message in green."""
    print(f"{Colors.GREEN}{msg}{Colors.ENDC}")


def print_info(msg: str) -> None:
    """Print info message in blue."""
    print(f"{Colors.BLUE}{msg}{Colors.ENDC}")


def print_warning(msg: str) -> None:
    """Print warning message in yellow."""
    print(f"{Colors.YELLOW}⚠  {msg}{Colors.ENDC}")


def die(msg: str, exit_code: int = 1) -> None:
    """Print error and exit."""
    print_error(msg)
    sys.exit(exit_code)


def load_yaml_file(file_path: Path) -> dict:
    """Load and parse a YAML file."""
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        die(f"Failed to load {file_path}: {e}")


def get_available_environments() -> List[str]:
    """Get list of available environment directories."""
    if not ENVIRONMENTS_DIR.exists():
        die(f"environments directory not found: {ENVIRONMENTS_DIR}")
    
    # Exclude sample directories and hidden directories
    exclude = {'sample_aws', 'sample_baremetal', 'sample_basekit'}
    
    envs = []
    for item in ENVIRONMENTS_DIR.iterdir():
        if item.is_dir() and not item.name.startswith('.') and item.name not in exclude:
            envs.append(item.name)
    
    return sorted(envs)


def select_environment_interactive() -> str:
    """Present a menu to select an environment."""
    envs = get_available_environments()
    
    if not envs:
        print_warning("No environments found")
        response = input("\nCreate a new environment? (y/n): ").strip().lower()
        if response == 'y':
            import create_environment
            sys.exit(create_environment.main())
        else:
            die(f"No environment directories found in {ENVIRONMENTS_DIR}")
    
    print("Select environment:")
    for idx, env in enumerate(envs, 1):
        print(f"  {idx}) {env}")
    print(f"  {len(envs) + 1}) + Create new environment")
    
    while True:
        try:
            choice = input(f"Selection [1-{len(envs) + 1}]: ")
            idx = int(choice) - 1
            
            if idx == len(envs):
                # Create new environment
                import create_environment
                sys.exit(create_environment.main())
            
            if 0 <= idx < len(envs):
                return envs[idx]
            else:
                print_error(f"Invalid selection. Choose 1-{len(envs) + 1}")
        except (ValueError, KeyboardInterrupt):
            print()
            die("Selection cancelled")


def detect_deployment_type(env_dir: Path) -> str:
    """
    Detect the deployment type by reading group_vars/deployment.yml.
    Returns the deployment type (basekit, baremetal, or aws).
    """
    group_vars_dir = env_dir / "group_vars"
    
    if not group_vars_dir.exists():
        die(f"Missing group_vars directory: {group_vars_dir}")
    
    # Look for deployment.yml
    deployment_file = group_vars_dir / "deployment.yml"
    
    if not deployment_file.exists():
        die(f"""Deployment configuration file not found: {deployment_file}

Expected: {deployment_file}

This file should contain:
  deployment_type: basekit    # or baremetal, or aws
  deployment_plan: default     # or custom, minimal, etc.
  onboarder: "onboarder-full.v3.5.0-rc7.tar.gz"

Debug:
  ls {group_vars_dir}
""")
    
    try:
        data = load_yaml_file(deployment_file)
        deployment_type = data.get('deployment_type', '')
        
        if not deployment_type:
            die(f"""Missing 'deployment_type' in {deployment_file}

The file must contain:
  deployment_type: basekit    # or baremetal, or aws
  deployment_plan: default
""")
        
        if deployment_type not in KNOWN_DEPLOYMENT_TYPES:
            die(f"""Invalid deployment_type '{deployment_type}' in {deployment_file}

Must be one of: {', '.join(KNOWN_DEPLOYMENT_TYPES)}
""")
        
        return deployment_type
        
    except Exception as e:
        die(f"Failed to load {deployment_file}: {e}")


def detect_container_runtime() -> Tuple[str, str]:
    """
    Detect if podman or docker is available.
    Returns (runtime_name, selinux_option).
    """
    if shutil.which("podman"):
        return ("podman", "rw,Z")
    elif shutil.which("docker"):
        return ("docker", "rw")
    else:
        die("Neither podman nor docker found in PATH")


def get_onboarder_image_path(group_vars_file: Path) -> Path:
    """Get the path to the onboarder image tar file."""
    data = load_yaml_file(group_vars_file)
    
    onboarder_tar = data.get('onboarder')
    if not onboarder_tar:
        die(f"'onboarder' not set in {group_vars_file}")
    
    image_path = IMAGES_DIR / "onboarder" / onboarder_tar
    
    if not image_path.exists():
        die(f"Onboarder image not found: {image_path}")
    
    return image_path


def load_container_image(runtime: str, image_path: Path) -> str:
    """
    Load the container image if not already loaded.
    Returns the image reference.
    """
    print_info(f"Checking for onboarder image...")
    
    # Check if image is already loaded
    try:
        result = subprocess.run(
            [runtime, "images", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True,
            text=True,
            check=True
        )
        
        for line in result.stdout.splitlines():
            if "onboarder" in line.lower():
                print_success(f"Image already loaded: {line}")
                return line.strip()
    except subprocess.CalledProcessError:
        pass
    
    # Load the image
    print_info(f"Loading image: {image_path}")
    try:
        subprocess.run(
            [runtime, "load", "-i", str(image_path)],
            check=True
        )
    except subprocess.CalledProcessError as e:
        die(f"Failed to load image: {e}")
    
    # Get the loaded image reference
    try:
        result = subprocess.run(
            [runtime, "images", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True,
            text=True,
            check=True
        )
        
        for line in result.stdout.splitlines():
            if "onboarder" in line.lower():
                print_success(f"Image loaded: {line}")
                return line.strip()
    except subprocess.CalledProcessError:
        pass
    
    die(f"Failed to find image after loading from {image_path}")


def remove_existing_container(runtime: str, container_name: str) -> None:
    """Remove existing container if it exists."""
    try:
        result = subprocess.run(
            [runtime, "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=True
        )
        
        if container_name in result.stdout.splitlines():
            print_info(f"Removing existing container: {container_name}")
            subprocess.run(
                [runtime, "rm", "-f", container_name],
                stdout=subprocess.DEVNULL,
                check=True
            )
    except subprocess.CalledProcessError:
        pass


def run_onboarder_container(
    runtime: str,
    selinux_opt: str,
    image_ref: str,
    env_name: str,
    env_dir: Path,
    log_dir: Path,
    deployment_type: str,
    validate_only: bool = False,
    resume: bool = False,
    verbose: bool = False
) -> int:
    """
    Run the onboarder container.
    Returns the exit code.
    """
    container_name = "onboarder"
    
    # Remove existing container
    remove_existing_container(runtime, container_name)
    
    # Get UID/GID
    uid = os.getuid()
    gid = os.getgid()
    
    # Build command arguments
    cmd_args = [
        "python3", "/install/data/main.py",
        "--env", env_name,
        "--deployment", deployment_type
    ]
    
    if validate_only:
        cmd_args.append("--validate-only")
    if resume:
        cmd_args.append("--resume")
    if verbose:
        cmd_args.append("--verbose")
    
    # Print execution details
    print()
    print("=" * 60)
    print(f"{Colors.BOLD}Running Onboarder{Colors.ENDC}")
    print("=" * 60)
    print(f"Environment:      {env_name}")
    print(f"Deployment Type:  {deployment_type}")
    if validate_only:
        print(f"Mode:             {Colors.YELLOW}VALIDATE ONLY{Colors.ENDC}")
    if resume:
        print(f"Resume:           Yes")
    if verbose:
        print(f"Verbose:          Yes")
    print(f"Logs:             {log_dir}")
    print(f"Runtime:          {runtime}")
    print("=" * 60)
    print()
    
    # Build container command
    container_cmd = [
        runtime, "run",
        "--name", container_name,
        "-u", f"{uid}:{gid}",
        "-v", f"{DATA_DIR}:/install/data:{selinux_opt}",
        "-v", f"{IMAGES_DIR}:/install/images:{selinux_opt}",
        "-v", f"{env_dir}:/docker-workspace/config/{env_name}:{selinux_opt}",
        "-v", f"{log_dir}:/install/logs:{selinux_opt}",
        "-w", "/install",
        image_ref
    ] + cmd_args
    
    # Run container
    try:
        result = subprocess.run(container_cmd)
        return result.returncode
    except KeyboardInterrupt:
        print()
        print_warning("Interrupted by user")
        return 130
    except Exception as e:
        print_error(f"Failed to run container: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="OpenSpace Onboarder Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive environment selection
  ./onboarder-run.py
  
  # Specify environment
  ./onboarder-run.py --env=my_deployment
  
  # Validate configuration only
  ./onboarder-run.py --env=my_deployment --validate-only
  
  # Resume from last successful step
  ./onboarder-run.py --env=my_deployment --resume
  
  # Verbose output
  ./onboarder-run.py --env=my_deployment --verbose
        """
    )
    
    parser.add_argument(
        "--env",
        help="Environment name (interactive selection if not specified)"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate configuration, don't run"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last successful step"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Get environment name
    if args.env:
        env_name = args.env
        env_dir = ENVIRONMENTS_DIR / env_name
        
        if not env_dir.exists():
            die(f"Environment directory not found: {env_dir}")
    else:
        # Interactive selection
        if not sys.stdin.isatty():
            die("No environment specified. Use --env=<name> or run interactively")
        
        env_name = select_environment_interactive()
        env_dir = ENVIRONMENTS_DIR / env_name
    
    print_success(f"Selected environment: {env_name}")
    
    # Detect deployment type
    deployment_type = detect_deployment_type(env_dir)
    print_info(f"Deployment type: {deployment_type}")
    
    # Verify required files
    inventory_file = env_dir / "config.yml"
    if not inventory_file.exists():
        die(f"Missing config.yml: {inventory_file}")
    
    group_vars_file = env_dir / "group_vars" / "deployment.yml"
    if not group_vars_file.exists():
        die(f"Missing deployment configuration: {group_vars_file}")
    
    # Detect container runtime
    runtime, selinux_opt = detect_container_runtime()
    print_info(f"Using runtime: {runtime}")
    
    # Get onboarder image
    image_path = get_onboarder_image_path(group_vars_file)
    
    # Load container image
    image_ref = load_container_image(runtime, image_path)
    
    # Setup logs directory
    log_dir = env_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Run the onboarder
    exit_code = run_onboarder_container(
        runtime=runtime,
        selinux_opt=selinux_opt,
        image_ref=image_ref,
        env_name=env_name,
        env_dir=env_dir,
        log_dir=log_dir,
        deployment_type=deployment_type,
        validate_only=args.validate_only,
        resume=args.resume,
        verbose=args.verbose
    )
    
    # Print result
    print()
    if exit_code == 0:
        print_success("✅ Onboarder completed successfully")
    else:
        print_error(f"❌ Onboarder failed with exit code: {exit_code}")
        print_info(f"Check logs in: {log_dir}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())