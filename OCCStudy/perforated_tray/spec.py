from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TrayPart(str, Enum):
    STRAIGHT = "ST"
    HORIZONTAL_ELBOW = "HE"
    VERTICAL_INSIDE = "VI"
    VERTICAL_OUTSIDE = "VO"
    HORIZONTAL_TEE = "HT"
    HORIZONTAL_CROSS = "HC"
    RIGHT_REDUCER = "RF"
    LEFT_REDUCER = "LF"
    STRAIGHT_REDUCER = "SF"


PART_LABELS: dict[str, str] = {
    TrayPart.STRAIGHT.value: "Straight tray",
    TrayPart.HORIZONTAL_ELBOW.value: "Horizontal elbow",
    TrayPart.VERTICAL_INSIDE.value: "Vertical inside elbow",
    TrayPart.VERTICAL_OUTSIDE.value: "Vertical outside elbow",
    TrayPart.HORIZONTAL_TEE.value: "Horizontal tee",
    TrayPart.HORIZONTAL_CROSS.value: "Horizontal cross",
    TrayPart.RIGHT_REDUCER.value: "Right hand reducer",
    TrayPart.LEFT_REDUCER.value: "Left hand reducer",
    TrayPart.STRAIGHT_REDUCER.value: "Straight reducer",
}

MATERIAL_LABELS = {
    "L": "SS316L",
    "G": "HDG",
}

SECTION_LABELS = {
    "BK": "Tray 1.5mm thickness",
}

VALID_WIDTHS_MM = (50, 100, 150, 200, 300)
VALID_ELBOW_ANGLES_DEG = (30, 45, 60, 90)
VALID_RADII_MM = (150, 300, 450)

TRAY_HEIGHT_MM = 50.0
TRAY_LIP_MM = 20.0
DEFAULT_REDUCER_LENGTH_MM = 300.0


@dataclass(frozen=True)
class PerforatedTraySpec:
    code: str
    part: TrayPart
    material_code: str
    section_code: str
    width1_mm: float
    thickness_mm: float = 1.5
    height_mm: float = TRAY_HEIGHT_MM
    width2_mm: float | None = None
    length_mm: float | None = None
    angle_deg: float | None = None
    radius_mm: float | None = None
    unit_weight_kg: float | None = None

    @property
    def material_name(self) -> str:
        return MATERIAL_LABELS.get(self.material_code, self.material_code)

    @property
    def section_name(self) -> str:
        return SECTION_LABELS.get(self.section_code, self.section_code)

    @property
    def part_name(self) -> str:
        return PART_LABELS[self.part.value]

    @property
    def is_reducer(self) -> bool:
        return self.part in {
            TrayPart.RIGHT_REDUCER,
            TrayPart.LEFT_REDUCER,
            TrayPart.STRAIGHT_REDUCER,
        }

    @property
    def drawing_length_mm(self) -> float:
        if self.length_mm is not None:
            return self.length_mm
        if self.is_reducer:
            return DEFAULT_REDUCER_LENGTH_MM
        if self.radius_mm is not None and self.angle_deg is not None:
            return max(self.radius_mm, self.arc_length_mm)
        if self.radius_mm is not None:
            return self.radius_mm * 2.0 + self.max_width_mm
        return DEFAULT_REDUCER_LENGTH_MM

    @property
    def arc_length_mm(self) -> float:
        if self.radius_mm is None or self.angle_deg is None:
            return 0.0
        return self.radius_mm * self.angle_deg * 3.141592653589793 / 180.0

    @property
    def max_width_mm(self) -> float:
        return max(self.width1_mm, self.width2_mm or self.width1_mm)

    @property
    def normalized_code(self) -> str:
        return self.code.upper()

    def summary_rows(self) -> list[tuple[str, str]]:
        rows = [
            ("Code", self.normalized_code),
            ("Type", self.part_name),
            ("Material", self.material_name),
            ("Section", self.section_name),
            ("Width W1", f"{self.width1_mm:g} mm"),
            ("Height H", f"{self.height_mm:g} mm"),
            ("Thickness", f"{self.thickness_mm:g} mm"),
        ]
        if self.width2_mm is not None:
            rows.append(("Width W2", f"{self.width2_mm:g} mm"))
        if self.length_mm is not None:
            rows.append(("Length L", f"{self.length_mm:g} mm"))
        if self.angle_deg is not None:
            rows.append(("Angle", f"{self.angle_deg:g} deg"))
        if self.radius_mm is not None:
            rows.append(("Radius R", f"{self.radius_mm:g} mm"))
        if self.unit_weight_kg is not None:
            rows.append(("Catalog U/W", f"{self.unit_weight_kg:g} kg"))
        return rows
