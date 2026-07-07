import subprocess
import shutil
from pathlib import Path


def render_mermaid(definition: str, output_path: str) -> str | None:
    """
    Render a Mermaid diagram definition to PNG using mmdc CLI.
    Returns output_path on success, None if mmdc is not installed.
    """
    if not shutil.which("mmdc"):
        print("  mmdc not found. Skipping diagram. Install: npm i -g @mermaid-js/mermaid-cli")
        return None

    input_file = str(Path(output_path).with_suffix(".mmd"))
    with open(input_file, "w", encoding="utf-8") as f:
        f.write(definition)

    result = subprocess.run(
        ["mmdc", "-i", input_file, "-o", output_path, "-t", "dark", "-b", "#0D0D0D"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    Path(input_file).unlink(missing_ok=True)

    if result.returncode == 0 and Path(output_path).exists():
        return output_path
    else:
        print(f"  Mermaid render failed: {result.stderr[:200]}")
        return None


def generate_ascii_diagram(lines: list[str], output_path: str) -> str:
    """
    Fallback: render ASCII art diagram as PNG using Pillow.
    Used when mmdc is not available.
    """
    from PIL import Image, ImageDraw, ImageFont
    import json

    bg_color = (13, 13, 13)
    text_color = (0, 200, 150)
    width, height = 1920, 1080

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("assets/fonts/JetBrainsMono-Regular.ttf", 28)
    except Exception:
        font = ImageFont.load_default()

    y = 80
    for line in lines:
        draw.text((80, y), line, fill=text_color, font=font)
        y += 42

    img.save(output_path, "PNG")
    return output_path
