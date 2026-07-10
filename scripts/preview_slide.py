"""
Hot-reload slide preview - D.1 from FuturePLAN.md

Usage:
    python scripts/preview_slide.py --layout code --headline "Pointers in C++"
    python scripts/preview_slide.py --layout content --headline "Variables" --bullets "A,B,C"
    python scripts/preview_slide.py --layout error_fix --headline "Common Mistake"

Opens the rendered PNG in your default image viewer.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.slide_renderer.renderer import SlideRenderer


def main():
    parser = argparse.ArgumentParser(description="Preview a single slide")
    parser.add_argument("--layout", default="content",
        choices=["title", "content", "code", "numbered_steps", "checklist",
                 "comparison", "error_fix", "terminal", "summary", "two_column", "exercise"],
        help="Slide layout")
    parser.add_argument("--headline", default="Preview Slide", help="Slide headline")
    parser.add_argument("--bullets", default="", help="Comma-separated bullets")
    parser.add_argument("--code", default="", help="Code content (for code/terminal layouts)")
    parser.add_argument("--tag", default="CONCEPT", help="Slide tag (HOOK/CONCEPT/CODE/...)")
    parser.add_argument("--out", default="", help="Output PNG path (default: preview.png in cwd)")
    parser.add_argument("--lesson-number", type=int, default=1)
    parser.add_argument("--total-slides", type=int, default=5)
    parser.add_argument("--no-open", action="store_true", help="Don't open in viewer")
    args = parser.parse_args()

    bullets = [b.strip() for b in args.bullets.split(",") if b.strip()] if args.bullets else []

    slide_data = {
        "id": "preview_001",
        "layout": args.layout,
        "headline": args.headline,
        "bullets": bullets,
        "code_content": args.code,
        "tag": args.tag,
        "lesson_number": args.lesson_number,
        # two_column / comparison defaults
        "left_label": "Before",
        "right_label": "After",
        "left_bullets": bullets[:len(bullets)//2] if bullets else [],
        "right_bullets": bullets[len(bullets)//2:] if bullets else [],
    }

    out_path = args.out or str(Path.cwd() / "preview.png")

    print(f"Rendering [{args.layout}] slide...")
    renderer = SlideRenderer()
    renderer.render_slide(
        slide_data,
        out_path,
        slide_index=0,
        total_slides=args.total_slides,
    )

    size_kb = Path(out_path).stat().st_size // 1024
    print(f"  Saved: {out_path} ({size_kb} KB)")

    if not args.no_open:
        try:
            os.startfile(out_path)  # Windows
        except AttributeError:
            subprocess.run(["open", out_path])   # macOS
        except Exception as e:
            print(f"  Could not open viewer: {e}")


if __name__ == "__main__":
    main()
