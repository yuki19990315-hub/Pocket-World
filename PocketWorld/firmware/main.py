"""MicroPython HTTP endpoint for Pocket World + Sanny Companion v0.4.

Upload main.py, safe_update.py, world_model.py, settings.py and /index.html
to the board's root filesystem. This first prototype provides the shared world
engine and the phone viewer; round LCD rendering requires a matching GC9A01 driver.
"""

import gc
import json
import os
import socket
import time

import settings
from world_model import PocketWorld
from safe_update import receive_update
from power_runtime import PowerRuntime
from motion_effects import MotionEffects

SAVE_FILE = "worlds.json"
SAVE_TEMP = "worlds.tmp"
SAVE_BACKUP = "worlds.bak"
SAVE_INTERVAL = 300  # seconds; avoid excessive flash writes
MOTION_SETTINGS_FILE = "motion_settings.json"


def load_worlds():
    for filename in (SAVE_FILE, SAVE_BACKUP):
        try:
            with open(filename, "r") as handle:
                return PocketWorld(json.load(handle))
        except (OSError, ValueError, TypeError):
            pass
    return PocketWorld()


def save_worlds(engine):
    try:
        with open(SAVE_TEMP, "w") as handle:
            json.dump(engine.persistable(), handle)
        try:
            os.remove(SAVE_BACKUP)
        except OSError:
            pass
        try:
            os.rename(SAVE_FILE, SAVE_BACKUP)
        except OSError:
            pass
        os.rename(SAVE_TEMP, SAVE_FILE)
    except OSError as exc:
        print("Save failed:", exc)


def configure_wifi():
    import network
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=settings.AP_SSID, password=settings.AP_PASSWORD)
    print("Phone AP:", settings.AP_SSID, "address:", ap.ifconfig()[0])

    if settings.STA_SSID:
        station = network.WLAN(network.STA_IF)
        station.active(True)
        station.connect(settings.STA_SSID, settings.STA_PASSWORD)
        print("STA connection requested (check network rules)")
    return ap


def response(client, status, content_type, body):
    if isinstance(body, str):
        body = body.encode("utf-8")
    head = ("HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n"
            "Cache-Control: no-store\r\nConnection: close\r\n\r\n" %
            (status, content_type, len(body)))
    client.sendall(head.encode("ascii"))
    client.sendall(body)


def serve_html(client):
    try:
        length = os.stat("index.html")[6]
        head = ("HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
                "Content-Length: %d\r\nCache-Control: no-store\r\n"
                "Connection: close\r\n\r\n" % length)
        client.sendall(head.encode("ascii"))
        with open("index.html", "rb") as handle:
            while True:
                chunk = handle.read(1024)
                if not chunk:
                    break
                client.sendall(chunk)
    except OSError:
        response(client, "500 Internal Server Error", "text/plain", "Missing /index.html")


def query_param(path, key):
    if "?" not in path:
        return None
    query = path.split("?", 1)[1]
    for entry in query.split("&"):
        pair = entry.split("=", 1)
        if len(pair) == 2 and pair[0] == key:
            return pair[1]
    return None


def parse_request(client):
    request = bytearray()
    while b"\r\n\r\n" not in request:
        block = client.recv(1024)
        if not block:
            raise ValueError("Incomplete HTTP headers")
        request.extend(block)
        if len(request) > 8192:
            raise ValueError("Headers too large")
    head, body = bytes(request).split(b"\r\n\r\n", 1)
    lines = head.decode("utf-8", "replace").split("\r\n")
    first = lines[0].split(" ")
    if len(first) < 2:
        raise ValueError("Malformed request line")
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    return first[0], first[1], headers, body


def authorized(headers):
    expected = getattr(settings, "ADMIN_KEY", "")
    return (expected and expected != "CHANGE_ME_BEFORE_UPDATING"
            and headers.get("x-admin-key") == expected)


