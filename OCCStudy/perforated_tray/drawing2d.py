from __future__ import annotations

from dataclasses import dataclass
from html import escape
from math import cos, radians, sin
from pathlib import Path
from typing import Iterable

from .drawing_geometry import PlanGeometry, Point, plan_geometry
from .perforation import Slot
from .spec import PerforatedTraySpec


@dataclass(frozen=True)
class DrawingOptions:
    page_width_mm: float = 420.0
    page_height_mm: float = 297.0
    margin_mm: float = 14.0


def save_svg_drawing(
    spec: PerforatedTraySpec,
    file_path: str | Path,
    options: DrawingOptions | None = None,
) -> Path:
    options = options or DrawingOptions()
    path = Path(file_path)
    path.write_text(render_svg_drawing(spec, options), encoding="utf-8")
    return path


def render_svg_drawing(spec: PerforatedTraySpec, options: DrawingOptions | None = None) -> str:
    options = options or DrawingOptions()
    geometry = plan_geometry(spec)
    canvas = SvgCanvas(options.page_width_mm, options.page_height_mm)
    canvas.raw(
        """
<style>
  .border { fill: none; stroke: #222; stroke-width: 0.45; }
  .outline { fill: #f8fafc; stroke: #111827; stroke-width: 0.7; }
  .slot { fill: #ffffff; stroke: #334155; stroke-width: 0.28; }
  .dim { stroke: #2563eb; stroke-width: 0.35; fill: none; }
  .dim-text { fill: #1d4ed8; font-family: Arial, sans-serif; font-size: 4px; }
  .label { fill: #111827; font-family: Arial, sans-serif; font-size: 4.2px; font-weight: 700; }
  .note { fill: #334155; font-family: Arial, sans-serif; font-size: 3.4px; }
  .title { fill: #111827; font-family: Arial, sans-serif; font-size: 6px; font-weight: 700; }
  .small { fill: #334155; font-family: Arial, sans-serif; font-size: 3.2px; }
</style>
""".strip()
    )
    canvas.rect(5, 5, options.page_width_mm - 10, options.page_height_mm - 10, css="border")
    canvas.text(14, 16, "PERFORATED TRAY PRODUCTION DRAWING", css="title")
    canvas.text(14, 23, spec.normalized_code, css="label")

    model_box = (24.0, 42.0, 245.0, 160.0)
    transform = PageTransform(geometry.bbox, model_box)
    _draw_svg_plan(canvas, geometry, transform)
    _draw_svg_dimensions(canvas, spec, geometry, transform)
    _draw_svg_section(canvas, spec, 292.0, 54.0)
    _draw_svg_title_block(canvas, spec, 270.0, 210.0)

    return canvas.finish()


def save_dxf_drawing(spec: PerforatedTraySpec, file_path: str | Path) -> Path:
    path = Path(file_path)
    writer = DxfWriter()
    _draw_dxf(writer, spec, plan_geometry(spec))
    path.write_text(writer.finish(), encoding="utf-8")
    return path


def _draw_svg_plan(canvas: "SvgCanvas", geometry: PlanGeometry, transform: "PageTransform") -> None:
    min_x, min_y, max_x, max_y = geometry.bbox
    label_x, label_y = transform.point(min_x, max_y)
    canvas.text(label_x, label_y - 8.0, geometry.view_label, css="label")

    for polygon in geometry.polygons:
        canvas.polyline([transform.point(x, y) for x, y in polygon], close=True, css="outline")

    for slot in geometry.slots:
        center = transform.point(slot.center_x, slot.center_y)
        canvas.rounded_slot(
            center[0],
            center[1],
            slot.length * transform.scale,
            slot.width * transform.scale,
            -slot.angle_deg,
        )


def _draw_svg_dimensions(
    canvas: "SvgCanvas",
    spec: PerforatedTraySpec,
    geometry: PlanGeometry,
    transform: "PageTransform",
) -> None:
    min_x, min_y, max_x, max_y = geometry.bbox
    bottom_left = transform.point(min_x, min_y)
    bottom_right = transform.point(max_x, min_y)
    top_left = transform.point(min_x, max_y)
    plan_width = max_y - min_y
    plan_length = max_x - min_x

    _svg_dim_horizontal(canvas, bottom_left[0], bottom_right[0], bottom_left[1] + 12.0, f"OVERALL {plan_length:g} mm")
    _svg_dim_vertical(canvas, top_left[0] - 12.0, top_left[1], bottom_left[1], f"W {plan_width:g} mm")

    if spec.length_mm is not None:
        _svg_dim_horizontal(canvas, bottom_left[0], bottom_right[0], bottom_left[1] + 22.0, f"L {spec.length_mm:g}")
    if spec.radius_mm is not None:
        canvas.text(bottom_left[0], bottom_left[1] + 28.0, f"R {spec.radius_mm:g} mm", css="dim-text")
    if spec.angle_deg is not None:
        canvas.text(bottom_left[0] + 42.0, bottom_left[1] + 28.0, f"ANGLE {spec.angle_deg:g} deg", css="dim-text")
    if spec.width2_mm is not None:
        canvas.text(bottom_left[0] + 92.0, bottom_left[1] + 28.0, f"W2 {spec.width2_mm:g} mm", css="dim-text")


