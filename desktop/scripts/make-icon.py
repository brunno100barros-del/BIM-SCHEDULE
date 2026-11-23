"""Gera desktop/build/icon.ico (256x256, PNG embutido) sem dependências externas.

Ícone simples: quadrado azul-escuro arredondado com barras de Gantt em ciano.
"""
import struct, zlib
from pathlib import Path

S = 256
def px(x, y):
    r = 44
    cx = min(max(x, r), S - 1 - r); cy = min(max(y, r), S - 1 - r)
    if (x - cx) ** 2 + (y - cy) ** 2 > r * r:
        return (0, 0, 0, 0)
    bars = [(48, 150, 60, 84), (96, 200, 104, 128), (72, 176, 148, 172), (128, 214, 192, 216)]
    for x0, x1, y0, y1 in bars:
        if x0 <= x < x1 and y0 <= y < y1:
            return (56, 189, 248, 255)
    if 36 <= x < 42 and 50 <= y < 222:
        return (148, 163, 184, 255)
    return (15, 23, 42, 255)

raw = b"".join(b"\x00" + b"".join(bytes(px(x, y)) for x in range(S)) for y in range(S))
def chunk(t, d):
    return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", S, S, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
ico = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22) + png
out = Path(__file__).resolve().parents[1] / "build" / "icon.ico"
out.write_bytes(ico)
print(out, len(ico))
