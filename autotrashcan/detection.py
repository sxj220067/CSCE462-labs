import cv2
import numpy as np
import config


class MotionDetector:
    """Simple motion detector based on background subtraction + morphology."""

    def __init__(self):
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=config.MOG_HISTORY,
            varThreshold=config.MOG_VAR_THRESHOLD,
            detectShadows=config.MOG_DETECT_SHADOWS,
        )
        self.kernel = cv2.getStructuringElement(cv2.MORPH_RECT, config.MORPH_KERNEL)

    def detect(self, frame):
        if frame is None:
            return None, None, []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        fg_mask = self.background_subtractor.apply(gray)
        fg_mask = cv2.GaussianBlur(fg_mask, config.BLUR_SIZE, 0)
        _, thresh = cv2.threshold(fg_mask, config.THRESHOLD_VALUE, 255, cv2.THRESH_BINARY)

        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, self.kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, self.kernel)

        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < config.MIN_CONTOUR_AREA or area > config.MAX_CONTOUR_AREA:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = float(w) / float(max(h, 1))
            if aspect_ratio < config.ASPECT_RATIO_MIN or aspect_ratio > config.ASPECT_RATIO_MAX:
                continue

            candidates.append((cnt, area, (x, y, w, h)))

        candidates.sort(key=lambda item: item[1], reverse=True)
        candidates = candidates[: config.MAX_CANDIDATES]

        if not candidates:
            return cleaned, thresh, []

        # primary target: largest candidate
        best_cnt, best_area, best_bbox = candidates[0]
        return cleaned, thresh, [(best_cnt, best_bbox)]
