import cv2
import numpy as np
from pathlib import Path

import config


class MotionDetector:
    """Detect the largest plausible color target in the frame."""

    def __init__(self):
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, config.MORPH_KERNEL)
        self.motion_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, config.MOTION_MORPH_KERNEL)
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=config.MOG_HISTORY,
            varThreshold=config.MOG_VAR_THRESHOLD,
            detectShadows=config.MOG_DETECT_SHADOWS,
        )
        self.frame_count = 0
        if hasattr(config, "TARGET_HSV_RANGES"):
            self.target_ranges = tuple(config.TARGET_HSV_RANGES)
        else:
            self.target_ranges = ((config.TARGET_HSV_LOWER, config.TARGET_HSV_UPPER),)
        self.neutral_ranges = tuple(getattr(config, "NEUTRAL_HSV_RANGES", ()))

    def _build_hsv_range_mask(self, hsv, ranges):
        mask = None
        for lower, upper in ranges:
            range_mask = cv2.inRange(hsv, lower, upper)
            mask = range_mask if mask is None else cv2.bitwise_or(mask, range_mask)

        if mask is None:
            height, width = hsv.shape[:2]
            return np.zeros((height, width), dtype=np.uint8)

        return mask

    def _build_target_mask(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        b_channel, g_channel, r_channel = cv2.split(frame)
        _, sat, val = cv2.split(hsv)

        hsv_mask = self._build_hsv_range_mask(hsv, self.target_ranges)

        sat_gate = sat >= config.HSV_GREEN_MIN_SAT
        val_gate = val >= config.HSV_GREEN_MIN_VAL
        hsv_gate = (hsv_mask > 0) & sat_gate & val_gate

        green_dominance_mask = (
            (g_channel >= config.MIN_GREEN_CHANNEL)
            & ((g_channel.astype(np.int16) - r_channel.astype(np.int16)) >= config.GREEN_DOMINANCE_DELTA)
            & ((g_channel.astype(np.int16) - b_channel.astype(np.int16)) >= config.GREEN_DOMINANCE_DELTA)
        )

        score = (
            hsv_gate.astype(np.uint8)
            + green_dominance_mask.astype(np.uint8)
        )
        combined_mask = np.where(score >= config.TARGET_BLEND_MIN_SCORE, 255, 0).astype(np.uint8)

        combined_mask = cv2.GaussianBlur(combined_mask, config.BLUR_SIZE, 0)
        _, combined_mask = cv2.threshold(
            combined_mask,
            config.TARGET_MASK_THRESHOLD,
            255,
            cv2.THRESH_BINARY,
        )
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, self.kernel)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, self.kernel)
        combined_mask = cv2.dilate(combined_mask, self.kernel, iterations=config.TARGET_DILATE_ITERATIONS)

        return combined_mask

    def detect(self, frame):
        if frame is None:
            return None, None, []

        self.frame_count += 1

        target_mask = self._build_target_mask(frame)

        learning_rate = config.MOG_LEARNING_RATE
        if self.frame_count <= config.MOTION_WARMUP_FRAMES:
            learning_rate = -1

        motion_mask = self.bg_subtractor.apply(frame, learningRate=learning_rate)
        _, motion_mask = cv2.threshold(motion_mask, config.THRESHOLD_VALUE, 255, cv2.THRESH_BINARY)
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_OPEN, self.motion_kernel)
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_CLOSE, self.motion_kernel)

        contours, _ = cv2.findContours(target_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        frame_height, frame_width = frame.shape[:2]
        search_top = int(frame_height * config.SEARCH_TOP_RATIO)
        search_bottom = int(frame_height * config.SEARCH_BOTTOM_RATIO)

        if self.frame_count <= config.MOTION_WARMUP_FRAMES:
            return motion_mask, target_mask, []

        candidates = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < config.MIN_CONTOUR_AREA or area > config.MAX_CONTOUR_AREA:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = float(w) / float(max(h, 1))
            if aspect_ratio < config.ASPECT_RATIO_MIN or aspect_ratio > config.ASPECT_RATIO_MAX:
                continue

            cx = x + w / 2.0
            cy = y + h / 2.0
            if cy < search_top or cy > search_bottom:
                continue

            bbox_mask = target_mask[y : y + h, x : x + w]
            target_pixels = cv2.countNonZero(bbox_mask)
            bbox_area = max(w * h, 1)
            target_ratio = target_pixels / float(bbox_area)
            if target_pixels < config.MIN_TARGET_PIXELS or target_ratio < config.MIN_TARGET_RATIO:
                continue

            color_confidence = min(1.0, target_pixels / float(max(area, 1.0)))
            if color_confidence < config.MIN_COLOR_CONFIDENCE:
                continue

            motion_bbox = motion_mask[y : y + h, x : x + w]
            motion_pixels = cv2.countNonZero(motion_bbox)
            motion_overlap = motion_pixels / float(bbox_area)
            if motion_pixels < config.MIN_MOTION_PIXELS or motion_overlap < config.MIN_MOTION_OVERLAP_RATIO:
                continue

            center_bias = 1.0 - abs(cx - (frame_width / 2.0)) / max(frame_width / 2.0, 1.0)
            edge_distance = min(x, frame_width - (x + w))
            edge_penalty = 0.0
            if edge_distance < config.EDGE_PENALTY_MARGIN_PX:
                edge_penalty = (config.EDGE_PENALTY_MARGIN_PX - edge_distance) * 8.0
            score = (
                area
                + (target_ratio * 650.0)
                + (motion_overlap * 850.0)
                + (color_confidence * 700.0)
                + (center_bias * 120.0)
                - edge_penalty
            )
            candidates.append((cnt, score, (x, y, w, h)))

        candidates.sort(key=lambda item: item[1], reverse=True)
        candidates = candidates[: config.MAX_CANDIDATES]

        if not candidates:
            return motion_mask, target_mask, []

        return motion_mask, target_mask, [(cnt, bbox) for cnt, _, bbox in candidates]


class ObjectDetector:
    """Detect target objects with an OpenCV DNN model and motion gating."""

    LABEL_ALIASES = {
        "can": {"wine glass", "bottle"},
        "bottle": {"wine glass"},
    }

    def __init__(self):
        self.motion_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, config.MOTION_MORPH_KERNEL)
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=config.MOG_HISTORY,
            varThreshold=config.MOG_VAR_THRESHOLD,
            detectShadows=config.MOG_DETECT_SHADOWS,
        )
        self.frame_count = 0
        self.model = self._load_model()
        self.class_names = self._load_class_names()
        self.target_labels = {label.strip().lower() for label in config.OBJECT_TARGET_LABELS if label.strip()}

    def _load_model(self):
        model_path = Path(config.OBJECT_MODEL_PATH)
        if not model_path.exists():
            raise RuntimeError(f"Object model not found: {model_path}")

        config_path = Path(config.OBJECT_CONFIG_PATH) if config.OBJECT_CONFIG_PATH else None
        if config_path and config_path.exists():
            model = cv2.dnn_DetectionModel(str(model_path), str(config_path))
        else:
            model = cv2.dnn_DetectionModel(str(model_path))

        model.setInputParams(
            size=(config.OBJECT_INPUT_WIDTH, config.OBJECT_INPUT_HEIGHT),
            scale=config.OBJECT_SCALE,
            mean=config.OBJECT_MEAN,
            swapRB=config.OBJECT_SWAP_RB,
        )
        return model

    def _load_class_names(self):
        classes_path = Path(config.OBJECT_CLASSES_PATH)
        if not classes_path.exists():
            return []

        return [line.strip() for line in classes_path.read_text().splitlines() if line.strip()]

    def _label_for_class_id(self, class_id):
        index = int(class_id) - 1
        if 0 <= index < len(self.class_names):
            return self.class_names[index]
        return str(class_id)

    def _is_target_label(self, label):
        normalized = label.lower()
        if normalized in self.target_labels:
            return True

        for target in self.target_labels:
            if normalized in self.LABEL_ALIASES.get(target, set()):
                return True

        return any(target in normalized for target in self.target_labels)

    def _build_motion_mask(self, frame):
        learning_rate = config.MOG_LEARNING_RATE
        if self.frame_count <= config.MOTION_WARMUP_FRAMES:
            learning_rate = -1

        motion_mask = self.bg_subtractor.apply(frame, learningRate=learning_rate)
        _, motion_mask = cv2.threshold(motion_mask, config.THRESHOLD_VALUE, 255, cv2.THRESH_BINARY)
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_OPEN, self.motion_kernel)
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_CLOSE, self.motion_kernel)
        return motion_mask

    def detect(self, frame):
        if frame is None:
            return None, None, []

        self.frame_count += 1
        frame_height, frame_width = frame.shape[:2]
        motion_mask = self._build_motion_mask(frame)
        target_mask = np.zeros((frame_height, frame_width), dtype=np.uint8)

        if self.frame_count <= config.MOTION_WARMUP_FRAMES:
            return motion_mask, target_mask, []

        class_ids, confidences, boxes = self.model.detect(
            frame,
            confThreshold=config.OBJECT_CONFIDENCE_THRESHOLD,
            nmsThreshold=config.OBJECT_NMS_THRESHOLD,
        )

        if class_ids is None or len(class_ids) == 0:
            return motion_mask, target_mask, []

        search_top = int(frame_height * config.SEARCH_TOP_RATIO)
        search_bottom = int(frame_height * config.SEARCH_BOTTOM_RATIO)
        candidates = []

        for class_id, confidence, box in zip(class_ids.flatten(), confidences.flatten(), boxes):
            label = self._label_for_class_id(class_id)
            if self.class_names and not self._is_target_label(label):
                continue

            x, y, w, h = [int(v) for v in box]
            x = max(0, min(frame_width - 1, x))
            y = max(0, min(frame_height - 1, y))
            w = max(1, min(frame_width - x, w))
            h = max(1, min(frame_height - y, h))
            area = w * h
            if area < config.MIN_CONTOUR_AREA or area > config.MAX_CONTOUR_AREA:
                continue

            aspect_ratio = float(w) / float(max(h, 1))
            if aspect_ratio < config.ASPECT_RATIO_MIN or aspect_ratio > config.ASPECT_RATIO_MAX:
                continue

            cx = x + w / 2.0
            cy = y + h / 2.0
            if cy < search_top or cy > search_bottom:
                continue

            motion_bbox = motion_mask[y : y + h, x : x + w]
            motion_pixels = cv2.countNonZero(motion_bbox)
            bbox_area = max(area, 1)
            motion_overlap = motion_pixels / float(bbox_area)
            if motion_pixels < config.MIN_MOTION_PIXELS or motion_overlap < config.MIN_MOTION_OVERLAP_RATIO:
                continue

            cv2.rectangle(target_mask, (x, y), (x + w, y + h), 255, -1)
            center_bias = 1.0 - abs(cx - (frame_width / 2.0)) / max(frame_width / 2.0, 1.0)
            edge_distance = min(x, frame_width - (x + w))
            edge_penalty = 0.0
            if edge_distance < config.EDGE_PENALTY_MARGIN_PX:
                edge_penalty = (config.EDGE_PENALTY_MARGIN_PX - edge_distance) * 8.0
            score = (
                area
                + (float(confidence) * 1600.0)
                + (motion_overlap * 900.0)
                + (center_bias * 120.0)
                - edge_penalty
            )
            candidates.append((None, score, (x, y, w, h)))

        candidates.sort(key=lambda item: item[1], reverse=True)
        candidates = candidates[: config.MAX_CANDIDATES]

        if not candidates:
            return motion_mask, target_mask, []

        return motion_mask, target_mask, [(cnt, bbox) for cnt, _, bbox in candidates]


class HybridDetector:
    """Use object detection when available, with color detection as a fallback."""

    def __init__(self):
        self.color_detector = MotionDetector()
        self.object_detector = ObjectDetector()

    def detect(self, frame):
        motion_mask, target_mask, candidates = self.object_detector.detect(frame)
        if candidates:
            return motion_mask, target_mask, candidates
        return self.color_detector.detect(frame)


def create_detector():
    mode = config.DETECTOR_MODE.lower()
    if mode == "color":
        return MotionDetector()
    if mode == "object":
        return ObjectDetector()
    if mode == "hybrid":
        try:
            return HybridDetector()
        except Exception as exc:
            print(f"Object detector unavailable, falling back to color detector: {exc}")
            return MotionDetector()

    raise RuntimeError(f"Unsupported DETECTOR_MODE: {config.DETECTOR_MODE}")
