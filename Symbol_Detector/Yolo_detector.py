import cv2
import os
import torch
from ultralytics import YOLO


class YoloDetector:
    def __init__(self, model_path='best.pt'):
        model_path = os.fspath(model_path)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"모델 파일을 찾을 수 없습니다: {model_path}")
        self.model = YOLO(model_path)
        self.device = 0 if torch.cuda.is_available() else "cpu"

    def detect(self, raw_img, target_class, conf_threshold):
        orig_h, orig_w = raw_img.shape[:2]
        images_to_process = []

        # 원본 이미지 비율에 따라 분할 처리
        if orig_w == orig_h:
            images_to_process.append(("full", cv2.resize(raw_img, (640, 640))))
        elif orig_w > orig_h:
            mid = orig_w // 2
            images_to_process.append(("left", cv2.resize(raw_img[:, :mid], (640, 640))))
            images_to_process.append(("right", cv2.resize(raw_img[:, mid:], (640, 640))))
        else:
            mid = orig_h // 2
            images_to_process.append(("top", cv2.resize(raw_img[:mid, :], (640, 640))))
            images_to_process.append(("bottom", cv2.resize(raw_img[mid:, :], (640, 640))))

        detected_boxes = []

        # 분할된 각 이미지에 대해 추론 수행
        for suffix, target_img in images_to_process:
            results = self.model.predict(source=target_img, conf=conf_threshold, device=self.device, verbose=False)

            for box in results[0].boxes:
                cls_name = self.model.names[int(box.cls[0].item())]
                if cls_name != target_class:
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = box.conf[0].item()

                # 분할된 이미지의 좌표를 원본 이미지 좌표로 복원
                orig_coords = self._scale_coords(x1, y1, x2, y2, orig_w, orig_h, suffix)
                detected_boxes.append((*orig_coords, cls_name, conf))

        return detected_boxes

    def _scale_coords(self, x1, y1, x2, y2, orig_w, orig_h, suffix):
        # 좌표 복원 계산 로직
        if orig_w == orig_h:
            sx, sy = orig_w / 640.0, orig_h / 640.0
            return int(x1 * sx), int(y1 * sy), int(x2 * sx), int(y2 * sy)
        elif orig_w > orig_h:
            mid = orig_w // 2
            if suffix == "left":
                sx, sy = mid / 640.0, orig_h / 640.0
                return int(x1 * sx), int(y1 * sy), int(x2 * sx), int(y2 * sy)
            else:
                sx, sy = (orig_w - mid) / 640.0, orig_h / 640.0
                return int(x1 * sx) + mid, int(y1 * sy), int(x2 * sx) + mid, int(y2 * sy)
        else:
            mid = orig_h // 2
            if suffix == "top":
                sx, sy = orig_w / 640.0, mid / 640.0
                return int(x1 * sx), int(y1 * sy), int(x2 * sx), int(y2 * sy)
            else:
                sx, sy = orig_w / 640.0, (orig_h - mid) / 640.0
                return int(x1 * sx), int(y1 * sy) + mid, int(x2 * sx), int(y2 * sy) + mid
