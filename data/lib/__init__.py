"""
OpenSpace Installer Library
Core modules for the installation orchestrator.
"""

# Exit codes
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 2
EXIT_FILE_NOT_FOUND = 3
EXIT_UNSUPPORTED_KIND = 4
EXIT_STEP_FAILED = 5
EXIT_VALIDATION_FAILED = 6

__all__ = [
    'EXIT_SUCCESS',
    'EXIT_CONFIG_ERROR', 
    'EXIT_FILE_NOT_FOUND',
    'EXIT_UNSUPPORTED_KIND',
    'EXIT_STEP_FAILED',
    'EXIT_VALIDATION_FAILED',
]