from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path
from typing import Any

from .catalog import CATALOG_EXAMPLES, parse_catalog_example
from .drawing2d import save_dxf_drawing, save_svg_drawing
from .ipc import UI_COMMAND_FILE, write_ui_model_command
from .parser import parse_perforated_code
from .spec import PerforatedTraySpec


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OCC_MAIN = PROJECT_ROOT / "OCCStudy" / "OCC_main.py"
VALIDATOR = PROJECT_ROOT / "OCCStudy" / "validate_perforated_catalog.py"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "OCCStudy" / "outputs"
DEFAULT_VALIDATION_DIR = PROJECT_ROOT / "OCCStudy" / "validation_reports"


def list_catalog_codes() -> dict[str, Any]:
    return {
        "count": len(CATALOG_EXAMPLES),
        "codes": CATALOG_EXAMPLES,
    }


def describe_tray_code(code: str) -> dict[str, Any]:
    spec = parse_code_with_catalog_weight(code)
    return spec_to_dict(spec)


def create_2d_outputs(
    code: str,
    output_dir: str | None = None,
    make_svg: bool = True,
    make_dxf: bool = True,
) -> dict[str, Any]:
    spec = parse_code_with_catalog_weight(code)
    target_dir = resolve_output_dir(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    outputs: dict[str, str] = {}
    if make_svg:
        svg_path = target_dir / f"{spec.normalized_code}.svg"
        save_svg_drawing(spec, svg_path)
        outputs["svg"] = str(svg_path)
    if make_dxf:
        dxf_path = target_dir / f"{spec.normalized_code}.dxf"
        save_dxf_drawing(spec, dxf_path)
        outputs["dxf"] = str(dxf_path)

    return {
        "code": spec.normalized_code,
        "output_dir": str(target_dir),
        "outputs": outputs,
    }


def create_step_output(code: str, output_dir: str | None = None) -> dict[str, Any]:
    spec = parse_code_with_catalog_weight(code)
    target_dir = resolve_output_dir(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    step_path = target_dir / f"{spec.normalized_code}.step"

    from .export import save_step_model

    save_step_model(spec, step_path)
    return {
        "code": spec.normalized_code,
        "step": str(step_path),
    }


def launch_gui(code: str | None = None) -> dict[str, Any]:
    args = [sys.executable, str(OCC_MAIN)]
    if code:
        args.extend(["--code", parse_code_with_catalog_weight(code).normalized_code])

    process = subprocess.Popen(
        args,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_creation_flags(),
    )
    return {
        "pid": process.pid,
        "command": args,
        "cwd": str(PROJECT_ROOT),
    }


def show_tray_in_ui(code: str, launch_app: bool = False) -> dict[str, Any]:
    spec = parse_code_with_catalog_weight(code)
    payload = write_ui_model_command(spec.normalized_code)
    result: dict[str, Any] = {
        "code": spec.normalized_code,
        "ui_command_file": str(UI_COMMAND_FILE),
        "request_id": payload["request_id"],
        "message": "Model command sent to the tray UI. If the UI is open, it will update within about one second.",
    }
    if launch_app:
        result["launched_app"] = launch_gui(spec.normalized_code)
    return result


def validate_catalog_models(
    pdf_path: str | None = None,
    output_dir: str | None = None,
    build_3d: bool = True,
) -> dict[str, Any]:
    target_dir = Path(output_dir) if output_dir else DEFAULT_VALIDATION_DIR
    if not target_dir.is_absolute():
        target_dir = PROJECT_ROOT / target_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    args = [
        sys.executable,
        str(VALIDATOR),
        "--output-dir",
        str(target_dir),
    ]
    if pdf_path:
        args.extend(["--pdf", pdf_path])
    if build_3d:
        args.append("--build-3d")

    completed = subprocess.run(
        args,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    report_path = target_dir / "perforated_validation.json"
    csv_path = target_dir / "perforated_validation.csv"
    report: dict[str, Any] = {}
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))

    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "summary": report.get("summary", {}),
        "report_json": str(report_path),
        "report_csv": str(csv_path),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def parse_code_with_catalog_weight(code: str) -> PerforatedTraySpec:
    normalized = code.strip().upper()
    if normalized in CATALOG_EXAMPLES:
        return parse_catalog_example(normalized)
    return parse_perforated_code(normalized)


def spec_to_dict(spec: PerforatedTraySpec) -> dict[str, Any]:
    return {
        "code": spec.normalized_code,
        "part": spec.part.value,
        "part_name": spec.part_name,
        "material_code": spec.material_code,
        "material_name": spec.material_name,
        "section_code": spec.section_code,
        "section_name": spec.section_name,
        "width1_mm": spec.width1_mm,
        "width2_mm": spec.width2_mm,
        "height_mm": spec.height_mm,
        "thickness_mm": spec.thickness_mm,
        "length_mm": spec.length_mm,
        "drawing_length_mm": spec.drawing_length_mm,
        "angle_deg": spec.angle_deg,
        "radius_mm": spec.radius_mm,
        "unit_weight_kg": spec.unit_weight_kg,
        "summary": [{"name": name, "value": value} for name, value in spec.summary_rows()],
    }


def resolve_output_dir(output_dir: str | None) -> Path:
    if not output_dir:
        return DEFAULT_OUTPUT_DIR
    path = Path(output_dir)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _creation_flags() -> int:
    if sys.platform != "win32":
        return 0
    return getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