def _draw_svg_section(canvas: "SvgCanvas", spec: PerforatedTraySpec, x: float, y: float) -> None:
    width = 74.0
    height = 48.0
    base_y = y + height
    side_h = height * 0.78
    lip = 12.0
    canvas.text(x, y - 9.0, "SECTION A-A", css="label")
    canvas.line(x, base_y, x + width, base_y, css="outline")
    canvas.line(x, base_y, x, base_y - side_h, css="outline")
    canvas.line(x + width, base_y, x + width, base_y - side_h, css="outline")
    canvas.line(x, base_y - side_h, x + lip, base_y - side_h, css="outline")
    canvas.line(x + width - lip, base_y - side_h, x + width, base_y - side_h, css="outline")
    _svg_dim_horizontal(canvas, x, x + width, base_y + 10.0, f"W1 {spec.width1_mm:g} mm")
    _svg_dim_vertical(canvas, x + width + 10.0, base_y - side_h, base_y, f"H {spec.height_mm:g} mm")
    canvas.text(x, base_y + 21.0, f"t {spec.thickness_mm:g} mm / {spec.section_code}", css="dim-text")


def _draw_svg_title_block(canvas: "SvgCanvas", spec: PerforatedTraySpec, x: float, y: float) -> None:
    width = 134.0
    row_h = 8.0
    rows = [
        ("CODE", spec.normalized_code),
        ("TYPE", spec.part_name),
        ("MATERIAL", spec.material_name),
        ("SECTION", spec.section_name),
        ("W1", f"{spec.width1_mm:g} mm"),
        ("H", f"{spec.height_mm:g} mm"),
    ]
    if spec.width2_mm is not None:
        rows.append(("W2", f"{spec.width2_mm:g} mm"))
    if spec.length_mm is not None:
        rows.append(("L", f"{spec.length_mm:g} mm"))
    if spec.radius_mm is not None:
        rows.append(("R", f"{spec.radius_mm:g} mm"))
    if spec.angle_deg is not None:
        rows.append(("ANGLE", f"{spec.angle_deg:g} deg"))
    if spec.unit_weight_kg is not None:
        rows.append(("U/W", f"{spec.unit_weight_kg:g} kg"))

    canvas.rect(x, y, width, row_h * (len(rows) + 1), css="border")
    canvas.text(x + 3.0, y + 5.2, "CATALOG PARAMETERS", css="label")
    for index, (key, value) in enumerate(rows, start=1):
        yy = y + index * row_h
        canvas.line(x, yy, x + width, yy, css="border")
        canvas.text(x + 3.0, yy + 5.2, key, css="small")
        canvas.text(x + 42.0, yy + 5.2, value, css="small")


def _svg_dim_horizontal(canvas: "SvgCanvas", x1: float, x2: float, y: float, label: str) -> None:
    canvas.line(x1, y, x2, y, css="dim")
    canvas.line(x1, y - 3.0, x1, y + 3.0, css="dim")
    canvas.line(x2, y - 3.0, x2, y + 3.0, css="dim")
    canvas.line(x1, y, x1 + 3.0, y - 2.0, css="dim")
    canvas.line(x2, y, x2 - 3.0, y - 2.0, css="dim")
    canvas.text((x1 + x2) / 2.0 - 14.0, y - 2.2, label, css="dim-text")


def _svg_dim_vertical(canvas: "SvgCanvas", x: float, y1: float, y2: float, label: str) -> None:
    canvas.line(x, y1, x, y2, css="dim")
    canvas.line(x - 3.0, y1, x + 3.0, y1, css="dim")
    canvas.line(x - 3.0, y2, x + 3.0, y2, css="dim")
    canvas.text(x - 24.0, (y1 + y2) / 2.0, label, css="dim-text")


def _draw_dxf(writer: "DxfWriter", spec: PerforatedTraySpec, geometry: PlanGeometry) -> None:
    writer.text(0.0, -180.0, f"PERFORATED TRAY: {spec.normalized_code}", 35.0, "TEXT")
    writer.text(0.0, -230.0, f"{spec.part_name} / {spec.material_name} / {spec.section_name}", 24.0, "TEXT")
    for polygon in geometry.polygons:
        writer.polyline(polygon, closed=True, layer="OUTLINE")
    for slot in geometry.slots:
        _dxf_slot(writer, slot)

    min_x, min_y, max_x, max_y = geometry.bbox
    writer.dimension_line((min_x, min_y - 80.0), (max_x, min_y - 80.0), f"OVERALL {max_x - min_x:g} mm")
    writer.dimension_line((min_x - 80.0, min_y), (min_x - 80.0, max_y), f"W {max_y - min_y:g} mm")
    if spec.radius_mm is not None:
        writer.text(min_x, max_y + 80.0, f"R {spec.radius_mm:g} mm", 22.0, "DIM")
    if spec.angle_deg is not None:
        writer.text(min_x + 260.0, max_y + 80.0, f"ANGLE {spec.angle_deg:g} deg", 22.0, "DIM")
    if spec.width2_mm is not None:
        writer.text(min_x + 620.0, max_y + 80.0, f"W2 {spec.width2_mm:g} mm", 22.0, "DIM")


