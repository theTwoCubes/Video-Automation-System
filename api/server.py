"""
FastAPI backend for the theTwoCubes GUI dashboard.
Run: uvicorn api.server:app --reload --port 8000
"""
import json
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.usage_log import get_usage_report

app = FastAPI(title="theTwoCubes Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = Path(__file__).parent.parent

# track test run status in memory (lightweight)
_test_runs: dict[str, dict] = {}


def _db():
    try:
        from db.database import init_db, SessionLocal
        init_db()
        return SessionLocal()
    except Exception:
        return None


#  Courses & Lessons 

@app.get("/api/courses")
def list_courses():
    db = _db()
    if not db:
        return []
    try:
        from db import models
        courses = db.query(models.Course).all()
        result = []
        for c in courses:
            lessons = db.query(models.Lesson).filter(models.Lesson.course_id == c.id).all()
            done = sum(1 for l in lessons if l.status == "done")
            result.append({
                "id": c.id,
                "title": c.title,
                "target_audience": getattr(c, "target_audience", ""),
                "total_lessons": len(lessons),
                "done_lessons": done,
                "pending_lessons": sum(1 for l in lessons if l.status == "pending"),
                "processing_lessons": sum(1 for l in lessons if l.status == "processing"),
                "failed_lessons": sum(1 for l in lessons if l.status == "failed"),
            })
        return result
    finally:
        db.close()


@app.get("/api/courses/{course_id}/lessons")
def list_lessons(course_id: str):
    db = _db()
    if not db:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        from db import models
        course = db.get(models.Course, course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        lessons = (
            db.query(models.Lesson)
            .filter(models.Lesson.course_id == course_id)
            .order_by(models.Lesson.position)
            .all()
        )
        result = []
        for l in lessons:
            summary = {}
            failed_error = ""
            if l.output_dir:
                sp = Path(l.output_dir) / "lesson_summary.json"
                if sp.exists():
                    summary = json.loads(sp.read_text(encoding="utf-8"))
                fp = Path(l.output_dir) / "FAILED.txt"
                if fp.exists():
                    failed_error = fp.read_text(encoding="utf-8")[:200]
            result.append({
                "id": l.id,
                "title": l.title,
                "position": l.position,
                "status": l.status,
                "output_dir": l.output_dir or "",
                "qa_score": summary.get("qa_score", 0),
                "seo_title": summary.get("seo_title", ""),
                "video_path": summary.get("video_path", ""),
                "thumbnail_path": summary.get("thumbnail_path", ""),
                "quiz_questions": summary.get("quiz_questions", 0),
                "slide_validation_issues": summary.get("slide_validation_issues", 0),
                "pacing_flags": summary.get("pacing_flags", 0),
                "failed_error": failed_error,
                "updated_at": str(getattr(l, "updated_at", "")),
            })
        return {"course": {"id": course.id, "title": course.title}, "lessons": result}
    finally:
        db.close()


@app.get("/api/lessons/{lesson_id}/slides")
def get_slides(lesson_id: str):
    db = _db()
    if not db:
        return {"slides": []}
    try:
        from db import models
        lesson = db.get(models.Lesson, lesson_id)
        if not lesson or not lesson.output_dir:
            raise HTTPException(status_code=404, detail="Lesson not found")
        slide_dir = Path(lesson.output_dir) / "slides"
        if not slide_dir.exists():
            return {"slides": []}
        slides = sorted(slide_dir.glob("*.png"))
        return {"slides": [str(s) for s in slides]}
    finally:
        db.close()


#  Video Generation 

@app.post("/api/courses/{course_id}/generate")
def trigger_generation(course_id: str, background_tasks: BackgroundTasks):
    """Trigger next video generation in background."""
    script = ROOT / "scripts" / "generate_next_video.py"
    background_tasks.add_task(
        subprocess.run,
        [sys.executable, str(script), "--course-id", course_id],
        cwd=str(ROOT),
    )
    return {"status": "started", "message": "Generation started in background"}


#  Test Pipeline 

@app.get("/api/test/fixtures")
def list_fixtures():
    """List all available fixture files."""
    from pipelines.test_pipeline import list_fixtures
    return list_fixtures()


class TestRunRequest(BaseModel):
    fixture_path: str = "tests/fixtures/cpp_variables_lesson.json"
    force_restart: bool = False
    from_step: str = "slides"


@app.post("/api/test/run")
def run_test(req: TestRunRequest, background_tasks: BackgroundTasks):
    """Trigger a test pipeline run with fixture data."""
    run_id = f"run_{datetime.utcnow().strftime('%H%M%S')}"
    _test_runs[run_id] = {
        "id": run_id,
        "status": "running",
        "fixture": req.fixture_path,
        "started_at": datetime.utcnow().isoformat(),
        "video_path": None,
        "error": None,
    }

    def _do_run():
        try:
            from pipelines.test_pipeline import run_test_pipeline
            result = run_test_pipeline(
                fixture_path=req.fixture_path,
                force_restart=req.force_restart,
                from_step=req.from_step,
            )
            _test_runs[run_id]["status"] = "done" if not result.get("error") else "failed"
            _test_runs[run_id]["video_path"] = result.get("video_path", "")
            _test_runs[run_id]["error"] = result.get("error")
            _test_runs[run_id]["video_quality"] = result.get("video_quality", {})
            _test_runs[run_id]["completed_at"] = datetime.utcnow().isoformat()
        except Exception as e:
            _test_runs[run_id]["status"] = "failed"
            _test_runs[run_id]["error"] = str(e)
            _test_runs[run_id]["completed_at"] = datetime.utcnow().isoformat()

    background_tasks.add_task(_do_run)
    return {"run_id": run_id, "status": "started"}


@app.get("/api/test/runs")
def list_test_runs():
    """Return all test run statuses."""
    return list(_test_runs.values())


@app.get("/api/test/runs/{run_id}")
def get_test_run(run_id: str):
    if run_id not in _test_runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return _test_runs[run_id]


#  Quiz 

@app.get("/api/lessons/{lesson_id}/quiz")
def get_quiz(lesson_id: str):
    """Return quiz questions for a lesson."""
    db = _db()
    try:
        if db:
            from db import models
            lesson = db.get(models.Lesson, lesson_id)
            if lesson and lesson.output_dir:
                qp = Path(lesson.output_dir) / "quiz.json"
                if qp.exists():
                    return json.loads(qp.read_text(encoding="utf-8"))
    finally:
        if db:
            db.close()
    return {"lesson_id": lesson_id, "questions": []}


#  Failed Lessons Alert 

@app.get("/api/alerts")
def get_alerts():
    """
    Returns aggregate alert counts across all courses.
    Used by GUI to show red banner if any lessons failed.
    """
    db = _db()
    if not db:
        return {"failed_lessons": 0, "details": []}
    try:
        from db import models
        failed = db.query(models.Lesson).filter(models.Lesson.status == "failed").all()
        details = []
        for l in failed:
            err = ""
            if l.output_dir:
                fp = Path(l.output_dir) / "FAILED.txt"
                if fp.exists():
                    err = fp.read_text(encoding="utf-8")[:200]
            details.append({
                "lesson_id": l.id,
                "lesson_title": l.title,
                "course_id": l.course_id,
                "error": err or getattr(l, "error", ""),
            })
        return {"failed_lessons": len(failed), "details": details}
    finally:
        db.close()


#  Usage & Health 

@app.get("/api/usage")
def get_usage():
    return get_usage_report()


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.1"}
