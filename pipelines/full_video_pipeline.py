import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Literal

from langgraph.graph import StateGraph, END

from contracts.schemas import PipelineState
from agents.lesson_planner_agent import LessonPlannerAgent
from agents.script_agent import ScriptAgent
from agents.code_agent import CodeAgent
from agents.diagram_agent import DiagramAgent
from agents.slide_agent import SlideAgent
from agents.voice_agent import VoiceAgent
from agents.video_agent import VideoAgent
from agents.thumbnail_agent import ThumbnailAgent
from agents.qa_agent import QAAgent
from agents.seo_agent import SEOAgent
from agents.quiz_agent import QuizAgent
from config.settings import settings

# Fields each agent is responsible for saving to checkpoints
AGENT_FIELDS = {
    "plan_lesson":      ["lesson_plan"],
    "write_script":     ["script"],
    "generate_code":    ["code_examples"],
    "generate_diagrams":["diagrams", "diagram_image_paths"],
    "generate_slides":  ["slide_contents", "slide_image_paths", "slide_id_to_path"],
    "synthesize_voice": ["audio_paths"],
    "compose_video":    ["video_path"],
    "generate_thumbnail":["thumbnail_path"],
    "qa_check":         ["qa_report"],
    "generate_seo":     ["seo_metadata"],
    "generate_quiz":    ["quiz_questions"],
}


def _checkpoint_path(output_dir: str, step: str) -> Path:
    return Path(output_dir) / "checkpoints" / f"{step}.json"


def _save_checkpoint(output_dir: str, step: str, state: PipelineState, fields: list[str]):
    cp_dir = Path(output_dir) / "checkpoints"
    cp_dir.mkdir(parents=True, exist_ok=True)
    data = {k: state.get(k) for k in fields if state.get(k) is not None}
    _checkpoint_path(output_dir, step).write_text(
        json.dumps(data, default=str, indent=2), encoding="utf-8"
    )


def _load_checkpoint(output_dir: str, step: str) -> dict | None:
    cp = _checkpoint_path(output_dir, step)
    if cp.exists():
        return json.loads(cp.read_text(encoding="utf-8"))
    return None


def _with_checkpoint(step_name: str, agent_fn):
    """Wrap a node function with checkpoint save/load logic and error handling."""
    fields = AGENT_FIELDS.get(step_name, [])

    def wrapped(state: PipelineState) -> PipelineState:
        if state.get("error"):
            print(f"[{step_name}] Skipping execution because pipeline is in error state.")
            return state

        output_dir = state.get("output_dir", "")
        if output_dir:
            saved = _load_checkpoint(output_dir, step_name)
            if saved:
                print(f"[Checkpoint] Skipping {step_name} - loaded from checkpoint")
                return {**state, **saved}

        try:
            result = agent_fn(state)
        except Exception as e:
            import traceback
            err_msg = f"Exception in {step_name}:\n{e}\n{traceback.format_exc()}"
            print(f"[Error] {err_msg}")
            result = {**state, "error": err_msg}

        if output_dir and not result.get("error") and fields:
            _save_checkpoint(output_dir, step_name, result, fields)

        return result

    return wrapped


def node_plan_lesson(state: PipelineState) -> PipelineState:
    return LessonPlannerAgent().run(state)


def node_write_script(state: PipelineState) -> PipelineState:
    return ScriptAgent().run(state)


def node_generate_code(state: PipelineState) -> PipelineState:
    return CodeAgent().run(state)


def node_generate_diagrams(state: PipelineState) -> PipelineState:
    return DiagramAgent().run(state)


def node_generate_slides(state: PipelineState) -> PipelineState:
    return SlideAgent().run(state)


def node_synthesize_voice(state: PipelineState) -> PipelineState:
    return VoiceAgent().run(state)


def node_compose_video(state: PipelineState) -> PipelineState:
    return VideoAgent().run(state)


def node_generate_thumbnail(state: PipelineState) -> PipelineState:
    return ThumbnailAgent().run(state)


def node_qa_check(state: PipelineState) -> PipelineState:
    return QAAgent().run(state)


def node_generate_seo(state: PipelineState) -> PipelineState:
    return SEOAgent().run(state)


def node_generate_quiz(state: PipelineState) -> PipelineState:
    return QuizAgent().run(state)


