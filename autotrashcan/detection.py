import cv2

import config


class MotionDetector:
    """Detect the largest plausible bright-yellow blob in the frame."""

    def __init__(self):
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, config.MORPH_KERNEL)
        if hasattr(config, "TARGET_HSV_RANGES"):
            self.target_ranges = tuple(config.TARGET_HSV_RANGES)
        else:
            self.target_ranges = ((config.TARGET_HSV_LOWER, config.TARGET_HSV_UPPER),)

    def detect(self, frame):
        if frame is None:
            return None, None, []

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        target_mask = None
        for lower, upper in self.target_ranges:
            range_mask = cv2.inRange(hsv, lower, upper)
            target_mask = range_mask if target_mask is None else cv2.bitwise_or(target_mask, range_mask)

        target_mask = cv2.GaussianBlur(target_mask, config.BLUR_SIZE, 0)
        _, target_mask = cv2.threshold(target_mask, 127, 255, cv2.THRESH_BINARY)
        target_mask = cv2.morphologyEx(target_mask, cv2.MORPH_OPEN, self.kernel)
        target_mask = cv2.morphologyEx(target_mask, cv2.MORPH_CLOSE, self.kernel)

        contours, _ = cv2.findContours(target_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        frame_height, frame_width = frame.shape[:2]
        search_top = int(frame_height * config.SEARCH_TOP_RATIO)
        search_bottom = int(frame_height * config.SEARCH_BOTTOM_RATIO)

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

            center_bias = 1.0 - abs(cx - (frame_width / 2.0)) / max(frame_width / 2.0, 1.0)
            score = area + (target_ratio * 600.0) + (center_bias * 120.0)
            candidates.append((cnt, score, (x, y, w, h)))

        candidates.sort(key=lambda item: item[1], reverse=True)
        candidates = candidates[: config.MAX_CANDIDATES]

        if not candidates:
            return target_mask, target_mask, []

        return target_mask, target_mask, [(cnt, bbox) for cnt, _, bbox in candidates]
