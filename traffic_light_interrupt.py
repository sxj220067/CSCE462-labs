# traffic_light_interrupt.py
import time
import threading
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
    "dp": 12,   # optional, not used
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
COOLDOWN = 20
# state
press_event = threading.Event()
state_lock = threading.Lock()
last_valid_press_time = 0.0
sequence_running = False


# GPIO SETUP 
def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # RGB outputs
    for pin in (L1_R, L1_G, L1_B, L2_R, L2_G, L2_B):
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

    # 7-seg outputs
    for pin in SEG_PINS.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

    # Button input with pulldown 
    GPIO.setup(BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)


# HELPERS
def set_rgb(r_pin, g_pin, b_pin, color: str):
    """Common cathode RGB: HIGH turns the selected color on."""
    GPIO.output(r_pin, GPIO.LOW)
    GPIO.output(g_pin, GPIO.LOW)
    GPIO.output(b_pin, GPIO.LOW)

    if color == "red":
        GPIO.output(r_pin, GPIO.HIGH)
    elif color == "green":
        GPIO.output(g_pin, GPIO.HIGH)
    elif color == "blue":
        GPIO.output(b_pin, GPIO.HIGH)
    elif color == "off":
        pass 
    else:
        pass


def clear_7seg():
    for pin in SEG_PINS.values():
        GPIO.output(pin, GPIO.LOW)


def show_digit(d: int):
    clear_7seg()
    for seg in DIGITS.get(d, []):
        GPIO.output(SEG_PINS[seg], GPIO.HIGH)


def blink_light2_blue(times: int = 3, on_time: float = 0.25, off_time: float = 0.25):
    for _ in range(times):
        set_rgb(L2_R, L2_G, L2_B, "blue")
        time.sleep(on_time)
        set_rgb(L2_R, L2_G, L2_B, "off")
        time.sleep(off_time)
    set_rgb(L2_R, L2_G, L2_B, "red")


def run_countdown_l1():

    set_rgb(L1_R, L1_G, L1_B, "green")

    for n in range(9, -1, -1):
        show_digit(n)

        if n > 4:
            set_rgb(L1_R, L1_G, L1_B, "green")
            time.sleep(1.0)
        else:
            start = time.monotonic()
            duration = 1.0
            flash = 0.2
            while time.monotonic() - start < duration:
                set_rgb(L1_R, L1_G, L1_B, "blue")
                time.sleep(flash)
                set_rgb(L1_R, L1_G, L1_B, "off")
                time.sleep(flash)

    clear_7seg()
    set_rgb(L1_R, L1_G, L1_B, "red")
    set_rgb(L2_R, L2_G, L2_B, "green")


def run_sequence():
    blink_light2_blue(times=3, on_time=0.25, off_time=0.25)
    run_countdown_l1()


# INTERRUPT CALLBACK 
def button_callback(channel):
    """
    Interrupt handler for BUTTON press.
    Keep it FAST:
      - enforce cooldown
      - avoid re-entrancy
      - signal main loop to run the sequence
    """
    global last_valid_press_time, sequence_running

    now = time.time()
    with state_lock:
        if sequence_running:
            return
        if now - last_valid_press_time < COOLDOWN:
            return

        last_valid_press_time = now
        sequence_running = True
        press_event.set()



def main():
    global sequence_running

    setup_gpio()

    # default state
    set_rgb(L1_R, L1_G, L1_B, "red")
    set_rgb(L2_R, L2_G, L2_B, "green")
    clear_7seg()

    # Interrupt on RISING edge because pull-down 
    GPIO.add_event_detect(BUTTON, GPIO.RISING, callback=button_callback, bouncetime=200)

    try:
        while True:
            press_event.wait()
            press_event.clear()
            
            run_sequence()

            with state_lock:
                sequence_running = False

    finally:
        clear_7seg()
        set_rgb(L1_R, L1_G, L1_B, "off")
        set_rgb(L2_R, L2_G, L2_B, "off")
        GPIO.cleanup()


if __name__ == "__main__":
    main()