def node_save_outputs(state: PipelineState) -> PipelineState:
    output_dir = Path(state["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "lesson_id": state["lesson_id"],
        "lesson_title": state["lesson_title"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "primary_sections": state.get("primary_sections", []),
        "reference_sections": state.get("reference_sections", []),
        "video_path": state.get("video_path", ""),
        "thumbnail_path": state.get("thumbnail_path", ""),
        "qa_score": state.get("qa_report", {}).get("score", 0),
        "seo_title": state.get("seo_metadata", {}).get("title", ""),
        "seo_description": state.get("seo_metadata", {}).get("description", ""),
        "tags": state.get("seo_metadata", {}).get("tags", []),
        "chapters": state.get("seo_metadata", {}).get("chapters", []),
        "pinned_comment": state.get("seo_metadata", {}).get("pinned_comment", ""),
        "quiz_questions": len(state.get("quiz_questions") or []),
        "slide_validation_issues": len(state.get("slide_validation_issues") or []),
        "pacing_flags": len(state.get("pacing_flags") or []),
        "video_quality": state.get("video_quality", {}),
    }

    summary_path = output_dir / "lesson_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Save exact injected context for tracing
    if state.get("section_text"):
        (output_dir / "reference_material.txt").write_text(state["section_text"], encoding="utf-8")

    if state.get("script"):
        with open(output_dir / "script.json", "w", encoding="utf-8") as f:
            json.dump(state["script"], f, indent=2)

    seo = state.get("seo_metadata", {})
    if seo:
        with open(output_dir / "youtube_metadata.txt", "w", encoding="utf-8") as f:
            f.write(f"TITLE:\n{seo.get('title', '')}\n\n")
            f.write(f"DESCRIPTION:\n{seo.get('description', '')}\n\n")
            f.write(f"TAGS:\n{', '.join(seo.get('tags', []))}\n\n")
            f.write("CHAPTERS:\n")
            for ch in seo.get("chapters", []):
                f.write(f"{ch.get('timestamp', '')} {ch.get('title', '')}\n")
            f.write(f"\nPINNED COMMENT:\n{seo.get('pinned_comment', '')}\n")

    # write subtitle file if it was generated
    srt = state.get("subtitle_srt", "")
    if srt:
        (output_dir / "subtitles.srt").write_text(srt, encoding="utf-8")

    print(f"\n[Pipeline] Done! Outputs saved to: {output_dir}")
    print(f"  Summary: {summary_path}")
    if summary.get("video_path"):
        print(f"  Video:   {summary['video_path']}")
    print(f"  QA Score: {summary['qa_score']}/100")
    return state


def should_stop_on_error(state: PipelineState) -> Literal["continue", "stop"]:
    if state.get("error"):
        print(f"[Pipeline] Stopping due to error: {state['error']}")
        return "stop"
    return "continue"


def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    # wrap every node with checkpoint logic
    graph.add_node("plan_lesson",          _with_checkpoint("plan_lesson",          node_plan_lesson))
    graph.add_node("write_script",         _with_checkpoint("write_script",         node_write_script))
    graph.add_node("generate_code",        _with_checkpoint("generate_code",        node_generate_code))
    graph.add_node("generate_diagrams",    _with_checkpoint("generate_diagrams",    node_generate_diagrams))
    graph.add_node("generate_slides",      _with_checkpoint("generate_slides",      node_generate_slides))
    graph.add_node("synthesize_voice",     _with_checkpoint("synthesize_voice",     node_synthesize_voice))
    graph.add_node("compose_video",        _with_checkpoint("compose_video",        node_compose_video))
    graph.add_node("generate_thumbnail",   _with_checkpoint("generate_thumbnail",   node_generate_thumbnail))
    graph.add_node("qa_check",             _with_checkpoint("qa_check",             node_qa_check))
    graph.add_node("generate_seo",         _with_checkpoint("generate_seo",         node_generate_seo))
    graph.add_node("generate_quiz",        _with_checkpoint("generate_quiz",        node_generate_quiz))
    graph.add_node("save_outputs",         node_save_outputs)

    graph.set_entry_point("plan_lesson")

    graph.add_edge("plan_lesson",       "write_script")
    graph.add_edge("write_script",      "generate_code")
    graph.add_edge("generate_code",     "generate_diagrams")
    graph.add_edge("generate_diagrams", "generate_slides")
    graph.add_edge("generate_slides",   "synthesize_voice")

    graph.add_conditional_edges(
        "synthesize_voice",
        should_stop_on_error,
        {"continue": "compose_video", "stop": END},
    )

    graph.add_edge("compose_video",        "generate_thumbnail")
    graph.add_edge("generate_thumbnail",   "qa_check")
    graph.add_edge("qa_check",             "generate_seo")
    graph.add_edge("generate_seo",         "generate_quiz")
    graph.add_edge("generate_quiz",        "save_outputs")
    graph.add_edge("save_outputs",         END)

    return graph.compile()


def run_pipeline(
    source_id: str,
    proc_source_id: str,
    primary_sections: list[str],
    reference_sections: list[str],
    course_id: str,
    course_title: str,
    lesson_id: str,
    lesson_title: str,
    lesson_position: int,
    topic_tags: list[str],
    prerequisites: list[str],
    target_audience: str = "beginners",
    estimated_duration_minutes: int = 12,
    force_restart: bool = False,
    previous_lesson_summary: dict | None = None,
    difficulty: str = "beginner",
    next_lesson_title: str = "",
    profile_name: str = "default",
) -> PipelineState:

    output_dir = str(
        Path(settings.OUTPUT_DIR) / course_id / f"{lesson_position:03d}_{lesson_id[:8]}"
    )
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # clear checkpoints if forcing a fresh restart
    if force_restart:
        import shutil
        cp_dir = Path(output_dir) / "checkpoints"
        if cp_dir.exists():
            shutil.rmtree(cp_dir)
            
        # Clear old media to prevent disk bloat
        seg_dir = Path(output_dir) / "segments"
        if seg_dir.exists():
            shutil.rmtree(seg_dir)
            
        for ext in ("*.mp4", "*.mp3", "*.png", "*.srt", "*.json"):
            for f in Path(output_dir).glob(ext):
                # Don't delete lesson_summary.json yet
                if f.name != "lesson_summary.json":
                    try: f.unlink()
                    except: pass
                    
        print("[Pipeline] Cleared checkpoints and old media for fresh run.")

    # Load the rendering profile (voice/music/slides/rendering settings) - this was
    # previously never loaded at all, so compose_video_aligned always saw an empty
    # profile dict and silently rendered with zero music/intro/outro regardless of
    # what any profile YAML said.
    from config.profile_loader import load_profile
    profile = load_profile(profile_name)

    # Pre-load section text from the processed PDF (deterministic, no embeddings)
    from services.knowledge.pdf_processor import PDFProcessor
    processor = PDFProcessor()
    all_section_ids = primary_sections + [s for s in reference_sections if s not in primary_sections]
    try:
        section_text = processor.get_sections(proc_source_id, all_section_ids)
    except Exception as e:
        print(f"[Pipeline] WARNING: Could not load section text: {e}")
        section_text = "No reference material available."

    initial_state: PipelineState = {
        "source_id": source_id,
        "proc_source_id": proc_source_id,
        "primary_sections": primary_sections,
        "reference_sections": reference_sections,
        "section_text": section_text,
        "course_id": course_id,
        "course_title": course_title,
        "lesson_id": lesson_id,
        "lesson_title": lesson_title,
        "lesson_position": lesson_position,
        "topic_tags": topic_tags,
        "prerequisites": prerequisites,
        "target_audience": target_audience,
        "estimated_duration_minutes": estimated_duration_minutes,
        "difficulty": difficulty,
        "previous_lesson_summary": previous_lesson_summary,
        "next_lesson_title": next_lesson_title,
        "profile": profile,
        "lesson_plan": None,
        "script": None,
        "code_examples": None,
        "diagrams": None,
        "slide_contents": None,
        "audio_paths": None,
        "slide_image_paths": None,
        "slide_id_to_path": None,
        "diagram_image_paths": None,
        "video_path": None,
        "thumbnail_path": None,
        "subtitle_srt": None,
        "qa_report": None,
        "seo_metadata": None,
        "quiz_questions": None,
        "output_dir": output_dir,
        "error": None,
        "retry_count": 0,
    }

    pipeline = build_pipeline()
    failed_marker = Path(output_dir) / "FAILED.txt"
    try:
        final_state = pipeline.invoke(initial_state)
        if final_state.get("error"):
            failed_marker.write_text(
                "Pipeline error:\n" + str(final_state["error"]), encoding="utf-8"
            )
        elif failed_marker.exists():
            failed_marker.unlink()
        return final_state
    except Exception as exc:
        import traceback
        failed_marker.write_text(
            "Unhandled exception:\n" + str(exc) + "\n\n" + traceback.format_exc(),
            encoding="utf-8",
        )
        raise
