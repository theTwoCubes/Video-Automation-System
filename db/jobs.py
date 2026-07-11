"""
Durable job store - replaces the in-memory task dicts the API used to keep
(_ingest_tasks, _curricula_tasks, _test_runs, _rerender_tasks). Backing these
with SQLite means job status survives a reload, doesn't grow unbounded in
memory, and works when the API runs with more than one worker (a poll can hit a
worker that never saw the task otherwise).

Each job is (id, kind, status, data-JSON). Helpers read/merge the JSON blob so
callers never mutate a detached dict expecting it to persist.
"""
from __future__ import annotations

import json
from typing import Optional

from db.database import SessionLocal, init_db
from db import models

_INITED = False


def _ensure() -> None:
    global _INITED
    if not _INITED:
        init_db()
        _INITED = True


def create_job(kind: str, job_id: str, **data) -> str:
    """Create (or replace) a job. `status` may be passed in data; defaults to
    'running'."""
    _ensure()
    status = data.pop("status", "running")
    db = SessionLocal()
    try:
        db.merge(models.Job(id=job_id, kind=kind, status=status, data=json.dumps(data)))
        db.commit()
    finally:
        db.close()
    return job_id


def update_job(job_id: str, **fields) -> None:
    """Merge `fields` into a job's JSON blob. A `status` field is also mirrored
    onto the indexed column so it can be queried cheaply."""
    _ensure()
    db = SessionLocal()
    try:
        j = db.get(models.Job, job_id)
        if not j:
            return
        blob = json.loads(j.data or "{}")
        blob.update(fields)
        if "status" in fields:
            j.status = fields["status"]
        j.data = json.dumps(blob, default=str)
        db.commit()
    finally:
        db.close()


def append_log(job_id: str, line: str) -> None:
    """Append one line to a job's `log` list (used by the re-render stream)."""
    _ensure()
    db = SessionLocal()
    try:
        j = db.get(models.Job, job_id)
        if not j:
            return
        blob = json.loads(j.data or "{}")
        blob.setdefault("log", []).append(line)
        j.data = json.dumps(blob, default=str)
        db.commit()
    finally:
        db.close()


def get_job(job_id: str) -> Optional[dict]:
    """Return the job as a plain dict (with `status` merged in), or None."""
    _ensure()
    db = SessionLocal()
    try:
        j = db.get(models.Job, job_id)
        if not j:
            return None
        blob = json.loads(j.data or "{}")
        blob["status"] = j.status
        blob["id"] = j.id
        blob["kind"] = j.kind
        return blob
    finally:
        db.close()


def list_jobs(kind: Optional[str] = None) -> list[dict]:
    _ensure()
    db = SessionLocal()
    try:
        q = db.query(models.Job)
        if kind:
            q = q.filter(models.Job.kind == kind)
        out = []
        for j in q.order_by(models.Job.created_at.desc()).all():
            blob = json.loads(j.data or "{}")
            blob["status"] = j.status
            blob["id"] = j.id
            blob["kind"] = j.kind
            out.append(blob)
        return out
    finally:
        db.close()
