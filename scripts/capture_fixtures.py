#!/usr/bin/env python3
"""
Capture fixtures: runs a REAL pipeline (with LLM calls) and saves all
LLM outputs to a fixture JSON so future test runs never need to call the AI again.

Usage:
  python scripts/capture_fixtures.py --lesson-id <id>
  python scripts/capture_fixtures.py --lesson-id cpp_vars_001 --output tests/fixtures/cpp_vars.json

This script reads an existing lesson's checkpoint files and bundles them
into a single self-contained fixture JSON.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import argparse
from pathlib import Path
from config.settings import settings


def capture_from_checkpoints(output_dir: str, lesson_meta: dict, out_path: str):
    """Read checkpoint JSON files and merge into a fixture."""
    cp_dir = Path(output_dir) / "checkpoints"
    if not cp_dir.exists():
        print(f"No checkpoints found at {cp_dir}")
        return

    fixture = {**lesson_meta}
    
    field_map = {
        "plan_lesson":       ["lesson_plan"],
        "write_script":      ["script"],
        "generate_code":     ["code_examples"],
        "generate_diagrams": ["diagrams", "diagram_image_paths"],
        "generate_slides":   ["slide_contents", "slide_image_paths", "slide_id_to_path"],
        "qa_check":          ["qa_report"],
        "generate_seo":      ["seo_metadata"],
    }

    for step, fields in field_map.items():
        cp_file = cp_dir / f"{step}.json"
        if cp_file.exists():
            data = json.loads(cp_file.read_text(encoding="utf-8"))
            for field in fields:
                if field in data and data[field] is not None:
                    fixture[field] = data[field]
            print(f"  Loaded: {step}")
        else:
            print(f"  Missing: {step}")

    # strip image paths from slide_contents (they'll be re-rendered)
    if "slide_contents" in fixture:
        for slide in fixture["slide_contents"]:
            slide.pop("_image_path", None)

    out_path_obj = Path(out_path)
    out_path_obj.parent.mkdir(parents=True, exist_ok=True)
    out_path_obj.write_text(json.dumps(fixture, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFixture saved: {out_path}")
    print(f"  Slides: {len(fixture.get('slide_contents', []))}")
    print(f"  Script segments: {len(fixture.get('script', {}).get('segments', []))}")


def capture_from_lesson_id(lesson_id: str, out_path: str):
    """Read lesson metadata from the DB and capture its checkpoints."""
    try:
        from db.database import init_db, SessionLocal
        from db import models
        init_db()
        db = SessionLocal()
        lesson = db.get(models.Lesson, lesson_id)
        if not lesson:
            print(f"Lesson {lesson_id} not found in DB.")
            return
        course = db.get(models.Course, lesson.course_id)
        meta = {
            "lesson_id": lesson.id,
            "lesson_title": lesson.title,
            "course_id": lesson.course_id,
            "course_title": course.title if course else "",
            "lesson_position": lesson.position,
            "target_audience": getattr(course, "target_audience", "beginners"),
            "topic_tags": [],
            "prerequisites": [],
        }
        output_dir = lesson.output_dir or ""
        db.close()
        capture_from_checkpoints(output_dir, meta, out_path)
    except Exception as e:
        print(f"DB error: {e}")
        print("Try --output-dir instead.")


def main():
    parser = argparse.ArgumentParser(description="Capture fixture from pipeline checkpoints")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--lesson-id", help="Lesson ID to capture from DB")
    group.add_argument("--output-dir", help="Direct path to lesson output directory")
    parser.add_argument("--output", default="", help="Output fixture JSON path")
    parser.add_argument("--lesson-title", default="Test Lesson")
    parser.add_argument("--course-title", default="Test Course")
    args = parser.parse_args()

    if not args.output:
        slug = (args.lesson_id or "test").replace("-", "_").replace(" ", "_")
        args.output = f"tests/fixtures/{slug}.json"

    if args.lesson_id:
        capture_from_lesson_id(args.lesson_id, args.output)
    else:
        meta = {
            "lesson_id": "captured_lesson",
            "lesson_title": args.lesson_title,
            "course_title": args.course_title,
        }
        capture_from_checkpoints(args.output_dir, meta, args.output)


if __name__ == "__main__":
    main()
