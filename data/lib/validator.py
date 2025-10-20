"""
Deployment validation utilities.
"""

import logging
from pathlib import Path
from typing import Dict, Any, List

from .inventory import find_step_file


def validate_deployment(deployment_file: Path, deployment_data: Dict[str, Any], 
                       group_vars: Dict[str, Any], data_dir: Path,
                       logger: logging.Logger) -> bool:
    """Validate deployment structure and file existence."""
    logger.info("=" * 60)
    logger.info("VALIDATION: Checking deployment configuration")
    logger.info("=" * 60)
    
    errors = []
    
    if "steps" not in deployment_data:
        errors.append(f"Deployment must have 'steps' key: {deployment_file}")
        return False
    
    steps = deployment_data.get("steps", [])
    if not isinstance(steps, list):
        errors.append(f"'steps' must be a list: {deployment_file}")
        return False
    
    if not steps:
        errors.append(f"Deployment has no steps defined: {deployment_file}")
        return False
    
    logger.info(f"✓ Deployment has {len(steps)} steps")
    
    # Validate metadata if present
    metadata = deployment_data.get("metadata", {})
    if metadata:
        logger.info(f"✓ Deployment: {metadata.get('name', 'Unknown')}")
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
                step_file = find_step_file(file_path, data_dir)
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
        logger.error("\n❌ DEPLOYMENT VALIDATION FAILED:")
        for error in errors:
            logger.error(f"  - {error}")
        return False
    
    logger.info("\n✅ Deployment validation passed!")
    logger.info("=" * 60)
    return True