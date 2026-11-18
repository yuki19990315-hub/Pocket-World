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
