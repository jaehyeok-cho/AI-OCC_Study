from __future__ import annotations

import re

from .spec import (
    MATERIAL_LABELS,
    SECTION_LABELS,
    VALID_ELBOW_ANGLES_DEG,
    VALID_RADII_MM,
    VALID_WIDTHS_MM,
    PerforatedTraySpec,
    TrayPart,
)


class TrayCodeError(ValueError):
    """Raised when a perforated tray catalog code cannot be decoded."""


CODE_RE = re.compile(
    r"^P(?P<part>ST|HE|VI|VO|HT|HC|RF|LF|SF)"
    r"(?P<material>[LG])"
    r"(?P<section>BK)-"
    r"(?P<body>\d+)"
    r"(?:-(?P<thickness>\d+(?:\.\d+)?)T)?$",
    re.IGNORECASE,
)


def parse_perforated_code(code: str, unit_weight_kg: float | None = None) -> PerforatedTraySpec:
    normalized = code.strip().upper()
    match = CODE_RE.match(normalized)
    if not match:
        raise TrayCodeError(
            "Use a perforated tray code such as PSTLBK-01530-1.5T "
            "or PHELBK-0159030-1.5T."
        )

    part = TrayPart(match.group("part"))
    material_code = match.group("material")
    section_code = match.group("section")
    body = match.group("body")
    thickness_mm = float(match.group("thickness") or 1.5)

    if material_code not in MATERIAL_LABELS:
        raise TrayCodeError(f"Unsupported material code: {material_code}")
    if section_code not in SECTION_LABELS:
        raise TrayCodeError(f"Unsupported tray section: {section_code}")

    width1_mm: float
    width2_mm: float | None = None
    length_mm: float | None = None
    angle_deg: float | None = None
    radius_mm: float | None = None

    if part == TrayPart.STRAIGHT:
        _require_digits(body, 5, part)
        width1_mm = _decode_width(body[:3])
        length_mm = _decode_length(body[3:])
    elif part in {TrayPart.HORIZONTAL_ELBOW, TrayPart.VERTICAL_INSIDE, TrayPart.VERTICAL_OUTSIDE}:
        _require_digits(body, 7, part)
        width1_mm = _decode_width(body[:3])
        angle_deg = float(_decode_angle(body[3:5]))
        radius_mm = _decode_radius(body[5:])
    elif part in {TrayPart.HORIZONTAL_TEE, TrayPart.HORIZONTAL_CROSS}:
        if len(body) == 5:
            width1_mm = _decode_width(body[:3])
            radius_mm = _decode_radius(body[3:])
        elif len(body) == 8:
            width1_mm = _decode_width(body[:3])
            width2_mm = _decode_width(body[3:6])
            radius_mm = _decode_radius(body[6:])
            if width2_mm >= width1_mm:
                raise TrayCodeError("Unequal tee/cross codes should use W2 smaller than W1.")
        else:
            raise TrayCodeError(f"{part.value} body should be 5 or 8 digits, got {len(body)}.")
    elif part in {TrayPart.RIGHT_REDUCER, TrayPart.LEFT_REDUCER, TrayPart.STRAIGHT_REDUCER}:
        _require_digits(body, 6, part)
        width1_mm = _decode_width(body[:3])
        width2_mm = _decode_width(body[3:])
        if width2_mm >= width1_mm:
            raise TrayCodeError("Reducer codes should use W2 smaller than W1.")
    else:
        raise TrayCodeError(f"Unsupported perforated tray part: {part.value}")

    return PerforatedTraySpec(
        code=normalized,
        part=part,
        material_code=material_code,
        section_code=section_code,
        width1_mm=width1_mm,
        width2_mm=width2_mm,
        length_mm=length_mm,
        angle_deg=angle_deg,
        radius_mm=radius_mm,
        thickness_mm=thickness_mm,
        unit_weight_kg=unit_weight_kg,
    )


def _require_digits(body: str, expected: int, part: TrayPart) -> None:
    if len(body) != expected:
        raise TrayCodeError(f"{part.value} body should be {expected} digits, got {len(body)}.")


def _decode_width(raw: str) -> float:
    width = int(raw) * 10
    if width not in VALID_WIDTHS_MM:
        valid = ", ".join(str(value) for value in VALID_WIDTHS_MM)
        raise TrayCodeError(f"Unsupported width {width} mm. Valid widths: {valid} mm.")
    return float(width)


def _decode_length(raw: str) -> float:
    length = int(raw) * 100
    if length <= 0:
        raise TrayCodeError("Length code must be greater than zero.")
    return float(length)


def _decode_angle(raw: str) -> int:
    angle = int(raw)
    if angle not in VALID_ELBOW_ANGLES_DEG:
        valid = ", ".join(str(value) for value in VALID_ELBOW_ANGLES_DEG)
        raise TrayCodeError(f"Unsupported elbow angle {angle} deg. Valid angles: {valid} deg.")
    return angle


def _decode_radius(raw: str) -> float:
    radius = int(raw) * 10
    if radius not in VALID_RADII_MM:
        valid = ", ".join(str(value) for value in VALID_RADII_MM)
        raise TrayCodeError(f"Unsupported radius {radius} mm. Valid radii: {valid} mm.")
    return float(radius)
