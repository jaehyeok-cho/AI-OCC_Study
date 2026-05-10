import sys
import os
from pathlib import Path
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QGraphicsView, QListWidget, QListWidgetItem, QLabel, QMessageBox,
    QGraphicsRectItem, QFrame, QSlider)
from PyQt6.QtCore import Qt, QSize, QRectF, QByteArray, QBuffer, QIODevice
from PyQt6.QtGui import QPixmap, QIcon, QPen, QColor, QFont
from PIL import Image
from PIL.ImageQt import ImageQt

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# 분리된 모델 모듈 임포트
import PDF2PNG
from local_control_server import LocalControlServer
from Yolo_detector import YoloDetector
from VLM_detector import VLMDetector
from PDF_Canvas import PDFViewCanvas

MODEL_PATH = SCRIPT_DIR / "best.pt"
SYMBOL_DIR = SCRIPT_DIR / "Symbols"
MAX_DISPLAY_SIDE = 8000


def load_pixmap_for_display(file_path):
    pixmap = QPixmap(str(file_path))
    if not pixmap.isNull():
        return pixmap

    Image.MAX_IMAGE_PIXELS = None
    with Image.open(file_path) as image:
        image = image.convert("RGBA")
        if max(image.size) > MAX_DISPLAY_SIDE:
            image.thumbnail((MAX_DISPLAY_SIDE, MAX_DISPLAY_SIDE), Image.Resampling.LANCZOS)
        return QPixmap.fromImage(ImageQt(image))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Industrial Symbol Detector UI")
        self.resize(1500, 1000)

        self.png_files = []
        self.current_page_idx = -1
        self.original_page_pixmap = None
        self.symbol_folder = SYMBOL_DIR

        self.drawn_items = []
        self.detected_boxes_data = []

        # 모델 인스턴스 지연 생성용 변수
        self.yolo_detector = None
        self.vlm_detector = None

        self.init_ui()
        self.load_initial_symbols()

        self.control_server = LocalControlServer(self)
        self.control_server.start()

    def init_ui(self):
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        # 상단 리본 메뉴 설정
        ribbon_frame = QFrame()
        ribbon_frame.setStyleSheet(
            "QFrame { background-color: #f0f2f5; border-radius: 8px; border: 1px solid #d1d5db; }")
        ribbon_layout = QHBoxLayout(ribbon_frame)

        ribbon_btn_style = """
            QPushButton { background-color: #ffffff; border: 1px solid #d1d5db; border-radius: 6px; 
                          min-width: 100px; max-width: 120px; min-height: 60px; font-weight: bold; color: #374151; }
            QPushButton:hover { background-color: #e5e7eb; border: 1px solid #9ca3af; }
            QPushButton:pressed { background-color: #d1d5db; padding-top: 2px; padding-left: 2px; }
        """

        self.btn_open = QPushButton("도면 열기\n(PDF/이미지)")
        self.btn_open.setStyleSheet(ribbon_btn_style)
        self.btn_open.clicked.connect(self.open_file)

        self.btn_capture = QPushButton("영역 캡쳐")
        self.btn_capture.setStyleSheet(ribbon_btn_style)
        self.btn_capture.clicked.connect(lambda: self.set_mode('general'))

        self.btn_reset = QPushButton("뷰어 초기화\n(원본 보기)")
        self.btn_reset.setStyleSheet(ribbon_btn_style)
        self.btn_reset.clicked.connect(self.reset_to_original)

        ribbon_layout.addWidget(self.btn_open)
        ribbon_layout.addWidget(self.btn_capture)
        ribbon_layout.addWidget(self.btn_reset)
        root_layout.addWidget(ribbon_frame)

        # 중앙 콘텐츠 레이아웃 (뷰어, 사이드바)
        content_layout = QHBoxLayout()

        self.canvas = PDFViewCanvas()
        self.canvas.setStyleSheet(
            "QGraphicsView { background-color: #e5e5e5; border: 1px solid #d1d5db; border-radius: 4px; }")
        content_layout.addWidget(self.canvas, stretch=4)

        # 사이드바 패널 설정
        sidebar = QVBoxLayout()
        sidebar.addWidget(QLabel("<b>등록된 심볼 리스트 (타겟 선택)</b>"))

        self.symbol_list_widget = QListWidget()
        self.symbol_list_widget.setIconSize(QSize(100, 100))
        self.symbol_list_widget.setStyleSheet("QListWidget { border: 1px solid #d1d5db; border-radius: 4px; }")
        sidebar.addWidget(self.symbol_list_widget)

        sidebar_btn_style = """
            QPushButton { background-color: #ffffff; border: 1px solid #d1d5db; border-radius: 4px; min-height: 35px; font-weight: bold; }
            QPushButton:hover { background-color: #e5e7eb; }
        """

        symbol_btn_layout = QHBoxLayout()
        self.btn_add_symbol = QPushButton("심볼 추가")
        self.btn_add_symbol.setStyleSheet(sidebar_btn_style)
        self.btn_add_symbol.clicked.connect(self.add_symbol_from_file_dialog)

        self.btn_delete_symbol = QPushButton("선택 삭제")
        self.btn_delete_symbol.setStyleSheet(sidebar_btn_style)
        self.btn_delete_symbol.clicked.connect(self.delete_symbol)

        symbol_btn_layout.addWidget(self.btn_add_symbol)
        symbol_btn_layout.addWidget(self.btn_delete_symbol)
        sidebar.addLayout(symbol_btn_layout)

        # Confidence 슬라이더 설정
        self.conf_label = QLabel("<b>Confidence Threshold: 0.10</b>")
        self.conf_slider = QSlider(Qt.Orientation.Horizontal)
        self.conf_slider.setRange(0, 100)
        self.conf_slider.setValue(10)
        self.conf_slider.setTickInterval(10)
        self.conf_slider.valueChanged.connect(
            lambda v: self.conf_label.setText(f"<b>Confidence Threshold: {v / 100.0:.2f}</b>"))

        sidebar.addSpacing(15)
        sidebar.addWidget(self.conf_label)
        sidebar.addWidget(self.conf_slider)
        sidebar.addSpacing(15)

        # 디텍팅 및 결과 저장 버튼 설정
        def color_btn_style(
                bg): return f"QPushButton {{ background-color: {bg}; color: white; font-weight: bold; border-radius: 5px; min-height: 45px; }}"

        self.btn_detect = QPushButton("YOLO 디텍팅 실행")
        self.btn_detect.setStyleSheet(color_btn_style("#4CAF50"))
        self.btn_detect.clicked.connect(self.run_detection)
        sidebar.addWidget(self.btn_detect)

        self.btn_vlm_detect = QPushButton("VLM 디텍팅 실행 (Owlv2)")
        self.btn_vlm_detect.setStyleSheet(color_btn_style("#9C27B0"))
        self.btn_vlm_detect.clicked.connect(self.run_vlm_detection)
        sidebar.addWidget(self.btn_vlm_detect)

        self.btn_clear_boxes = QPushButton("바운딩 박스 지우기")
        self.btn_clear_boxes.setStyleSheet(color_btn_style("#ff9800"))
        self.btn_clear_boxes.clicked.connect(self.clear_bounding_boxes)
        sidebar.addWidget(self.btn_clear_boxes)

        self.btn_save_result = QPushButton("결과 이미지 저장")
        self.btn_save_result.setStyleSheet(color_btn_style("#2196F3"))
        self.btn_save_result.clicked.connect(self.save_detection_result)
        sidebar.addWidget(self.btn_save_result)

        content_layout.addLayout(sidebar, stretch=1)
        root_layout.addLayout(content_layout)

        container = QWidget()
        container.setLayout(root_layout)
        self.setCentralWidget(container)

    def load_initial_symbols(self):
        if not self.symbol_folder.exists():
            self.symbol_folder.mkdir(parents=True)
            return

        for file_path in sorted(self.symbol_folder.iterdir()):
            if file_path.suffix.lower() in ('.png', '.jpg', '.jpeg'):
                self.add_symbol_item(file_path, file_path.name)

    def add_symbol_from_file_dialog(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "심볼 이미지 선택", "", "Images (*.png *.jpg *.jpeg)")
        for path in file_paths:
            self.add_symbol_item(path, os.path.basename(path))

    def add_symbol_item(self, file_path, filename):
        file_path = Path(file_path)
        pixmap = QPixmap(str(file_path))
        if not pixmap.isNull():
            item = QListWidgetItem()
            item.setIcon(QIcon(pixmap))
            item.setText(os.path.splitext(filename)[0])
            item.setData(Qt.ItemDataRole.UserRole, str(file_path.resolve()))
            self.symbol_list_widget.addItem(item)

    def delete_symbol(self):
        for item in self.symbol_list_widget.selectedItems():
            self.symbol_list_widget.takeItem(self.symbol_list_widget.row(item))

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", "Files (*.pdf *.png *.jpg *.jpeg)")
        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            self.png_files = PDF2PNG.convert_pdf_to_ultra_high_res(file_path) if ext == '.pdf' else [file_path]
            if self.png_files:
                self.load_page(0)

    def load_page(self, page_idx):
        if 0 <= page_idx < len(self.png_files):
            try:
                pixmap = load_pixmap_for_display(self.png_files[page_idx])
                if pixmap.isNull():
                    raise ValueError(f"이미지를 열 수 없습니다: {self.png_files[page_idx]}")

                self.original_page_pixmap = pixmap
                self.clear_bounding_boxes()
                self.canvas.set_pdf_page(pixmap)
                self.current_page_idx = page_idx
                self.canvas.fitInView(self.canvas.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            except Exception as e:
                QMessageBox.critical(self, "로드 오류", str(e))

    def set_mode(self, mode):
        self.canvas.capture_mode = mode
        self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)

    def reset_to_original(self):
        if self.original_page_pixmap:
            self.clear_bounding_boxes()
            self.canvas.set_pdf_page(self.original_page_pixmap)

    def get_current_cv2_image(self):
        if self.canvas.origin_pixmap is None: return None

        ba = QByteArray()
        buffer = QBuffer(ba)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        self.canvas.origin_pixmap.toImage().save(buffer, "PNG")
        buffer.close()

        return cv2.imdecode(np.frombuffer(ba.data(), np.uint8), cv2.IMREAD_COLOR)

    def run_detection(self):
        if self.canvas.origin_pixmap is None:
            return QMessageBox.warning(self, "경고", "도면을 열거나 영역을 캡쳐해주세요.")

        selected_items = self.symbol_list_widget.selectedItems()
        if not selected_items:
            return QMessageBox.warning(self, "경고", "타겟 심볼을 선택해주세요.")

        target_class = selected_items[0].text()
        current_conf = self.conf_slider.value() / 100.0

        if self.yolo_detector is None:
            try:
                self.yolo_detector = YoloDetector(MODEL_PATH)
            except Exception as e:
                return QMessageBox.critical(self, "오류", str(e))

        raw_img = self.get_current_cv2_image()
        if raw_img is None: return

        self.clear_bounding_boxes()
        try:
            boxes = self.yolo_detector.detect(raw_img, target_class, current_conf)
        except Exception as e:
            return QMessageBox.critical(self, "탐지 오류", str(e))

        for box in boxes:
            self.detected_boxes_data.append(box)
            self.draw_box_on_canvas(*box)

        QMessageBox.information(self, "탐지 완료", f"YOLO로 총 {len(boxes)}개 심볼 검출됨.")

    def run_vlm_detection(self):
        if self.canvas.origin_pixmap is None:
            return QMessageBox.warning(self, "경고", "도면을 열거나 영역을 캡쳐해주세요.")

        selected_items = self.symbol_list_widget.selectedItems()
        if not selected_items:
            return QMessageBox.warning(self, "경고", "쿼리 심볼을 선택해주세요.")

        target_class = selected_items[0].text()
        symbol_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
        current_conf = self.conf_slider.value() / 100.0

        if self.vlm_detector is None:
            try:
                self.vlm_detector = VLMDetector()
            except Exception as e:
                return QMessageBox.critical(self, "VLM 초기화 오류", str(e))

        raw_img = self.get_current_cv2_image()
        if raw_img is None: return

        self.clear_bounding_boxes()
        try:
            boxes = self.vlm_detector.detect(raw_img, symbol_path, target_class, current_conf)
        except Exception as e:
            return QMessageBox.critical(self, "탐지 오류", str(e))

        for box in boxes:
            self.detected_boxes_data.append(box)
            self.draw_box_on_canvas(*box)

        QMessageBox.information(self, "탐지 완료", f"VLM 모델로 총 {len(boxes)}개 심볼 검출됨.")

    def draw_box_on_canvas(self, x1, y1, x2, y2, label, conf):
        rect_item = QGraphicsRectItem(QRectF(x1, y1, x2 - x1, y2 - y1))
        rect_item.setPen(QPen(QColor(255, 0, 0), 5))
        self.canvas.scene.addItem(rect_item)
        self.drawn_items.append(rect_item)

        text_item = self.canvas.scene.addText(f"{label} ({conf:.2f})", QFont("Arial", 16, QFont.Weight.Bold))
        text_item.setDefaultTextColor(QColor(255, 0, 0))
        text_item.setPos(x1, y1 - 35)
        self.drawn_items.append(text_item)

    def clear_bounding_boxes(self):
        for item in self.drawn_items:
            if item.scene() is self.canvas.scene:
                self.canvas.scene.removeItem(item)
        self.drawn_items.clear()
        self.detected_boxes_data.clear()

    def save_detection_result(self):
        if not self.detected_boxes_data:
            return QMessageBox.warning(self, "알림", "저장할 결과가 없습니다.")

        save_path, _ = QFileDialog.getSaveFileName(self, "결과 저장", "detect_result.png",
                                                   "PNG Files (*.png);;JPEG (*.jpg)")
        if save_path:
            img = self.get_current_cv2_image()
            if img is None:
                return QMessageBox.warning(self, "알림", "저장할 이미지가 없습니다.")

            for (x1, y1, x2, y2, label, conf) in self.detected_boxes_data:
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 4)
                cv2.putText(img, f"{label} {conf:.2f}", (x1, max(0, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 1.5,
                            (0, 0, 255), 3)

            cv2.imwrite(save_path, img)
            QMessageBox.information(self, "저장 완료", f"성공적으로 저장되었습니다.\n{save_path}")

    def closeEvent(self, event):
        if hasattr(self, "control_server"):
            self.control_server.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(
        "QWidget { background-color: #f8f9fa; color: #333333; } QMessageBox { background-color: #ffffff; }")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
