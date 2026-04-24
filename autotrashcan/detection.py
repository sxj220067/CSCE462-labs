import cv2
import numpy as np

import config


class MotionDetector:
    """Detect the largest plausible moving target as a fallback."""

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
        self.fast_color_detection = bool(getattr(config, "FAST_COLOR_DETECTION", False))

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
        hsv_mask = self._build_hsv_range_mask(hsv, self.target_ranges)
        combined_mask = hsv_mask
        if not self.fast_color_detection:
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

        proposal_mask = cv2.bitwise_or(target_mask, motion_mask)
        proposal_mask = cv2.morphologyEx(proposal_mask, cv2.MORPH_CLOSE, self.motion_kernel)
        contours, _ = cv2.findContours(proposal_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
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

            bbox_mask = proposal_mask[y : y + h, x : x + w]
            target_pixels = cv2.countNonZero(bbox_mask)
            bbox_area = max(w * h, 1)
            target_ratio = target_pixels / float(bbox_area)
            if target_pixels < config.MIN_TARGET_PIXELS or target_ratio < config.MIN_TARGET_RATIO:
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
                + (center_bias * 120.0)
                - edge_penalty
            )
            candidates.append((cnt, score, (x, y, w, h)))

        candidates.sort(key=lambda item: item[1], reverse=True)
        candidates = candidates[: config.MAX_CANDIDATES]

        if not candidates:
            return motion_mask, target_mask, []

        return motion_mask, target_mask, [(cnt, bbox) for cnt, _, bbox in candidates]


def create_detector():
    return MotionDetector()
