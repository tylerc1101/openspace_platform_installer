"""
RPM installation utilities.
"""

import logging
from pathlib import Path
from typing import List

from .context import ExecutionContext
from .executor import run_command


def install_rpms(ctx: ExecutionContext) -> bool:
    """
    Install any RPMs found in images/rpms/ directory.
    
    Args:
        ctx: Execution context
        
    Returns:
        True if successful or no RPMs found, False on failure
        
    Example:
        >>> if not install_rpms(ctx):
        ...     print("RPM installation failed!")
        ...     sys.exit(1)
    """
    rpms_dir = ctx.images_dir / "rpms"
    
    if not rpms_dir.exists():
        ctx.logger.info("No rpms directory found, skipping RPM installation")
        return True
    
    rpm_files = list(rpms_dir.glob("*.rpm"))
    
    if not rpm_files:
        ctx.logger.info("No RPM files found in rpms directory")
        return True
    
    ctx.logger.info("=" * 60)
    ctx.logger.info("Installing RPMs from images/rpms/")
    ctx.logger.info("=" * 60)
    ctx.logger.info(f"Found {len(rpm_files)} RPM(s) to install:")
    
    for rpm in rpm_files:
        ctx.logger.info(f"  - {rpm.name}")
    
    rpm_paths = [str(rpm) for rpm in rpm_files]
    command = ["rpm", "-ivh", "--force"] + rpm_paths
    
    log_file = ctx.log_dir / "00-install-rpms.log"
    
    ctx.logger.info(f"Installing RPMs... (log: {log_file})")
    exit_code = run_command(command, log_file, ctx)
    
    if exit_code == 0:
        ctx.logger.info("✅ RPMs installed successfully")
        ctx.logger.info("=" * 60 + "\n")
        return True
    else:
        ctx.logger.error(f"❌ RPM installation failed (exit code: {exit_code})")
        ctx.logger.error(f"See log: {log_file}")
        ctx.logger.info("=" * 60 + "\n")
        return False