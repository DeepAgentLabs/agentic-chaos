"""Generate a terminal demo GIF from actual offline example output.

Run: uv run --with pillow python scripts/generate_v05_demo.py
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[1]
commands = ["examples/chaos_streaming_demo.py", "examples/chaos_provider_patching_demo.py"]
lines = ["agentic-chaos v0.5 | offline demo", ""]
frames = []
font = ImageFont.truetype("DejaVuSansMono.ttf", 16)
for command in commands:
    output = subprocess.check_output([sys.executable, command], cwd=root, text=True)
    for line in [f"$ python {command}", *output.splitlines(), ""]:
        lines.append(line)
        frame = Image.new("RGB", (900, 300), "#111827")
        draw = ImageDraw.Draw(frame)
        draw.multiline_text((20, 20), "\n".join(lines), font=font, fill="#86efac", spacing=7)
        frames.append(frame)
path = root / "docs/assets/v0.5-demo.gif"
frames[0].save(path, save_all=True, append_images=frames[1:], duration=900, loop=0)
print(path)
