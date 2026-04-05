"""
DataSentinel — Engines Package
Re-exports all engine functions for convenient imports.
"""

from engines.detection import process_and_detect
from engines.cleaning import clean_dataset
from engines.visualization import get_viz_data
from engines.insights import generate_insights
from engines.query import execute_natural_query, confirm_and_execute_edit

__all__ = [
    "process_and_detect",
    "clean_dataset",
    "get_viz_data",
    "generate_insights",
    "execute_natural_query",
    "confirm_and_execute_edit",
]
