"""Generate the v0.6 terminal demo GIF from actual offline example output.

Run: uv run --with pillow python scripts/generate_v06_demo.py
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[1]
commands = [
    (
        "pytest examples/pytest_chaos --chaos -q",
        [sys.executable, "-m", "pytest", "examples/pytest_chaos", "--chaos", "-q"]
        + ["-p", "no:cacheprovider", "-o", "addopts="],
    ),
    (
        "python examples/chaos_contracts_demo.py",
        [sys.executable, "examples/chaos_contracts_demo.py"],
    ),
]
lines = ["agentic-chaos 0.6.0 | pytest plugin & contracts", ""]
frames = []
font = ImageFont.truetype("DejaVuSansMono.ttf", 15)
width, height, visible = 1180, 560, 26
for label, command in commands:
    output = subprocess.run(command, cwd=root, text=True, capture_output=True, check=True).stdout
    for line in [f"$ {label}", *output.rstrip().splitlines(), ""]:
        lines.append(line if len(line) <= 120 else line[:119] + "…")
        frame = Image.new("RGB", (width, height), "#111827")
        draw = ImageDraw.Draw(frame)
        draw.multiline_text(
            (20, 20), "\n".join(lines[-visible:]), font=font, fill="#86efac", spacing=6
        )
        frames.append(frame)
path = root / "docs/assets/v0.6-demo.gif"
frames[0].save(path, save_all=True, append_images=frames[1:], duration=700, loop=0)
print(path)
