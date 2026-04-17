from collections import deque
from enum import Enum
import config


class TrackState(Enum):
    SEARCHING = 1
    TRACKING = 2
    LOST = 3


class ObjectTracker:
    def __init__(self):
        self.centers = deque(maxlen=config.TRACK_HISTORY)
        self.bboxes = deque(maxlen=config.TRACK_HISTORY)
        self.state = TrackState.SEARCHING
        self.lost_frames = 0
        self.locked_frames = 0
        self.reacquire_cooldown = 0
        self.candidate_count = 0

    def update(self, bbox):
        if self.reacquire_cooldown > 0:
            self.reacquire_cooldown -= 1

        if bbox is None:
            self.lost_frames += 1
            if self.lost_frames >= config.TRACK_LOST_MAX_FRAMES:
                if self.state != TrackState.LOST:
                    self.state = TrackState.LOST
                    self.centers.clear()
                    self.bboxes.clear()
                    self.locked_frames = 0
                    self.reacquire_cooldown = config.TARGET_REACQUIRE_COOLDOWN_FRAMES
            else:
                self.state = TrackState.SEARCHING if not self.centers else TrackState.TRACKING
            return

        x, y, w, h = bbox
        center = (int(x + w / 2), int(y + h / 2))
        self.centers.append(center)
        self.bboxes.append(bbox)
        self.lost_frames = 0
        self.locked_frames += 1
        self.state = TrackState.TRACKING

    def select_best_candidate(self, candidates):
        self.candidate_count = len(candidates)

        if not candidates:
            return None

        if self.reacquire_cooldown > 0 and not self.centers:
            return None

        last_center = self.get_center()
        predicted_center = self.predict_next_center()
        last_bbox = self.get_last_bbox()
        last_area = None
        if last_bbox is not None:
            _, _, last_w, last_h = last_bbox
            last_area = max(last_w * last_h, 1)
        best_bbox = None
        best_score = None
        fallback_bbox = None
        fallback_score = None

        for _, bbox in candidates:
            x, y, w, h = bbox
            center = (int(x + w / 2), int(y + h / 2))
            area = w * h
            base_score = area - (y * 2)

            if fallback_score is None or base_score > fallback_score:
                fallback_score = base_score
                fallback_bbox = bbox

            if last_center is None:
                score = base_score
            else:
                anchor = predicted_center if predicted_center is not None else last_center
                dx = center[0] - anchor[0]
                dy = center[1] - anchor[1]
                distance_sq = dx * dx + dy * dy
                if distance_sq > (config.MAX_TRACK_JUMP_PX * config.MAX_TRACK_JUMP_PX):
                    continue
                lock_bonus = config.TARGET_LOCK_BONUS if self.is_locked() else (config.TARGET_LOCK_BONUS * 0.3)
                score = area + lock_bonus - distance_sq

                if last_area is not None:
                    area_ratio = max(area, last_area) / float(min(area, last_area))
                    if area_ratio > config.TARGET_AREA_CHANGE_MAX_RATIO:
                        continue
                    score -= (area_ratio - 1.0) * config.TARGET_AREA_CHANGE_PENALTY

            if best_score is None or score > best_score:
                best_score = score
                best_bbox = bbox

        if best_bbox is None:
            return fallback_bbox

        return best_bbox

    def predict_next_center(self):
        if len(self.centers) < 2:
            return self.get_center()

        x1, y1 = self.centers[-2]
        x2, y2 = self.centers[-1]
        return (x2 + (x2 - x1), y2 + (y2 - y1))

    def get_motion_vector(self):
        if len(self.centers) < 2:
            return 0, 0

        x1, y1 = self.centers[-2]
        x2, y2 = self.centers[-1]
        return x2 - x1, y2 - y1

    def is_target_stable(self):
        if len(self.centers) < config.MIN_TRACK_POINTS or len(self.bboxes) < config.MIN_TRACK_POINTS:
            return False

        recent_centers = list(self.centers)[-config.MIN_TRACK_POINTS :]
        recent_bboxes = list(self.bboxes)[-config.MIN_TRACK_POINTS :]

        max_step = 0.0
        for idx in range(1, len(recent_centers)):
            x1, y1 = recent_centers[idx - 1]
            x2, y2 = recent_centers[idx]
            step = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            max_step = max(max_step, step)

        areas = [w * h for _, _, w, h in recent_bboxes]
        min_area = max(min(areas), 1)
        max_area = max(areas)
        area_ratio = max_area / float(min_area)

        return (
            self.is_locked()
            and max_step <= config.TARGET_STABLE_MAX_STEP_PX
            and area_ratio <= config.TARGET_STABLE_MAX_AREA_RATIO
        )

    def is_locked(self):
        return self.locked_frames >= config.TARGET_MIN_LOCK_FRAMES

    def get_state(self):
        if self.state == TrackState.TRACKING and len(self.centers) < 2:
            return TrackState.SEARCHING
        return self.state

    def get_center(self):
        return self.centers[-1] if self.centers else None

    def get_path(self):
        return list(self.centers)

    def get_last_bbox(self):
        return self.bboxes[-1] if self.bboxes else None

    def is_tracking(self):
        return self.get_state() == TrackState.TRACKING

    def reset(self):
        self.centers.clear()
        self.bboxes.clear()
        self.state = TrackState.SEARCHING
        self.lost_frames = 0
        self.locked_frames = 0
        self.reacquire_cooldown = 0
        self.candidate_count = 0
