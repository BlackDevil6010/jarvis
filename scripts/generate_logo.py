"""Generates the official high-resolution J.A.R.V.I.S. brand logo.
A futuristic cybernetic Arc Reactor motif in glowing cyan, navy, electric blue, and white.
"""

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

def create_jarvis_logo(size=512, output_path="assets/branding/jarvis_logo.png"):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center = size / 2.0
    r_max = size * 0.44

    # Outer ambient glow ring
    for r, alpha in [(r_max + 12, 35), (r_max + 6, 70), (r_max, 150)]:
        draw.ellipse(
            [center - r, center - r, center + r, center + r],
            outline=(0, 240, 255, alpha),
            width=3
        )

    # Outer solid structural ring
    draw.ellipse(
        [center - r_max, center - r_max, center + r_max, center + r_max],
        outline=(0, 210, 255, 230),
        width=4
    )

    # Radial tick marks (Cyber HUD aesthetic)
    num_ticks = 36
    for i in range(num_ticks):
        angle = math.radians(i * (360.0 / num_ticks))
        is_major = (i % 3 == 0)
        len_tick = 18 if is_major else 8
        w_tick = 3 if is_major else 1
        alpha_tick = 255 if is_major else 140

        x1 = center + (r_max - 4) * math.cos(angle)
        y1 = center + (r_max - 4) * math.sin(angle)
        x2 = center + (r_max - 4 - len_tick) * math.cos(angle)
        y2 = center + (r_max - 4 - len_tick) * math.sin(angle)

        draw.line([(x1, y1), (x2, y2)], fill=(0, 240, 255, alpha_tick), width=w_tick)

    # Mid ring (Navy / Cyan border)
    r_mid = size * 0.30
    draw.ellipse(
        [center - r_mid, center - r_mid, center + r_mid, center + r_mid],
        fill=(11, 24, 48, 220),
        outline=(0, 240, 255, 255),
        width=3
    )

    # Triangular Arc Reactor Core segments
    r_tri = size * 0.22
    for rot in [0, 120, 240]:
        rad_rot = math.radians(rot)
        points = []
        for a in [0, 120, 240]:
            total_a = rad_rot + math.radians(a)
            points.append((center + r_tri * math.cos(total_a), center + r_tri * math.sin(total_a)))
        draw.polygon(points, outline=(0, 190, 255, 180), width=2)

    # Inner core glow ring
    r_core = size * 0.16
    draw.ellipse(
        [center - r_core, center - r_core, center + r_core, center + r_core],
        fill=(0, 40, 80, 240),
        outline=(0, 240, 255, 255),
        width=3
    )

    # Brilliant central core
    r_center = size * 0.08
    draw.ellipse(
        [center - r_center, center - r_center, center + r_center, center + r_center],
        fill=(230, 248, 255, 255),
        outline=(0, 240, 255, 255),
        width=2
    )

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_file, "PNG")
    print(f"Generated official JARVIS logo at: {out_file.resolve()} ({size}x{size})")

if __name__ == "__main__":
    create_jarvis_logo()
