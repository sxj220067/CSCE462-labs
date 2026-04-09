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
