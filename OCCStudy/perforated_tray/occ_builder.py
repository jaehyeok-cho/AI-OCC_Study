from __future__ import annotations

from math import atan2, cos, radians, sin, sqrt

from OCC.Core.BRep import BRep_Builder
from OCC.Core.BRepBuilderAPI import (
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_Transform,
)
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCC.Core.TopoDS import TopoDS_Compound
from OCC.Core.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pln, gp_Pnt, gp_Trsf, gp_Vec

from .drawing_geometry import Point, plan_geometry
from .perforation import slots_for_rectangle
from .spec import TRAY_LIP_MM, PerforatedTraySpec, TrayPart


def build_perforated_tray(spec: PerforatedTraySpec):
    if spec.part == TrayPart.STRAIGHT:
        return make_channel_segment(
            spec.length_mm or spec.drawing_length_mm,
            spec.width1_mm,
            spec.height_mm,
            spec.thickness_mm,
        )

    if spec.part == TrayPart.HORIZONTAL_ELBOW:
        return make_horizontal_elbow(spec)

    if spec.part in {TrayPart.VERTICAL_INSIDE, TrayPart.VERTICAL_OUTSIDE}:
        return make_vertical_elbow(spec)

    if spec.part in {TrayPart.HORIZONTAL_TEE, TrayPart.HORIZONTAL_CROSS} or spec.is_reducer:
        return make_plan_channel(spec)

    return make_channel_segment(
        spec.drawing_length_mm,
        spec.width1_mm,
        spec.height_mm,
        spec.thickness_mm,
    )


def build_perforation_markers(spec: PerforatedTraySpec):
    if spec.part in {TrayPart.VERTICAL_INSIDE, TrayPart.VERTICAL_OUTSIDE}:
        return make_vertical_perforation_markers(spec)

    geometry = plan_geometry(spec)
    markers = [
        make_slot_marker(slot.center_x, slot.center_y, slot.length, slot.width, spec.thickness_mm, slot.angle_deg)
        for slot in geometry.slots
    ]
    return make_compound(markers)


def make_horizontal_elbow(spec: PerforatedTraySpec):
    width = spec.width1_mm
    radius = spec.radius_mm or 300.0
    angle = spec.angle_deg or 90.0
    return make_sector_channel(radius, width, angle, spec.height_mm, spec.thickness_mm)


def make_vertical_elbow(spec: PerforatedTraySpec):
    width = spec.width1_mm
    radius = spec.radius_mm or 300.0
    angle = spec.angle_deg or 90.0
    sign = -1.0 if spec.part == TrayPart.VERTICAL_INSIDE else 1.0
    side_height = max(spec.height_mm, spec.thickness_mm)
    lip = min(TRAY_LIP_MM, max(width / 3.0, 6.0))
    shapes = [
        make_xz_sector_prism(radius, 0.0, spec.thickness_mm, angle, width, sign),
        make_xz_sector_prism(radius, spec.thickness_mm, side_height, angle, spec.thickness_mm, sign),
        translate(
            make_xz_sector_prism(radius, spec.thickness_mm, side_height, angle, spec.thickness_mm, sign),
            0.0,
            width - spec.thickness_mm,
            0.0,
        ),
        translate(make_xz_sector_prism(radius, side_height, side_height + spec.thickness_mm, angle, lip, sign), 0.0, spec.thickness_mm, 0.0),
        translate(
            make_xz_sector_prism(radius, side_height, side_height + spec.thickness_mm, angle, lip, sign),
            0.0,
            width - spec.thickness_mm - lip,
            0.0,
        ),
    ]
    return make_compound(shapes)


def make_plan_channel(spec: PerforatedTraySpec):
    geometry = plan_geometry(spec)
    shapes = []
    for polygon in geometry.polygons:
        shapes.append(make_plate_prism(polygon, spec.thickness_mm))
        shapes.extend(make_polygon_side_walls(polygon, spec))
    return make_compound(shapes)


