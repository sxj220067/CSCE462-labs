import os
import time
import json
from pathlib import Path
import cv2

import config
from camera import create_capture, read_frame, release_capture
from control_interface import (
    STOP,
    compute_path_command,
    is_within_overhead_stop_zone,
    plan_path_to_target,
    send_motor_command,
)
from detection import create_detector
from prediction import is_descending, predict_landing_point
from tracking import ObjectTracker, TrackState


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def load_learning_state():
    if not config.SELF_LEARNING_ENABLED:
        return 0.0, 0.0

    path = Path(config.SELF_LEARNING_SAVE_PATH)
    if not path.exists():
        return 0.0, 0.0

    try:
        data = json.loads(path.read_text())
    except Exception:
        return 0.0, 0.0

    learned_x_bias = clamp(
        float(data.get("x_bias", 0.0)),
        -config.SELF_LEARNING_MAX_X_BIAS_PX,
        config.SELF_LEARNING_MAX_X_BIAS_PX,
    )
    learned_y_bias = clamp(
        float(data.get("y_bias", 0.0)),
        -config.SELF_LEARNING_MAX_Y_BIAS_PX,
        config.SELF_LEARNING_MAX_Y_BIAS_PX,
    )
    return learned_x_bias, learned_y_bias


def save_learning_state(learned_x_bias, learned_y_bias):
    if not config.SELF_LEARNING_ENABLED:
        return

    path = Path(config.SELF_LEARNING_SAVE_PATH)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "x_bias": round(learned_x_bias, 3),
                    "y_bias": round(learned_y_bias, 3),
                },
                indent=2,
            )
        )
    except Exception:
        pass


def apply_learning_bias(target_point, frame_width, frame_height, learned_x_bias, learned_y_bias):
    if target_point is None:
        return None

    adjusted_x = int(round(target_point[0] + learned_x_bias))
    adjusted_y = int(round(target_point[1] + learned_y_bias))
    adjusted_x = clamp(adjusted_x, 0, frame_width - 1)
    adjusted_y = clamp(adjusted_y, 0, frame_height - 1)
    return adjusted_x, adjusted_y


def update_learning_bias(learned_x_bias, learned_y_bias, target_center):
    center_x = config.FRAME_WIDTH // 2
    center_y = config.FRAME_HEIGHT // 2
    dx = float(target_center[0] - center_x)
    dy = float(target_center[1] - center_y)
    stop_dy = dy - float(config.OVERHEAD_STOP_Y_OFFSET_PX)

    if abs(dx) >= config.SELF_LEARNING_MIN_ERROR_PX:
        learned_x_bias = clamp(
            learned_x_bias + (dx * config.SELF_LEARNING_RATE),
            -config.SELF_LEARNING_MAX_X_BIAS_PX,
            config.SELF_LEARNING_MAX_X_BIAS_PX,
        )
    else:
        learned_x_bias *= 0.98

    if abs(stop_dy) >= config.SELF_LEARNING_MIN_ERROR_PX:
        learned_y_bias = clamp(
            learned_y_bias + (stop_dy * config.SELF_LEARNING_RATE),
            -config.SELF_LEARNING_MAX_Y_BIAS_PX,
            config.SELF_LEARNING_MAX_Y_BIAS_PX,
        )
    else:
        learned_y_bias *= 0.98

    return learned_x_bias, learned_y_bias


