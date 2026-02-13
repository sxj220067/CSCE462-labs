# Lab 3 configuration (edit this file first)

# -------------------------------
# SPI bus/device (hardware CE0/CE1)
# -------------------------------
SPI_BUS = 0
SPI_DEVICE = 0          # 0 = CE0, 1 = CE1
SPI_MAX_HZ = 1350000    # MCP3008 supports higher, but this is stable for many setups
SPI_MODE = 0

# -------------------------------
# Chip Select wiring
# -------------------------------
# If you wired MCP3008 CS to CE0/CE1, keep this False.
# If you wired MCP3008 CS to a GPIO pin (e.g., GPIO22 as in the lab handout),
# set this True and set GPIO_CS_PIN accordingly.
USE_GPIO_CS = True
GPIO_CS_PIN = 22        # BCM numbering

# -------------------------------
# Sensor channels
# -------------------------------
LIGHT_CH = 0            # MCP3008 CH0..CH7
TEMP_CH = 1             # MCP3008 CH0..CH7

# -------------------------------
# Scaling assumptions (from lab handout)
# -------------------------------
VREF = 3.3              # MCP3008 VREF (typically 3.3V in this lab)

# Temperature sensor mapping (lab says ~ -50°F..280°F corresponds to 0..3.3V)
TEMP_F_MIN = -50.0
TEMP_F_MAX = 280.0

# Light sensor display scale (lab says 0..100 corresponds to 0..3.3V)
LIGHT_MIN = 0.0
LIGHT_MAX = 100.0

# -------------------------------
# Oscilloscope sampling
# -------------------------------
SAMPLE_RATE_HZ = 2000   # samples per second (adjust based on your signal frequency)
SAMPLE_SECONDS = 0.5    # capture window length
WAVE_CH = 0             # channel used for waveform input (often CH0)
