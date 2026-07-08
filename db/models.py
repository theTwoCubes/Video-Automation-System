import uuid
from datetime import datetime
from sqlalchemy import (
    String, Text, Integer, Float, Boolean, DateTime,
    ForeignKey, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.database import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(50))  # pdf | url | markdown | repo
    file_path: Mapped[str] = mapped_column(Text, nullable=True)
    original_url: Mapped[str] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=True)
    topic_tags: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(255))
    topic: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="mixed")
    target_audience: Mapped[str] = mapped_column(String(100), default="beginners")
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_sources.id"), nullable=True)
    curriculum: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lessons: Mapped[list["Lesson"]] = relationship("Lesson", back_populates="course")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(String(36), ForeignKey("courses.id"))
    title: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer)
    topic_tags: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    difficulty: Mapped[str] = mapped_column(String(20), default="beginner")
    estimated_duration_minutes: Mapped[int] = mapped_column(Integer, default=12)
    prerequisites: Mapped[str] = mapped_column(Text, default="[]")  # JSON titles
    status: Mapped[str] = mapped_column(String(30), default="pending")
    # pending | planning | scripting | rendering | qa | done | failed
    output_dir: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    course: Mapped["Course"] = relationship("Course", back_populates="lessons")
    script: Mapped["Script"] = relationship("Script", back_populates="lesson", uselist=False)
    qa_report: Mapped["QAReport"] = relationship("QAReport", back_populates="lesson", uselist=False)
    seo: Mapped["SEOMetadata"] = relationship("SEOMetadata", back_populates="lesson", uselist=False)


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    lesson_id: Mapped[str] = mapped_column(String(36), ForeignKey("lessons.id"), unique=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[str] = mapped_column(Text)  # JSON ScriptJSON
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    estimated_duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="script")


class QAReport(Base):
    __tablename__ = "qa_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    lesson_id: Mapped[str] = mapped_column(String(36), ForeignKey("lessons.id"), unique=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    checks: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False)
    issues: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="qa_report")


class SEOMetadata(Base):
    __tablename__ = "seo_metadata"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    lesson_id: Mapped[str] = mapped_column(String(36), ForeignKey("lessons.id"), unique=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    tags: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    chapters: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    pinned_comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="seo")


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    lesson_id: Mapped[str] = mapped_column(String(36), ForeignKey("lessons.id"))
    job_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
