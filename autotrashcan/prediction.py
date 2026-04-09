import math
import numpy as np
import config


def estimate_velocity(points, fps):
    if len(points) < 2 or fps <= 0:
        return 0.0, 0.0

    n = min(len(points), config.MIN_TRACK_POINTS)
    p1 = np.array(points[-n])
    p2 = np.array(points[-1])

    dt = float(n - 1) / float(fps)
    if dt <= 0:
        return 0.0, 0.0

    vx = (p2[0] - p1[0]) / dt
    vy = (p2[1] - p1[1]) / dt
    return vx, vy


def predict_landing_point(points, frame_height, frame_width, fps):
    if len(points) < config.MIN_TRACK_POINTS:
        return None

    current = np.array(points[-1], dtype=np.float32)
    vx, vy = estimate_velocity(points, fps)

    if abs(vx) < 1e-2 and abs(vy) < 1e-2:
        return tuple(current.astype(int))

    y_ground = frame_height * config.GROUND_LINE_RATIO
    y0 = current[1]
    c = y0 - y_ground

    a = 0.5 * config.GRAVITY_PX_PER_S2
    b = vy

    discriminant = b * b - 4.0 * a * c
    t_hit = None

    if discriminant >= 0 and abs(a) > 1e-6:
        root = math.sqrt(discriminant)
        t1 = (-b + root) / (2.0 * a)
        t2 = (-b - root) / (2.0 * a)
        valid = [t for t in (t1, t2) if t >= 0]
        if valid:
            t_hit = min(valid)

    if t_hit is None:
        t_hit = config.MIN_PREDICT_TIME

    t_hit = max(min(t_hit, config.MAX_PREDICT_TIME), config.MIN_PREDICT_TIME)

    x_pred = current[0] + vx * t_hit
    y_pred = y_ground

    x_pred = max(0, min(frame_width - 1, int(round(x_pred))))
    y_pred = max(0, min(frame_height - 1, int(round(y_pred))))

    return (x_pred, y_pred)
