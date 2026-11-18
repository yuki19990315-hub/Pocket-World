"""Convert the design preview artwork into compact, SPI-ready LCD frames."""

import argparse
import zlib
from pathlib import Path

WORLDS = ("nature", "city", "hybrid", "fantasy", "forest", "aquarium")
SIZE = (240, 240)


def encode(rgb):
    pixels = bytearray()
    for red, green, blue in zip(rgb[0::3], rgb[1::3], rgb[2::3]):
        pixels.append((red & 248) | (green >> 5))
        pixels.append(((green & 28) << 3) | (blue >> 3))
    packed = zlib.compress(pixels, level=9)
    assert len(pixels) == 240 * 240 * 2 and zlib.decompress(packed) == pixels
    return packed


def build_frames(output, read_rgb):
    output.mkdir(parents=True, exist_ok=True)
    size = 0
    for world in WORLDS:
        young = read_rgb(world + "-young")
        mature = read_rgb(world + "-mature")
        middle = bytes((a + b) // 2 for a, b in zip(young, mature))
        for day, frame in ((0, young), (15, middle), (30, mature)):
            packed = encode(frame)
            (output / ("lcd-art-%s-%d.dat" % (world, day))).write_bytes(packed)
            size += len(packed)
    print("18 LCD frames, %d bytes" % size)


def main():
    from PIL import Image

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output
    source = Path(__file__).resolve().parents[1] / "design" / "assets"

    def read_rgb(name):
        with Image.open(source / (name + ".png")) as image:
            if image.size != SIZE:
                raise ValueError("Unexpected artwork size for %s: %s" % (name, image.size))
            return image.convert("RGB").tobytes()

    build_frames(output, read_rgb)


if __name__ == "__main__":
    main()
