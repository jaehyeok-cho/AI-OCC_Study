from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin

from .perforation import Slot, slots_for_rectangle, slots_for_sector
from .spec import DEFAULT_REDUCER_LENGTH_MM, PerforatedTraySpec, TrayPart


Point = tuple[float, float]


@dataclass(frozen=True)
class PlanGeometry:
    polygons: list[list[Point]]
    slots: list[Slot]
    bbox: tuple[float, float, float, float]
    view_label: str = "TOP VIEW"


def plan_geometry(spec: PerforatedTraySpec) -> PlanGeometry:
    if spec.part == TrayPart.STRAIGHT:
        length = spec.length_mm or spec.drawing_length_mm
        width = spec.width1_mm
        polygons = [[(0.0, 0.0), (length, 0.0), (length, width), (0.0, width)]]
        slots = slots_for_rectangle(length, width)
        return PlanGeometry(polygons, slots, _bbox(polygons), "TOP VIEW")

    if spec.part in {TrayPart.HORIZONTAL_ELBOW, TrayPart.VERTICAL_INSIDE, TrayPart.VERTICAL_OUTSIDE}:
        angle = spec.angle_deg or 90.0
        radius = spec.radius_mm or 300.0
        width = spec.width1_mm
        polygon = _sector_polygon(radius, width, angle)
        slots = slots_for_sector(radius, width, angle)
        label = "SIDE VIEW" if spec.part in {TrayPart.VERTICAL_INSIDE, TrayPart.VERTICAL_OUTSIDE} else "TOP VIEW"
        return PlanGeometry([polygon], slots, _bbox([polygon]), label)

    if spec.part in {TrayPart.HORIZONTAL_TEE, TrayPart.HORIZONTAL_CROSS}:
        radius = spec.radius_mm or 300.0
        main_width = spec.width1_mm
        branch_width = spec.width2_mm or spec.width1_mm
        main_length = radius * 2.0 + main_width
        branch_length = radius + branch_width
        y0 = branch_length
        branch_x = main_length / 2.0 - branch_width / 2.0
        fillet = _tee_corner_radius(radius, branch_x, branch_width, main_width, branch_length)
        if spec.part == TrayPart.HORIZONTAL_CROSS:
            total_y = y0 + main_width + branch_length
            branch_right = branch_x + branch_width
            main_top = y0 + main_width
            polygon = _clean_points(
                [
                    (branch_x, 0.0),
                    (branch_right, 0.0),
                    (branch_right, y0 - fillet),
                    *_arc_points((branch_right + fillet, y0 - fillet), fillet, 180.0, 90.0),
                    (main_length, y0),
                    (main_length, main_top),
                    (branch_right + fillet, main_top),
                    *_arc_points((branch_right + fillet, main_top + fillet), fillet, 270.0, 180.0),
                    (branch_right, total_y),
                    (branch_x, total_y),
                    (branch_x, main_top + fillet),
                    *_arc_points((branch_x - fillet, main_top + fillet), fillet, 0.0, 270.0),
                    (0.0, main_top),
                    (0.0, y0),
                    (branch_x - fillet, y0),
                    *_arc_points((branch_x - fillet, y0 - fillet), fillet, 90.0, 0.0),
                ]
            )
        else:
            branch_right = branch_x + branch_width
            polygon = _clean_points(
                [
                    (0.0, y0),
                    (branch_x - fillet, y0),
                    *_arc_points((branch_x - fillet, y0 - fillet), fillet, 90.0, 0.0),
                    (branch_x, 0.0),
                    (branch_right, 0.0),
                    (branch_right, y0 - fillet),
                    *_arc_points((branch_right + fillet, y0 - fillet), fillet, 180.0, 90.0),
                    (main_length, y0),
                    (main_length, y0 + main_width),
                    (0.0, y0 + main_width),
                ]
            )

        slots = _slots_inside_polygon(polygon, max_slots=220)
        return PlanGeometry([polygon], slots, _bbox([polygon]), "TOP VIEW")

    if spec.is_reducer:
        length = DEFAULT_REDUCER_LENGTH_MM
        w1 = spec.width1_mm
        w2 = spec.width2_mm or spec.width1_mm
        polygon = _reducer_polygon(spec.part, length, w1, w2)
        slots = _slots_inside_polygon(polygon, max_slots=80)
        return PlanGeometry([polygon], slots, _bbox([polygon]), "TOP VIEW")

    length = spec.drawing_length_mm
    width = spec.width1_mm
    polygons = [[(0.0, 0.0), (length, 0.0), (length, width), (0.0, width)]]
    return PlanGeometry(polygons, [], _bbox(polygons), "TOP VIEW")