def make_channel_segment(length: float, width: float, height: float, thickness: float):
    base = make_box(length, width, thickness)

    side_height = max(height - thickness, thickness)
    lip = min(TRAY_LIP_MM, max(width / 3.0, 6.0))
    shapes = [
        base,
        make_box(length, thickness, side_height, 0.0, 0.0, thickness),
        make_box(length, thickness, side_height, 0.0, width - thickness, thickness),
        make_box(length, lip, thickness, 0.0, thickness, height),
        make_box(length, lip, thickness, 0.0, width - thickness - lip, height),
    ]
    return make_compound(shapes)


def make_sector_channel(radius: float, width: float, angle: float, height: float, thickness: float):
    points = sector_points(radius, width, angle)
    base = make_plate_prism(points, thickness)
    side_height = max(height - thickness, thickness)
    inner_radius = max(radius - width / 2.0, thickness)
    outer_radius = radius + width / 2.0
    shapes = [
        base,
        make_arc_wall(inner_radius, angle, thickness, side_height, thickness),
        make_arc_wall(outer_radius, angle, thickness, side_height, thickness),
    ]
    return make_compound(shapes)


def make_polygon_side_walls(polygon: list[Point], spec: PerforatedTraySpec):
    threshold = spec.max_width_mm * 1.05
    side_height = max(spec.height_mm - spec.thickness_mm, spec.thickness_mm)
    walls = []
    for p1, p2 in polygon_edges(polygon):
        if _is_short_axis_aligned_edge(p1, p2, threshold):
            continue
        walls.append(make_bar_between(p1, p2, spec.thickness_mm, side_height + spec.thickness_mm, spec.thickness_mm))
    return walls


def make_vertical_perforation_markers(spec: PerforatedTraySpec):
    radius = spec.radius_mm or 300.0
    angle = spec.angle_deg or 90.0
    sign = -1.0 if spec.part == TrayPart.VERTICAL_INSIDE else 1.0
    arc_length = radius * radians(angle)
    markers = []
    for slot in slots_for_rectangle(arc_length, spec.width1_mm, max_slots=140):
        theta = min(radians(angle), max(0.0, slot.center_x / radius))
        point = (radius * sin(theta), slot.center_y, sign * radius * (1.0 - cos(theta)))
        marker = make_slot_marker_at_origin(slot.length, slot.width, spec.thickness_mm, slot.angle_deg)
        marker = translate(marker, 0.0, slot.center_y, spec.thickness_mm + 0.08)
        marker = rotate_y(marker, -sign * theta * 180.0 / 3.141592653589793)
        markers.append(translate(marker, point[0], 0.0, point[2]))
    return make_compound(markers)


def make_arc_wall(radius: float, angle: float, thickness: float, height: float, z: float):
    segments = max(8, int(abs(angle) / 6.0))
    points = [
        (
            radius * cos(radians(angle * index / segments)),
            radius * sin(radians(angle * index / segments)),
        )
        for index in range(segments + 1)
    ]
    return make_compound(
        make_bar_between(points[index], points[index + 1], thickness, height + thickness, z)
        for index in range(len(points) - 1)
    )


def sector_points(radius: float, width: float, angle: float, segments: int = 32):
    inner_radius = max(radius - width / 2.0, 1.0)
    outer_radius = radius + width / 2.0
    outer_points = [
        (
            outer_radius * cos(radians(angle * index / segments)),
            outer_radius * sin(radians(angle * index / segments)),
        )
        for index in range(segments + 1)
    ]
    inner_points = [
        (
            inner_radius * cos(radians(angle * index / segments)),
            inner_radius * sin(radians(angle * index / segments)),
        )
        for index in range(segments + 1)
    ]
    return outer_points + list(reversed(inner_points))


def make_slot_marker(cx: float, cy: float, length: float, width: float, thickness: float, angle_deg: float = 0.0):
    marker = make_slot_marker_at_origin(length, width, thickness, angle_deg)
    return translate(marker, cx, cy, thickness + 0.08)


def make_slot_marker_at_origin(length: float, width: float, thickness: float, angle_deg: float = 0.0):
    straight = max(length - width, 1.0)
    marker_height = 0.16
    shapes = [
        make_box(straight, width, marker_height, -straight / 2.0, -width / 2.0, 0.0),
        make_cylinder_z(width / 2.0, marker_height, -straight / 2.0, 0.0, 0.0),
        make_cylinder_z(width / 2.0, marker_height, straight / 2.0, 0.0, 0.0),
    ]
    return rotate_z(make_compound(shapes), angle_deg)


