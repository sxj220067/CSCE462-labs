import cv2
import numpy as np

import config


def _kernel():
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, config.MORPH_KERNEL)


def _mask_from_ranges(hsv_frame, ranges):
    mask = None
    for lower, upper in ranges:
        next_mask = cv2.inRange(hsv_frame, np.array(lower, dtype=np.uint8), np.array(upper, dtype=np.uint8))
        mask = next_mask if mask is None else cv2.bitwise_or(mask, next_mask)
    if mask is None:
        height, width = hsv_frame.shape[:2]
        return np.zeros((height, width), dtype=np.uint8)
    mask = cv2.GaussianBlur(mask, config.BLUR_SIZE, 0)
    _, mask = cv2.threshold(mask, 80, 255, cv2.THRESH_BINARY)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, _kernel())
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, _kernel())
    mask = cv2.dilate(mask, _kernel(), iterations=config.MARKER_DILATE_ITERATIONS)
    return mask


def _find_largest_blob(mask, min_area, max_area):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_area = None
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        center = (int(x + (w / 2)), int(y + (h / 2)))
        if best_area is None or area > best_area:
            best_area = area
            best = {
                "bbox": (x, y, w, h),
                "center": center,
                "area": area,
                "contour": contour,
            }
    return best


def _find_target_candidates(mask):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < config.MIN_TARGET_AREA or area > config.MAX_TARGET_AREA:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        center = (int(x + (w / 2)), int(y + (h / 2)))
        candidates.append(
            {
                "bbox": (x, y, w, h),
                "center": center,
                "area": area,
                "contour": contour,
            }
        )
    candidates.sort(key=lambda item: item["area"], reverse=True)
    return candidates


def _find_obstacle_candidates(mask):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < config.MIN_OBSTACLE_AREA or area > config.MAX_OBSTACLE_AREA:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        candidates.append(
            {
                "bbox": (x, y, w, h),
                "center": (int(x + (w / 2)), int(y + (h / 2))),
                "area": area,
                "radius": max(w, h) / 2,
                "contour": contour,
            }
        )
    candidates.sort(key=lambda item: item["area"], reverse=True)
    return candidates


class WallCameraDetector:
    def detect(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        front_mask = _mask_from_ranges(hsv, config.FRONT_MARKER_HSV_RANGES)
        back_mask = _mask_from_ranges(hsv, config.BACK_MARKER_HSV_RANGES)
        target_mask = _mask_from_ranges(hsv, config.TARGET_HSV_RANGES)
        obstacle_mask = _mask_from_ranges(hsv, config.OBSTACLE_HSV_RANGES)

        front_marker = _find_largest_blob(front_mask, config.MIN_MARKER_AREA, config.MAX_MARKER_AREA)
        back_marker = _find_largest_blob(back_mask, config.MIN_MARKER_AREA, config.MAX_MARKER_AREA)
        target_candidates = _find_target_candidates(target_mask)
        obstacle_candidates = _find_obstacle_candidates(obstacle_mask)

        can_state = None
        if front_marker is not None and back_marker is not None:
            front_center = front_marker["center"]
            back_center = back_marker["center"]
            can_state = {
                "front": front_marker,
                "back": back_marker,
                "center": (
                    int((front_center[0] + back_center[0]) / 2),
                    int((front_center[1] + back_center[1]) / 2),
                ),
                "heading": (
                    front_center[0] - back_center[0],
                    front_center[1] - back_center[1],
                ),
            }

        return {
            "front_mask": front_mask,
            "back_mask": back_mask,
            "target_mask": target_mask,
            "obstacle_mask": obstacle_mask,
            "can_state": can_state,
            "target_candidates": target_candidates,
            "obstacle_candidates": obstacle_candidates,
        }


def create_detector():
    return WallCameraDetector()
