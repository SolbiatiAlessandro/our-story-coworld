"""PNG images of the canvas, standard library only, so players can look instead of parsing letters."""

from __future__ import annotations

import base64
import struct
import zlib

from ourstory.engine import EMPTY, PALETTE

BACKGROUND = (244, 241, 234)
RGB = {k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5)) for k, v in PALETTE.items()}


def png(grid: list[list[str]] | list[str], scale: int = 6) -> bytes:
    raw = bytearray()
    for row in grid:
        line = b"".join(bytes(RGB.get(c, BACKGROUND) if c != EMPTY else BACKGROUND) * scale for c in row)
        for _ in range(scale):
            raw += b"\x00" + line
    h, w = len(grid) * scale, len(grid[0]) * scale

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def png_b64(grid, scale: int = 6) -> str:
    return base64.b64encode(png(grid, scale)).decode()