def _sector_polygon(radius_mm: float, width_mm: float, angle_deg: float, segments: int = 28) -> list[Point]:
    inner = max(radius_mm - width_mm / 2.0, 1.0)
    outer = radius_mm + width_mm / 2.0
    outer_points = []
    inner_points = []

    for index in range(segments + 1):
        theta = radians(angle_deg * index / segments)
        outer_points.append((outer * cos(theta), outer * sin(theta)))
        inner_points.append((inner * cos(theta), inner * sin(theta)))

    return outer_points + list(reversed(inner_points))


def _tee_corner_radius(radius_mm: float, branch_x: float, branch_width: float, main_width: float, branch_length: float) -> float:
    return max(
        1.0,
        min(
            radius_mm,
            branch_x,
            branch_length,
            max(branch_width, main_width) * 2.0,
        ),
    )


def _arc_points(center: Point, radius: float, start_deg: float, end_deg: float, segments: int = 14) -> list[Point]:
    start = radians(start_deg)
    end = radians(end_deg)
    step = (end - start) / segments
    return [
        (
            center[0] + radius * cos(start + step * index),
            center[1] + radius * sin(start + step * index),
        )
        for index in range(1, segments + 1)
    ]


def _clean_points(points: list[Point]) -> list[Point]:
    cleaned: list[Point] = []
    for point in points:
        if not cleaned or abs(cleaned[-1][0] - point[0]) > 1e-6 or abs(cleaned[-1][1] - point[1]) > 1e-6:
            cleaned.append(point)
    return cleaned


def _reducer_polygon(part: TrayPart, length_mm: float, w1_mm: float, w2_mm: float) -> list[Point]:
    if part == TrayPart.RIGHT_REDUCER:
        return [(0.0, 0.0), (length_mm, 0.0), (length_mm, w2_mm), (0.0, w1_mm)]
    if part == TrayPart.LEFT_REDUCER:
        return [(0.0, 0.0), (length_mm, w1_mm - w2_mm), (length_mm, w1_mm), (0.0, w1_mm)]

    y_mid = max(w1_mm, w2_mm) / 2.0
    return [
        (0.0, y_mid - w1_mm / 2.0),
        (length_mm, y_mid - w2_mm / 2.0),
        (length_mm, y_mid + w2_mm / 2.0),
        (0.0, y_mid + w1_mm / 2.0),
    ]


def _slots_inside_polygon(polygon: list[Point], max_slots: int) -> list[Slot]:
    min_x, min_y, max_x, max_y = _bbox([polygon])
    slots = slots_for_rectangle(max_x - min_x, max_y - min_y, origin_x=min_x, origin_y=min_y, max_slots=max_slots * 2)
    filtered = [slot for slot in slots if _slot_inside_polygon(slot, polygon)]
    return filtered[:max_slots]


def _slot_inside_polygon(slot: Slot, polygon: list[Point]) -> bool:
    angle = radians(slot.angle_deg)
    half_length = slot.length / 2.0
    half_width = slot.width / 2.0
    axis_x, axis_y = cos(angle), sin(angle)
    normal_x, normal_y = -sin(angle), cos(angle)
    test_points = [
        (0.0, 0.0),
        (-half_length, 0.0),
        (half_length, 0.0),
        (-half_length, -half_width),
        (-half_length, half_width),
        (half_length, -half_width),
        (half_length, half_width),
        (0.0, -half_width),
        (0.0, half_width),
    ]
    return all(
        _point_inside_polygon(
            (
                slot.center_x + local_x * axis_x + local_y * normal_x,
                slot.center_y + local_x * axis_y + local_y * normal_y,
            ),
            polygon,
        )
        for local_x, local_y in test_points
    )


def _point_inside_polygon(point: Point, polygon: list[Point]) -> bool:
    x, y = point
    inside = False
    previous_x, previous_y = polygon[-1]
    for current_x, current_y in polygon:
        crosses = (current_y > y) != (previous_y > y)
        if crosses:
            slope_x = (previous_x - current_x) * (y - current_y) / (previous_y - current_y) + current_x
            if x < slope_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def _bbox(polygons: list[list[Point]]) -> tuple[float, float, float, float]:
    xs = [point[0] for polygon in polygons for point in polygon]
    ys = [point[1] for polygon in polygons for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)
