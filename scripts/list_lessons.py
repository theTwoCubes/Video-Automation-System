#!/usr/bin/env python3
"""List all lessons and their status for a course."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import typer
from rich.console import Console
from rich.table import Table
from db.database import init_db, SessionLocal
from db import models

app = typer.Typer()
console = Console()


@app.command()
def main(
    course_id: str = typer.Option("", "--course-id", help="Filter by course ID"),
):
    init_db()
    db = SessionLocal()

    status_colors = {
        "pending": "dim",
        "processing": "yellow",
        "done": "green",
        "failed": "red",
    }

    if course_id:
        courses = [db.query(models.Course).get(course_id)]
    else:
        courses = db.query(models.Course).all()

    for course in courses:
        if not course:
            console.print("[red]Course not found[/]")
            continue

        console.print(f"\n[bold cyan]{course.title}[/] | ID: {course.id[:8]}...")
        lessons = (
            db.query(models.Lesson)
            .filter(models.Lesson.course_id == course.id)
            .order_by(models.Lesson.position)
            .all()
        )

        table = Table()
        table.add_column("#", style="dim", width=4)
        table.add_column("Title", style="cyan")
        table.add_column("Status")
        table.add_column("Difficulty", style="yellow")
        table.add_column("Duration")

        for l in lessons:
            color = status_colors.get(l.status, "white")
            table.add_row(
                str(l.position),
                l.title[:60],
                f"[{color}]{l.status}[/]",
                l.difficulty,
                f"{l.estimated_duration_minutes}m",
            )

        console.print(table)
        done = sum(1 for l in lessons if l.status == "done")
        console.print(f"  Progress: {done}/{len(lessons)} lessons done")

    db.close()


if __name__ == "__main__":
    app()
