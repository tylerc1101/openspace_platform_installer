"""
Inventory parsing and host information retrieval.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

from .config import load_yaml_file


def get_host_from_inventory(inventory_file: Path, host_or_group: str) -> Dict[str, Any]:
    """
    Get connection info for a host from inventory.
    Returns dict with ansible_host, ansible_user, ansible_ssh_pass, etc.
    """
    try:
        inventory = load_yaml_file(inventory_file)
    except Exception as e:
        raise ValueError(f"Failed to load inventory: {e}")
    
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
        raise ValueError(f"Host or group '{host_or_group}' not found in inventory")
    
    return host_info


def find_step_file(file_path: str, data_dir: Path) -> Path:
    """
    Convert step file paths to absolute paths.
    All paths in deployments should be relative to /install/data.
    """
    path = Path(file_path)
    
    if path.is_absolute():
        if str(path).startswith("/install/environments/"):
            return path
        raise ValueError(
            f"Use relative paths in deployments (relative to /install/data): {file_path}"
        )
    
    return data_dir / path