"""
SafeSpace Internal Module

This package contains internal utilities and implementation details for SafeSpace.
These modules are not part of the public API and may change without notice.
"""

from .load_environment import (
    load_environment,
    get_environment_variable,
    is_environment_loaded,
    get_safe_env_root,
    in_safe_environment,
)
