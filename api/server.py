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


from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile, Form
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
                    tags_parsed = []
                    try:
                        import json
                        tags_parsed = json.loads(src.topic_tags) if src.topic_tags else []
                    except:
                        pass
                    source_data = {
                        "id": src.id,
                        "name": src.name,
                        "type": src.type,
                        "chunk_count": src.chunk_count,
                        "status": src.status,
                        "topic_tags": tags_parsed
                    }

            result.append({
                "id": c.id,
                "title": c.title,
                "target_audience": getattr(c, "target_audience", ""),
                "source": source_data,
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


#  Knowledge Ingestion 

class IngestRequest(BaseModel):
    source: str
    name: str
    source_type: str = "pdf"
    tags: str = ""

@app.post("/api/courses/{course_id}/source")
def add_knowledge_source(
    course_id: str, 
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    source_type: str = Form(...),
    source: str = Form(None),
    file: UploadFile = File(None)
):
    db = _db()
    if not db:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        from db import models
        course = db.get(models.Course, course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        topic = course.topic
    finally:
        db.close()

    task_id = f"ingest_{datetime.utcnow().strftime('%H%M%S')}"
    _ingest_tasks[task_id] = {"status": "running", "source_id": None, "error": None}

    # If it's a PDF upload, save it to a temporary file
    final_source = source
    if source_type == "pdf" and file:
        import shutil
        upload_dir = Path("data/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / f"{task_id}_{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        final_source = str(file_path.absolute())

    def _do_ingest():
        try:
            from services.knowledge.ingestion import KnowledgeIngestionService
            svc = KnowledgeIngestionService()
            tag_list = [topic.lower()]
            sid = svc.ingest(
                name=name,
                source_type=source_type,
                path_or_url=final_source,
                topic_tags=tag_list,
            )
            # Link to course
            db2 = _db()
            if db2:
                from db import models
                c = db2.get(models.Course, course_id)
                if c:
                    c.source_id = sid
                    db2.commit()
                db2.close()

            _ingest_tasks[task_id]["status"] = "done"
            _ingest_tasks[task_id]["source_id"] = sid
        except Exception as e:
            _ingest_tasks[task_id]["status"] = "failed"
            _ingest_tasks[task_id]["error"] = str(e)

    background_tasks.add_task(_do_ingest)
    return {"task_id": task_id, "status": "started"}

@app.get("/api/ingest/{task_id}")
def get_ingest_status(task_id: str):
    if task_id not in _ingest_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return _ingest_tasks[task_id]


class QueryRequest(BaseModel):
    query: str

@app.post("/api/courses/{course_id}/query")
def query_knowledge(course_id: str, req: QueryRequest):
    db = _db()
    if not db:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        from db import models
        course = db.get(models.Course, course_id)
        if not course or not course.source_id:
            raise HTTPException(status_code=400, detail="Course has no knowledge source")
        
        # Query Chroma
        from services.knowledge.ingestion import KnowledgeIngestionService
        svc = KnowledgeIngestionService()
        collection = svc._get_collection(course.source_id)
        
        embeds = svc.embedder.embed(req.query)
        results = collection.query(
            query_embeddings=[embeds],
            n_results=3
        )
        
        chunks = []
        if results and results["documents"]:
            for doc in results["documents"][0]:
                chunks.append(doc)
        
        return {"chunks": chunks}
    finally:
        db.close()


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
            raise HTTPException(status_code=400, detail="Course or knowledge source not found")
        source_id = course.source_id
        topic = course.topic
        target_audience = course.target_audience
    finally:
        db.close()

    task_id = f"curr_{datetime.utcnow().strftime('%H%M%S')}"
    _curricula_tasks[task_id] = {"status": "running", "curriculum": None, "error": None}

    def _do_generate():
        try:
            from agents.curriculum_agent import CurriculumAgent
            agent = CurriculumAgent()
            state = {
                "source_id": source_id,
                "topic": topic,
                "target_audience": target_audience,
                "min_lessons": req.min_lessons,
            }
            res = agent.run(state)
            
            # Save curriculum to DB automatically
            db2 = _db()
            if db2:
                from db import models
                c = db2.get(models.Course, req.course_id)
                if c:
                    curr = res.get("curriculum", {})
                    c.curriculum = json.dumps(curr)
                    db2.commit()
                db2.close()

            _curricula_tasks[task_id]["status"] = "done"
            _curricula_tasks[task_id]["curriculum"] = res.get("curriculum")
        except Exception as e:
            _curricula_tasks[task_id]["status"] = "failed"
            _curricula_tasks[task_id]["error"] = str(e)

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
            f.write(f"\\n--- Started run at {datetime.utcnow().isoformat()} ---\\n")
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
