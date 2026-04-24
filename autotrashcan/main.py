import os
import time
import cv2

import config
from camera import create_capture, read_frame, release_capture
from control_interface import (
    STOP,
    compute_approach_command,
    compute_overhead_command,
    send_motor_command,
)
from detection import create_detector


def draw_status(frame, text, fps):
    cv2.putText(frame, f"Status: {text}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)


def draw_tracking(frame, current_bbox, predicted_point):
    if current_bbox is not None:
        x, y, w, h = current_bbox
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 128, 255), 2)

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

    if config.CAMERA_FACING_UP:
        frame_center = (config.FRAME_WIDTH // 2, config.FRAME_HEIGHT // 2)
        cv2.circle(frame, frame_center, config.OVERHEAD_CENTER_RADIUS_PX, (255, 255, 255), 1)
        cv2.drawMarker(frame, frame_center, (255, 255, 255), cv2.MARKER_CROSS, 18, 1)


def main():
    cap = create_capture()
    detector = create_detector()
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
        f"window={'on' if window_enabled else 'off'}, motor_mock={config.MOTOR_MOCK}"
    )

    last_time = time.time()
    fps = 0.0
    frame_count = 0
    last_command = STOP
    last_offset = 0
    last_turn_strength = 0.0
    last_command_sent_time = 0.0
    try:
        while True:
            frame = read_frame(cap)
            if frame is None:
                print("Warning: empty frame from camera")
                continue

            motion_mask, thresh_mask, candidates = detector.detect(frame)
            current_bbox = candidates[0][1] if candidates else None

            aim_point = None
            command = STOP
            offset = 0
            turn_strength = 0.0
            state = "DETECTED" if current_bbox is not None else "SEARCHING"

            if current_bbox is not None:
                x, y, w, h = current_bbox
                target_center = (int(x + w / 2), int(y + h / 2))
                aim_point = target_center

                if config.CAMERA_FACING_UP:
                    command, offset, turn_strength = compute_overhead_command(
                        target_center,
                        config.FRAME_WIDTH,
                        config.FRAME_HEIGHT,
                    )
                else:
                    command, offset, turn_strength = compute_approach_command(
                        current_bbox,
                        config.FRAME_WIDTH,
                        config.FRAME_HEIGHT,
                    )

            now = time.time()

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

            frame_count += 1
            if now - last_time >= 1.0:
                fps = frame_count / (now - last_time)
                frame_count = 0
                last_time = now

            if now - last_status_print >= config.STATUS_PRINT_INTERVAL:
                print(
                    f"[STATUS] state={state} fps={fps:.1f} "
                    f"candidates={len(candidates)} "
                    f"detected={current_bbox is not None} command={command} strength={turn_strength:.2f}"
                )
                last_status_print = now

            if config.DEBUG_DRAW:
                draw_tracking(frame, current_bbox, aim_point)
                draw_status(frame, state, fps)
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
        release_capture(cap)
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
