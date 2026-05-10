import sys
from pathlib import Path

try:
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from OCC.Core.TopoDS import TopoDS_Compound
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from OCC.Core.Quantity import Quantity_Color, Quantity_NOC_STEELBLUE
    from OCC.Display.backend import get_qt_modules, load_backend

    load_backend("pyqt6")
    QtCoreCompat, _, _, _ = get_qt_modules()
    QtCoreCompat.Qt.LeftButton = QtCoreCompat.Qt.MouseButton.LeftButton
    QtCoreCompat.Qt.RightButton = QtCoreCompat.Qt.MouseButton.RightButton
    QtCoreCompat.Qt.MiddleButton = QtCoreCompat.Qt.MouseButton.MiddleButton
    QtCoreCompat.Qt.MidButton = QtCoreCompat.Qt.MouseButton.MiddleButton
    QtCoreCompat.Qt.ShiftModifier = QtCoreCompat.Qt.KeyboardModifier.ShiftModifier
    from OCC.Display.qtDisplay import qtViewer3d
except Exception as exc:
    print("pythonOCC 초기화 실패:", exc)
    print("README.md의 설치 방법을 확인해 주세요.")
    raise

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication,
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
    QVBoxLayout,
    QWidget,
)

MODEL_COLOR = Quantity_Color(Quantity_NOC_STEELBLUE)


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


def translate(shape, dx=0.0, dy=0.0, dz=0.0):
    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(dx, dy, dz))
    return BRepBuilderAPI_Transform(shape, transform, True).Shape()


def make_compound(shapes):
    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    for shape in shapes:
        builder.Add(compound, shape)
    return compound


def make_box(x, y, z, dx=0.0, dy=0.0, dz=0.0):
    return translate(BRepPrimAPI_MakeBox(x, y, z).Shape(), dx, dy, dz)


def make_pipe(length, outer_radius, inner_radius):
    axis = gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0))
    outer = BRepPrimAPI_MakeCylinder(axis, outer_radius, length).Shape()
    inner = BRepPrimAPI_MakeCylinder(axis, inner_radius, length + 20).Shape()
    inner = translate(inner, -10, 0, 0)
    return BRepAlgoAPI_Cut(outer, inner).Shape()


def make_deck_panel():
    shapes = [make_box(5200, 2600, 80)]

    for y in (420, 1120, 1820):
        shapes.append(make_box(5200, 70, 420, 0, y, 80))
        shapes.append(make_box(5200, 260, 45, 0, y - 95, 500))

    for x in (1200, 2600, 4000):
        shapes.append(make_box(80, 2600, 300, x, 0, 80))
        shapes.append(make_box(300, 2600, 45, x - 110, 0, 360))

    return make_compound(shapes)


def make_pipe_spool():
    pipe = make_pipe(3600, 210, 150)
    flange_left = translate(make_pipe(180, 360, 170), -90, 0, 0)
    flange_right = translate(make_pipe(180, 360, 170), 3510, 0, 0)

    supports = [
        make_box(260, 520, 90, 720, -260, -420),
        make_box(160, 320, 420, 770, -160, -420),
        make_box(260, 520, 90, 2600, -260, -420),
        make_box(160, 320, 420, 2650, -160, -420),
    ]
    return make_compound([pipe, flange_left, flange_right, *supports])


