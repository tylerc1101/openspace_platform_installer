#!/usr/bin/env python3
"""
OpenSpace Onboarder Runner
--------------------------
Loads the onboarder container and starts an interactive shell.
Manages container lifecycle: creates new or attaches to existing.

Requires a deployment file: <env_name>.deployment.yml

Features:
  - Requires *.deployment.yml file for single-config deployment
  - Generates all config files on first container startup
  - Runs prep_onboarder_container.yml after config generation
  - Always places you in /docker-workspace/config/install
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple


# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
ENVIRONMENTS_DIR = SCRIPT_DIR / "environments"
IMAGES_DIR = SCRIPT_DIR / "images"

# Container workspace paths (inside container)
CONTAINER_WORKSPACE = "/docker-workspace"
CONTAINER_CONFIG_DIR = f"{CONTAINER_WORKSPACE}/config"
CONTAINER_INSTALL_DIR = f"{CONTAINER_CONFIG_DIR}/install"

# Onboarder image configuration
ONBOARDER_IMAGE = "onboarder-full.v3.5.0-rc7.tar.gz"

# First-run marker file (inside container)
FIRST_RUN_MARKER = f"{CONTAINER_INSTALL_DIR}/.initialized"


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
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


def print_step(msg: str) -> None:
    """Print step message in cyan."""
    print(f"{Colors.CYAN}→ {msg}{Colors.ENDC}")


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


def find_deployment_file() -> Optional[Path]:
    """
    Find a *.deployment.yml file in the script directory.
    Returns the deployment file path or None if not found.
    """
    deployment_files = list(SCRIPT_DIR.glob("*.deployment.yml"))

    if not deployment_files:
        return None

    if len(deployment_files) == 1:
        return deployment_files[0]

    # Multiple files - prompt user
    print()
    print(f"{Colors.BOLD}Multiple deployment files found:{Colors.ENDC}")
    print()

    for i, f in enumerate(deployment_files, 1):
        env_name = f.stem.replace('.deployment', '')
        print(f"  {i}. {f.name} (env: {env_name})")

    print()

    while True:
        try:
            choice = input(f"Select deployment file [1-{len(deployment_files)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(deployment_files):
                return deployment_files[idx]
            else:
                print_warning(f"Please enter a number between 1 and {len(deployment_files)}")
        except ValueError:
            print_warning("Please enter a valid number")
        except KeyboardInterrupt:
            print()
            die("Aborted by user")


def extract_env_name(deployment_file: Path) -> str:
    """
    Extract environment name from deployment file.
    e.g., 'skcp_bottom.deployment.yml' -> 'skcp_bottom'
    """
    return deployment_file.stem.replace('.deployment', '')


def get_deployment_metadata(deployment_file: Path) -> dict:
    """
    Read deployment file and extract metadata (type, version, onboarder_version).
    Returns dict with deployment_type, deployment_version, onboarder_version.
    """
    import yaml

    try:
        with open(deployment_file, 'r') as f:
            data = yaml.safe_load(f)

        deployment = data.get('deployment', {})

        return {
            'deployment_type': deployment.get('type', 'basekit'),
            'deployment_version': deployment.get('version', '1.0.1'),
            'onboarder_version': deployment.get('onboarder_version', '3.5.0-rc7'),
        }
    except Exception as e:
        print_warning(f"Could not parse deployment file: {e}")
        return {
            'deployment_type': 'basekit',
            'deployment_version': '1.0.1',
            'onboarder_version': '3.5.0-rc7',
        }


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


def create_first_run_script(
    env_name: str,
    deployment_type: str,
    deployment_version: str,
    onboarder_version: str
) -> str:
    """
    Create the shell script that runs on first container startup.
    This script:
      1. Creates /docker-workspace/config/install directory
      2. Copies deployment.yml there
      3. Runs generate_config.yml to create all config files
      4. Runs prep_onboarder_container.yml
      5. Creates .initialized marker

    Returns the script content as a string.
    """
    script = f'''#!/bin/bash
set -e

INSTALL_DIR="{CONTAINER_INSTALL_DIR}"
MARKER_FILE="{FIRST_RUN_MARKER}"
DEPLOYMENT_FILE="/tmp/deployment.yml"
DEPLOYMENT_TYPE="{deployment_type}"
DEPLOYMENT_VERSION="{deployment_version}"
ONBOARDER_VERSION="{onboarder_version}"
ENV_NAME="{env_name}"

# Colors
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
CYAN='\\033[0;36m'
NC='\\033[0m'

echo ""
echo -e "${{CYAN}}╔════════════════════════════════════════════════════════════════╗${{NC}}"
echo -e "${{CYAN}}║     OpenSpace Onboarder - First Run Configuration             ║${{NC}}"
echo -e "${{CYAN}}╚════════════════════════════════════════════════════════════════╝${{NC}}"
echo ""

# Check if already initialized
if [ -f "$MARKER_FILE" ]; then
    echo -e "${{GREEN}}✓ Environment already initialized${{NC}}"
    echo ""
    cd "$INSTALL_DIR"
    exit 0
fi

echo -e "${{BLUE}}→ Setting up environment: $ENV_NAME${{NC}}"
echo -e "  Deployment Type:    $DEPLOYMENT_TYPE"
echo -e "  Deployment Version: $DEPLOYMENT_VERSION"
echo -e "  Onboarder Version:  $ONBOARDER_VERSION"
echo ""

# Step 1: Create install directory
echo -e "${{BLUE}}[1/5] Creating install directory...${{NC}}"
mkdir -p "$INSTALL_DIR"
echo -e "${{GREEN}}  ✓ Created $INSTALL_DIR${{NC}}"

# Step 2: Copy deployment.yml
echo -e "${{BLUE}}[2/5] Copying deployment configuration...${{NC}}"
cp "$DEPLOYMENT_FILE" "$INSTALL_DIR/deployment.yml"
echo -e "${{GREEN}}  ✓ Copied deployment.yml${{NC}}"

# Step 3: Run config generation
echo -e "${{BLUE}}[3/5] Generating configuration files...${{NC}}"

GENERATOR_PLAYBOOK="{CONTAINER_WORKSPACE}/data/deployments/$DEPLOYMENT_TYPE/$DEPLOYMENT_VERSION/tasks/generate_config.yml"

if [ -f "$GENERATOR_PLAYBOOK" ]; then
    cd "$INSTALL_DIR"

    # Run the generator playbook
    ansible-playbook "$GENERATOR_PLAYBOOK" \\
        -e "env_name=$ENV_NAME" \\
        -e "config_dir=$INSTALL_DIR" \\
        -e "deployment_file=$INSTALL_DIR/deployment.yml" \\
        -c local \\
        -i localhost,

    echo -e "${{GREEN}}  ✓ Configuration files generated${{NC}}"
else
    echo -e "${{RED}}  ✗ Generator playbook not found: $GENERATOR_PLAYBOOK${{NC}}"
    echo -e "${{RED}}    Cannot continue without generate_config.yml${{NC}}"
    exit 1
fi

echo ""
echo -e "${{CYAN}}╔════════════════════════════════════════════════════════════════╗${{NC}}"
echo -e "${{CYAN}}║     Run Onboarder Preparation Playbook                         ║${{NC}}"
echo -e "${{CYAN}}╚════════════════════════════════════════════════════════════════╝${{NC}}"
echo ""

# Step 4: Run prep_onboarder_container.yml
echo -e "${{BLUE}}[4/5] Preparing onboarder container...${{NC}}"

PREP_PLAYBOOK="{CONTAINER_WORKSPACE}/data/onboarders/$ONBOARDER_VERSION/tasks/prep_onboarder_container.yml"

if [ -f "$PREP_PLAYBOOK" ]; then
    cd "$INSTALL_DIR"

    # Run the prep playbook
    ansible-playbook "$PREP_PLAYBOOK" \\
        -e "env_name=$ENV_NAME" \\
        -e "config_dir=$INSTALL_DIR" \\
        -c local \\
        -i localhost,

    echo -e "${{GREEN}}  ✓ Onboarder container prepared${{NC}}"
else
    echo -e "${{YELLOW}}  ⚠ Prep playbook not found: $PREP_PLAYBOOK${{NC}}"
    echo -e "${{YELLOW}}    Skipping container preparation${{NC}}"
fi

# Step 5: Create marker file
echo -e "${{BLUE}}[5/5] Finalizing setup...${{NC}}"
cat > "$MARKER_FILE" << EOF
initialized=$(date -Iseconds)
env_name=$ENV_NAME
deployment_type=$DEPLOYMENT_TYPE
deployment_version=$DEPLOYMENT_VERSION
onboarder_version=$ONBOARDER_VERSION
EOF
echo -e "${{GREEN}}  ✓ Setup complete${{NC}}"

echo ""
echo -e "${{GREEN}}╔════════════════════════════════════════════════════════════════╗${{NC}}"
echo -e "${{GREEN}}║     Environment Ready!                                         ║${{NC}}"
echo -e "${{GREEN}}╚════════════════════════════════════════════════════════════════╝${{NC}}"
echo ""
echo -e "  ${{YELLOW}}Generated files:${{NC}}"
ls -la "$INSTALL_DIR" 2>/dev/null | grep -v "^total" | grep -v "^\\." | head -15 | while read line; do
    echo "    $line"
done
echo ""
echo -e "  ${{YELLOW}}Next steps:${{NC}}"
echo "    task --list           # See available tasks"
echo "    task prep             # Prepare environment"
echo "    task deploy-mcm       # Deploy MCM"
echo ""

cd "$INSTALL_DIR"
'''
    return script


def run_interactive_shell(
    runtime: str,
    selinux_opt: str,
    image_ref: str,
    deployment_file: Path,
    metadata: dict
) -> int:
    """
    Run the onboarder container in interactive mode.
    If container exists, attach to it. Otherwise create new one.
    Always ends up in /docker-workspace/config/install.
    Returns the exit code.
    """
    container_name = "onboarder"
    env_name = extract_env_name(deployment_file)

    # Check container status
    status = get_container_status(runtime, container_name)

    if status == 'running':
        # Container is running, exec into it at the install directory
        print_success(f"Container '{container_name}' is already running. Attaching...")
        print()

        try:
            result = subprocess.run([
                runtime, "exec", "-it",
                "-w", CONTAINER_INSTALL_DIR,
                container_name,
                "/bin/bash"
            ])
            return result.returncode
        except KeyboardInterrupt:
            print()
            print_info("Exited container (container still running)")
            print_info(f"To re-attach: {runtime} exec -it -w {CONTAINER_INSTALL_DIR} {container_name} /bin/bash")
            return 0
        except Exception as e:
            print_error(f"Failed to exec into container: {e}")
            return 1

    elif status == 'exited':
        # Container exists but is stopped, start and exec into it
        print_info(f"Container '{container_name}' exists but is stopped. Starting...")

        try:
            subprocess.run([runtime, "start", container_name], check=True)
            print_success(f"Container started. Attaching...")
            print()

            result = subprocess.run([
                runtime, "exec", "-it",
                "-w", CONTAINER_INSTALL_DIR,
                container_name,
                "/bin/bash"
            ])
            return result.returncode
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to start container: {e}")
            return 1
        except KeyboardInterrupt:
            print()
            print_info("Exited container (container still running)")
            return 0
        except Exception as e:
            print_error(f"Failed to exec into container: {e}")
            return 1

    else:
        # Container doesn't exist, create new one
        print_info(f"Creating new container '{container_name}'...")
        print_step(f"Deployment file: {deployment_file.name}")
        print_step(f"Environment name: {env_name}")
        print_step(f"Deployment type: {metadata['deployment_type']}")
        print_step(f"Deployment version: {metadata['deployment_version']}")
        print_step(f"Onboarder version: {metadata['onboarder_version']}")

        # Print startup message
        print()
        print("=" * 70)
        print(f"{Colors.BOLD}Starting OpenSpace Onboarder Shell{Colors.ENDC}")
        print("=" * 70)
        print(f"Runtime:           {runtime}")
        print(f"Environment:       {env_name}")
        print(f"Install Directory: {CONTAINER_INSTALL_DIR}")
        print()
        print(f"{Colors.CYAN}First-Run Setup:{Colors.ENDC}")
        print(f"  1. Generate configuration files from deployment.yml")
        print(f"  2. Run prep_onboarder_container.yml")
        print(f"  3. Drop into shell at {CONTAINER_INSTALL_DIR}")
        print()
        print(f"{Colors.YELLOW}Container Management:{Colors.ENDC}")
        print(f"  exit                          # Exit shell (container persists)")
        print(f"  {runtime} exec -it -w {CONTAINER_INSTALL_DIR} {container_name} /bin/bash")
        print(f"  {runtime} rm {container_name}        # Remove container when done")
        print("=" * 70)
        print()

        # Build volume mounts
        volume_mounts = [
            "-v", f"{DATA_DIR}:/docker-workspace/data:{selinux_opt}",
            "-v", f"{IMAGES_DIR}:/docker-workspace/images:{selinux_opt}",
            "-v", f"{ENVIRONMENTS_DIR}:/docker-workspace/environments:{selinux_opt}",
        ]

        # Mount deployment file to /tmp/deployment.yml
        # Use same selinux option as other mounts (Z for podman)
        deployment_mount_opt = "ro,Z" if "Z" in selinux_opt else "ro"
        volume_mounts.extend([
            "-v", f"{deployment_file}:/tmp/deployment.yml:{deployment_mount_opt}"
        ])

        # Create the first-run script
        first_run_script = create_first_run_script(
            env_name=env_name,
            deployment_type=metadata['deployment_type'],
            deployment_version=metadata['deployment_version'],
            onboarder_version=metadata['onboarder_version']
        )

        # Write the script to a temp file on host and mount it
        first_run_script_path = SCRIPT_DIR / ".onboarder-first-run.sh"
        with open(first_run_script_path, 'w') as f:
            f.write(first_run_script)
        first_run_script_path.chmod(0o755)

        first_run_mount_opt = "ro,Z" if "Z" in selinux_opt else "ro"
        volume_mounts.extend([
            "-v", f"{first_run_script_path}:/tmp/first-run.sh:{first_run_mount_opt}"
        ])

        # Build container command
        # Start in /docker-workspace (exists), run first-run script (creates install dir), then cd into it
        container_cmd = [
            runtime, "run",
            "--name", container_name,
            "--network", "host",
            "-it",
        ] + volume_mounts + [
            "-w", CONTAINER_WORKSPACE,
            image_ref,
            "/bin/bash", "-c", f"/tmp/first-run.sh && cd {CONTAINER_INSTALL_DIR} && exec /bin/bash"
        ]

        # Run container
        try:
            result = subprocess.run(container_cmd)

            # Clean up first-run script
            if first_run_script_path.exists():
                first_run_script_path.unlink()

            return result.returncode
        except KeyboardInterrupt:
            print()
            print_warning("Interrupted by user")
            # Clean up first-run script
            if first_run_script_path.exists():
                first_run_script_path.unlink()
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
Requires a deployment configuration file: <env_name>.deployment.yml

USAGE:
  1. Create your deployment config:
     <env_name>.deployment.yml  (e.g., skcp_bottom.deployment.yml)

  2. Run this script:
     ./onboarder-run.py

  3. On first start, all configs are auto-generated and you land in:
     /docker-workspace/config/install/

  4. Run your deployment:
     task --list               # See available tasks
     task prep                 # Prepare environment
     task deploy-mcm           # Deploy MCM

Container Management:
  ./onboarder-run.py              # Start or attach to container
  podman rm onboarder             # Remove container (to start fresh)

Examples:
  # Start with deployment file
  ./onboarder-run.py

  # Specify a different deployment file
  ./onboarder-run.py --deployment /path/to/my.deployment.yml
        """
    )

    parser.add_argument(
        '--deployment', '-d',
        type=Path,
        help='Explicitly specify deployment file (default: auto-detect *.deployment.yml)'
    )

    args = parser.parse_args()

    # Verify directories exist
    if not DATA_DIR.exists():
        die(f"Data directory not found: {DATA_DIR}")

    if not ENVIRONMENTS_DIR.exists():
        die(f"Environments directory not found: {ENVIRONMENTS_DIR}")

    if not IMAGES_DIR.exists():
        die(f"Images directory not found: {IMAGES_DIR}")

    # Detect container runtime
    runtime, selinux_opt = detect_container_runtime()
    print_info(f"Using runtime: {runtime}")

    # Find deployment file
    if args.deployment:
        # Explicit deployment file specified
        if not args.deployment.exists():
            die(f"Deployment file not found: {args.deployment}")
        deployment_file = args.deployment.resolve()
    else:
        # Auto-detect deployment file
        deployment_file = find_deployment_file()

        if not deployment_file:
            print()
            print_error("No deployment file found!")
            print()
            print(f"Please create a deployment configuration file:")
            print(f"  {Colors.CYAN}<env_name>.deployment.yml{Colors.ENDC}")
            print()
            print(f"Example:")
            print(f"  {Colors.GREEN}skcp_bottom.deployment.yml{Colors.ENDC}")
            print()
            print(f"The file should contain your deployment configuration.")
            print(f"See the deployment.yml.example template for reference.")
            print()
            sys.exit(1)

    print_success(f"Using deployment file: {deployment_file.name}")

    # Read deployment metadata
    metadata = get_deployment_metadata(deployment_file)

    # Check if container already exists
    status = get_container_status(runtime, "onboarder")

    if status != 'none':
        # Container exists, we'll attach/start it
        print_info(f"Container 'onboarder' found (status: {status})")

        # Get image reference from existing container
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
    else:
        # Need to load image for new container
        image_path = IMAGES_DIR / "onboarder" / ONBOARDER_IMAGE

        if not image_path.exists():
            die(f"Onboarder image not found: {image_path}\n"
                f"Please update ONBOARDER_IMAGE variable in this script.")

        # Load container image
        image_ref = load_container_image(runtime, image_path)

    # Run interactive shell
    exit_code = run_interactive_shell(
        runtime=runtime,
        selinux_opt=selinux_opt,
        image_ref=image_ref,
        deployment_file=deployment_file,
        metadata=metadata
    )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
