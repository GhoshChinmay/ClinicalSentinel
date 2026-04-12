"""
DataSentinel — Engines Package
Re-exports all engine functions for convenient imports.
"""

from engines.detection import process_and_detect
from engines.cleaning import clean_dataset
from engines.visualization import get_viz_data
from engines.insights import generate_insights
from engines.query import execute_natural_query, confirm_and_execute_edit
from engines.quality import generate_quality_report
from engines.pii_scanner import scan_for_pii, pseudonymise_columns

__all__ = [
    "process_and_detect",
    "clean_dataset",
    "get_viz_data",
    "generate_insights",
    "execute_natural_query",
    "confirm_and_execute_edit",
    "generate_quality_report",
    "scan_for_pii",
    "pseudonymise_columns",
]
