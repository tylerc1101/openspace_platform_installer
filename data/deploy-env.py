#!/usr/bin/env python3
"""
OpenSpace Environment Deployment
---------------------------------
Deploy OpenSpace to a specific environment.
"""

import argparse
import sys
from pathlib import Path
from typing import List

# Import our modules
from data.lib import (
    EXIT_SUCCESS, EXIT_CONFIG_ERROR, EXIT_FILE_NOT_FOUND,
    EXIT_UNSUPPORTED_KIND, EXIT_STEP_FAILED, EXIT_VALIDATION_FAILED
)
from data.lib.config import setup_logging, load_yaml_file
from data.lib.context import ExecutionContext
from data.lib.exceptions import DeploymentError, ConfigurationError, ValidationError
from data.lib.installer import install_rpms
from data.lib.state import StateManager
from data.lib.step_executor import StepExecutor
from data.lib.validator import validate_deployment


# Where everything lives inside the container
WORKSPACE_DIR = Path("/docker-workspace")
DATA_DIR = WORKSPACE_DIR / "data"
CONFIG_DIR = WORKSPACE_DIR / "config"
IMAGES_DIR = WORKSPACE_DIR / "images"


def get_available_environments() -> List[str]:
    """Get list of available environment directories."""
    if not CONFIG_DIR.exists():
        print(f"ERROR: Config directory not found: {CONFIG_DIR}", file=sys.stderr)
        sys.exit(EXIT_CONFIG_ERROR)
    
    # Exclude sample directories and hidden directories
    exclude = {'sample_aws', 'sample_baremetal', 'sample_basekit'}
    
    envs = []
    for item in CONFIG_DIR.iterdir():
        if item.is_dir() and not item.name.startswith('.') and item.name not in exclude:
            # Verify it has required structure
            if (item / "config.yml").exists():
                envs.append(item.name)
    
    return sorted(envs)


def select_environment_interactive() -> str:
    """Present a menu to select an environment."""
    envs = get_available_environments()
    
    if not envs:
        print()
        print("=" * 60)
        print("ERROR: No environment directories found")
        print("=" * 60)
        print(f"Expected to find environments in: {CONFIG_DIR}")
        print()
        print("Each environment should have:")
        print("  - config.yml (inventory file)")
        print("  - group_vars/deployment.yml")
        print()
        sys.exit(EXIT_CONFIG_ERROR)
    
    print()
    print("=" * 60)
    print("Available Environments:")
    print("=" * 60)
    for idx, env in enumerate(envs, 1):
        print(f"  {idx}) {env}")
    print("=" * 60)
    
    while True:
        try:
            choice = input(f"\nSelect environment [1-{len(envs)}]: ").strip()
            idx = int(choice) - 1
            
            if 0 <= idx < len(envs):
                return envs[idx]
            else:
                print(f"ERROR: Invalid selection. Choose 1-{len(envs)}", file=sys.stderr)
        except ValueError:
            print("ERROR: Please enter a number", file=sys.stderr)
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled by user")
            sys.exit(130)


def detect_deployment_type(env_dir: Path) -> str:
    """
    Detect the deployment type by reading group_vars/deployment.yml.
    Returns the deployment type (basekit, baremetal, or aws).
    """
    group_vars_file = env_dir / "group_vars" / "deployment.yml"
    
    if not group_vars_file.exists():
        raise ConfigurationError(
            f"Deployment configuration file not found: {group_vars_file}\n"
            f"Expected: group_vars/deployment.yml"
        )
    
    data = load_yaml_file(group_vars_file)
    deployment_type = data.get('deployment_type', '')
    
    if not deployment_type:
        raise ConfigurationError(
            f"Missing 'deployment_type' in {group_vars_file}\n"
            f"Expected: deployment_type: basekit|baremetal|aws"
        )
    
    known_types = ["basekit", "baremetal", "aws"]
    if deployment_type not in known_types:
        raise ConfigurationError(
            f"Invalid deployment_type '{deployment_type}' in {group_vars_file}\n"
            f"Must be one of: {', '.join(known_types)}"
        )
    
    return deployment_type


def parse_arguments() -> argparse.Namespace:
    """Parse and return command line arguments."""
    parser = argparse.ArgumentParser(
        description="Deploy OpenSpace environment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive environment selection
  python3 deploy-env.py
  
  # Specify environment
  python3 deploy-env.py --env=my_deployment
  
  # Validate configuration only
  python3 deploy-env.py --env=my_deployment --validate-only
  
  # Resume from last successful step
  python3 deploy-env.py --env=my_deployment --resume
  
  # Verbose output
  python3 deploy-env.py --env=my_deployment --verbose
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
        help="Skip already completed steps"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose logging"
    )
    
    return parser.parse_args()


