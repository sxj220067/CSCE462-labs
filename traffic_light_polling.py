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
def set_rbg(r_pin, g_pin, b_pin, color:str):
    GPIO.output(r_pin,GPIO.LOW)
    GPIO.output(g_pin,GPIO.LOW)
    GPIO.output(b_pin,GPIO.LOW)
    if color == "red":
        GPIO.output(r_pin,GPIO.HIGH)
    elif color == "green":
        GPIO.output(g_pin,GPIO.HIGH)
    elif color == "blue":
        GPIO.output(b_pin,GPIO.HIGH)
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
        set_rbg(L2_R,L2_G,L2_B, "blue")
        set_rbg(L2_R,L2_G,L2_B, "off")
        time.sleep(off_time)
    set_rbg(L2_R,L2_G,L2_B, "red")

#4 c,d,e
def run_countdown_l1():
    
    set_rbg(L1_R,L1_G,L1_B, "green")

    for n in range (9, -1 ,-1):
        show_digit(n)

        start = time.monotonic()
        duration = 1.0
        off_time = 0.2
        if n <= 4:
            while time.monotonic() - start < duration:
            
                set_rbg(L1_R,L1_G,L1_B, "blue")
                time.sleep(off_time)
                if time.monotonic() - start > duration:
                    break
                set_rbg(L1_R,L1_G,L1_B, "off")
                time.sleep(off_time)
    clear_7seg()
    set_rbg(L1_R,L1_G,L1_B, "red")
    set_rbg(L2_R,L2_G,L2_B, "green")


# make read_button_debounced



def main():
    setup_gpio()

    #4a when button is not pressed traffic light 2 stays green
    set_rbg(L1_R, L1_G, L1_B, "red")
    set_rbg(L2_R, L2_G, L2_B, "green")
    clear_7seg()

    

    