# Third-party implementation references

`round_screen.py` contains a re-expressed initialization command sequence for
the GC9A01A controller, adapted from Adafruit's `Adafruit_GC9A01A.cpp`.

- Source: https://github.com/adafruit/Adafruit_GC9A01A/blob/main/Adafruit_GC9A01A.cpp
- Copyright (c) Adafruit Industries and contributors.
- License: BSD 3-Clause (see the upstream repository for the complete license).

The SPI streaming layer, image blender, touch handling and battery gauge are
Pocket World code. The pin mapping follows the Waveshare board documentation:
https://docs.waveshare.com/ESP32-S3-Touch-LCD-1.28

The illustrated Pocket World backgrounds under `design/assets` were created
for this project using an image generation tool and prepared as 240×240 assets.
