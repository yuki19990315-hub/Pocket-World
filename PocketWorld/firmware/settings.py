"""Edit these values before uploading the project to your ESP32-S3."""

# ESP32's own Wi-Fi. Your phone can connect even without office Wi-Fi.
AP_SSID = "SANNY-ESP32"
AP_PASSWORD = "replace-this-password"  # CHANGE before daily use (8+ chars).

# Used by the Sanny Companion Android app to authorize file updates.
# Change this to a long, unique secret. Updates are DISABLED until changed.
ADMIN_KEY = "CHANGE_ME_BEFORE_UPDATING"

# Optional: connect the board to a personally controlled Wi-Fi network.
# Do not join workplace Wi-Fi without the organization's permission.
STA_SSID = ""
STA_PASSWORD = ""

PORT = 80

# Hardware sleep requires USB access for recovery and real-world RTC testing.
# Keep disabled until the round-LCD/backlight driver and physical reset access
# have been checked. Time settings can be saved from the app in either case.
ENABLE_DEEP_SLEEP = False

# Read the on-board QMI8658 on GPIO6 SDA / GPIO7 SCL where available.
ENABLE_MOTION_SENSOR = True

# External INMP441 6-pin I2S microphone. Leave False until the mic is wired and
# the PCB's exposed pins have been verified against the actual board revision.
# GPIO15/16/17 are candidates from the Waveshare Rev3 schematic, not a physical
# wiring confirmation. L/R should be tied to GND for the left I2S channel.
ENABLE_MICROPHONE = False
MIC_SCK_PIN = 15
MIC_WS_PIN = 16
MIC_SD_PIN = 17
MIC_SLOT = 0
