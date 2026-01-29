import time
import RPi.GPIO as GPIO

#Pin mapping (BCM numbering)
# Traffic Light RGB
L1_R , L1_G, L1_B = 17, 27, 22
L2_R, L2_G, L2_B = 23, 24, 25

# Button with pull-down resistor
BUTTON = 5

# 7-segment segments a,b,c,d,e,f,g,dp
SEG_PINS = {
    "a": 13,
    "b": 6,
    "c": 16,
    "d": 20,
    "e": 21,
    "f": 19,
    "g": 26,
    "dp": 12, 
}
DIGITS = {
    0: ["a","b","c","d","e","f"],
    1: ["b","c"],
    2: ["a","b","d","e","g"],
    3: ["a","b","c","d","g"],
    4: ["b","c","f","g"],
    5: ["a","c","d","f","g"],
    6: ["a","c","d","e","f","g"],
    7: ["a","b","c"],
    8: ["a","b","c","d","e","f","g"],
    9: ["a","b","c","d","f","g"],
}
COOLDOWN_SECONDS = 20
POLL_DELAY = 0.01
DEBOUNCE_SECONDS = 0.2

def setup_gpio():
    # set it as BCM numbering
    GPIO.setmode(GPIO.BCM)

    GPIO.setwarnings(False)

    # Light outputs setup 
    for pin in (L1_R, L1_G, L1_B, L2_R, L2_G, L2_B):
        GPIO.setup(pin,GPIO.OUT)
        GPIO.output(pin,GPIO.LOW)

    # 7 segments outputs setup
    for pin in SEG_PINS.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
    GPIO.setup(BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# sets color for light
def set_rgb(r_pin, g_pin, b_pin, color:str):
    GPIO.output(r_pin,GPIO.LOW)
    GPIO.output(g_pin,GPIO.LOW)
    GPIO.output(b_pin,GPIO.LOW)
    if color == "red":
        GPIO.output(r_pin,GPIO.HIGH)
    elif color == "green":
        GPIO.output(g_pin,GPIO.HIGH)
    elif color == "blue":
        GPIO.output(b_pin,GPIO.HIGH)
    elif color == "off":
        GPIO.output(r_pin,GPIO.LOW)
        GPIO.output(g_pin,GPIO.LOW)
        GPIO.output(b_pin,GPIO.LOW)
    else:
        pass

# turn off 7 seg
def clear_7seg():
    for pin in SEG_PINS.values():
        GPIO.output(pin,GPIO.LOW)

# show digit as int on 7 seg
def show_digit(d:int):
    clear_7seg()
    for num in DIGITS.get(d,[]):
        GPIO.output(SEG_PINS[num],GPIO.HIGH)

# 4b when the button is pressed, traffic light 2 turns 
# to blue, blinks 3 times, turns red
def blink_light2_blue(times: int = 3, on_time: float = 0.5, off_time: float = 0.5):
    for i in range(times):
        set_rgb(L2_R,L2_G,L2_B, "blue")
        time.sleep(on_time)
        set_rgb(L2_R,L2_G,L2_B, "off")
        time.sleep(off_time)
    set_rgb(L2_R,L2_G,L2_B, "red")

#4 c,d,e
def run_countdown_l1():
    
    set_rgb(L1_R,L1_G,L1_B, "green")

    for n in range (9, -1 ,-1):
        show_digit(n)

        start = time.monotonic()
        duration = 1.0
        off_time = 0.2
        if n > 4:
            # Hold green and the number for 1 second
            set_rgb(L1_R, L1_G, L1_B, "blue")
            time.sleep(duration)
        else:
            while time.monotonic() - start < duration:

                set_rgb(L1_R,L1_G,L1_B, "green")
                time.sleep(off_time)
                if time.monotonic() - start > duration:
                    break
                set_rgb(L1_R,L1_G,L1_B, "off")
                time.sleep(off_time)
        
    clear_7seg()
    set_rgb(L1_R,L1_G,L1_B, "red")
    set_rgb(L2_R,L2_G,L2_B, "green")


# make read_button_debounced
def read_button_pressed_debounce(last_press_time: float) -> bool:
    pressed = (GPIO.input(BUTTON) == GPIO.HIGH)
    if not pressed:
        return False

    now = time.time()
    if now - last_press_time < DEBOUNCE_SECONDS:
        return False

    return True
def main():
    setup_gpio()

    # (a) initial: TL2 green, TL1 red
    set_rgb(L1_R, L1_G, L1_B, "red")
    set_rgb(L2_R, L2_G, L2_B, "green")
    clear_7seg()

    last_debounce_time = 0.0
    last_valid_press_time = -1e9  # so first press is always allowed

    try:
        while True:
            # Keep TL2 green when idle (safe re-assert)
            # (doesn't hurt even if already green)
            # set_rgb(L2_R, L2_G, L2_B, "green")  # optional

            # detect press (debounced)
            if read_button_pressed_debounce(last_debounce_time):
                last_debounce_time = time.time()

                now = time.time()
                # (f) cooldown: only accept if 20 seconds passed
                if now - last_valid_press_time >= COOLDOWN_SECONDS:
                    last_valid_press_time = now

                    # (b) TL2 blue blink then red
                    blink_light2_blue(times=3, on_time=0.25, off_time=0.25)

                    # (c)(d)(e) TL1 countdown + flashing + restore
                    run_countdown_l1()

                # else: ignore press during cooldown

            time.sleep(POLL_DELAY)

    finally:
        clear_7seg()
        set_rgb(L1_R, L1_G, L1_B, "off")
        set_rgb(L2_R, L2_G, L2_B, "off")
        GPIO.cleanup()


if __name__ == "__main__":
    main()

    

    