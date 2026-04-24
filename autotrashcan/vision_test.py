import os
import time

import cv2

import config
from camera import create_capture, read_frame, release_capture
from detection import create_detector


def describe_position(bbox, frame_width, frame_height):
    if bbox is None:
        return "no target", "unknown"

    x, y, w, h = bbox
    center_x = int(x + (w / 2))
    center_y = int(y + (h / 2))
    area = w * h

    x_offset = center_x - (frame_width // 2)
    y_offset = center_y - (frame_height // 2)

    if config.CAMERA_FACING_UP:
        if x_offset < -config.OVERHEAD_AXIS_DEADZONE_PX:
            horizontal = "left"
        elif x_offset > config.OVERHEAD_AXIS_DEADZONE_PX:
            horizontal = "right"
        else:
            horizontal = "centered-x"

        if y_offset < -config.OVERHEAD_AXIS_DEADZONE_PX:
            vertical = "ahead"
        elif y_offset > config.OVERHEAD_AXIS_DEADZONE_PX:
            vertical = "behind"
        else:
            vertical = "centered-y"

        summary = (
            f"{horizontal}, {vertical}, "
            f"center=({center_x},{center_y}), offset=({x_offset},{y_offset}), area={area}"
        )
        return summary, horizontal

    stop_y = int(frame_height * config.TARGET_CLOSE_Y_RATIO)

    if x_offset < -config.TARGET_STOP_X_DEADZONE_PX:
        horizontal = "left"
    elif x_offset > config.TARGET_STOP_X_DEADZONE_PX:
        horizontal = "right"
    else:
        horizontal = "centered"

    if center_y < stop_y:
        vertical = "too far"
    else:
        vertical = "drop zone"

    summary = (
        f"{horizontal}, {vertical}, "
        f"center=({center_x},{center_y}), offset={x_offset}, area={area}"
    )
    return summary, horizontal


def main():
    cap = create_capture()
    detector = create_detector()
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    last_print = 0.0

    print("Vision test starting.")
    print("Show the target object to the camera.")
    print("Press q or Esc to quit.")

    try:
        while True:
            frame = read_frame(cap)
            if frame is None:
                continue

            motion_mask, target_mask, candidates = detector.detect(frame)
            bbox = candidates[0][1] if candidates else None
            status_text, horizontal = describe_position(bbox, config.FRAME_WIDTH, config.FRAME_HEIGHT)

            now = time.time()
            if now - last_print >= 0.5:
                print(f"[VISION] candidates={len(candidates)} status={status_text}")
                last_print = now

            if bbox is not None:
                x, y, w, h = bbox
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 128, 255), 2)
                cv2.circle(frame, (x + w // 2, y + h // 2), 5, (0, 0, 255), -1)
                cv2.putText(
                    frame,
                    status_text,
                    (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                )
            else:
                cv2.putText(
                    frame,
                    "No target detected",
                    (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2,
                )

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
                cv2.circle(
                    frame,
                    (config.FRAME_WIDTH // 2, config.FRAME_HEIGHT // 2),
                    config.OVERHEAD_CENTER_RADIUS_PX,
                    (255, 255, 255),
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

            if has_display and config.SHOW_WINDOW:
                cv2.imshow("AutoTrashCan Vision Test", frame)
                mask_bgr = cv2.cvtColor(target_mask, cv2.COLOR_GRAY2BGR)
                cv2.imshow("AutoTrashCan Target Mask", mask_bgr)
                motion_bgr = cv2.cvtColor(motion_mask, cv2.COLOR_GRAY2BGR)
                cv2.imshow("AutoTrashCan Motion Mask", motion_bgr)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    break
            else:
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    break

    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        release_capture(cap)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
