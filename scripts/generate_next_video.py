#!/usr/bin/env python3
"""
Generate the next pending video for a course.

Usage:
  python scripts/generate_next_video.py --course-id <course_id>
  python scripts/generate_next_video.py --course-id <course_id> --lesson-id <specific_lesson_id>
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
from datetime import datetime, timezone

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from db.database import init_db, SessionLocal
from db import models
from pipelines.full_video_pipeline import run_pipeline

app = typer.Typer()
console = Console()


@app.command()
def main(
    course_id: str = typer.Option(..., "--course-id", help="Course ID"),
    lesson_id: str = typer.Option("", "--lesson-id", help="Specific lesson ID (optional)"),
):
    init_db()

    db = SessionLocal()
    try:
        course = db.get(models.Course, course_id)
        if not course:
            console.print(f"[red]Course not found: {course_id}[/]")
            raise typer.Exit(1)

        if lesson_id:
            lesson = db.get(models.Lesson, lesson_id)
            if not lesson or lesson.course_id != course_id:
                console.print(f"[red]Lesson not found: {lesson_id}[/]")
                raise typer.Exit(1)
        else:
            # find next pending lesson
            lesson = (
                db.query(models.Lesson)
                .filter(
                    models.Lesson.course_id == course_id,
                    models.Lesson.status == "pending",
                )
                .order_by(models.Lesson.position)
                .first()
            )

        if not lesson:
            console.print("[yellow]No pending lessons found. All lessons are done or in progress.[/]")
            raise typer.Exit(0)

        source_id = course.source_id
        topic_tags = json.loads(lesson.topic_tags or "[]")
        prerequisites = json.loads(lesson.prerequisites or "[]")
        difficulty = getattr(lesson, 'difficulty', 'beginner')

        # Load section declarations from the curriculum plan
        curriculum = json.loads(course.curriculum or "{}")
        proc_source_id = curriculum.get("source_id", "")
        lecture_plan = next(
            (lec for lec in curriculum.get("lectures", []) if lec.get("title") == lesson.title),
            {}
        )
        primary_sections = lecture_plan.get("primary_sections", [])
        reference_sections = lecture_plan.get("reference_sections", [])

        # real title of the next lesson in the curriculum, if any - grounds the
        # script's "next time..." teaser instead of letting the LLM invent one
        next_lesson = (
            db.query(models.Lesson)
            .filter(
                models.Lesson.course_id == course_id,
                models.Lesson.position == lesson.position + 1,
            )
            .first()
        )
        next_lesson_title = next_lesson.title if next_lesson else ""

    finally:
        db.close()

    console.print(Panel(
        f"[bold cyan]Lesson {lesson.position}:[/] {lesson.title}\n"
        f"[dim]Course: {course.title}[/]",
        title="[bold green]theTwoCubes Video Generator[/]",
    ))

    start_time = time.time()

    # mark as in-progress
    db = SessionLocal()
    try:
        lesson_obj = db.get(models.Lesson, lesson.id)
        lesson_obj.status = "processing"
        db.commit()
    finally:
        db.close()

    try:
        final_state = run_pipeline(
            source_id=source_id,
            proc_source_id=proc_source_id,
            primary_sections=primary_sections,
            reference_sections=reference_sections,
            course_id=course_id,
            course_title=course.title,
            lesson_id=lesson.id,
            lesson_title=lesson.title,
            lesson_position=lesson.position,
            topic_tags=topic_tags,
            prerequisites=prerequisites,
            target_audience=course.target_audience,
            estimated_duration_minutes=lesson.estimated_duration_minutes,
            difficulty=difficulty,
            next_lesson_title=next_lesson_title,
        )

        elapsed = time.time() - start_time
        qa_report = final_state.get("qa_report") or {}
        qa_score = qa_report.get("score", 0)
        status = "done" if not final_state.get("error") else "failed"

        # update lesson status in DB
        db = SessionLocal()
        try:
            lesson_obj = db.get(models.Lesson, lesson.id)
            lesson_obj.status = status
            lesson_obj.output_dir = final_state.get("output_dir", "")
            lesson_obj.updated_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

        # print summary
        table = Table(title="Pipeline Summary", show_header=False)
        table.add_column("Key", style="dim")
        table.add_column("Value", style="cyan")

        seo = final_state.get("seo_metadata", {}) or {}
        table.add_row("Status", "[green]Done[/]" if status == "done" else "[red]Failed[/]")
        table.add_row("Time", f"{elapsed:.0f}s")
        table.add_row("QA Score", f"{qa_score}/100")
        table.add_row("YouTube Title", seo.get("title", "N/A")[:70])
        if final_state.get("video_path"):
            table.add_row("Video", final_state["video_path"])
        if final_state.get("thumbnail_path"):
            table.add_row("Thumbnail", final_state["thumbnail_path"])
        output_dir = final_state.get("output_dir", "")
        if output_dir:
            table.add_row("Metadata", f"{output_dir}/youtube_metadata.txt")

        console.print(table)

        if qa_score < 70:
            console.print("\n[yellow]QA score below 70. Review recommended before uploading.[/]")

    except Exception as e:
        console.print(f"\n[red]Pipeline failed: {e}[/]")
        db = SessionLocal()
        try:
            lesson_obj = db.get(models.Lesson, lesson.id)
            lesson_obj.status = "failed"
            db.commit()
        finally:
            db.close()
        raise


if __name__ == "__main__":
    app()
