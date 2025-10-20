"""
Inventory parsing and host information retrieval.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

from .config import load_yaml_file
from .exceptions import InventoryError


def get_host_from_inventory(inventory_file: Path, host_or_group: str, 
                           logger: logging.Logger = None) -> Dict[str, Any]:
    """
    Get connection info for a host from inventory.
    
    Args:
        inventory_file: Path to Ansible inventory file
        host_or_group: Hostname or group name to find
        logger: Optional logger for messages
        
    Returns:
        Dictionary with ansible_host, ansible_user, ansible_ssh_pass, etc.
        
    Raises:
        InventoryError: If host/group not found or inventory invalid
        
    Example:
        >>> host_info = get_host_from_inventory(
        ...     Path("inventory.yml"), 
        ...     "webserver"
        ... )
        >>> print(host_info['ansible_host'])
        10.0.0.100
    """
    logger = logger or logging.getLogger(__name__)
    
    try:
        inventory = load_yaml_file(inventory_file, logger)
    except Exception as e:
        raise InventoryError(f"Failed to load inventory: {e}")
    
    def find_host(data: Dict, target: str, parent_vars: Dict = None) -> Optional[Dict]:
        """Recursively search for host in inventory."""
        parent_vars = parent_vars or {}
        
        # Merge parent vars
        current_vars = parent_vars.copy()
        if 'vars' in data:
            current_vars.update(data['vars'])
        
        # Check hosts at this level
        if 'hosts' in data and isinstance(data['hosts'], dict):
            if target in data['hosts']:
                host_data = data['hosts'][target].copy() if isinstance(data['hosts'][target], dict) else {}
                host_data.update(current_vars)
                return host_data
        
        # Check children
        if 'children' in data and isinstance(data['children'], dict):
            # Check if target is a group name
            if target in data['children']:
                group_data = data['children'][target]
                # Return first host in this group
                if 'hosts' in group_data and isinstance(group_data['hosts'], dict):
                    first_host_name = list(group_data['hosts'].keys())[0]
                    host_data = group_data['hosts'][first_host_name].copy()
                    if 'vars' in group_data:
                        host_data.update(group_data['vars'])
                    host_data.update(current_vars)
                    return host_data
            
            # Recurse into children
            for child_name, child_data in data['children'].items():
                result = find_host(child_data, target, current_vars)
                if result:
                    return result
        
        return None
    
    # Special case: localhost
    if host_or_group == 'localhost':
        return {'ansible_host': 'localhost', 'ansible_user': os.getenv('USER', 'root')}
    
    host_info = find_host(inventory.get('all', {}), host_or_group)
    
    if not host_info:
        msg = f"Host or group '{host_or_group}' not found in inventory"
        logger.error(msg)
        raise InventoryError(msg)
    
    return host_info


def find_step_file(file_path: str, data_dir: Path) -> Path:
    """
    Convert step file paths to absolute paths.
    All paths in deployments should be relative to data_dir.
    
    Args:
        file_path: Relative or absolute file path
        data_dir: Base data directory (usually /install/data)
        
    Returns:
        Absolute Path object
        
    Raises:
        InventoryError: If path is invalid
        
    Example:
        >>> path = find_step_file("tasks/common/setup.yml", Path("/install/data"))
        >>> print(path)
        /install/data/tasks/common/setup.yml
    """
    path = Path(file_path)
    
    if path.is_absolute():
        if str(path).startswith("/docker-workspace/config/"):
            return path
        raise InventoryError(
            f"Use relative paths in deployments (relative to {data_dir}): {file_path}"
        )
    
    return data_dir / path