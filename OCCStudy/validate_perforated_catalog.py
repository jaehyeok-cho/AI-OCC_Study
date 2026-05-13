from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from time import perf_counter

from perforated_tray.drawing2d import render_svg_drawing
from perforated_tray.drawing_geometry import plan_geometry
from perforated_tray.mcp_tools import parse_code_with_catalog_weight


CODE_RE = re.compile(r"\bP(?:ST|HE|VI|VO|HT|HC|RF|LF|SF)[LG]BK-\d+(?:-1\.5T)?\b")
DEFAULT_PDF_PATH = (
    r"C:\연구실_행정업무\35. PDMS사업\10. 받은자료"
    r"\(260407)Frome서한공업_최신카탈로그\260401 서한공업-해양플랜트 카다록 수정.pdf"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate perforated tray catalog automation.")
    parser.add_argument("--pdf", default=DEFAULT_PDF_PATH)
    parser.add_argument("--output-dir", default=str(Path("OCCStudy") / "validation_reports"))
    parser.add_argument("--build-3d", action="store_true", help="Also build OCC shapes for every extracted code.")
    args = parser.parse_args()

    started = perf_counter()
    pdf_path = Path(args.pdf)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    codes = extract_perforated_codes(pdf_path)
    results = [validate_code(code, build_3d=args.build_3d) for code in codes]
    summary = summarize(results, perf_counter() - started, pdf_path)

    json_path = output_dir / "perforated_validation.json"
    csv_path = output_dir / "perforated_validation.csv"
    json_path.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, results)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"JSON: {json_path.resolve()}")
    print(f"CSV : {csv_path.resolve()}")
    return 0 if summary["failed"] == 0 else 1


def extract_perforated_codes(pdf_path: Path) -> list[str]:
    try:
        import fitz
    except ImportError as exc:
        raise SystemExit("PyMuPDF is required. Install with `pip install PyMuPDF`.") from exc

    doc = fitz.open(pdf_path)
    text_parts = []
    # Catalog page 33-44 in the printed document corresponds to PDF indices 16-21.
    for page_index in range(16, min(22, doc.page_count)):
        text_parts.append(doc[page_index].get_text("text") or "")

    return sorted(set(CODE_RE.findall("\n".join(text_parts))))


def validate_code(code: str, build_3d: bool) -> dict:
    result = {
        "code": code,
        "part": "",
        "parse_ok": False,
        "geometry_ok": False,
        "svg_ok": False,
        "occ_shape_ok": None,
        "occ_valid_ok": None,
        "status": "failed",
        "error": "",
    }
    try:
        spec = parse_code_with_catalog_weight(code)
        result["part"] = spec.part.value
        result["parse_ok"] = True

        geometry = plan_geometry(spec)
        result["geometry_ok"] = bool(geometry.polygons and geometry.bbox[2] > geometry.bbox[0] and geometry.bbox[3] > geometry.bbox[1])

        svg = render_svg_drawing(spec)
        result["svg_ok"] = "<svg" in svg and spec.normalized_code in svg

        if build_3d:
            from OCC.Core.BRepCheck import BRepCheck_Analyzer

            from perforated_tray.occ_builder import build_perforated_tray

            shape = build_perforated_tray(spec)
            result["occ_shape_ok"] = not shape.IsNull()
            result["occ_valid_ok"] = bool(BRepCheck_Analyzer(shape).IsValid())

        result["status"] = (
            "ok"
            if result["parse_ok"]
            and result["geometry_ok"]
            and result["svg_ok"]
            and result["occ_shape_ok"] is not False
            and result["occ_valid_ok"] is not False
            else "failed"
        )
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def summarize(results: list[dict], elapsed_sec: float, pdf_path: Path) -> dict:
    counter = Counter(result["part"] or "ERROR" for result in results)
    failed = [result for result in results if result["status"] != "ok"]
    return {
        "pdf": str(pdf_path),
        "total_codes": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "by_part": dict(sorted(counter.items())),
        "elapsed_sec": round(elapsed_sec, 3),
    }


def write_csv(path: Path, results: list[dict]) -> None:
    fieldnames = ["code", "part", "parse_ok", "geometry_ok", "svg_ok", "occ_shape_ok", "occ_valid_ok", "status", "error"]
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


if __name__ == "__main__":
    sys.exit(main())
