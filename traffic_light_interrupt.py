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