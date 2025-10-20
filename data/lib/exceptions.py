"""
Custom exceptions for the OpenSpace Installer.
"""


class DeploymentError(Exception):
    """Base exception for all deployment errors."""
    pass


class ConfigurationError(DeploymentError):
    """Raised when configuration is invalid or missing."""
    pass


class ValidationError(DeploymentError):
    """Raised when validation fails."""
    pass


class FileNotFoundError(DeploymentError):
    """Raised when a required file is not found."""
    pass


class ExecutionError(DeploymentError):
    """Raised when a step execution fails."""
    
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


class InventoryError(DeploymentError):
    """Raised when inventory parsing fails."""
    pass