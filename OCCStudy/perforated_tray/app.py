from __future__ import annotations

import argparse
import sys
from pathlib import Path

from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.Quantity import Quantity_Color, Quantity_NOC_STEELBLUE, Quantity_NOC_WHITE
from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCC.Display.backend import get_qt_modules, load_backend

load_backend("pyqt6")
QtCoreCompat, _, _, _ = get_qt_modules()
QtCoreCompat.Qt.LeftButton = QtCoreCompat.Qt.MouseButton.LeftButton
QtCoreCompat.Qt.RightButton = QtCoreCompat.Qt.MouseButton.RightButton
QtCoreCompat.Qt.MiddleButton = QtCoreCompat.Qt.MouseButton.MiddleButton
QtCoreCompat.Qt.MidButton = QtCoreCompat.Qt.MouseButton.MiddleButton
QtCoreCompat.Qt.ShiftModifier = QtCoreCompat.Qt.KeyboardModifier.ShiftModifier

from OCC.Display.qtDisplay import qtViewer3d
from PyQt6.QtCore import QByteArray, QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
try:
    from PyQt6.QtSvgWidgets import QSvgWidget
except Exception:
    QSvgWidget = None

from .catalog import CATALOG_EXAMPLES, parse_catalog_example
from .dimension3d import display_3d_dimensions
from .drawing2d import render_svg_drawing, save_dxf_drawing, save_svg_drawing
from .ipc import read_ui_model_command
from .mcp_tools import validate_catalog_models
from .occ_builder import build_perforated_tray, build_perforation_markers
from .parser import TrayCodeError, parse_perforated_code
from .spec import PerforatedTraySpec


MODEL_COLOR = Quantity_Color(Quantity_NOC_STEELBLUE)
SLOT_COLOR = Quantity_Color(Quantity_NOC_WHITE)


