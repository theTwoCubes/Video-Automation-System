"""
Boundary validation for pipeline agent outputs.

Each agent is responsible for producing specific fields in the shared
PipelineState (see AGENT_FIELDS in pipelines/full_video_pipeline.py). This
module validates those fields the moment the agent finishes, so a malformed or
empty LLM/render output fails loudly at its OWN boundary with a clear message,
instead of surfacing three agents later as a confusing downstream crash.

`errors` are fatal (the pipeline stops and writes FAILED.txt); `warnings` are
advisory and only logged.
"""
from __future__ import annotations

from typing import List, Tuple


def _nonempty_list(v) -> bool:
    return isinstance(v, list) and len(v) > 0


def validate_step(step: str, state: dict) -> Tuple[List[str], List[str]]:
    """Return (errors, warnings) for the given step's outputs in `state`."""
    errors: List[str] = []
    warnings: List[str] = []

    if step == "plan_lesson":
        plan = state.get("lesson_plan")
        if not isinstance(plan, dict) or not _nonempty_list(plan.get("sections")):
            errors.append("lesson_plan has no sections")

    elif step == "write_script":
        script = state.get("script")
        segs = script.get("segments") if isinstance(script, dict) else None
        if not _nonempty_list(segs):
            errors.append("script has no segments")
        else:
            narr = [s for s in segs
                    if s.get("type") in ("narration", "code_demo") and s.get("text", "").strip()]
            if not narr:
                errors.append("script has no narratable segments")
            if any(not s.get("slide_id") for s in segs):
                warnings.append("some script segments have no slide_id")

    elif step == "generate_slides":
        slides = state.get("slide_contents")
        paths = state.get("slide_image_paths")
        if not _nonempty_list(slides):
            errors.append("no slide_contents produced")
        if not _nonempty_list(paths):
            errors.append("no slide images rendered")
        for s in (slides or []):
            sid = s.get("id", "?")
            if not s.get("id"):
                warnings.append("a slide is missing its id")
            if not s.get("layout"):
                warnings.append(f"slide {sid} missing layout")
            if s.get("layout") not in ("title",) and not (s.get("headline") or "").strip():
                warnings.append(f"slide {sid} missing headline")

    elif step == "synthesize_voice":
        if not _nonempty_list(state.get("audio_paths")):
            errors.append("no audio segments synthesized")

    elif step == "compose_video":
        if not state.get("video_path"):
            errors.append("no video_path produced")

    return errors, warnings
