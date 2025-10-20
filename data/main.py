#!/usr/bin/env python3
"""
OpenSpace Installer Orchestrator
--------------------------------
Main entry point for deployment execution.
Orchestrates the installation workflow using modular components.
"""

import argparse
import sys
from pathlib import Path

# Import our modules - FIXED PATHS
from lib import (
    EXIT_SUCCESS, EXIT_CONFIG_ERROR, EXIT_FILE_NOT_FOUND,
    EXIT_UNSUPPORTED_KIND, EXIT_STEP_FAILED, EXIT_VALIDATION_FAILED
)
from lib.config import setup_logging, load_yaml_file
from lib.context import ExecutionContext
from lib.exceptions import DeploymentError, ConfigurationError, ValidationError
from lib.installer import install_rpms
from lib.state import StateManager
from lib.step_executor import StepExecutor
from lib.validator import validate_deployment


# Where everything lives
BASE_DIR = Path("/install")
DATA_DIR = BASE_DIR / "data"
ENV_DIR = BASE_DIR / "environments"
IMAGES_DIR = BASE_DIR / "images"
LOG_DIR = BASE_DIR / "logs"


def parse_arguments() -> argparse.Namespace:
    """Parse and return command line arguments."""
    parser = argparse.ArgumentParser(description="Run installation steps")
    parser.add_argument("--env", required=True, help="Environment name")
    parser.add_argument("--deployment", required=True, help="Deployment type (basekit/baremetal/aws)")
    parser.add_argument("--resume", action="store_true", help="Skip already completed steps")
    parser.add_argument("--validate-only", action="store_true", help="Only validate, don't run")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    return parser.parse_args()


def load_configuration(ctx: ExecutionContext) -> tuple:
    """
    Load deployment configuration files.
    
    Args:
        ctx: Execution context
        
    Returns:
        Tuple of (group_vars dict, deployment_data dict)
        
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
    
    # Find deployment file
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
    
    # Setup logging first
    logger = setup_logging(LOG_DIR, args.verbose)
    
    logger.info("=" * 60)
    logger.info("OpenSpace Onboarder Starting")
    logger.info("=" * 60)
    logger.info(f"Environment: {args.env}")
    logger.info(f"Deployment Type: {args.deployment}")
    logger.info(f"Resume mode: {args.resume}")
    logger.info("=" * 60)
    
    try:
        # Create execution context
        ctx = ExecutionContext(
            base_dir=BASE_DIR,
            data_dir=DATA_DIR,
            env_dir=ENV_DIR,
            images_dir=IMAGES_DIR,
            log_dir=LOG_DIR,
            env_name=args.env,
            deployment_type=args.deployment,
            logger=logger,
            verbose=args.verbose,
            resume=args.resume
        )
        
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
        
        # Initialize state manager
        state_mgr = StateManager(ctx.state_file, ctx.log_dir, logger)
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