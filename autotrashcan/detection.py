import cv2
import numpy as np

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

    def _build_target_mask(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        b_channel, g_channel, r_channel = cv2.split(frame)
        _, a_channel, _ = cv2.split(lab)
        hue, sat, val = cv2.split(hsv)

        hsv_mask = None
        for lower, upper in self.target_ranges:
            range_mask = cv2.inRange(hsv, lower, upper)
            hsv_mask = range_mask if hsv_mask is None else cv2.bitwise_or(hsv_mask, range_mask)

        sat_gate = sat >= config.HSV_RED_MIN_SAT
        val_gate = val >= config.HSV_RED_MIN_VAL
        hsv_gate = (hsv_mask > 0) & sat_gate & val_gate

        red_dominance_mask = (
            (r_channel >= config.MIN_RED_CHANNEL)
            & ((r_channel.astype(np.int16) - g_channel.astype(np.int16)) >= config.RED_DOMINANCE_DELTA)
            & ((r_channel.astype(np.int16) - b_channel.astype(np.int16)) >= config.RED_DOMINANCE_DELTA)
        )
        lab_red_mask = a_channel >= config.LAB_RED_MIN

        score = (
            hsv_gate.astype(np.uint8)
            + red_dominance_mask.astype(np.uint8)
            + lab_red_mask.astype(np.uint8)
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
            if x <= config.EDGE_IGNORE_PX or (x + w) >= (frame_width - config.EDGE_IGNORE_PX):
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
            score = (
                area
                + (target_ratio * 650.0)
                + (motion_overlap * 850.0)
                + (color_confidence * 700.0)
                + (center_bias * 120.0)
            )
            candidates.append((cnt, score, (x, y, w, h)))

        candidates.sort(key=lambda item: item[1], reverse=True)
        candidates = candidates[: config.MAX_CANDIDATES]

        if not candidates:
            return motion_mask, target_mask, []

        return motion_mask, target_mask, [(cnt, bbox) for cnt, _, bbox in candidates]
