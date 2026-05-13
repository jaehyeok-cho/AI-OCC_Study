# AI-OCC_Study

## Perforated tray OCC example

`OCCStudy/OCC_main.py` runs a purpose-built training example based on the
Suhhan perforated tray catalog numbering system.

Features:

- Decode perforated tray codes such as `PSTLBK-01530-1.5T`,
  `PHELBK-0159030-1.5T`, and `PRFLBK-030015-1.5T`.
- Generate a 3D pythonOCC model with optional floor perforation markers for
  fast interactive previews.
- Overlay 3D dimension guides for length, width, height, radius, angle, and W2
  where applicable.
- Export STEP models.
- Export 2D production drawings as SVG or DXF with dimensions and a title block.
- Preview the 2D SVG drawing in the application through the `2D drawing` tab.
- Validate all perforated tray codes extracted from the catalog PDF from the UI
  or from MCP.

Run:

```bat
python OCCStudy\OCC_main.py
```

Run with an initial tray code:

```bat
python OCCStudy\OCC_main.py --code PSTLBK-01530-1.5T
```

## MCP server

`OCCStudy/tray_mcp_server.py` exposes the tray automation as MCP tools for
Codex or another MCP client.

Tools:

- `list_perforated_tray_codes`
- `parse_perforated_tray_code`
- `export_perforated_tray_2d`
- `export_perforated_tray_step`
- `launch_perforated_tray_app`
- `model_perforated_tray_in_ui`
- `validate_perforated_catalog`

`model_perforated_tray_in_ui` sends a modeling command to the running PyQt UI.
If the UI is already open, it updates the 3D model in that window. Pass
`launch_app=true` when you also want MCP to open a UI window.

Example Codex MCP config:

```toml
[mcp_servers.ai_occ_study]
command = "python"
args = ["C:\\Code_Python\\AI-OCC_Study\\OCCStudy\\tray_mcp_server.py"]
```

Use the Python from the `AI-OCC_Study` environment so `mcp`, `pythonOCC`, and
`pyqt` are available.

The original repository setup file creates the conda environment and installs
`pythonocc-core` and `pyqt`.

## Catalog validation

Run the full catalog check directly:

```bat
python OCCStudy\validate_perforated_catalog.py --build-3d
```

The validator extracts perforated tray codes from the catalog PDF, then checks
parsing, 2D drawing geometry, SVG generation, OCC shape generation, and OCC
shape validity. Reports are written to:

- `OCCStudy\validation_reports\perforated_validation.json`
- `OCCStudy\validation_reports\perforated_validation.csv`
