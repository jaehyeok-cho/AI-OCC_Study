from __future__ import annotations

from dataclasses import replace

from .parser import parse_perforated_code
from .spec import PerforatedTraySpec


# Representative perforated tray examples from the Suhhan catalog pages 33-44.
# The parser can decode the whole numbering pattern, so this list is intentionally
# small enough for training UI selection while still covering every supported type.
CATALOG_EXAMPLES = [
    "PSTLBK-00530-1.5T",
    "PSTLBK-01060-1.5T",
    "PSTLBK-01530-1.5T",
    "PSTLBK-02030-1.5T",
    "PSTLBK-03030-1.5T",
    "PHELBK-0159030-1.5T",
    "PHELBK-0206045-1.5T",
    "PVILBK-0154515-1.5T",
    "PVOLBK-0303030-1.5T",
    "PHTLBK-03002045-1.5T",
    "PHTLBK-01530-1.5T",
    "PHCLBK-02001530-1.5T",
    "PHCLBK-03045-1.5T",
    "PRFLBK-030015-1.5T",
    "PLFLBK-020010-1.5T",
    "PSFLBK-015010-1.5T",
]

CATALOG_UNIT_WEIGHT_KG = {
    "PSTLBK-00530-1.5T": 6.03,
    "PSTLBK-01030-1.5T": 7.26,
    "PSTLBK-01530-1.5T": 8.49,
    "PSTLBK-01060-1.5T": 14.52,
    "PSTLBK-01560-1.5T": 16.98,
    "PSTLBK-02030-1.5T": 10.02,
    "PSTLBK-03030-1.5T": 12.39,
    "PHELBK-0159030-1.5T": 2.65,
    "PHELBK-0206045-1.5T": 3.08,
    "PVILBK-0154515-1.5T": 1.17,
    "PVOLBK-0303030-1.5T": 1.82,
    "PHTLBK-03002045-1.5T": 9.51,
    "PHTLBK-01530-1.5T": 4.70,
    "PHCLBK-02001530-1.5T": 6.78,
    "PHCLBK-03045-1.5T": 13.99,
    "PRFLBK-030015-1.5T": 1.78,
    "PLFLBK-020010-1.5T": 1.41,
    "PSFLBK-015010-1.5T": 1.27,
}


def parse_catalog_example(code: str) -> PerforatedTraySpec:
    normalized = code.strip().upper()
    spec = parse_perforated_code(normalized)
    weight = CATALOG_UNIT_WEIGHT_KG.get(normalized)
    if weight is None:
        return spec
    return replace(spec, unit_weight_kg=weight)
