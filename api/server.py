"""
FastAPI backend for the theTwoCubes GUI dashboard.
Run: uvicorn api.server:app --reload --port 8000
"""
import json
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime, timezone


from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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

# Serve rendered output (slides, audio, video) as static assets
_output_dir = ROOT / "output"
_output_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=_output_dir), name="static")

# track test run status in memory (lightweight)
_test_runs: dict[str, dict] = {}


def _db():
    try:
        from db.database import init_db, SessionLocal
        init_db()
        return SessionLocal()
    except Exception:
        return None


#  In-memory Task Tracking 

_ingest_tasks: dict[str, dict] = {}
_curricula_tasks: dict[str, dict] = {}

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
            source_data = None
            if c.source_id:
                src = db.get(models.KnowledgeSource, c.source_id)
                if src:
                    source_data = {
                        "id": src.id,
                        "name": src.name,
                        "section_count": src.section_count,
                        "status": src.status,
                    }
            import json
            curriculum_data = None
            if c.curriculum:
                try:
                    curriculum_data = json.loads(c.curriculum)
                except Exception:
                    pass

            result.append({
                "id": c.id,
                "title": c.title,
                "topic": c.topic,
                "target_audience": getattr(c, "target_audience", ""),
                "source": source_data,
                "curriculum": curriculum_data,
                "total_lessons": len(lessons),
                "done_lessons": done,
                "pending_lessons": sum(1 for l in lessons if l.status == "pending"),
                "processing_lessons": sum(1 for l in lessons if l.status == "processing"),
                "failed_lessons": sum(1 for l in lessons if l.status == "failed"),
            })
        return result
    finally:
        db.close()

class CourseCreateRequest(BaseModel):
    title: str
    topic: str
    target_audience: str = "beginners"
    difficulty: str = "mixed"

@app.post("/api/courses")
def create_course(req: CourseCreateRequest):
    db = _db()
    if not db:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        from db import models
        import uuid
        course_id = req.topic.lower().replace(" ", "_").replace("-", "_") + "_" + str(uuid.uuid4())[:4]
        course = models.Course(
            id=course_id,
            title=req.title,
            topic=req.topic,
            target_audience=req.target_audience,
            difficulty=req.difficulty,
        )
        db.add(course)
        db.commit()
        return {"id": course.id, "title": course.title}
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



# PDF Processing (replaces old ingestion + ChromaDB)

