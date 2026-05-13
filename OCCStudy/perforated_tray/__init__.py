"""Perforated cable tray automation example."""

from .catalog import CATALOG_EXAMPLES, parse_catalog_example
from .parser import parse_perforated_code
from .spec import PerforatedTraySpec, TrayPart

__all__ = [
    "CATALOG_EXAMPLES",
    "PerforatedTraySpec",
    "TrayPart",
    "parse_catalog_example",
    "parse_perforated_code",
]
