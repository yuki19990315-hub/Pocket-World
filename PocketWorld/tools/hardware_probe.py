"""Sanny ESP32-S3 USB first-contact probe (MicroPython only).

Run from PC with `python -m mpremote connect COMx run hardware_probe.py`.
This script NEVER erases firmware or writes to the device filesystem.
It reads the built-in QMI8658 / touch I2C address list, battery ADC raw
value, and MicroPython build information. It does not drive the LCD or mic.

Note: mpremote itself may interrupt a running main.py and soft-reset the VM.
"""

import gc
import os
import sys


print("=== SANNY HARDWARE PROBE 1 ===")
print("Script: no flash writes, no firmware upload")
print("Python:", sys.version)
try:
    print("Platform:", os.uname())
except Exception as error:
    print("Platform read failed:", type(error).__name__, str(error))

try:
    import machine
    print("Reset cause:", machine.reset_cause())
    print("I2S API available:", hasattr(machine, "I2S"))
except Exception as error:
    machine = None
    print("Machine API unavailable:", type(error).__name__, str(error))

if machine is not None:
    try:
        bus = machine.I2C(0, sda=machine.Pin(6), scl=machine.Pin(7), freq=100000)
        addresses = bus.scan()
        print("I2C found:", ["0x%02X" % addr for addr in addresses])
        print("QMI8658 IMU (usually 0x6A/0x6B):", 0x6A in addresses or 0x6B in addresses)
        print("CST816 touch (usually 0x15):", 0x15 in addresses)
        # Do not send reset, wake, or configuration commands to any chip.
    except Exception as error:
        print("I2C error:", type(error).__name__, str(error))
    try:
        battery_adc = machine.ADC(machine.Pin(1))
        if hasattr(battery_adc, "atten") and hasattr(machine.ADC, "ATTN_11DB"):
            battery_adc.atten(machine.ADC.ATTN_11DB)
        if hasattr(battery_adc, "read"):
            raw = battery_adc.read()
        else:
            raw = battery_adc.read_u16()
        print("Battery ADC raw (NOT a percentage):", raw)
    except Exception as error:
        print("Battery ADC error:", type(error).__name__, str(error))

try:
    gc.collect()
    print("Free RAM bytes:", gc.mem_free())
except Exception:
    pass
print("=== END PROBE ===")
