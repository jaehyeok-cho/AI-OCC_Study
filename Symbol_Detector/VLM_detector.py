import cv2
import torch
from PIL import Image
from transformers import Owlv2Processor, Owlv2ForObjectDetection


class VLMDetector:
    def __init__(self, model_id="google/owlv2-base-patch16-ensemble"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = Owlv2Processor.from_pretrained(model_id)
        self.model = Owlv2ForObjectDetection.from_pretrained(model_id).to(self.device)

    def detect(self, raw_img, symbol_image_path, target_class, conf_threshold, max_width=200, max_height=200):
        # OpenCV 이미지를 PIL 이미지로 변환
        drawing_image = Image.fromarray(cv2.cvtColor(raw_img, cv2.COLOR_BGR2RGB))
        symbol_query_image = Image.open(symbol_image_path).convert("RGB")

        # 전처리 및 모델 추론
        inputs = self.processor(
            images=drawing_image,
            query_images=symbol_query_image,
            return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model.image_guided_detection(**inputs)

        # 원본 해상도에 맞게 결과 후처리
        target_sizes = torch.Tensor([drawing_image.size[::-1]]).to(self.device)
        results = self.processor.post_process_image_guided_detection(
            outputs, threshold=conf_threshold, nms_threshold=0.9, target_sizes=target_sizes
        )[0]

        detected_boxes = []

        # 설정된 크기를 초과하지 않는 박스만 필터링하여 반환
        for box, score in zip(results["boxes"], results["scores"]):
            xmin, ymin, xmax, ymax = box.tolist()
            if (xmax - xmin) > max_width or (ymax - ymin) > max_height:
                continue

            detected_boxes.append((int(xmin), int(ymin), int(xmax), int(ymax), target_class, score.item()))

        return detected_boxes