def make_plate_prism(points: list[tuple[float, float]], thickness: float):
    polygon = BRepBuilderAPI_MakePolygon()
    for x, y in points:
        polygon.Add(gp_Pnt(x, y, 0.0))
    polygon.Close()
    face = BRepBuilderAPI_MakeFace(polygon.Wire()).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0.0, 0.0, thickness)).Shape()


def make_xz_sector_prism(radius: float, offset_start: float, offset_end: float, angle: float, depth_y: float, sign: float):
    points = xz_sector_band_points(radius, offset_start, offset_end, angle, sign)
    polygon = BRepBuilderAPI_MakePolygon()
    for x, z in points:
        polygon.Add(gp_Pnt(x, 0.0, z))
    polygon.Close()
    plane = gp_Pln(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(0.0, 1.0, 0.0))
    face = BRepBuilderAPI_MakeFace(plane, polygon.Wire(), True).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0.0, depth_y, 0.0)).Shape()


def xz_sector_band_points(radius: float, offset_start: float, offset_end: float, angle: float, sign: float, segments: int = 36):
    outer_points = [
        _offset_xz_arc_point(radius, angle * index / segments, sign, offset_end)
        for index in range(segments + 1)
    ]
    inner_points = [
        _offset_xz_arc_point(radius, angle * index / segments, sign, offset_start)
        for index in range(segments + 1)
    ]
    return outer_points + list(reversed(inner_points))


def _offset_xz_arc_point(radius: float, angle_deg: float, sign: float, offset: float):
    theta = radians(angle_deg)
    center_x = radius * sin(theta)
    center_z = sign * radius * (1.0 - cos(theta))
    normal_x = -sign * sin(theta)
    normal_z = cos(theta)
    return center_x + offset * normal_x, center_z + offset * normal_z


def _is_short_axis_aligned_edge(p1: Point, p2: Point, threshold: float) -> bool:
    if distance_2d(p1, p2) > threshold:
        return False
    return abs(p1[0] - p2[0]) < 1e-6 or abs(p1[1] - p2[1]) < 1e-6


def make_bar_between(
    p1: tuple[float, float],
    p2: tuple[float, float],
    thickness: float,
    height: float,
    z: float,
):
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    length = sqrt(dx * dx + dy * dy)
    angle = atan2(dy, dx) * 180.0 / 3.141592653589793
    bar = make_box(length, thickness, max(height - thickness, thickness), 0.0, -thickness / 2.0, z)
    return translate(rotate_z(bar, angle), x1, y1, 0.0)


def make_box(x: float, y: float, z: float, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0):
    return translate(BRepPrimAPI_MakeBox(x, y, z).Shape(), dx, dy, dz)


def make_cylinder_z(radius: float, height: float, x: float, y: float, z: float):
    axis = gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0.0, 0.0, 1.0))
    return BRepPrimAPI_MakeCylinder(axis, radius, height).Shape()


def make_compound(shapes):
    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    for shape in shapes:
        builder.Add(compound, shape)
    return compound


def polygon_edges(points: list[Point]):
    return zip(points, [*points[1:], points[0]])


def distance_2d(p1: Point, p2: Point):
    return sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


def translate(shape, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0):
    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(dx, dy, dz))
    return BRepBuilderAPI_Transform(shape, transform, True).Shape()


def rotate_z(shape, angle_deg: float):
    transform = gp_Trsf()
    transform.SetRotation(gp_Ax1(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(0.0, 0.0, 1.0)), radians(angle_deg))
    return BRepBuilderAPI_Transform(shape, transform, True).Shape()


def rotate_y(shape, angle_deg: float):
    transform = gp_Trsf()
    transform.SetRotation(gp_Ax1(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(0.0, 1.0, 0.0)), radians(angle_deg))
    return BRepBuilderAPI_Transform(shape, transform, True).Shape()
