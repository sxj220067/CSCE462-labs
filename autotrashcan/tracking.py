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

    def update(self, bbox):
        if bbox is None:
            self.lost_frames += 1
            if self.lost_frames >= config.TRACK_LOST_MAX_FRAMES:
                self.state = TrackState.LOST
                self.centers.clear()
                self.bboxes.clear()
            else:
                self.state = TrackState.SEARCHING if not self.centers else TrackState.TRACKING
            return

        x, y, w, h = bbox
        center = (int(x + w / 2), int(y + h / 2))
        self.centers.append(center)
        self.bboxes.append(bbox)
        self.lost_frames = 0
        self.state = TrackState.TRACKING

    def select_best_candidate(self, candidates):
        if not candidates:
            return None

        last_center = self.get_center()
        best_bbox = None
        best_score = None

        for _, bbox in candidates:
            x, y, w, h = bbox
            center = (int(x + w / 2), int(y + h / 2))
            area = w * h

            if last_center is None:
                score = area - (y * 2)
            else:
                dx = center[0] - last_center[0]
                dy = center[1] - last_center[1]
                distance_sq = dx * dx + dy * dy
                if distance_sq > (config.MAX_TRACK_JUMP_PX * config.MAX_TRACK_JUMP_PX):
                    continue
                score = area + config.TARGET_LOCK_BONUS - distance_sq

            if best_score is None or score > best_score:
                best_score = score
                best_bbox = bbox

        return best_bbox

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