def _dxf_slot(writer: "DxfWriter", slot: Slot) -> None:
    half_l = slot.length / 2.0
    half_w = slot.width / 2.0
    local_points = [(-half_l, -half_w), (half_l, -half_w), (half_l, half_w), (-half_l, half_w)]
    theta = radians(slot.angle_deg)
    points = [
        (
            slot.center_x + x * cos(theta) - y * sin(theta),
            slot.center_y + x * sin(theta) + y * cos(theta),
        )
        for x, y in local_points
    ]
    writer.polyline(points, closed=True, layer="SLOTS")


class PageTransform:
    def __init__(self, bbox: tuple[float, float, float, float], box: tuple[float, float, float, float]) -> None:
        self.min_x, self.min_y, self.max_x, self.max_y = bbox
        self.x, self.y, self.width, self.height = box
        model_width = max(self.max_x - self.min_x, 1.0)
        model_height = max(self.max_y - self.min_y, 1.0)
        self.scale = min(self.width / model_width, self.height / model_height)
        self.pad_x = (self.width - model_width * self.scale) / 2.0
        self.pad_y = (self.height - model_height * self.scale) / 2.0

    def point(self, x: float, y: float) -> Point:
        px = self.x + self.pad_x + (x - self.min_x) * self.scale
        py = self.y + self.height - self.pad_y - (y - self.min_y) * self.scale
        return px, py


class SvgCanvas:
    def __init__(self, width_mm: float, height_mm: float) -> None:
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.parts = [
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm:g}mm" '
                f'height="{height_mm:g}mm" viewBox="0 0 {width_mm:g} {height_mm:g}">'
            )
        ]

    def finish(self) -> str:
        return "\n".join([*self.parts, "</svg>\n"])

    def raw(self, text: str) -> None:
        self.parts.append(text)

    def line(self, x1: float, y1: float, x2: float, y2: float, css: str = "") -> None:
        self.parts.append(
            f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" class="{css}" />'
        )

    def rect(self, x: float, y: float, width: float, height: float, css: str = "") -> None:
        self.parts.append(
            f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" class="{css}" />'
        )

    def text(self, x: float, y: float, text: str, css: str = "") -> None:
        self.parts.append(f'<text x="{x:g}" y="{y:g}" class="{css}">{escape(text)}</text>')

    def polyline(self, points: Iterable[Point], close: bool = False, css: str = "") -> None:
        point_text = " ".join(f"{x:g},{y:g}" for x, y in points)
        if close:
            self.parts.append(f'<polygon points="{point_text}" class="{css}" />')
        else:
            self.parts.append(f'<polyline points="{point_text}" class="{css}" />')

    def rounded_slot(self, cx: float, cy: float, length: float, width: float, angle_deg: float) -> None:
        rx = min(width / 2.0, length / 2.0)
        self.parts.append(
            f'<rect x="{cx - length / 2.0:g}" y="{cy - width / 2.0:g}" '
            f'width="{length:g}" height="{width:g}" rx="{rx:g}" class="slot" '
            f'transform="rotate({angle_deg:g} {cx:g} {cy:g})" />'
        )


class DxfWriter:
    def __init__(self) -> None:
        self.entities: list[str] = []

    def finish(self) -> str:
        return "\n".join(
            [
                "0",
                "SECTION",
                "2",
                "ENTITIES",
                *self.entities,
                "0",
                "ENDSEC",
                "0",
                "EOF",
                "",
            ]
        )

    def line(self, p1: Point, p2: Point, layer: str = "0") -> None:
        self.entities.extend(
            [
                "0",
                "LINE",
                "8",
                layer,
                "10",
                f"{p1[0]:g}",
                "20",
                f"{p1[1]:g}",
                "11",
                f"{p2[0]:g}",
                "21",
                f"{p2[1]:g}",
            ]
        )

    def polyline(self, points: Iterable[Point], closed: bool = False, layer: str = "0") -> None:
        pts = list(points)
        flags = "1" if closed else "0"
        self.entities.extend(["0", "LWPOLYLINE", "8", layer, "90", str(len(pts)), "70", flags])
        for x, y in pts:
            self.entities.extend(["10", f"{x:g}", "20", f"{y:g}"])

    def text(self, x: float, y: float, text: str, height: float, layer: str = "TEXT") -> None:
        self.entities.extend(
            [
                "0",
                "TEXT",
                "8",
                layer,
                "10",
                f"{x:g}",
                "20",
                f"{y:g}",
                "40",
                f"{height:g}",
                "1",
                text,
            ]
        )

    def dimension_line(self, p1: Point, p2: Point, label: str) -> None:
        self.line(p1, p2, "DIM")
        self.line((p1[0] - 12.0, p1[1]), (p1[0] + 12.0, p1[1]), "DIM")
        self.line((p2[0] - 12.0, p2[1]), (p2[0] + 12.0, p2[1]), "DIM")
        self.text((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0 + 22.0, label, 22.0, "DIM")
