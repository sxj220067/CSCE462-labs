from __future__ import annotations

import time

from config import (
    SPI_BUS, SPI_DEVICE, SPI_MAX_HZ, SPI_MODE,
    USE_GPIO_CS, GPIO_CS_PIN,
    LIGHT_CH, TEMP_CH,
    VREF, TEMP_F_MIN, TEMP_F_MAX, LIGHT_MIN, LIGHT_MAX
)
from mcp3008 import MCP3008, MCP3008Config


def scale_linear(v: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
    if in_max - in_min == 0:
        return out_min
    t = (v - in_min) / (in_max - in_min)
    return out_min + t * (out_max - out_min)


def main() -> None:
    adc = MCP3008(MCP3008Config(
        bus=SPI_BUS,
        device=SPI_DEVICE,
        max_hz=SPI_MAX_HZ,
        mode=SPI_MODE,
        use_gpio_cs=USE_GPIO_CS,
        gpio_cs_pin=GPIO_CS_PIN
    ))

    try:
        print("Reading sensors (Ctrl+C to stop)...")
        while True:
            light_v = adc.read_voltage(LIGHT_CH, vref=VREF)
            temp_v = adc.read_voltage(TEMP_CH, vref=VREF)

            # Lab-provided scales (0..3.3V -> 0..100, and 0..3.3V -> -50..280F)
            light = scale_linear(light_v, 0.0, VREF, LIGHT_MIN, LIGHT_MAX)
            temp_f = scale_linear(temp_v, 0.0, VREF, TEMP_F_MIN, TEMP_F_MAX)

            print(f"Light(CH{LIGHT_CH}): {light:6.1f} /100  ({light_v:0.3f} V) | "
                  f"Temp(CH{TEMP_CH}): {temp_f:7.1f} °F ({temp_v:0.3f} V)")
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        adc.close()


if __name__ == "__main__":
    main()