def make_equipment_seat():
    base = make_box(3600, 2200, 120)
    skid_1 = make_box(3400, 260, 260, 100, 260, 120)
    skid_2 = make_box(3400, 260, 260, 100, 1680, 120)
    pads = [
        make_box(420, 420, 80, 420, 440, 380),
        make_box(420, 420, 80, 2760, 440, 380),
        make_box(420, 420, 80, 420, 1340, 380),
        make_box(420, 420, 80, 2760, 1340, 380),
    ]
    columns = [
        make_box(180, 180, 900, 540, 560, 460),
        make_box(180, 180, 900, 2880, 560, 460),
        make_box(180, 180, 900, 540, 1460, 460),
        make_box(180, 180, 900, 2880, 1460, 460),
    ]
    top = make_box(3000, 1600, 120, 300, 300, 1360)
    return make_compound([base, skid_1, skid_2, *pads, *columns, top])


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("pythonOCC Shipyard Automation Demo")
        self.resize(1600, 950)
        self.setMinimumSize(1100, 720)
        self.current_shape = None
        self.current_name = "model"
        self._initial_model_loaded = False
        self._build_ui()

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
        root.addWidget(self.viewer, stretch=1)

        side = QFrame()
        side.setFixedWidth(340)
        side.setObjectName("sidePanel")
        side_layout = QVBoxLayout(side)
        side_layout.setSpacing(12)

        title = QLabel("OCC 자동 모델링 예제")
        title.setObjectName("title")
        subtitle = QLabel("조선 설계 업무에서 반복 형상을 버튼으로 생성하는 간단한 데모입니다.")
        subtitle.setWordWrap(True)
        side_layout.addWidget(title)
        side_layout.addWidget(subtitle)

        model_group = QGroupBox("자동 생성 모델")
        grid = QGridLayout(model_group)
        self._add_button(grid, "Deck Panel", 0, 0, self.show_deck_panel)
        self._add_button(grid, "Pipe Spool", 0, 1, self.show_pipe_spool)
        self._add_button(grid, "Equipment Seat", 1, 0, self.show_equipment_seat)
        self._add_button(grid, "Clear", 1, 1, self.clear_view)
        side_layout.addWidget(model_group)

        action_group = QGroupBox("산출물")
        action_layout = QVBoxLayout(action_group)
        save_btn = QPushButton("STEP 파일 저장")
        save_btn.clicked.connect(self.save_step)
        action_layout.addWidget(save_btn)
        fit_btn = QPushButton("화면 맞춤")
        fit_btn.clicked.connect(lambda: self.display.FitAll())
        action_layout.addWidget(fit_btn)
        side_layout.addWidget(action_group)

        note = QLabel(
            "예시 포인트\n"
            "- 설계 규칙을 파라미터로 바꾸면 반복 모델링을 자동화할 수 있습니다.\n"
            "- 생성된 형상은 STEP으로 저장해 CAD 도구와 연계할 수 있습니다."
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
            QWidget { background: #f4f6f8; color: #1f2933; font-size: 13px; }
            #sidePanel { background: #ffffff; border: 1px solid #d8dee6; border-radius: 8px; }
            #title { font-size: 22px; font-weight: 700; }
            #note { background: #eef5ff; border: 1px solid #bdd7f5; border-radius: 6px; padding: 10px; }
            QGroupBox { font-weight: 700; border: 1px solid #d8dee6; border-radius: 6px; margin-top: 10px; padding-top: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QPushButton { background: #ffffff; border: 1px solid #b8c2cc; border-radius: 6px; min-height: 42px; font-weight: 600; }
            QPushButton:hover { background: #e9f2ff; border-color: #6aa6e8; }
            QPushButton:pressed { background: #d8eaff; }
            """
        )

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
        self.show_deck_panel()

    def sync_viewer_size(self):
        self.viewer.updateGeometry()
        self.viewer.resize(self.viewer.size())
        self.display.View.MustBeResized()
        self.display.SetModeShaded()

    def _add_button(self, layout, text, row, col, handler):
        button = QPushButton(text)
        button.clicked.connect(handler)
        layout.addWidget(button, row, col)

    def display_shape(self, shape, name):
        if not self.viewer._inited:
            self.viewer.allow_driver_initialization()
            self.viewer.update()
            QTimer.singleShot(150, lambda: self.display_shape(shape, name))
            return

        self.clear_view()
        self.current_shape = shape
        self.current_name = name
        self.display.DisplayShape(shape, update=False, color=MODEL_COLOR, transparency=0.05)
        self.sync_viewer_size()
        self.display.FitAll()
        self.display.Repaint()

    def show_deck_panel(self):
        self.display_shape(make_deck_panel(), "deck_panel")

    def show_pipe_spool(self):
        self.display_shape(make_pipe_spool(), "pipe_spool")

    def show_equipment_seat(self):
        self.display_shape(make_equipment_seat(), "equipment_seat")

    def clear_view(self):
        self.display.EraseAll()
        self.current_shape = None

    def save_step(self):
        if self.current_shape is None:
            QMessageBox.warning(self, "저장할 형상 없음", "먼저 모델을 생성해 주세요.")
            return

        default_path = Path.cwd() / f"{self.current_name}.step"
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


def main():
    high_dpi_attr = getattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling", None)
    if high_dpi_attr is not None:
        QApplication.setAttribute(high_dpi_attr, True)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
