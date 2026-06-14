#!/usr/bin/env python3
"""Generate application icon as a multiresolution .ICO file.

Creates an Indonesian flag-style icon (red over white) with "I" and "D"
letter shapes. No external dependencies — pure Python + standard library.
"""

import struct
from pathlib import Path

RED = (0xCE, 0x11, 0x26)
WHITE = (0xFF, 0xFF, 0xFF)


def make_id_grid(size: int) -> tuple[list[str], list[str]]:
    """Generate top and bottom half grids for the 'ID' icon at given size.

    Top half = red background with white letters.
    Bottom half = white background with red letters.
    The 'I' is a vertical bar in the left ~30% of the grid.
    The 'D' is a rounded rectangle in the right ~55% of the grid.
    """
    half = size // 2
    top = []
    bot = []

    # Letter layout zones (proportional)
    i_left = int(size * 0.08)
    i_right = int(size * 0.32)
    i_bar_thick = max(1, size // 12)
    i_mid_top = int(size * 0.38)
    i_mid_bot = int(size * 0.62)

    d_left = int(size * 0.42)
    d_right = int(size * 0.92)
    d_top = int(size * 0.08)
    d_bot = int(size * 0.92)
    d_thick = max(1, size // 12)
    d_hole_left = d_left + d_thick
    d_hole_right = d_right - d_thick
    d_hole_top = d_top + d_thick
    d_hole_bot = d_bot - d_thick - (2 if size <= 32 else 0)

    for y in range(half):
        top_row = []
        bot_row = []
        for x in range(size):
            # "I" shape
            in_i = (
                (i_left <= x <= i_right and (y < i_bar_thick or y >= half - i_bar_thick))  # top/bottom bars
                or (i_left <= x <= i_right and i_mid_top <= y <= i_mid_bot)               # middle stem
            )
            # "D" shape: outline with hollow center
            in_d_outline = d_left <= x <= d_right and d_top <= y <= d_bot
            in_d_hole = d_hole_left <= x <= d_hole_right and d_hole_top <= y <= d_hole_bot
            in_d = in_d_outline and not in_d_hole

            in_letter = in_i or in_d

            # Top half: red bg, white fg
            if y < half:
                if in_letter:
                    top_row.append("W")  # white letter on red bg
                else:
                    top_row.append("R")  # red bg
            # Bottom half mirrors top conceptually but with reversed colors
            if in_letter:
                bot_row.append("R")  # red letter on white bg
            else:
                bot_row.append("W")  # white bg

        top.append("".join(top_row))
        bot.append("".join(bot_row))

    return top, bot


def build_bmp(px_width: int, px_height: int,
              top_grid: list[str], bot_grid: list[str]) -> bytes:
    """Build a 32-bit BGRA BMP for an ICO image."""
    half = px_height // 2
    rows = []

    for y in range(px_height):
        row = bytearray()
        for x in range(px_width):
            if y < half:
                ch = top_grid[y][x]
                r, g, b = WHITE if ch == "W" else RED
            else:
                ch = bot_grid[y - half][x]
                r, g, b = RED if ch == "R" else WHITE
            row += struct.pack("BBBB", b, g, r, 0xFF)

        while len(row) % 4 != 0:
            row.append(0)
        rows.append(bytes(row))

    # BMP stores rows bottom-to-top
    return b"".join(reversed(rows))


def build_ico(sizes: list[int]) -> bytes:
    num = len(sizes)
    offset = 6 + 16 * num
    entries = []
    images = []

    for sz in sizes:
        top, bot = make_id_grid(sz)
        pixel_data = build_bmp(sz, sz, top, bot)
        pixel_size = len(pixel_data)

        # DIB header: BITMAPINFOHEADER with doubled height (ICO format)
        mask_row_bytes = ((sz + 31) // 32) * 4
        mask_data = bytes(mask_row_bytes * sz)

        bmp = bytearray()
        bmp += struct.pack("<I", 40)                      # header size
        bmp += struct.pack("<ii", sz, sz * 2)             # width, height*2 (ICO format)
        bmp += struct.pack("<H", 1)                       # planes
        bmp += struct.pack("<H", 32)                      # bpp
        bmp += struct.pack("<I", 0)                       # compression
        bmp += struct.pack("<I", pixel_size)              # image size
        bmp += struct.pack("<ii", 0, 0)                   # x/m DPI
        bmp += struct.pack("<II", 0, 0)                   # colors used, colors important

        bmp += pixel_data
        bmp += mask_data
        images.append(bytes(bmp))
        img_sz = len(bmp)

        entry = struct.pack("<BBBBHHII", sz if sz < 256 else 0, sz if sz < 256 else 0, 0, 0, 1, 32, img_sz, offset)
        entries.append(entry)
        offset += img_sz

    return struct.pack("<HHH", 0, 1, num) + b"".join(entries) + b"".join(images)


def main():
    sizes = [16, 32, 48, 256]

    # Validate grids
    for sz in sizes:
        top, bot = make_id_grid(sz)
        half = sz // 2
        assert len(top) == half, f"top grid: {len(top)} != {half}"
        assert len(bot) == half, f"bot grid: {len(bot)} != {half}"
        for i, r in enumerate(top):
            assert len(r) == sz, f"top[{i}] len={len(r)} != {sz}"
        for i, r in enumerate(bot):
            assert len(r) == sz, f"bot[{i}] len={len(r)} != {sz}"

    out_path = Path(__file__).resolve().parent / "icon.ico"
    ico_data = build_ico(sizes)
    out_path.write_bytes(ico_data)

    for sz in sizes:
        top, bot = make_id_grid(sz)
        # Print miniature preview
        print(f"\n--- {sz}x{sz} top ---")
        for row in top:
            print(row)
    print(f"\nGenerated {out_path} ({len(ico_data)} bytes)")

if __name__ == "__main__":
    main()
