from __future__ import annotations

from perforated_tray.mcp_tools import (
    create_2d_outputs,
    create_step_output,
    describe_tray_code,
    launch_gui,
    list_catalog_codes,
    show_tray_in_ui,
    validate_catalog_models,
)


try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:
    raise SystemExit(
        "The MCP Python SDK is not installed. Install it with `pip install mcp` "
        "inside the AI-OCC_Study environment."
    ) from exc


mcp = FastMCP("ai-occ-study")


@mcp.tool()
def list_perforated_tray_codes() -> dict:
    """List representative perforated tray catalog codes supported by the demo."""

    return list_catalog_codes()


@mcp.tool()
def parse_perforated_tray_code(code: str) -> dict:
    """Decode a Suhhan perforated tray code into type, material, and dimensions."""

    return describe_tray_code(code)


@mcp.tool()
def export_perforated_tray_2d(
    code: str,
    output_dir: str | None = None,
    make_svg: bool = True,
    make_dxf: bool = True,
) -> dict:
    """Create SVG and/or DXF 2D production drawings for a perforated tray code."""

    return create_2d_outputs(code, output_dir, make_svg, make_dxf)


@mcp.tool()
def export_perforated_tray_step(code: str, output_dir: str | None = None) -> dict:
    """Create a STEP 3D model for a perforated tray code. Requires pythonOCC."""

    return create_step_output(code, output_dir)


@mcp.tool()
def launch_perforated_tray_app(code: str | None = None) -> dict:
    """Launch the PyQt pythonOCC tray application, optionally with an initial code."""

    return launch_gui(code)


@mcp.tool()
def model_perforated_tray_in_ui(code: str, launch_app: bool = False) -> dict:
    """Model and display a tray code in the running PyQt UI.

    If launch_app is true, a new UI window is launched with the same code after
    the display command is written.
    """

    return show_tray_in_ui(code, launch_app)


@mcp.tool()
def validate_perforated_catalog(
    pdf_path: str | None = None,
    output_dir: str | None = None,
    build_3d: bool = True,
) -> dict:
    """Validate every perforated tray code extracted from the catalog PDF."""

    return validate_catalog_models(pdf_path, output_dir, build_3d)


if __name__ == "__main__":
    mcp.run()
