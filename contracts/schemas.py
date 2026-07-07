from typing import Optional, List, Any
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class LessonSection(BaseModel):
    id: str
    title: str
    type: str  # hook | concept | deep_dive | code_demo | mistakes | summary | exercise | whats_next
    duration_seconds: int
    needs_diagram: bool = False
    needs_code: bool = False


class LessonPlan(BaseModel):
    lesson_id: str
    title: str
    objectives: List[str]
    sections: List[LessonSection]
    duration_estimate_minutes: int
    difficulty: str  # beginner | intermediate | advanced
    prerequisites: List[str]
    key_concepts: List[str]


class ScriptSegment(BaseModel):
    id: str
    type: str  # narration | code_demo | diagram
    text: str = ""
    duration_estimate_seconds: int = 0
    visual_cue: str = ""  # slide:title, code:id, diagram:id
    pause_after_ms: int = 300
    code_ref: str = ""
    diagram_ref: str = ""


class ScriptJSON(BaseModel):
    lesson_id: str
    segments: List[ScriptSegment]
    total_words: int = 0
    estimated_duration_seconds: int = 0


class CodeExample(BaseModel):
    id: str
    lesson_id: str
    language: str
    source_code: str
    expected_output: str = ""
    actual_output: str = ""
    is_validated: bool = False
    annotations: List[dict] = Field(default_factory=list)


class DiagramSpec(BaseModel):
    id: str
    type: str  # mermaid | ascii | manim
    definition: str
    title: str = ""
    output_path: str = ""


class SlideContent(BaseModel):
    id: str
    layout: str  # title | content | code | diagram | exercise
    headline: str
    bullets: List[str] = Field(default_factory=list)
    code_ref: str = ""
    diagram_ref: str = ""
    notes: str = ""


class QAReport(BaseModel):
    lesson_id: str
    score: float
    checks: dict
    requires_human_review: bool = False
    issues: List[str] = Field(default_factory=list)


class SEOMetadata(BaseModel):
    lesson_id: str
    title: str
    description: str
    tags: List[str]
    chapters: List[dict]
    pinned_comment: str = ""


class PipelineState(TypedDict):
    source_id: str
    course_id: str
    course_title: str
    lesson_id: str
    lesson_title: str
    lesson_position: int
    topic_tags: List[str]
    prerequisites: List[str]
    target_audience: str
    estimated_duration_minutes: int

    lesson_plan: Optional[dict]
    script: Optional[dict]
    code_examples: Optional[List[dict]]
    diagrams: Optional[List[dict]]
    slide_contents: Optional[List[dict]]

    audio_paths: Optional[List[str]]
    slide_image_paths: Optional[List[str]]
    slide_id_to_path: Optional[dict]
    diagram_image_paths: Optional[dict]
    video_path: Optional[str]
    thumbnail_path: Optional[str]

    qa_report: Optional[dict]
    seo_metadata: Optional[dict]
    subtitle_srt: Optional[str]

    output_dir: str
    error: Optional[str]
    retry_count: int
