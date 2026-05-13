from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin


@dataclass(frozen=True)
class Slot:
    center_x: float
    center_y: float
    length: float = 25.0
    width: float = 7.0
    angle_deg: float = 0.0


def slots_for_rectangle(
    length_mm: float,
    width_mm: float,
    *,
    origin_x: float = 0.0,
    origin_y: float = 0.0,
    max_slots: int = 260,
) -> list[Slot]:
    rows = _row_centers(width_mm)
    x_pitch = 80.0
    margin_x = 55.0
    slots: list[Slot] = []

    for row_index, y in enumerate(rows):
        offset = 0.0 if row_index % 2 == 0 else x_pitch / 2.0
        x = margin_x + offset
        while x <= length_mm - margin_x:
            slots.append(Slot(origin_x + x, origin_y + y))
            x += x_pitch

    return _decimate(slots, max_slots)


def slots_for_sector(
    radius_mm: float,
    width_mm: float,
    angle_deg: float,
    *,
    center_x: float = 0.0,
    center_y: float = 0.0,
    max_slots: int = 160,
) -> list[Slot]:
    inner = max(radius_mm - width_mm / 2.0, 10.0)
    outer = radius_mm + width_mm / 2.0
    radial_rows = _row_centers(outer - inner)
    angle_pitch = max(6.0, 70.0 / max(radius_mm, 1.0) * 180.0 / 3.141592653589793)
    slots: list[Slot] = []

    for row_index, row_offset in enumerate(radial_rows):
        current_radius = inner + row_offset
        theta = 8.0 + row_index * angle_pitch * 0.45
        while theta <= angle_deg - 8.0:
            rad = radians(theta)
            slots.append(
                Slot(
                    center_x + current_radius * cos(rad),
                    center_y + current_radius * sin(rad),
                    angle_deg=theta + 90.0,
                )
            )
            theta += angle_pitch

    return _decimate(slots, max_slots)


def _row_centers(width_mm: float) -> list[float]:
    if width_mm <= 55.0:
        return [width_mm / 2.0]

    margin = 25.0
    rows: list[float] = []
    y = margin
    while y <= width_mm - margin + 0.01:
        rows.append(y)
        y += 40.0

    if not rows:
        return [width_mm / 2.0]
    return rows


def _decimate(slots: list[Slot], max_slots: int) -> list[Slot]:
    if len(slots) <= max_slots:
        return slots

    step = max(1, round(len(slots) / max_slots))
    return slots[::step]
