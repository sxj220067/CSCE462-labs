import cv2
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
        self.target_lower = config.TARGET_HSV_LOWER
        self.target_upper = config.TARGET_HSV_UPPER

    def detect(self, frame):
        if frame is None:
            return None, None, []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        target_mask = cv2.inRange(hsv, self.target_lower, self.target_upper)
        target_mask = cv2.morphologyEx(target_mask, cv2.MORPH_OPEN, self.kernel)
        target_mask = cv2.morphologyEx(target_mask, cv2.MORPH_CLOSE, self.kernel)

        fg_mask = self.background_subtractor.apply(gray, learningRate=config.MOG_LEARNING_RATE)
        fg_mask = cv2.GaussianBlur(fg_mask, config.BLUR_SIZE, 0)
        _, thresh = cv2.threshold(fg_mask, config.THRESHOLD_VALUE, 255, cv2.THRESH_BINARY)

        motion_mask = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, self.kernel)
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_OPEN, self.kernel)

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

            bbox_mask = target_mask[y : y + h, x : x + w]
            target_pixels = cv2.countNonZero(bbox_mask)
            bbox_area = max(w * h, 1)
            target_ratio = target_pixels / float(bbox_area)
            if target_pixels < config.MIN_TARGET_PIXELS or target_ratio < config.MIN_TARGET_RATIO:
                continue

            motion_roi = motion_mask[y : y + h, x : x + w]
            motion_pixels = cv2.countNonZero(motion_roi)
            motion_ratio = motion_pixels / float(bbox_area)

            cx = x + w / 2.0
            cy = y + h / 2.0
            if cy < search_top or cy > search_bottom:
                continue
            if x <= config.EDGE_IGNORE_PX or (x + w) >= (frame_width - config.EDGE_IGNORE_PX):
                continue

            center_bias = 1.0 - abs(cx - (frame_width / 2.0)) / max(frame_width / 2.0, 1.0)
            upper_bias = 1.0 - ((cy - search_top) / max(search_bottom - search_top, 1.0))
            score = (
                area
                + (250.0 * center_bias)
                + (150.0 * upper_bias)
                + (target_ratio * 500.0)
                + (motion_ratio * 350.0)
            )
            candidates.append((cnt, score, (x, y, w, h)))

        candidates.sort(key=lambda item: item[1], reverse=True)
        candidates = candidates[: config.MAX_CANDIDATES]

        if not candidates:
            return target_mask, motion_mask, []

        return target_mask, motion_mask, [(cnt, bbox) for cnt, _, bbox in candidates]
