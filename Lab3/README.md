Lab 3 Python Starter (MCP3008 + Sensors + Mini Oscilloscope)

Files
- mcp3008.py        : SPI driver for MCP3008 (supports HW CS or GPIO CS)
- sensors_demo.py   : Read light + temperature sensors on two channels
- oscilloscope.py   : Sample a waveform, classify (sine/triangle/square), estimate frequency
- wave_analysis.py  : Classification + frequency helpers (noise-tolerant)
- config.py         : One place to set SPI + channel + scaling options

Quick setup (Raspberry Pi OS)
1) Enable SPI: Raspberry Pi Configuration -> Interfaces -> SPI -> Enable
2) Install deps:
   sudo apt-get update
   sudo apt-get install -y python3-pip python3-rpi.gpio
   pip3 install spidev

Run
- Sensors:
  python3 sensors_demo.py
- Oscilloscope:
  python3 oscilloscope.py

Notes
- MCP3008 is 10-bit (0..1023). If VREF=3.3V, voltage = reading * 3.3 / 1023.
- If you wired MCP3008 CS to a GPIO pin (e.g., GPIO22), set USE_GPIO_CS=True in config.py.
