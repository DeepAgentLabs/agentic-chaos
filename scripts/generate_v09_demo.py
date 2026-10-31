"""Generate the v0.9 terminal demo GIF from actual offline example output.

Run: uv run --with pillow python scripts/generate_v09_demo.py
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[1]
cli = [sys.executable, "-m", "agentic_chaos.cli.main"]
history = Path(tempfile.mkdtemp()) / "resilience-history.json"
commands = [
    (
        "python examples/chaos_resilience_demo.py",
        [sys.executable, "examples/chaos_resilience_demo.py"],
    ),
    (
        "agentic-chaos experiment run examples/workflows/resilience-probes.yaml --history ...",
        [
            *cli,
            "experiment",
            "run",
            "examples/workflows/resilience-probes.yaml",
            "--no-input",
            "--history",
            str(history),
        ],  # fmt: skip
    ),
]
lines = ["agentic-chaos 0.9.0 | resilience probes & resilience score", ""]
frames = []
font = ImageFont.truetype("DejaVuSansMono.ttf", 15)
width, height, visible = 1180, 620, 29
env = {**os.environ, "COLUMNS": "120", "NO_COLOR": "1"}
for label, command in commands:
    output = subprocess.run(
        command, cwd=root, text=True, capture_output=True, check=True, env=env
    ).stdout
    for line in [f"$ {label}", *output.rstrip().splitlines(), ""]:
        lines.append(line if len(line) <= 120 else line[:119] + "…")
        frame = Image.new("RGB", (width, height), "#111827")
        draw = ImageDraw.Draw(frame)
        draw.multiline_text(
            (20, 20), "\n".join(lines[-visible:]), font=font, fill="#86efac", spacing=6
        )
        frames.append(frame)
path = root / "docs/assets/v0.9-demo.gif"
frames[0].save(path, save_all=True, append_images=frames[1:], duration=600, loop=0)
print(path)
