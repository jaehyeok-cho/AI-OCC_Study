from PyQt6.QtWidgets import (QGraphicsView, QGraphicsScene, QRubberBand,)
from PyQt6.QtCore import Qt, QRect, QSize, QPoint
from PyQt6.QtGui import QPixmap

class PDFViewCanvas(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        self.pixmap_item = None
        self.origin_pixmap = None
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.origin_point = QPoint()
        self.capture_mode = None

    def set_pdf_page(self, pixmap):
        self.scene.clear()
        self.origin_pixmap = pixmap
        self.pixmap_item = self.scene.addPixmap(pixmap)
        self.setSceneRect(self.pixmap_item.boundingRect())

    def wheelEvent(self, event):
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if self.capture_mode and event.button() == Qt.MouseButton.LeftButton:
            self.origin_point = event.pos()
            self.rubber_band.setGeometry(QRect(self.origin_point, QSize()))
            self.rubber_band.show()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.capture_mode and not self.origin_point.isNull():
            self.rubber_band.setGeometry(QRect(self.origin_point, event.pos()).normalized())
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.capture_mode and not self.origin_point.isNull():
            selected_rect = self.rubber_band.geometry()
            self.rubber_band.hide()
            self.process_capture(selected_rect)
            self.origin_point = QPoint()
        else:
            super().mouseReleaseEvent(event)

    def process_capture(self, rect):
        if self.origin_pixmap is None or rect.isNull() or rect.width() <= 1 or rect.height() <= 1:
            self.capture_mode = None
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            return

        scene_rect = self.mapToScene(rect).boundingRect()
        cropped_image = self.origin_pixmap.toImage().copy(scene_rect.toRect())

        if self.capture_mode == 'general':
            self.set_pdf_page(QPixmap.fromImage(cropped_image))

        self.capture_mode = None
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
