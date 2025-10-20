"""
RPM installation utilities.
"""

import logging
from pathlib import Path
from typing import List

from .executor import run_command


def install_rpms(images_dir: Path, log_dir: Path, data_dir: Path, 
                logger: logging.Logger) -> bool:
    """
    Install any RPMs found in /install/images/rpms/.
    Returns True if successful or no RPMs found, False on failure.
    """
    rpms_dir = images_dir / "rpms"
    
    if not rpms_dir.exists():
        logger.info("No rpms directory found, skipping RPM installation")
        return True
    
    rpm_files = list(rpms_dir.glob("*.rpm"))
    
    if not rpm_files:
        logger.info("No RPM files found in rpms directory")
        return True
    
    logger.info("=" * 60)
    logger.info("Installing RPMs from images/rpms/")
    logger.info("=" * 60)
    logger.info(f"Found {len(rpm_files)} RPM(s) to install:")
    
    for rpm in rpm_files:
        logger.info(f"  - {rpm.name}")
    
    rpm_paths = [str(rpm) for rpm in rpm_files]
    command = ["rpm", "-ivh", "--force"] + rpm_paths
    
    log_file = log_dir / "00-install-rpms.log"
    
    logger.info(f"Installing RPMs... (log: {log_file})")
    exit_code = run_command(command, log_file, log_dir, data_dir)
    
    if exit_code == 0:
        logger.info("✅ RPMs installed successfully")
        logger.info("=" * 60 + "\n")
        return True
    else:
        logger.error(f"❌ RPM installation failed (exit code: {exit_code})")
        logger.error(f"See log: {log_file}")
        logger.info("=" * 60 + "\n")
        return False