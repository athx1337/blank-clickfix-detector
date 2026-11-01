"""Render original BLANK bracket-and-dot icons using only the Python standard library."""
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_icons():
    destination = ROOT / "extension/icons"
    destination.mkdir(exist_ok=True)
    for size in (16, 32, 48, 128):
        pixels = bytearray()
        for y in range(size):
            pixels.append(0)  # PNG filter: none
            for x in range(size):
                # Supersampling keeps brackets and the round dot readable at small sizes.
                samples = []
                for dy in range(4):
                    for dx in range(4):
                        u, v = (x + (dx + 0.5) / 4) / size, (y + (dy + 0.5) / 4) / size
                        bracket = ((0.22 < u < 0.29 or 0.71 < u < 0.78) and 0.23 < v < 0.77) or (
                            (0.22 < u < 0.41 or 0.59 < u < 0.78) and
                            (0.23 < v < 0.30 or 0.70 < v < 0.77))
                        dot = (u - 0.5) ** 2 + (v - 0.5) ** 2 < 0.075 ** 2
                        samples.append((248, 250, 249) if bracket else (111, 224, 181) if dot else (25, 40, 58))
                pixels.extend(round(sum(c[i] for c in samples) / 16) for i in range(3))

        def chunk(kind, data):
            return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))

        png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!2I5B", size, size, 8, 2, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(bytes(pixels), 9)) + chunk(b"IEND", b""))
        (destination / f"blank-{size}.png").write_bytes(png)


if __name__ == "__main__":
    build_icons()
