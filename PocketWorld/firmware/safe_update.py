"""Conservative, bounded file updates for Sanny's local HTTP server.

The HTTP authentication is handled by main.py. This module enforces file
allowlisting, streamed writes, syntax checks for Python, and a .bak copy.
It does not overwrite main.py, settings.py, boot.py or firmware partitions.
"""

import os

MAX_FILE_SIZE = 128 * 1024
BASE_FILES = ("index.html", "world_model.py")
ASSET_EXTENSIONS = (".png", ".jpg", ".json", ".dat")


def valid_filename(filename):
    if not isinstance(filename, str) or not filename or len(filename) > 72:
        return False
    if filename in BASE_FILES:
        return True
    if not filename.startswith("assets/"):
        return False
    basename = filename[7:]
    if not basename or basename.startswith(".") or ".." in basename:
        return False
    for char in basename:
        if not ("a" <= char <= "z" or "A" <= char <= "Z" or
                "0" <= char <= "9" or char in "_.-"):
            return False
    return basename.lower().endswith(ASSET_EXTENSIONS)


def _remove_if_exists(path):
    try:
        os.remove(path)
    except OSError:
        pass


def receive_update(filename, length, initial, connection):
    """Receive exactly length bytes from a request body.

    Returns bytes written. Raises ValueError or OSError on failure. Previous
    destination remains untouched until the full file has been validated.
    """
    if not valid_filename(filename):
        raise ValueError("File type or path not allowed")
    if not isinstance(length, int) or length < 1 or length > MAX_FILE_SIZE:
        raise ValueError("File must be 1 to 131072 bytes")
    if len(initial) > length:
        raise ValueError("Unexpected request body length")
    if filename.startswith("assets/"):
        try:
            os.mkdir("assets")
        except OSError:
            pass
    incoming = filename + ".incoming"
    backup = filename + ".bak"
    remaining = length - len(initial)
    try:
        with open(incoming, "wb") as output:
            if initial:
                output.write(initial)
            while remaining:
                block = connection.recv(min(1024, remaining))
                if not block:
                    raise ValueError("Incomplete file transfer")
                output.write(block)
                remaining -= len(block)

        if filename.endswith(".py"):
            with open(incoming, "r") as file:
                source = file.read()
            # A syntax check catches accidental corrupt uploads. Runtime
            # compatibility still needs testing on the actual hardware.
            compile(source, filename, "exec")

        _remove_if_exists(backup)
        try:
            os.rename(filename, backup)
        except OSError:
            pass  # new file
        try:
            os.rename(incoming, filename)
        except OSError:
            try:
                os.rename(backup, filename)
            except OSError:
                pass
            raise
    except Exception:
        _remove_if_exists(incoming)
        raise
    return length