def load_configuration(ctx: ExecutionContext) -> tuple:
    """
    Load deployment configuration files.
    
    Args:
        ctx: Execution context
        
    Returns:
        Tuple of (deployment_file, deployment_data)
        
    Raises:
        ConfigurationError: If configuration files are missing or invalid
    """
    # Check required files
    inventory_file = ctx.env_path / "config.yml"
    group_vars_file = ctx.env_path / "group_vars" / "deployment.yml"
    
    if not inventory_file.exists():
        raise ConfigurationError(f"Config file not found: {inventory_file}")
    
    if not group_vars_file.exists():
        raise ConfigurationError(
            f"Deployment configuration file not found: {group_vars_file}\n"
            f"Expected: group_vars/deployment.yml"
        )
    
    # Set inventory file in context
    ctx.inventory_file = inventory_file
    
    # Load group vars
    group_vars = load_yaml_file(group_vars_file, ctx.logger)
    
    if "deployment_type" not in group_vars:
        raise ConfigurationError(f"Missing 'deployment_type' in {group_vars_file}")
    
    if "deployment_plan" not in group_vars:
        raise ConfigurationError(f"Missing 'deployment_plan' in {group_vars_file}")
    
    deployment_plan = group_vars["deployment_plan"]
    ctx.deployment_plan = deployment_plan
    ctx.group_vars = group_vars
    
    # Find deployment file in data/deployments
    deployment_file = DATA_DIR / "deployments" / ctx.deployment_type / f"{deployment_plan}.yml"
    if not deployment_file.exists():
        raise ConfigurationError(f"Deployment file not found: {deployment_file}")
    
    ctx.logger.info(f"Using deployment file: {deployment_file}")
    
    # Load deployment
    deployment_data = load_yaml_file(deployment_file, ctx.logger)
    
    return deployment_file, deployment_data


def main():
    """Main execution function."""
    # Parse arguments
    args = parse_arguments()
    
    # Get environment name
    if args.env:
        env_name = args.env
        env_dir = CONFIG_DIR / env_name
        
        if not env_dir.exists():
            print(f"ERROR: Environment directory not found: {env_dir}", file=sys.stderr)
            return EXIT_CONFIG_ERROR
    else:
        # Interactive selection
        if not sys.stdin.isatty():
            print("ERROR: No environment specified. Use --env=<name> or run interactively", 
                  file=sys.stderr)
            return EXIT_CONFIG_ERROR
        
        env_name = select_environment_interactive()
        env_dir = CONFIG_DIR / env_name
    
    # Detect deployment type
    try:
        deployment_type = detect_deployment_type(env_dir)
    except ConfigurationError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    
    # Setup cache directory structure
    cache_dir = env_dir / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Create execution context (log_dir will be auto-derived)
    ctx = ExecutionContext(
        base_dir=WORKSPACE_DIR,
        data_dir=DATA_DIR,
        env_dir=CONFIG_DIR,
        images_dir=IMAGES_DIR,
        env_name=env_name,
        deployment_type=deployment_type,
        verbose=args.verbose,
        resume=args.resume
    )
    
    # Ensure log directory exists
    ctx.log_path.mkdir(parents=True, exist_ok=True)
    
    # Setup logging
    logger = setup_logging(ctx.log_path, args.verbose)
    
    logger.info("=" * 60)
    logger.info("OpenSpace Deployment Starting")
    logger.info("=" * 60)
    logger.info(f"Environment: {env_name}")
    logger.info(f"Deployment Type: {deployment_type}")
    logger.info(f"Resume mode: {args.resume}")
    logger.info(f"Logs: {ctx.log_path}")
    logger.info("=" * 60)
    
    try:
        # Context is already created above
        ctx.logger = logger
        
        # Load configuration
        deployment_file, deployment_data = load_configuration(ctx)
        
        # Validate deployment structure
        if not validate_deployment(deployment_file, deployment_data, ctx):
            return EXIT_VALIDATION_FAILED
        
        # If validate-only mode, stop here
        if args.validate_only:
            logger.info("\n✅ Validation complete. Exiting (--validate-only mode)")
            return EXIT_SUCCESS
        
        # Install RPMs before running steps
        if not install_rpms(ctx):
            logger.error("Failed to install required RPMs")
            return EXIT_CONFIG_ERROR
        
        # Extract steps
        steps = deployment_data.get("steps", [])
        if not steps:
            logger.error("No steps found in deployment")
            return EXIT_CONFIG_ERROR
        
        # Initialize state manager (state file in .cache)
        state_mgr = StateManager(ctx.state_file, ctx.log_path, logger)
        state_mgr.initialize(ctx.env_name, ctx.deployment_type, ctx.deployment_plan)
        
        # Create step executor
        executor = StepExecutor(ctx, state_mgr)
        
        # Execute steps
        logger.info("\n" + "=" * 60)
        logger.info(f"Starting execution of {len(steps)} steps")
        logger.info("=" * 60 + "\n")
        
        for index, step in enumerate(steps, start=1):
            if not executor.execute_step(step, index, len(steps)):
                # Step failed and on_failure != "continue"
                return EXIT_STEP_FAILED
        
        # All steps completed
        logger.info("\n" + "=" * 70)
        logger.info("✅ ALL STEPS COMPLETED SUCCESSFULLY!")
        logger.info("=" * 70)
        return EXIT_SUCCESS
        
    except ConfigurationError as e:
        logger.error(f"\n❌ Configuration Error: {e}")
        return EXIT_CONFIG_ERROR
    
    except ValidationError as e:
        logger.error(f"\n❌ Validation Error: {e}")
        return EXIT_VALIDATION_FAILED
    
    except DeploymentError as e:
        logger.error(f"\n❌ Deployment Error: {e}")
        return EXIT_STEP_FAILED
    
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Interrupted by user")
        return 130
    
    except Exception as e:
        logger.error(f"\n❌ Unexpected Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return EXIT_STEP_FAILED


if __name__ == "__main__":
    sys.exit(main())