def draw_status(frame, text, fps):
    cv2.putText(frame, f"Status: {text}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)


def draw_tracking(frame, tracker, predicted_point, planned_path, target_verified):
    if tracker.get_last_bbox() is not None:
        x, y, w, h = tracker.get_last_bbox()
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 128, 255), 2)

    path = tracker.get_path()
    for pt in path:
        cv2.circle(frame, pt, 3, (0, 255, 255), -1)

    if predicted_point is not None:
        cv2.circle(frame, predicted_point, 8, (0, 0, 255), 2)
        cv2.putText(
            frame,
            "Aim",
            (predicted_point[0] + 8, predicted_point[1] - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2,
        )

    if planned_path:
        for idx in range(len(planned_path) - 1):
            cv2.line(frame, planned_path[idx], planned_path[idx + 1], (255, 0, 255), 2)
        for point in planned_path:
            cv2.circle(frame, point, 4, (255, 0, 255), -1)

    verification_color = (0, 200, 0) if target_verified else (0, 165, 255)
    verification_text = "Target checked" if target_verified else "Checking target"
    cv2.putText(frame, verification_text, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, verification_color, 2)

    if config.CAMERA_FACING_UP:
        frame_center = (config.FRAME_WIDTH // 2, config.FRAME_HEIGHT // 2)
        cv2.circle(frame, frame_center, config.OVERHEAD_CENTER_RADIUS_PX, (255, 255, 255), 1)
        cv2.drawMarker(frame, frame_center, (255, 255, 255), cv2.MARKER_CROSS, 18, 1)


def main():
    cap = create_capture()
    detector = create_detector()
    tracker = ObjectTracker()
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    window_enabled = config.SHOW_WINDOW and has_display
    last_status_print = time.time()

    if config.SHOW_WINDOW and not has_display:
        print(
            "No graphical display detected. Continuing without a preview window. "
            "Set SHOW_WINDOW = False in config.py to suppress this message."
        )

    print(
        f"AutoTrashCan starting: backend={config.CAMERA_BACKEND}, "
        f"window={'on' if window_enabled else 'off'}, motor_mock={config.MOTOR_MOCK}, "
        f"detector_mode={config.DETECTOR_MODE}"
    )

    last_time = time.time()
    fps = 0.0
    frame_count = 0
    last_command = STOP
    last_offset = 0
    last_turn_strength = 0.0
    last_command_sent_time = 0.0
    target_hold_until = 0.0
    learned_x_bias, learned_y_bias = load_learning_state()
    last_learning_update = 0.0
    last_learning_save = time.time()
    try:
        while True:
            frame = read_frame(cap)
            if frame is None:
                print("Warning: empty frame from camera")
                continue

            motion_mask, thresh_mask, candidates = detector.detect(frame)
            state = tracker.get_state()

            current_bbox = None
            if candidates:
                current_bbox = tracker.select_best_candidate(candidates)
                tracker.update(current_bbox)
                state = tracker.get_state()
            else:
                tracker.update(None)
                state = tracker.get_state()

            aim_point = None
            planned_path = []
            command = STOP
            offset = 0
            turn_strength = 0.0
            target_verified = tracker.is_target_stable()

            if current_bbox is not None:
                x, y, w, h = current_bbox
                target_center = (int(x + w / 2), int(y + h / 2))
                biased_target_center = apply_learning_bias(
                    target_center,
                    config.FRAME_WIDTH,
                    config.FRAME_HEIGHT,
                    learned_x_bias,
                    learned_y_bias,
                )
                aim_point = biased_target_center
                predicted_point = None

                if config.CAMERA_FACING_UP and is_within_overhead_stop_zone(
                    biased_target_center,
                    config.FRAME_WIDTH,
                    config.FRAME_HEIGHT,
                ):
                    planned_path = plan_path_to_target(
                        biased_target_center,
                        config.FRAME_WIDTH,
                        config.FRAME_HEIGHT,
                    )
                    command = STOP
                elif config.USE_PREDICTION and len(tracker.get_path()) >= config.MIN_TRACK_POINTS:
                    if not config.REQUIRE_DESCENDING_FOR_CHASE or is_descending(tracker.get_path(), fps):
                        predicted_point = predict_landing_point(
                            tracker.get_path(),
                            config.FRAME_HEIGHT,
                            config.FRAME_WIDTH,
                            fps,
                        )

                if predicted_point is not None:
                    aim_point = apply_learning_bias(
                        predicted_point,
                        config.FRAME_WIDTH,
                        config.FRAME_HEIGHT,
                        learned_x_bias,
                        learned_y_bias,
                    )
                    planned_path = plan_path_to_target(aim_point, config.FRAME_WIDTH, config.FRAME_HEIGHT)
                    command, offset, turn_strength = compute_path_command(
                        planned_path,
                        config.FRAME_WIDTH,
                        config.FRAME_HEIGHT,
                        target_bbox=current_bbox,
                    )
                elif command != STOP:
                    command = STOP
            else:
                command = STOP

            now = time.time()

            if (
                config.SELF_LEARNING_ENABLED
                and current_bbox is not None
                and target_verified
                and command == STOP
                and (now - last_learning_update) >= config.SELF_LEARNING_UPDATE_INTERVAL_S
            ):
                learned_x_bias, learned_y_bias = update_learning_bias(
                    learned_x_bias,
                    learned_y_bias,
                    target_center,
                )
                last_learning_update = now

            if command == STOP and current_bbox is not None and planned_path:
                if target_hold_until <= now:
                    target_hold_until = now + config.OVERHEAD_TARGET_HOLD_S

            if now < target_hold_until:
                command = STOP
                offset = 0
                turn_strength = 0.0
            elif current_bbox is None:
                target_hold_until = 0.0

            should_send_command = (
                command != last_command
                or abs(offset - last_offset) > config.CENTER_DEADZONE_PX
                or abs(turn_strength - last_turn_strength) >= 0.1
                or (now - last_command_sent_time) >= config.COMMAND_UPDATE_INTERVAL_S
            )

            if should_send_command:
                send_motor_command(command, offset, turn_strength)
                last_command = command
                last_offset = offset
                last_turn_strength = turn_strength
                last_command_sent_time = now

            if config.SELF_LEARNING_ENABLED and (now - last_learning_save) >= 1.0:
                save_learning_state(learned_x_bias, learned_y_bias)
                last_learning_save = now

            frame_count += 1
            if now - last_time >= 1.0:
                fps = frame_count / (now - last_time)
                frame_count = 0
                last_time = now

            if now - last_status_print >= config.STATUS_PRINT_INTERVAL:
                print(
                    f"[STATUS] state={state.name} fps={fps:.1f} "
                    f"candidates={tracker.candidate_count} tracked_points={len(tracker.get_path())} "
                    f"locked={tracker.is_locked()} cooldown={tracker.reacquire_cooldown} "
                    f"stable={target_verified} command={command} strength={turn_strength:.2f} "
                    f"learn_bias=({learned_x_bias:.1f},{learned_y_bias:.1f})"
                )
                last_status_print = now

            if config.DEBUG_DRAW:
                draw_tracking(frame, tracker, aim_point, planned_path, target_verified)
                draw_status(frame, state.name, fps)
                cv2.line(
                    frame,
                    (config.FRAME_WIDTH // 2, 0),
                    (config.FRAME_WIDTH // 2, config.FRAME_HEIGHT),
                    (0, 255, 0),
                    1,
                )
                if config.CAMERA_FACING_UP:
                    cv2.line(
                        frame,
                        (0, config.FRAME_HEIGHT // 2),
                        (config.FRAME_WIDTH, config.FRAME_HEIGHT // 2),
                        (0, 255, 0),
                        1,
                    )
                else:
                    cv2.line(
                        frame,
                        (0, int(config.FRAME_HEIGHT * config.TARGET_CLOSE_Y_RATIO)),
                        (config.FRAME_WIDTH, int(config.FRAME_HEIGHT * config.TARGET_CLOSE_Y_RATIO)),
                        (0, 255, 0),
                        1,
                    )

            if window_enabled:
                try:
                    cv2.imshow(config.WINDOW_NAME, frame)
                except cv2.error:
                    window_enabled = False
                    print(
                        "OpenCV display is unavailable. Continuing without a preview window. "
                        "Set SHOW_WINDOW = False in config.py to suppress this message."
                    )

            key = cv2.waitKey(1) & 0xFF if window_enabled else -1
            if key == ord('q') or key == 27:
                break

    except KeyboardInterrupt:
        print("Interrupted by user")

    finally:
        save_learning_state(learned_x_bias, learned_y_bias)
        release_capture(cap)
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
