"""
State file management for tracking installation progress.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any


def load_state(state_file: Path) -> Dict[str, Any]:
    """Load the state file that tracks which steps completed."""
    if state_file.exists():
        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"Could not load state file: {e}. Starting fresh.")
    return {}


def save_state(state: Dict[str, Any], state_file: Path, log_dir: Path) -> None:
    """Save progress to the state file."""
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save state: {e}")