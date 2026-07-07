#!/usr/bin/env python3
"""
Human-in-the-loop slide reviewer. Displays each slide and prompts for approval.
Run this AFTER slides are generated but BEFORE audio synthesis.

Usage:
  python scripts/review_slides.py --lesson-id <lesson_id>

Workflow:
  - Shows each slide image path + headline
  - Press Enter to approve
  - Type a correction and press Enter to re-generate that slide
  - Type 'skip' to skip remaining reviews
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import typer
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

app = typer.Typer()
console = Console()


@app.command()
def main(
    lesson_id: str = typer.Option(..., "--lesson-id", help="Lesson ID to review"),
    course_id: str = typer.Option("", "--course-id", help="Course ID (optional)"),
):
    from db.database import init_db, SessionLocal
    from db import models

    init_db()
    db = SessionLocal()

    # find lesson output dir
    lesson = db.get(models.Lesson, lesson_id)
    if not lesson:
        console.print(f"[red]Lesson {lesson_id} not found.[/]")
        raise typer.Exit(1)
    db.close()

    output_dir = Path(lesson.output_dir) if lesson.output_dir else None
    if not output_dir or not output_dir.exists():
        console.print(f"[red]Output directory not found: {output_dir}[/]")
        raise typer.Exit(1)

    # load script.json for slide info
    script_path = output_dir / "script.json"
    if not script_path.exists():
        console.print("[red]script.json not found. Run generation first.[/]")
        raise typer.Exit(1)

    script = json.loads(script_path.read_text(encoding="utf-8"))
    slide_dir = output_dir / "slides"

    if not slide_dir.exists():
        console.print("[red]No slides directory found. Run generation first.[/]")
        raise typer.Exit(1)

    slide_files = sorted(slide_dir.glob("*.png"))
    if not slide_files:
        console.print("[red]No slide images found.[/]")
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold cyan]Slide Review[/] — {len(slide_files)} slides\n"
        f"[dim]Press Enter to approve • Type correction to flag • 'skip' to stop[/]",
        title="theTwoCubes Slide Reviewer",
    ))

    flagged = []
    for i, slide_path in enumerate(slide_files):
        console.print(f"\n[dim]─── Slide {i+1}/{len(slide_files)} ───[/]")
        console.print(f"  [cyan]{slide_path.name}[/]")
        console.print(f"  Path: [dim]{slide_path}[/]")

        # try to open the image for preview
        try:
            import subprocess
            subprocess.Popen(["start", "", str(slide_path)], shell=True)
        except Exception:
            pass

        answer = Prompt.ask(
            "  [green]✓ Approve (Enter)[/] / [yellow]correction[/] / [red]skip[/]",
            default="",
        )

        if answer.strip().lower() == "skip":
            console.print("[yellow]Skipping remaining slides.[/]")
            break
        elif answer.strip():
            flagged.append({
                "slide": slide_path.name,
                "index": i,
                "correction": answer.strip(),
            })
            console.print(f"  [yellow]Flagged for correction: {answer.strip()[:60]}[/]")

    # save review results
    review_path = output_dir / "slide_review.json"
    review_data = {
        "lesson_id": lesson_id,
        "total_slides": len(slide_files),
        "approved": len(slide_files) - len(flagged),
        "flagged": flagged,
    }
    review_path.write_text(json.dumps(review_data, indent=2), encoding="utf-8")

    console.print(f"\n[bold]Review complete:[/] {len(slide_files) - len(flagged)} approved, {len(flagged)} flagged.")
    console.print(f"Review saved to: [dim]{review_path}[/]")

    if flagged:
        console.print("\n[yellow]Flagged slides:[/]")
        for f in flagged:
            console.print(f"  {f['slide']}: {f['correction']}")


if __name__ == "__main__":
    app()
