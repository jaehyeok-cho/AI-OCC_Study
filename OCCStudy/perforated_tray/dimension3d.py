from __future__ import annotations

from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCC.Core.Quantity import Quantity_Color, Quantity_NOC_BLUE1
from OCC.Core.gp import gp_Pnt

from .spec import PerforatedTraySpec


DIM_COLOR = Quantity_Color(Quantity_NOC_BLUE1)
TEXT_COLOR = (0.02, 0.10, 0.35)
DIM_LINE_WIDTH = 4.0
DIM_TEXT_HEIGHT = 28.0


def display_3d_dimensions(display, spec: PerforatedTraySpec) -> list:
    offset = max(spec.max_width_mm * 0.35, 45.0)
    length = spec.drawing_length_mm
    width = spec.max_width_mm
    height = spec.height_mm
    label_z = height + 25.0
    text_structures = []

    _display_edge(display, (0.0, -offset, 0.0), (length, -offset, 0.0))
    text_structures.append(_display_text(display, (length / 2.0, -offset - 18.0, label_z), f"L {length:g} mm"))

    _display_edge(display, (-offset, 0.0, 0.0), (-offset, width, 0.0))
    text_structures.append(_display_text(display, (-offset - 70.0, width / 2.0, label_z), f"W1 {spec.width1_mm:g} mm"))

    _display_edge(display, (length + offset, width + offset, 0.0), (length + offset, width + offset, height))
    text_structures.append(_display_text(display, (length + offset + 12.0, width + offset, label_z), f"H {height:g} mm"))

    if spec.width2_mm is not None:
        text_structures.append(_display_text(display, (length * 0.55, width + offset, label_z), f"W2 {spec.width2_mm:g} mm"))
    if spec.radius_mm is not None:
        text_structures.append(_display_text(display, (length * 0.25, width + offset * 1.5, label_z), f"R {spec.radius_mm:g} mm"))
    if spec.angle_deg is not None:
        text_structures.append(_display_text(display, (length * 0.45, width + offset * 1.5, label_z), f"A {spec.angle_deg:g} deg"))

    return [structure for structure in text_structures if structure is not None]


def _display_edge(display, p1: tuple[float, float, float], p2: tuple[float, float, float]) -> None:
    edge = BRepBuilderAPI_MakeEdge(gp_Pnt(*p1), gp_Pnt(*p2)).Edge()
    ais_shapes = display.DisplayShape(edge, update=False, color=DIM_COLOR)
    for ais_shape in ais_shapes:
        try:
            ais_shape.SetWidth(DIM_LINE_WIDTH)
        except Exception:
            pass


def _display_text(display, point: tuple[float, float, float], text: str):
    try:
        return display.DisplayMessage(gp_Pnt(*point), text, height=DIM_TEXT_HEIGHT, message_color=TEXT_COLOR, update=False)
    except TypeError:
        try:
            return display.DisplayMessage(gp_Pnt(*point), text)
        except Exception:
            return None
