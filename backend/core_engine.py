"""
DataSentinel — Backward Compatibility Shim
All logic has been refactored into the engines/ package.
This file re-exports everything for any external imports.
"""

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