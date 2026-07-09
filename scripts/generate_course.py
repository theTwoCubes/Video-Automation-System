"""
Course Batch Runner — F.1 from FuturePLAN.md

Generates all pending lessons in a course sequentially.
Checkpoint-safe: if it crashes at lesson 47, restart continues from lesson 47.

Usage:
    python scripts/generate_course.py --course-id cpp_beginner
    python scripts/generate_course.py --course-id cpp_beginner --start-from 5
    python scripts/generate_course.py --course-id cpp_beginner --dry-run
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))



def _load_course(course_id: str) -> dict | None:
    try:
        from db.database import get_db_connection
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT * FROM courses WHERE id = ?", (course_id,)
            ).fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def _load_lessons(course_id: str) -> list[dict]:
    try:
        from db.database import get_db_connection
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM lessons WHERE course_id = ? ORDER BY position",
                (course_id,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def _mark_lesson_done(lesson_id: str, video_path: str):
    try:
        from db.database import get_db_connection
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE lessons SET status = 'done', video_path = ? WHERE id = ?",
                (video_path, lesson_id),
            )
            conn.commit()
    except Exception:
        pass


def _mark_lesson_failed(lesson_id: str, error: str):
    try:
        from db.database import get_db_connection
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE lessons SET status = 'failed', error = ? WHERE id = ?",
                (error[:500], lesson_id),
            )
            conn.commit()
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Generate all lessons in a course")
    parser.add_argument("--course-id", required=True, help="Course ID to process")
    parser.add_argument("--start-from", type=int, default=1, help="Start from lesson N (1-indexed)")
    parser.add_argument("--dry-run", action="store_true", help="List lessons but don't generate")
    parser.add_argument("--force-restart", action="store_true", help="Force re-generate all lessons")
    args = parser.parse_args()

    course = _load_course(args.course_id)
    if not course:
        print(f"Course '{args.course_id}' not found in DB.")
        return 1

    lessons = _load_lessons(args.course_id)
    if not lessons:
        print(f"No lessons found for course '{args.course_id}'.")
        return 1

    pending = [
        l for l in lessons
        if l.get("position", 0) >= args.start_from
        and (args.force_restart or l.get("status") not in ("done",))
    ]

    print(f"Course: {course.get('title', args.course_id)}")
    print(f"Total lessons: {len(lessons)}, Pending: {len(pending)}")
    print()

    if args.dry_run:
        for l in pending:
            status = l.get("status", "pending")
            print(f"  [{l['position']:3d}] {l['title']:<50s} [{status}]")
        return 0

    from pipelines.full_video_pipeline import run_pipeline

    succeeded = 0
    failed_list = []
    prev_summary = None
    start_time = datetime.now(timezone.utc)

    for idx, lesson in enumerate(pending):
        pos = lesson.get("position", idx + 1)
        lid = lesson["id"]
        title = lesson["title"]

        print(f"\n{'='*60}")
        print(f"Lesson {pos}/{len(lessons)}: {title}")
        print(f"{'='*60}")

        try:
            # Load section declarations from curriculum plan
            curriculum = json.loads(course.get("curriculum", "{}") or "{}")
            proc_source_id = curriculum.get("source_id", "")
            lecture_plan = next(
                (lec for lec in curriculum.get("lectures", []) if lec.get("title") == title),
                {}
            )
            primary_sections = lecture_plan.get("primary_sections", [])
            reference_sections = lecture_plan.get("reference_sections", [])

            final = run_pipeline(
                source_id=course.get("source_id", ""),
                proc_source_id=proc_source_id,
                primary_sections=primary_sections,
                reference_sections=reference_sections,
                course_id=args.course_id,
                course_title=course.get("title", ""),
                lesson_id=lid,
                lesson_title=title,
                lesson_position=pos,
                topic_tags=json.loads(lesson.get("topic_tags", "[]") or "[]"),
                prerequisites=json.loads(lesson.get("prerequisites", "[]") or "[]"),
                target_audience=course.get("target_audience", "beginners"),
                estimated_duration_minutes=lesson.get("estimated_duration_minutes", 12),
                difficulty=lesson.get("difficulty", "beginner"),
                force_restart=args.force_restart,
                previous_lesson_summary=prev_summary,
            )

            if final.get("error"):
                raise RuntimeError(final["error"])

            video_path = final.get("video_path", "")
            _mark_lesson_done(lid, video_path)

            # build previous_lesson_summary for next lesson (lesson continuity)
            prev_summary = {
                "title": title,
                "key_takeaways": (
                    final.get("seo_metadata", {}).get("key_takeaways", [])
                    or [b for s in (final.get("slide_contents") or [])
                        if s.get("layout") == "summary"
                        for b in s.get("bullets", [])][:5]
                ),
            }

            succeeded += 1
            elapsed = (datetime.now(timezone.utc) - start_time).seconds
            avg = elapsed // max(succeeded, 1)
            remaining = avg * (len(pending) - idx - 1)
            print(f"  Done. ETA for remaining: {remaining//60}m{remaining%60}s")

        except KeyboardInterrupt:
            print("\nInterrupted by user. Progress saved — restart to continue.")
            return 1
        except Exception as e:
            print(f"  FAILED: {e}")
            _mark_lesson_failed(lid, str(e))
            failed_list.append({"position": pos, "title": title, "error": str(e)})
            continue

    print(f"\n{'='*60}")
    print(f"Batch complete: {succeeded}/{len(pending)} lessons generated")
    if failed_list:
        print(f"  {len(failed_list)} failed:")
        for f in failed_list:
            print(f"    [{f['position']}] {f['title']}: {f['error'][:80]}")
    return 0 if not failed_list else 2


if __name__ == "__main__":
    sys.exit(main())
