#!/usr/bin/env python3
"""
OpenSpace Onboarder Runner
--------------------------
Loads the onboarder container and starts an interactive shell.
Manages container lifecycle: creates new or attaches to existing.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Tuple


# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
ENVIRONMENTS_DIR = SCRIPT_DIR / "environments"
IMAGES_DIR = SCRIPT_DIR / "images"

# Onboarder image configuration
ONBOARDER_IMAGE = "onboarder-full.v3.5.0-rc7.tar.gz"


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


def get_container_status(runtime: str, container_name: str) -> str:
    """
    Check if container exists and return its status.
    Returns: 'running', 'exited', or 'none'
    """
    try:
        result = subprocess.run(
            [runtime, "ps", "-a", "--filter", f"name=^{container_name}$", 
             "--format", "{{.Names}}\t{{.State}}"],
            capture_output=True,
            text=True,
            check=True
        )
        
        for line in result.stdout.strip().splitlines():
            if line:
                parts = line.split('\t')
                if len(parts) == 2 and parts[0] == container_name:
                    state = parts[1].lower()
                    if state == 'running':
                        return 'running'
                    else:
                        return 'exited'
        
        return 'none'
    except subprocess.CalledProcessError:
        return 'none'


def run_interactive_shell(
    runtime: str,
    selinux_opt: str,
    image_ref: str
) -> int:
    """
    Run the onboarder container in interactive mode.
    If container exists, attach to it. Otherwise create new one.
    Returns the exit code.
    """
    container_name = "onboarder"
    
    # Check container status
    status = get_container_status(runtime, container_name)
    
    if status == 'running':
        # Container is running, attach to it
        print_success(f"Container '{container_name}' is already running. Attaching...")
        print()
        
        try:
            result = subprocess.run([runtime, "attach", container_name])
            return result.returncode
        except KeyboardInterrupt:
            print()
            print_info("Detached from container (container still running)")
            print_info(f"To re-attach: {runtime} attach {container_name}")
            return 0
        except Exception as e:
            print_error(f"Failed to attach to container: {e}")
            return 1
    
    elif status == 'exited':
        # Container exists but is stopped, start and attach
        print_info(f"Container '{container_name}' exists but is stopped. Starting...")
        
        try:
            subprocess.run([runtime, "start", container_name], check=True)
            print_success(f"Container started. Attaching...")
            print()
            
            result = subprocess.run([runtime, "attach", container_name])
            return result.returncode
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to start container: {e}")
            return 1
        except KeyboardInterrupt:
            print()
            print_info("Detached from container (container still running)")
            return 0
        except Exception as e:
            print_error(f"Failed to attach to container: {e}")
            return 1
    
    else:
        # Container doesn't exist, create new one
        print_info(f"Creating new container '{container_name}'...")
        
        # Print startup message
        print()
        print("=" * 70)
        print(f"{Colors.BOLD}Starting OpenSpace Onboarder Shell{Colors.ENDC}")
        print("=" * 70)
        print(f"Runtime:           {runtime}")
        print(f"Working Directory: /docker-workspace")
        print()
        print(f"{Colors.GREEN}To run a deployment:{Colors.ENDC}")
        print(f"  python3 deploy-env.py")
        print()
        print(f"{Colors.BLUE}Available commands:{Colors.ENDC}")
        print(f"  python3 deploy-env.py              # Interactive deployment")
        print(f"  python3 deploy-env.py --env=<n>    # Specific environment")
        print(f"  python3 deploy-env.py --help       # See all options")
        print()
        print(f"{Colors.YELLOW}Container Management:{Colors.ENDC}")
        print(f"  exit                               # Exit shell (container persists)")
        print(f"  {runtime} attach {container_name}               # Re-attach to container")
        print(f"  {runtime} rm {container_name}                   # Remove container when done")
        print("=" * 70)
        print()
        
        # Build container command
        container_cmd = [
            runtime, "run",
            "--name", container_name,
            "-it",   # Interactive with TTY
            "-v", f"{DATA_DIR}:/docker-workspace/data:{selinux_opt}",
            "-v", f"{IMAGES_DIR}:/docker-workspace/images:{selinux_opt}",
            "-v", f"{ENVIRONMENTS_DIR}:/docker-workspace/environments:{selinux_opt}",
            "-v", f"{SCRIPT_DIR}/deploy-env.py:/docker-workspace/deploy-env.py:{selinux_opt}",
            "-w", "/docker-workspace",
            image_ref,
            "/bin/bash"
        ]
        
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
        description="OpenSpace Onboarder Interactive Shell",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script loads the onboarder container and drops you into an interactive shell.
If a container named 'onboarder' already exists, it will attach to it instead.

Once inside, run:
  python3 deploy-env.py

Container Management:
  ./onboarder-run.py              # Start or attach to container
  podman attach onboarder         # Re-attach to running container
  podman rm onboarder             # Remove container when done

Examples:
  # Start interactive shell
  ./onboarder-run.py
  
  # Inside the container, run deployments
  python3 deploy-env.py                    # Interactive selection
  python3 deploy-env.py --env=my_env       # Specific environment
  python3 deploy-env.py --validate-only    # Validate only
  python3 deploy-env.py --resume           # Resume deployment
        """
    )
    
    args = parser.parse_args()
    
    # Verify directories exist
    if not DATA_DIR.exists():
        die(f"Data directory not found: {DATA_DIR}")
    
    if not ENVIRONMENTS_DIR.exists():
        die(f"Environments directory not found: {ENVIRONMENTS_DIR}")
    
    # Detect container runtime
    runtime, selinux_opt = detect_container_runtime()
    print_info(f"Using runtime: {runtime}")
    
    # Check if container already exists
    status = get_container_status(runtime, "onboarder")
    
    if status != 'none':
        # Container exists, we'll attach/start it
        print_info(f"Container 'onboarder' found (status: {status})")
    else:
        # Need to load image for new container
        image_path = IMAGES_DIR / "onboarder" / ONBOARDER_IMAGE
        
        if not image_path.exists():
            die(f"Onboarder image not found: {image_path}\n"
                f"Please update ONBOARDER_IMAGE variable in this script.")
        
        # Load container image
        image_ref = load_container_image(runtime, image_path)
    
    # Get image reference for creating new container
    if status == 'none':
        # Already loaded above
        pass
    else:
        # Get image from existing container
        try:
            result = subprocess.run(
                [runtime, "inspect", "--format", "{{.Image}}", "onboarder"],
                capture_output=True,
                text=True,
                check=True
            )
            image_id = result.stdout.strip()
            
            # Get image name from ID
            result = subprocess.run(
                [runtime, "images", "--format", "{{.Repository}}:{{.Tag}}\t{{.ID}}"],
                capture_output=True,
                text=True,
                check=True
            )
            
            image_ref = None
            for line in result.stdout.splitlines():
                if image_id[:12] in line:
                    image_ref = line.split('\t')[0]
                    break
            
            if not image_ref:
                image_ref = image_id
        except subprocess.CalledProcessError:
            die("Failed to get image reference from existing container")
    
    # Run interactive shell
    exit_code = run_interactive_shell(
        runtime=runtime,
        selinux_opt=selinux_opt,
        image_ref=image_ref
    )
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())