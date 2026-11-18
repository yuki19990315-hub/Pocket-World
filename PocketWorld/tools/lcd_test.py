"""Run with mpremote after installing round_lcd.py."""

from time import sleep_ms
from machine import Pin
from round_lcd import RoundLCD, rgb

lcd = RoundLCD()
canvas = lcd.canvas
lcd.backlight.on()
for color in (rgb(255, 0, 0), rgb(0, 255, 0), rgb(0, 0, 255)):
    canvas.fill(color)
    lcd.show()
    sleep_ms(700)

white = rgb(255, 255, 255)
canvas.fill(0)
canvas.ellipse(120, 120, 104, 104, white)
canvas.rect(70, 72, 100, 54, rgb(0, 218, 210), True)
canvas.line(60, 159, 178, 183, rgb(255, 180, 32))
canvas.text("SANNY LCD", 84, 95, 0)
canvas.text("240 x 240", 84, 137, white)
lcd.show()
print("LCD_TEST sent RGB fills, circle, rectangle, line and text")

# Read back GC9A01A settings over the board's LCD_MISO line at a low SPI rate.
lcd.spi.init(baudrate=1000000, miso=Pin(12))
for register, expected in ((0x0B, 0x40), (0x0C, 0x05)):
    lcd.cs.off()
    try:
        lcd.dc.off()
        lcd.spi.write(bytes((register,)))
        lcd.dc.on()
        value = lcd.spi.read(3)[0]
    finally:
        lcd.cs.on()
    if value != expected:
        raise OSError("LCD register 0x%02X returned 0x%02X" % (register, value))
print("LCD_TEST controller readback passed (orientation and RGB565)")