@app.post("/api/courses/{course_id}/source")
def add_pdf_source(
    course_id: str,
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Upload a single PDF to a course. Processes it into a section index.
    This is the ONLY way to add a knowledge source to a course.
    """
    db = _db()
    if not db:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        from db import models
        course = db.get(models.Course, course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
    finally:
        db.close()

    # Save uploaded PDF
    import shutil
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = file.filename.replace(" ", "_")
    file_path = upload_dir / f"{course_id}_{safe_name}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    task_id = f"proc_{datetime.now(timezone.utc).strftime('%H%M%S')}"
    _ingest_tasks[task_id] = {"status": "running", "source_id": None, "error": None}

    def _do_process():
        try:
            from services.knowledge.pdf_processor import PDFProcessor
            from db.database import SessionLocal
            from db import models as m
            processor = PDFProcessor()
            sections, toc_text, proc_source_id = processor.process(str(file_path))

            db2 = SessionLocal()
            try:
                # Create or update KnowledgeSource record
                src = m.KnowledgeSource(
                    name=name,
                    type="pdf",
                    file_path=str(file_path),
                    sections_path=str(Path("data/processed") / proc_source_id / "sections.json"),
                    toc_text=toc_text,
                    section_count=len(sections),
                    status="ready",
                )
                db2.add(src)
                db2.flush()  # Ensure src.id is generated before assignment
                # Link to course
                c = db2.get(m.Course, course_id)
                if c:
                    c.source_id = src.id
                db2.commit()
                _ingest_tasks[task_id]["status"] = "done"
                _ingest_tasks[task_id]["source_id"] = src.id
                _ingest_tasks[task_id]["section_count"] = len(sections)
            finally:
                db2.close()
        except Exception as e:
            _ingest_tasks[task_id]["status"] = "failed"
            _ingest_tasks[task_id]["error"] = str(e)
            print(f"[ProcessPDF] ERROR: {e}")

    background_tasks.add_task(_do_process)
    return {"task_id": task_id, "status": "started"}


@app.get("/api/ingest/{task_id}")
def get_ingest_status(task_id: str):
    if task_id not in _ingest_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return _ingest_tasks[task_id]


# Section Browser (replaces old query endpoint)

@app.get("/api/courses/{course_id}/sections")
def list_sections(course_id: str):
    """Return all section IDs and titles for a course's processed PDF."""
    db = _db()
    if not db:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        from db import models
        course = db.get(models.Course, course_id)
        if not course or not course.source_id:
            raise HTTPException(status_code=400, detail="Course has no PDF source")
        src = db.get(models.KnowledgeSource, course.source_id)
        if not src or not src.sections_path:
            raise HTTPException(status_code=400, detail="PDF not yet processed")
    finally:
        db.close()

    from services.knowledge.pdf_processor import PDFProcessor
    # Derive source_id from sections_path (parent dir name)
    proc_source_id = Path(src.sections_path).parent.name
    processor = PDFProcessor()
    section_ids = processor.list_section_ids(proc_source_id)
    sections_data = json.loads(Path(src.sections_path).read_text(encoding="utf-8"))
    return {
        "section_count": len(section_ids),
        "sections": [
            {"id": sid, "title": sections_data[sid]["title"], "children": sections_data[sid]["children"]}
            for sid in section_ids
        ]
    }


@app.get("/api/courses/{course_id}/sections/{section_id}")
def get_section_text(course_id: str, section_id: str):
    """Return the full text of a specific section for preview."""
    db = _db()
    if not db:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        from db import models
        course = db.get(models.Course, course_id)
        if not course or not course.source_id:
            raise HTTPException(status_code=400, detail="Course has no PDF source")
        src = db.get(models.KnowledgeSource, course.source_id)
    finally:
        db.close()

    proc_source_id = Path(src.sections_path).parent.name
    from services.knowledge.pdf_processor import PDFProcessor
    processor = PDFProcessor()
    text = processor.get_sections(proc_source_id, [section_id])
    return {"section_id": section_id, "text": text}


#  Curriculum Generation 

class CurriculaGenerateRequest(BaseModel):
    course_id: str
    min_lessons: int = 30

@app.post("/api/curricula/generate")
def generate_curriculum(req: CurriculaGenerateRequest, background_tasks: BackgroundTasks):
    db = _db()
    if not db:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        from db import models
        course = db.get(models.Course, req.course_id)
        if not course or not course.source_id:
            raise HTTPException(status_code=400, detail="Course has no PDF source attached. Upload a PDF first.")
        src = db.get(models.KnowledgeSource, course.source_id)
        if not src or src.status != "ready":
            raise HTTPException(status_code=400, detail="PDF is not yet processed.")
        proc_source_id = Path(src.sections_path).parent.name
        topic = course.topic
        target_audience = course.target_audience
    finally:
        db.close()

    task_id = f"curr_{datetime.now(timezone.utc).strftime('%H%M%S')}"
    _curricula_tasks[task_id] = {"status": "running", "curriculum": None, "error": None}

    def _do_generate():
        try:
            from agents.curriculum_agent import CurriculumAgent
            from db.database import SessionLocal
            from db import models as m
            agent = CurriculumAgent()
            state = {
                "source_id": proc_source_id,
                "topic": topic,
                "target_audience": target_audience,
                "min_lessons": req.min_lessons,
            }
            res = agent.run(state)
            curriculum = res.get("curriculum", {})
            lectures = curriculum.get("lectures", [])

            db2 = SessionLocal()
            try:
                c = db2.get(m.Course, req.course_id)
                if c:
                    c.curriculum = json.dumps(curriculum)
                    # Create Lesson rows from the lecture plan
                    # Clear old lessons first
                    db2.query(m.Lesson).filter(m.Lesson.course_id == req.course_id).delete()
                    for lec in lectures:
                        lesson = m.Lesson(
                            course_id=req.course_id,
                            title=lec["title"],
                            position=lec["position"],
                            topic_tags=json.dumps(lec.get("topic_tags", [])),
                            difficulty=lec.get("difficulty", "beginner"),
                            estimated_duration_minutes=lec.get("estimated_minutes", 12),
                            prerequisites=json.dumps(lec.get("prerequisites", [])),
                            status="pending",
                        )
                        db2.add(lesson)
                    db2.commit()
            finally:
                db2.close()

            _curricula_tasks[task_id]["status"] = "done"
            _curricula_tasks[task_id]["curriculum"] = curriculum
            _curricula_tasks[task_id]["lecture_count"] = len(lectures)
        except Exception as e:
            _curricula_tasks[task_id]["status"] = "failed"
            _curricula_tasks[task_id]["error"] = str(e)
            print(f"[CurriculumGen] ERROR: {e}")

    background_tasks.add_task(_do_generate)
    return {"task_id": task_id, "status": "started"}

@app.get("/api/curricula/tasks/{task_id}")
def get_curricula_status(task_id: str):
    if task_id not in _curricula_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return _curricula_tasks[task_id]

class CurriculumEditRequest(BaseModel):
    curriculum: str

@app.put("/api/courses/{course_id}/curriculum")
def update_curriculum(course_id: str, req: CurriculumEditRequest):
    db = _db()
    if not db:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        from db import models
        course = db.get(models.Course, course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        course.curriculum = req.curriculum
        db.commit()
        return {"status": "success", "message": "Curriculum updated"}
    finally:
        db.close()


#  Video Generation 

from fastapi.responses import StreamingResponse
import time

@app.post("/api/courses/{course_id}/generate")
def trigger_generation(course_id: str, background_tasks: BackgroundTasks):
    """Trigger next video generation in background."""
    script = ROOT / "scripts" / "generate_next_video.py"
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{course_id}.log"
    
    def _run_with_logs():
        with open(log_file, "a") as f:
            f.write(f"\nStarted run at {datetime.now(timezone.utc).isoformat()}\n")
            subprocess.run(
                [sys.executable, str(script), "--course-id", course_id],
                cwd=str(ROOT),
                stdout=f,
                stderr=subprocess.STDOUT
            )

    background_tasks.add_task(_run_with_logs)
    return {"status": "started", "message": "Generation started in background"}

@app.get("/api/logs/{course_id}")
def stream_logs(course_id: str):
    """SSE endpoint to stream live logs for a course generation."""
    log_file = ROOT / "logs" / f"{course_id}.log"
    
    def log_generator():
        if not log_file.exists():
            yield "data: Waiting for logs to start...\\n\\n"
            while not log_file.exists():
                time.sleep(1)
        
        with open(log_file, "r") as f:
            f.seek(0, os.SEEK_END) # start from end to only get live logs
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                yield f"data: {line}\\n\\n"
                
    return StreamingResponse(log_generator(), media_type="text/event-stream")


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
    run_id = f"run_{datetime.now(timezone.utc).strftime('%H%M%S')}"
    _test_runs[run_id] = {
        "id": run_id,
        "status": "running",
        "fixture": req.fixture_path,
        "started_at": datetime.now(timezone.utc).isoformat(),
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
            _test_runs[run_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            _test_runs[run_id]["status"] = "failed"
            _test_runs[run_id]["error"] = str(e)
            _test_runs[run_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

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

#  Video Generation & Logging 

@app.post("/api/lessons/{lesson_id}/generate")
def generate_lesson(lesson_id: str, background_tasks: BackgroundTasks):
    db = _db()
    if not db:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        from db import models
        lesson = db.get(models.Lesson, lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")
        course_id = lesson.course_id
        
        # Prepare output directory
        log_dir = Path("output") / lesson_id
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "pipeline.log"
        
        def _run_pipeline():
            import subprocess
            import os
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"Starting video generation for lesson {lesson_id}...\n")
                process = subprocess.Popen(
                    ["python", "-m", "scripts.generate_next_video", "--course-id", course_id, "--lesson-id", lesson_id],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    bufsize=1,
                    cwd=str(Path.cwd()),
                    env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
                )
                for line in process.stdout:
                    f.write(line)
                    f.flush()
                process.wait()
                f.write(f"\nPipeline finished with exit code {process.returncode}\n")
        
        background_tasks.add_task(_run_pipeline)
        return {"status": "started", "lesson_id": lesson_id}
    finally:
        db.close()

from fastapi.responses import StreamingResponse
import asyncio

@app.get("/api/logs/lessons/{lesson_id}")
async def get_lesson_logs(lesson_id: str):
    log_file = Path("output") / lesson_id / "pipeline.log"
    
    async def log_generator():
        # Wait up to 5 seconds for the file to exist
        for _ in range(10):
            if log_file.exists():
                break
            await asyncio.sleep(0.5)
            
        if not log_file.exists():
            yield "data: Waiting for generation to start...\n\n"
            while not log_file.exists():
                await asyncio.sleep(1)
                
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line.strip()}\n\n"
                    if "Pipeline finished" in line:
                        break
                else:
                    await asyncio.sleep(0.5)
    
    return StreamingResponse(log_generator(), media_type="text/event-stream")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.1"}


#  PROFILES 

@app.get("/api/profiles")
def list_profiles_endpoint():
    from config.profile_loader import list_profiles
    return list_profiles()


@app.get("/api/profiles/{name}")
def get_profile(name: str):
    from config.profile_loader import load_profile
    return load_profile(name)


class ProfileSaveRequest(BaseModel):
    data: dict


@app.put("/api/profiles/{name}")
def save_profile_endpoint(name: str, req: ProfileSaveRequest):
    from config.profile_loader import save_profile as _save
    path = _save(name, req.data)
    return {"saved": str(path)}


@app.delete("/api/profiles/{name}")
def delete_profile_endpoint(name: str):
    from config.profile_loader import delete_profile as _del
    ok = _del(name)
    if not ok:
        raise HTTPException(status_code=400, detail="Cannot delete default profile")
    return {"deleted": name}


#  VOICES 

@app.get("/api/voices")
def list_voices():
    from config.profile_loader import get_voice_options
    return get_voice_options()


class VoicePreviewRequest(BaseModel):
    voice: str
    text: str = "Welcome to theTwoCubes Learning. Let us explore pointers in C plus plus."
    rate: str = "+0%"


@app.post("/api/voices/preview")
async def preview_voice(req: VoicePreviewRequest):
    import tempfile
    from fastapi.responses import FileResponse
    try:
        import edge_tts
    except ImportError:
        raise HTTPException(status_code=500, detail="edge-tts not installed")
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        out_path = f.name
    try:
        communicate = edge_tts.Communicate(req.text, req.voice, rate=req.rate)
        await communicate.save(out_path)
        return FileResponse(out_path, media_type="audio/mpeg", filename="preview.mp3")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


#  LESSONS (Testing Studio picker) 

@app.get("/api/lessons/rendered")
def list_rendered_lessons():
    results = []
    output_root = ROOT / "output"
    if not output_root.exists():
        return results
    for course_dir in sorted(output_root.iterdir()):
        if not course_dir.is_dir():
            continue
        for lesson_dir in sorted(course_dir.iterdir()):
            if not lesson_dir.is_dir():
                continue
            cp_dir = lesson_dir / "checkpoints"
            if not (cp_dir / "generate_slides.json").exists():
                continue
            lesson_id = lesson_dir.name.split("_", 1)[1] if "_" in lesson_dir.name else lesson_dir.name
            title = "Unknown"
            try:
                plan_cp = cp_dir / "plan_lesson.json"
                if plan_cp.exists():
                    plan = json.loads(plan_cp.read_text(encoding="utf-8"))
                    title = plan.get("lesson_plan", {}).get("title", title)
            except Exception:
                pass
            has_video = bool(list(lesson_dir.glob("*_final.mp4"))) or (lesson_dir / "lesson_rerendered.mp4").exists()
            results.append({
                "lesson_id": lesson_id,
                "course_dir": course_dir.name,
                "lesson_dir": lesson_dir.name,
                "title": title,
                "has_video": has_video,
                "checkpoints": [f.stem for f in sorted(cp_dir.glob("*.json"))],
            })
    return results


@app.get("/api/lessons/{lesson_id}/slides")
def get_lesson_slides(lesson_id: str):
    """Return slide image URLs for a lesson.

    Prefers slides from the isolated rerender folder (slides_rerender/) so the
    Testing Studio always shows the freshest renders without overwriting originals.
    Falls back to slides/ if no rerender exists yet.
    """
    output_root = ROOT / "output"
    for course_dir in output_root.iterdir():
        if not course_dir.is_dir():
            continue
        for lesson_dir in course_dir.iterdir():
            if lesson_id not in lesson_dir.name:
                continue
            # prefer isolated rerender folder
            for folder_name in ("slides_rerender", "slides"):
                slides_dir = lesson_dir / folder_name
                if slides_dir.exists():
                    paths = sorted(slides_dir.glob("*.png"))
                    if paths:
                        # return paths relative to the output root so /static/ can serve them
                        return [
                            str(p.relative_to(output_root)).replace("\\", "/")
                            for p in paths
                        ]
    raise HTTPException(status_code=404, detail=f"No slides found for lesson {lesson_id}")


@app.get("/api/lessons/{lesson_id}/video")
def get_lesson_video_path(lesson_id: str):
    output_root = ROOT / "output"
    for course_dir in output_root.iterdir():
        if not course_dir.is_dir():
            continue
        for lesson_dir in course_dir.iterdir():
            if lesson_id not in lesson_dir.name:
                continue
            p = lesson_dir / "lesson_rerendered.mp4"
            if p.exists():
                return {"path": str(p.relative_to(ROOT)).replace("\\", "/")}
            for vp in lesson_dir.glob("*_final.mp4"):
                return {"path": str(vp.relative_to(ROOT)).replace("\\", "/")}
    raise HTTPException(status_code=404, detail=f"Lesson {lesson_id} video not found")


#  RERENDER 

_rerender_tasks: dict = {}


class RerenderRequest(BaseModel):
    lesson_id: str
    steps: str = "all"
    profile: str = "testing"
    voice: str = ""
    music: str = ""


def _run_rerender(task_id: str, req: RerenderRequest):
    _rerender_tasks[task_id] = {
        "status": "running", "log": [],
        "started_at": datetime.now(timezone.utc).isoformat()
    }
    log = _rerender_tasks[task_id]["log"]
    try:
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "rerender_lesson.py"),
            "--lesson-id", req.lesson_id,
            "--steps", req.steps,
            "--profile", req.profile,
        ]
        if req.voice:
            cmd += ["--voice", req.voice]
        if req.music:
            cmd += ["--music", req.music]
        proc = subprocess.Popen(
            cmd, cwd=str(ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        for line in proc.stdout:
            log.append(line.rstrip())
        proc.wait()
        _rerender_tasks[task_id]["status"] = "done" if proc.returncode == 0 else "error"
        _rerender_tasks[task_id]["returncode"] = proc.returncode
    except Exception as e:
        _rerender_tasks[task_id]["status"] = "error"
        log.append(f"Exception: {e}")
    _rerender_tasks[task_id]["finished_at"] = datetime.now(timezone.utc).isoformat()


@app.post("/api/rerender")
def start_rerender(req: RerenderRequest, background_tasks: BackgroundTasks):
    import uuid
    task_id = "rr_" + uuid.uuid4().hex[:8]
    background_tasks.add_task(_run_rerender, task_id, req)
    return {"task_id": task_id}


@app.get("/api/rerender/{task_id}")
def get_rerender_status(task_id: str):
    if task_id not in _rerender_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return _rerender_tasks[task_id]


@app.get("/api/rerender/{task_id}/stream")
async def stream_rerender_log(task_id: str):
    import asyncio
    from fastapi.responses import StreamingResponse

    async def generator():
        sent = 0
        while True:
            task = _rerender_tasks.get(task_id)
            if not task:
                yield 'data: {"error": "not found"}\n\n'
                return
            log = task.get("log", [])
            while sent < len(log):
                import json as _json
                yield f"data: {_json.dumps({'line': log[sent]})}\n\n"
                sent += 1
            if task.get("status") in ("done", "error"):
                import json as _json
                yield f"data: {_json.dumps({'status': task['status']})}\n\n"
                return
            await asyncio.sleep(0.3)

    return StreamingResponse(generator(), media_type="text/event-stream")