def json_request(client, headers, first_body, maximum=2048):
    size = int(headers.get("content-length", "-1"))
    if size < 1 or size > maximum:
        raise ValueError("Invalid JSON length")
    data = bytearray(first_body)
    if len(data) > size:
        raise ValueError("Unexpected request bytes")
    while len(data) < size:
        more = client.recv(min(1024, size - len(data)))
        if not more:
            raise ValueError("Incomplete JSON request")
        data.extend(more)
    parsed = json.loads(data.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("JSON object required")
    return parsed


def load_motion_settings(motion):
    try:
        with open(MOTION_SETTINGS_FILE, "r") as handle:
            value = json.load(handle)
        if isinstance(value.get("shake_enabled"), bool):
            motion.shake_enabled = value["shake_enabled"]
    except (OSError, ValueError, TypeError, AttributeError):
        pass


def save_motion_settings(enabled):
    with open(MOTION_SETTINGS_FILE + ".tmp", "w") as handle:
        json.dump({"shake_enabled": enabled}, handle)
    try:
        os.remove(MOTION_SETTINGS_FILE + ".bak")
    except OSError:
        pass
    try:
        os.rename(MOTION_SETTINGS_FILE, MOTION_SETTINGS_FILE + ".bak")
    except OSError:
        pass
    os.rename(MOTION_SETTINGS_FILE + ".tmp", MOTION_SETTINGS_FILE)


def service(client, engine, power=None, motion=None):
    client.settimeout(7)
    try:
        method, path, headers, body = parse_request(client)
    except ValueError as exc:
        response(client, "400 Bad Request", "text/plain", str(exc))
        return False
    if method == "GET" and (path == "/" or path.startswith("/?")):
        serve_html(client)
    elif method == "GET" and path == "/api/info":
        key = getattr(settings, "ADMIN_KEY", "")
        response(client, "200 OK", "application/json", json.dumps({
            "name": "サンニー", "version": "0.4", "wifi": settings.AP_SSID,
            "updater_enabled": bool(key and key != "CHANGE_ME_BEFORE_UPDATING")
        }))
    elif method == "GET" and path.startswith("/api/state"):
        clock = query_param(path, "clock")
        changed = engine.reconcile_clock(clock) if clock else 0
        snapshot = engine.snapshot()
        snapshot["motion"] = motion.snapshot() if motion is not None else {
            "connected": False, "tilt_x": 0, "tilt_y": 0, "shake_id": 0}
        response(client, "200 OK", "application/json; charset=utf-8", json.dumps(snapshot))
        return bool(changed)
    elif method == "GET" and path == "/api/power":
        data = power.status() if power is not None else PowerRuntime().status()
        response(client, "200 OK", "application/json", json.dumps(data))
    elif method == "GET" and path == "/api/motion":
        response(client, "200 OK", "application/json",
                 json.dumps(motion.snapshot() if motion is not None else {"connected": False}))
    elif method == "POST" and path == "/api/motion/settings":
        if not authorized(headers):
            response(client, "403 Forbidden", "application/json", '{"error":"Invalid admin key"}')
            return False
        if motion is None:
            response(client, "503 Service Unavailable", "application/json", '{"error":"Motion unavailable"}')
            return False
        try:
            value = json_request(client, headers, body)
            enabled = value["shake_enabled"]
            if not isinstance(enabled, bool) or len(value) != 1:
                raise ValueError("shake_enabled must be boolean")
            save_motion_settings(enabled)
            motion.shake_enabled = enabled
            response(client, "200 OK", "application/json", json.dumps(motion.snapshot()))
        except (KeyError, ValueError, OSError, TypeError) as exc:
            response(client, "400 Bad Request", "application/json", json.dumps({"error": str(exc)}))
    elif method == "POST" and path in ("/api/power/schedule", "/api/time"):
        if not authorized(headers):
            response(client, "403 Forbidden", "application/json", '{"error":"Invalid admin key"}')
            return False
        if power is None:
            response(client, "503 Service Unavailable", "application/json", '{"error":"Power service unavailable"}')
            return False
        try:
            payload = json_request(client, headers, body)
            # Validate the supplied clock before persisting new settings.
            stamp = int(payload["clock"])
            if not 1577836800 <= stamp < 4102444800:
                raise ValueError("Clock is outside supported range")
            if path == "/api/power/schedule":
                power.update_schedule(payload["schedule"])
            power.sync_clock(stamp)
            changed = engine.reconcile_clock(stamp)
            response(client, "200 OK", "application/json", json.dumps(power.status()))
            return bool(changed)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            response(client, "400 Bad Request", "application/json", json.dumps({"error": str(exc)}))
    elif method == "POST" and path.startswith("/api/touch"):
        ident = query_param(path, "world")
        success = engine.tap(ident)
        response(client, "200 OK" if success else "404 Not Found",
                 "application/json", json.dumps({"ok": success}))
        return success
    elif method == "POST" and path == "/api/upload":
        if not authorized(headers):
            response(client, "403 Forbidden", "application/json", '{"error":"Invalid admin key"}')
            return False
        try:
            length = int(headers.get("content-length", "-1"))
            filename = headers.get("x-file-name", "")
            count = receive_update(filename, length, body, client)
            response(client, "200 OK", "application/json",
                     json.dumps({"ok": True, "file": filename, "bytes": count,
                                 "restart_required": filename.endswith(".py")}))
        except (ValueError, OSError, SyntaxError) as exc:
            response(client, "400 Bad Request", "application/json",
                     json.dumps({"error": str(exc)}))
    elif method == "POST" and path == "/api/restart":
        if not authorized(headers):
            response(client, "403 Forbidden", "application/json", '{"error":"Invalid admin key"}')
            return False
        response(client, "200 OK", "application/json", '{"ok":true,"restarting":true}')
        return "restart"
    else:
        response(client, "404 Not Found", "text/plain", "Not found")
    return False


def main():
    engine = load_worlds()
    power = PowerRuntime(getattr(settings, "ENABLE_DEEP_SLEEP", False))
    motion = MotionEffects()
    load_motion_settings(motion)
    sensor = None
    try:
        import machine
        power.restore_timer_wake(machine.reset_cause() == machine.DEEPSLEEP_RESET)
        if getattr(settings, "ENABLE_MOTION_SENSOR", True):
            from qmi8658 import QMI8658
            bus = machine.I2C(0, sda=machine.Pin(6), scl=machine.Pin(7), freq=400000)
            sensor = QMI8658(bus)
    except (ImportError, OSError, ValueError, AttributeError) as exc:
        print("Motion sensor unavailable:", exc)
    if power.now() is not None:
        engine.reconcile_clock(power.now())
    ap = None
    # Silent background wake: the weekend world grows while the LCD stays dark.
    if power.plan_sleep() is not None:
        enter_sleep(engine, power, sensor, ap)
    ap = configure_wifi()
    address = socket.getaddrinfo("0.0.0.0", settings.PORT)[0][-1]
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(address)
    server.listen(2)
    server.settimeout(0.12)
    print("Sanny Pocket World ready on http://192.168.4.1/")

    previous = time.ticks_ms()
    elapsed_ms = 0
    since_save = 0
    motion_ms = 0
    uptime_ms = 0
    while True:
        now = time.ticks_ms()
        delta = max(0, time.ticks_diff(now, previous))
        elapsed_ms += delta
        power.tick(delta)
        motion_ms += delta
        uptime_ms += delta
        previous = now
        if sensor is not None and motion_ms >= 100:
            motion_ms %= 100
            try:
                acceleration, angular_rate = sensor.read()
                motion.observe(acceleration, angular_rate, uptime_ms)
            except OSError as exc:
                print("Motion read failed, disabling sensor:", exc)
                sensor = None
        if elapsed_ms >= 1000:
            seconds = elapsed_ms // 1000
            elapsed_ms %= 1000
            engine.advance(seconds)
            since_save += seconds
        if since_save >= SAVE_INTERVAL:
            save_worlds(engine)
            since_save = 0
        if power.plan_sleep() is not None:
            enter_sleep(engine, power, sensor, ap)
        try:
            client, _ = server.accept()
        except OSError:
            continue
        result = False
        try:
            result = service(client, engine, power, motion)
            if result is True:
                save_worlds(engine)
                since_save = 0
        except Exception as exc:
            print("HTTP error:", exc)
        finally:
            client.close()
            gc.collect()
        if result == "restart":
            save_worlds(engine)
            time.sleep_ms(400)
            import machine
            machine.reset()


def enter_sleep(engine, power, sensor, ap):
    """Optional path; only reachable after hardware sleep is explicitly enabled."""
    seconds = power.plan_sleep()
    if seconds is None:
        return
    # Save an exact wall-time anchor before entering MicroPython deep sleep.
    engine.last_wall_epoch = power.now()
    engine.runtime_since_boot = 0
    save_worlds(engine)
    power.write_wake_marker(power.now() + seconds)
    if sensor is not None:
        sensor.standby()
    if ap is not None:
        ap.active(False)
    import machine
    machine.deepsleep(seconds * 1000)


if __name__ == "__main__":
    main()
