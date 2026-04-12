"""
DataSentinel — Backward Compatibility Shim
All logic has been refactored into the engines/ package.
This file re-exports everything for any external imports.
"""

import warnings

warnings.warn(
    "DataSentinel core_engine is deprecated and will be removed in a future release. "
    "Please import directly from the new engines/ package.",
    DeprecationWarning,
    stacklevel=2,
)

from engines import (
    process_and_detect,
    clean_dataset,
    get_viz_data,
    generate_insights,
    execute_natural_query,
    confirm_and_execute_edit,
)
from schema import SchemaEnforcer
from utils import _session_dir, _BACKEND_DIR

__all__ = [
    "process_and_detect",
    "clean_dataset",
    "get_viz_data",
    "generate_insights",
    "execute_natural_query",
    "confirm_and_execute_edit",
    "SchemaEnforcer",
    "_session_dir",
    "_BACKEND_DIR",
]