class DelayedQtViewer3d(qtViewer3d):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._driver_init_allowed = False

    def allow_driver_initialization(self):
        self._driver_init_allowed = True

    def paintEvent(self, event):
        if not self._driver_init_allowed and not self._inited:
            QWidget.paintEvent(self, event)
            return
        super().paintEvent(event)

    def resizeEvent(self, event):
        if not self._inited:
            QWidget.resizeEvent(self, event)
            return
        super().resizeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, initial_code: str | None = None):
        super().__init__()
        self.setWindowTitle("Perforated Tray OCC Automation")
        self.resize(1600, 950)
        self.setMinimumSize(1160, 720)
        self.initial_code = initial_code
        self.current_shape = None
        self.current_spec: PerforatedTraySpec | None = None
        self.dimension_text_structures = []
        self._initial_model_loaded = False
        self._last_ui_request_id: str | None = None
        self._build_ui()
        self._start_mcp_command_polling()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initial_model_loaded:
            self._initial_model_loaded = True
            QTimer.singleShot(250, self.initialize_viewer)

    def _build_ui(self):
        root = QHBoxLayout()
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        self.viewer = DelayedQtViewer3d(self)
        self.viewer.setMinimumSize(760, 620)
        self.viewer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.display = self.viewer._display
        self.dimension_overlay = QLabel(self.viewer)
        self.dimension_overlay.setObjectName("dimensionOverlay")
        self.dimension_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.dimension_overlay.move(14, 14)
        self.dimension_overlay.hide()

        self.tabs = QTabWidget()
        self.tabs.addTab(self.viewer, "3D 모델")
        self.drawing_preview = self._create_drawing_preview()
        self.tabs.addTab(self.drawing_preview, "2D 도면")
        root.addWidget(self.tabs, stretch=1)

        side = QFrame()
        side.setFixedWidth(390)
        side.setObjectName("sidePanel")
        side_layout = QVBoxLayout(side)
        side_layout.setSpacing(12)

        title = QLabel("퍼포레이티드 트레이 자동 모델링")
        title.setObjectName("title")
        subtitle = QLabel("카탈로그 코드 하나로 3D 모델, 3D 치수 오버레이, 2D 생산도면(SVG/DXF)을 생성합니다.")
        subtitle.setWordWrap(True)
        side_layout.addWidget(title)
        side_layout.addWidget(subtitle)

        input_group = QGroupBox("카탈로그 코드")
        input_layout = QVBoxLayout(input_group)
        self.code_combo = QComboBox()
        self.code_combo.setEditable(True)
        self.code_combo.addItems(CATALOG_EXAMPLES)
        self.code_combo.setCurrentText(self.initial_code or "PSTLBK-01530-1.5T")
        input_layout.addWidget(self.code_combo)

        self.perforation_check = QCheckBox("3D 바닥 타공 표시")
        self.perforation_check.setChecked(True)
        input_layout.addWidget(self.perforation_check)

        build_btn = QPushButton("3D 모델 생성")
        build_btn.clicked.connect(self.generate_model)
        input_layout.addWidget(build_btn)
        side_layout.addWidget(input_group)

        action_group = QGroupBox("내보내기")
        action_grid = QGridLayout(action_group)
        self._add_button(action_grid, "STEP 저장", 0, 0, self.save_step)
        self._add_button(action_grid, "SVG 도면", 0, 1, self.save_svg)
        self._add_button(action_grid, "DXF 도면", 1, 0, self.save_dxf)
        self._add_button(action_grid, "화면 맞춤", 1, 1, lambda: self.display.FitAll())
        self._add_button(action_grid, "카탈로그 검증", 2, 0, self.validate_catalog)
        side_layout.addWidget(action_group)

        info_group = QGroupBox("해석된 사양")
        info_layout = QVBoxLayout(info_group)
        self.spec_label = QLabel()
        self.spec_label.setObjectName("specLabel")
        self.spec_label.setWordWrap(True)
        info_layout.addWidget(self.spec_label)
        side_layout.addWidget(info_group)

        note = QLabel(
            "지원 코드: ST, HE, VI, VO, HT, HC, RF, LF, SF / 재질 L=SS316L, G=HDG / 섹션 BK=1.5t"
        )
        note.setObjectName("note")
        note.setWordWrap(True)
        side_layout.addWidget(note)
        side_layout.addStretch()

        root.addWidget(side)
        root.setStretch(0, 1)
        root.setStretch(1, 0)

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)
        self.setStyleSheet(
            """
            QWidget { background: #f5f7fa; color: #1f2933; font-size: 13px; }
            #sidePanel { background: #ffffff; border: 1px solid #d8dee6; border-radius: 8px; }
            #title { font-size: 22px; font-weight: 700; }
            #note { background: #eef6f8; border: 1px solid #b9d7df; border-radius: 6px; padding: 10px; }
            #specLabel { font-family: Consolas, 'Courier New', monospace; line-height: 1.35; }
            #dimensionOverlay { background: rgba(255, 255, 255, 220); border: 1px solid #b8c2cc; border-radius: 6px; padding: 8px; font-family: Consolas, 'Courier New', monospace; }
            QGroupBox { font-weight: 700; border: 1px solid #d8dee6; border-radius: 6px; margin-top: 10px; padding-top: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QComboBox { background: #ffffff; border: 1px solid #b8c2cc; border-radius: 6px; min-height: 36px; padding: 4px; }
            QPushButton { background: #ffffff; border: 1px solid #b8c2cc; border-radius: 6px; min-height: 40px; font-weight: 600; }
            QPushButton:hover { background: #e9f7fb; border-color: #4ba3b7; }
            QPushButton:pressed { background: #d6edf4; }
            QCheckBox { padding: 4px; }
            QTabWidget::pane { border: 1px solid #d8dee6; background: #ffffff; }
            QTabBar::tab { background: #edf2f7; border: 1px solid #cbd5df; padding: 8px 14px; }
            QTabBar::tab:selected { background: #ffffff; border-bottom-color: #ffffff; }
            """
        )

    def _create_drawing_preview(self):
        if QSvgWidget is not None:
            widget = QSvgWidget()
            widget.setMinimumSize(760, 620)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            return widget

        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setMinimumSize(760, 620)
        return editor

    def _start_mcp_command_polling(self):
        self.command_timer = QTimer(self)
        self.command_timer.timeout.connect(self.check_mcp_command)
        self.command_timer.start(700)

    def check_mcp_command(self):
        command = read_ui_model_command()
        if not command or command.get("action") != "model_tray":
            return

        request_id = command.get("request_id")
        if not request_id or request_id == self._last_ui_request_id:
            return

        code = str(command.get("code", "")).strip().upper()
        if not code:
            self._last_ui_request_id = request_id
            return

        self._last_ui_request_id = request_id
        self.code_combo.setCurrentText(code)
        self.tabs.setCurrentWidget(self.viewer)
        self.generate_model()

    def initialize_viewer(self):
        self.viewer.allow_driver_initialization()
        self.viewer.update()
        QTimer.singleShot(250, self.show_initial_model_when_ready)

    def show_initial_model_when_ready(self, attempts=0):
        if not self.viewer._inited:
            if attempts < 20:
                self.viewer.update()
                QTimer.singleShot(150, lambda: self.show_initial_model_when_ready(attempts + 1))
            return
        self.sync_viewer_size()
        self.generate_model()

    def sync_viewer_size(self):
        self.viewer.updateGeometry()
        self.viewer.resize(self.viewer.size())
        self.display.View.MustBeResized()
        self.display.SetModeShaded()

    def _add_button(self, layout, text, row, col, handler):
        button = QPushButton(text)
        button.clicked.connect(handler)
        layout.addWidget(button, row, col)

    def generate_model(self):
        try:
            spec = self._read_spec()
            shape = build_perforated_tray(spec)
        except TrayCodeError as exc:
            QMessageBox.warning(self, "코드 해석 실패", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "모델 생성 실패", str(exc))
            return

        self.display_shape(shape, spec)

    def _read_spec(self) -> PerforatedTraySpec:
        code = self.code_combo.currentText().strip()
        if code.upper() in CATALOG_EXAMPLES:
            return parse_catalog_example(code)
        return parse_perforated_code(code)

    def display_shape(self, shape, spec: PerforatedTraySpec):
        if not self.viewer._inited:
            self.viewer.allow_driver_initialization()
            self.viewer.update()
            QTimer.singleShot(150, lambda: self.display_shape(shape, spec))
            return

        self.clear_scene()
        self.current_shape = shape
        self.current_spec = spec
        self.display.DisplayShape(shape, update=False, color=MODEL_COLOR, transparency=0.03)
        if self.perforation_check.isChecked():
            markers = build_perforation_markers(spec)
            self.display.DisplayShape(markers, update=False, color=SLOT_COLOR, transparency=0.0)
        self.dimension_text_structures = display_3d_dimensions(self.display, spec)
        self.update_dimension_overlay(spec)
        self.sync_viewer_size()
        self.display.FitAll()
        self.display.Repaint()
        self.spec_label.setText(self._format_spec(spec))
        self.update_drawing_preview(spec)

    def clear_scene(self):
        self.clear_dimension_text()
        try:
            self.display.Context.RemoveAll(True)
        except Exception:
            pass

    def clear_dimension_text(self):
        for structure in self.dimension_text_structures:
            try:
                structure.Erase()
            except Exception:
                pass
            try:
                structure.Clear()
            except Exception:
                pass
            try:
                structure.Remove()
            except Exception:
                pass
        self.dimension_text_structures = []
        try:
            self.display.EraseAll()
        except Exception:
            pass
        try:
            self.display.Context.UpdateCurrentViewer()
        except Exception:
            pass

    def update_drawing_preview(self, spec: PerforatedTraySpec):
        svg = render_svg_drawing(spec)
        if QSvgWidget is not None and isinstance(self.drawing_preview, QSvgWidget):
            self.drawing_preview.load(QByteArray(svg.encode("utf-8")))
            return
        if isinstance(self.drawing_preview, QTextEdit):
            self.drawing_preview.setPlainText(svg)

    def update_dimension_overlay(self, spec: PerforatedTraySpec):
        lines = [
            f"L  {spec.drawing_length_mm:g} mm",
            f"W1 {spec.width1_mm:g} mm",
            f"H  {spec.height_mm:g} mm",
            f"t  {spec.thickness_mm:g} mm",
        ]
        if spec.width2_mm is not None:
            lines.append(f"W2 {spec.width2_mm:g} mm")
        if spec.radius_mm is not None:
            lines.append(f"R  {spec.radius_mm:g} mm")
        if spec.angle_deg is not None:
            lines.append(f"A  {spec.angle_deg:g} deg")
        self.dimension_overlay.setText("\n".join(lines))
        self.dimension_overlay.adjustSize()
        self.dimension_overlay.show()

    def save_step(self):
        if self.current_shape is None or self.current_spec is None:
            QMessageBox.warning(self, "저장할 모델 없음", "먼저 모델을 생성해 주세요.")
            return

        default_path = Path.cwd() / f"{self.current_spec.normalized_code}.step"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "STEP 파일 저장",
            str(default_path),
            "STEP Files (*.step *.stp)",
        )
        if not file_path:
            return

        writer = STEPControl_Writer()
        writer.Transfer(self.current_shape, STEPControl_AsIs)
        status = writer.Write(file_path)

        if status == IFSelect_RetDone:
            QMessageBox.information(self, "저장 완료", f"STEP 파일을 저장했습니다.\n{file_path}")
        else:
            QMessageBox.critical(self, "저장 실패", "STEP 파일 저장 중 오류가 발생했습니다.")

    def save_svg(self):
        spec = self._current_or_input_spec()
        if spec is None:
            return
        default_path = Path.cwd() / f"{spec.normalized_code}.svg"
        file_path, _ = QFileDialog.getSaveFileName(self, "SVG 도면 저장", str(default_path), "SVG Files (*.svg)")
        if not file_path:
            return
        save_svg_drawing(spec, file_path)
        QMessageBox.information(self, "저장 완료", f"SVG 도면을 저장했습니다.\n{file_path}")

    def save_dxf(self):
        spec = self._current_or_input_spec()
        if spec is None:
            return
        default_path = Path.cwd() / f"{spec.normalized_code}.dxf"
        file_path, _ = QFileDialog.getSaveFileName(self, "DXF 도면 저장", str(default_path), "DXF Files (*.dxf)")
        if not file_path:
            return
        save_dxf_drawing(spec, file_path)
        QMessageBox.information(self, "저장 완료", f"DXF 도면을 저장했습니다.\n{file_path}")

    def validate_catalog(self):
        try:
            result = validate_catalog_models(build_3d=True)
        except Exception as exc:
            QMessageBox.critical(self, "카탈로그 검증 실패", str(exc))
            return

        summary = result.get("summary", {})
        message = "\n".join(
            [
                f"전체 코드: {summary.get('total_codes', 0)}",
                f"통과: {summary.get('passed', 0)}",
                f"실패: {summary.get('failed', 0)}",
                f"타입별: {summary.get('by_part', {})}",
                "",
                f"JSON: {result.get('report_json', '')}",
                f"CSV: {result.get('report_csv', '')}",
            ]
        )
        if result.get("ok"):
            QMessageBox.information(self, "카탈로그 검증 완료", message)
        else:
            QMessageBox.warning(self, "카탈로그 검증 오류", message)

    def _current_or_input_spec(self) -> PerforatedTraySpec | None:
        if self.current_spec is not None:
            return self.current_spec
        try:
            return self._read_spec()
        except TrayCodeError as exc:
            QMessageBox.warning(self, "코드 해석 실패", str(exc))
            return None

    def _format_spec(self, spec: PerforatedTraySpec) -> str:
        return "\n".join(f"{key:<12}: {value}" for key, value in spec.summary_rows())


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--code")
    parsed, qt_args = parser.parse_known_args(sys.argv[1:])

    high_dpi_attr = getattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling", None)
    if high_dpi_attr is not None:
        QApplication.setAttribute(high_dpi_attr, True)

    app = QApplication([sys.argv[0], *qt_args])
    window = MainWindow(initial_code=parsed.code)
    window.show()
    sys.exit(app.exec())
