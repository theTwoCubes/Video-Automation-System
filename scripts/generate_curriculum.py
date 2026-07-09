#!/usr/bin/env python3
"""
Generate a course curriculum from an ingested knowledge source.

Usage:
  python scripts/generate_curriculum.py --source-id <source_id> --topic "C Programming"
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from db.database import init_db, SessionLocal
from db import models
from agents.curriculum_agent import CurriculumAgent

app = typer.Typer()
console = Console()


@app.command()
def main(
    source_id: str = typer.Option(..., "--source-id", help="Source ID from ingest step"),
    topic: str = typer.Option(..., "--topic", help="Course topic (e.g. C Programming)"),
    audience: str = typer.Option("beginners", "--audience", help="Target audience"),
    source_name: str = typer.Option("", "--source-name", help="Source name (optional)"),
):
    init_db()
    console.print(Panel(f"[bold green]Generating curriculum for:[/] {topic}", title="theTwoCubes Curriculum"))

    # get source info
    db = SessionLocal()
    source = db.get(models.KnowledgeSource, source_id)
    db.close()

    if not source:
        console.print(f"[red]Source not found: {source_id}[/]")
        raise typer.Exit(1)

    state = {
        "source_id": source_id,
        "topic": topic,
        "target_audience": audience,
        "source_name": source_name or source.name,
    }

    agent = CurriculumAgent()
    result = agent.run(state)
    curriculum = result.get("curriculum", {})

    # save course to DB
    db = SessionLocal()
    try:
        course = models.Course(
            title=curriculum.get("course_title", topic),
            topic=topic,
            description=curriculum.get("course_description", ""),
            target_audience=audience,
            source_id=source_id,
            curriculum=json.dumps(curriculum),
            status="draft",
        )
        db.add(course)
        db.flush()
        course_id = course.id

        # save lessons
        for lesson_data in curriculum.get("lessons", []):
            lesson = models.Lesson(
                course_id=course_id,
                title=lesson_data["title"],
                position=lesson_data["position"],
                topic_tags=json.dumps(lesson_data.get("topic_tags", [])),
                difficulty=lesson_data.get("difficulty", "beginner"),
                estimated_duration_minutes=lesson_data.get("estimated_duration_minutes", 12),
                prerequisites=json.dumps(lesson_data.get("prerequisites", [])),
                status="pending",
            )
            db.add(lesson)

        db.commit()
    finally:
        db.close()

    # display results
    table = Table(title=f"Course: {curriculum.get('course_title', topic)}")
    table.add_column("#", style="dim")
    table.add_column("Lesson Title", style="cyan")
    table.add_column("Difficulty", style="yellow")
    table.add_column("Duration")

    for lesson in curriculum.get("lessons", [])[:20]:
        table.add_row(
            str(lesson["position"]),
            lesson["title"],
            lesson.get("difficulty", "beginner"),
            f"{lesson.get('estimated_duration_minutes', 12)} min",
        )

    console.print(table)
    console.print(f"\n[bold green]Course created![/] Course ID: [cyan]{course_id}[/]")
    console.print(f"Generate your first video:\n  python scripts/generate_next_video.py --course-id {course_id}")


if __name__ == "__main__":
    app()
