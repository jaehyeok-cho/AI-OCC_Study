from __future__ import annotations

from pathlib import Path

from .occ_builder import build_perforated_tray
from .spec import PerforatedTraySpec


def save_step_model(spec: PerforatedTraySpec, file_path: str | Path) -> Path:
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer

    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    shape = build_perforated_tray(spec)

    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    status = writer.Write(str(path))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"STEP export failed: {path}")
    return path
