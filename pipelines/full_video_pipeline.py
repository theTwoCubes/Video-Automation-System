import json
import uuid
from pathlib import Path
from datetime import datetime
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
from config.settings import settings


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


def node_save_outputs(state: PipelineState) -> PipelineState:
    """Persist final outputs to disk and save metadata JSON."""
    output_dir = Path(state["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "lesson_id": state["lesson_id"],
        "lesson_title": state["lesson_title"],
        "generated_at": datetime.utcnow().isoformat(),
        "video_path": state.get("video_path", ""),
        "thumbnail_path": state.get("thumbnail_path", ""),
        "qa_score": state.get("qa_report", {}).get("score", 0),
        "seo_title": state.get("seo_metadata", {}).get("title", ""),
        "seo_description": state.get("seo_metadata", {}).get("description", ""),
        "tags": state.get("seo_metadata", {}).get("tags", []),
        "chapters": state.get("seo_metadata", {}).get("chapters", []),
        "pinned_comment": state.get("seo_metadata", {}).get("pinned_comment", ""),
    }

    summary_path = output_dir / "lesson_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # also save full script
    if state.get("script"):
        script_path = output_dir / "script.json"
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(state["script"], f, indent=2)

    # save SEO metadata as a txt for easy copy-paste
    seo = state.get("seo_metadata", {})
    if seo:
        seo_txt = output_dir / "youtube_metadata.txt"
        with open(seo_txt, "w", encoding="utf-8") as f:
            f.write(f"TITLE:\n{seo.get('title', '')}\n\n")
            f.write(f"DESCRIPTION:\n{seo.get('description', '')}\n\n")
            f.write(f"TAGS:\n{', '.join(seo.get('tags', []))}\n\n")
            f.write("CHAPTERS:\n")
            for ch in seo.get("chapters", []):
                f.write(f"{ch.get('timestamp', '')} {ch.get('title', '')}\n")
            f.write(f"\nPINNED COMMENT:\n{seo.get('pinned_comment', '')}\n")

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

    graph.add_node("plan_lesson", node_plan_lesson)
    graph.add_node("write_script", node_write_script)
    graph.add_node("generate_code", node_generate_code)
    graph.add_node("generate_diagrams", node_generate_diagrams)
    graph.add_node("generate_slides", node_generate_slides)
    graph.add_node("synthesize_voice", node_synthesize_voice)
    graph.add_node("compose_video", node_compose_video)
    graph.add_node("generate_thumbnail", node_generate_thumbnail)
    graph.add_node("qa_check", node_qa_check)
    graph.add_node("generate_seo", node_generate_seo)
    graph.add_node("save_outputs", node_save_outputs)

    graph.set_entry_point("plan_lesson")

    graph.add_edge("plan_lesson", "write_script")
    graph.add_edge("write_script", "generate_code")
    graph.add_edge("generate_code", "generate_diagrams")
    graph.add_edge("generate_diagrams", "generate_slides")
    graph.add_edge("generate_slides", "synthesize_voice")

    # stop if slide/voice generation failed
    graph.add_conditional_edges(
        "synthesize_voice",
        should_stop_on_error,
        {"continue": "compose_video", "stop": END},
    )

    graph.add_edge("compose_video", "generate_thumbnail")
    graph.add_edge("generate_thumbnail", "qa_check")
    graph.add_edge("qa_check", "generate_seo")
    graph.add_edge("generate_seo", "save_outputs")
    graph.add_edge("save_outputs", END)

    return graph.compile()


def run_pipeline(
    source_id: str,
    course_id: str,
    course_title: str,
    lesson_id: str,
    lesson_title: str,
    lesson_position: int,
    topic_tags: list[str],
    prerequisites: list[str],
    target_audience: str = "beginners",
    estimated_duration_minutes: int = 12,
) -> PipelineState:

    output_dir = str(
        Path(settings.OUTPUT_DIR) / course_id / f"{lesson_position:03d}_{lesson_id[:8]}"
    )
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    initial_state: PipelineState = {
        "source_id": source_id,
        "course_id": course_id,
        "course_title": course_title,
        "lesson_id": lesson_id,
        "lesson_title": lesson_title,
        "lesson_position": lesson_position,
        "topic_tags": topic_tags,
        "prerequisites": prerequisites,
        "target_audience": target_audience,
        "estimated_duration_minutes": estimated_duration_minutes,
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
        "qa_report": None,
        "seo_metadata": None,
        "output_dir": output_dir,
        "error": None,
        "retry_count": 0,
    }

    pipeline = build_pipeline()
    final_state = pipeline.invoke(initial_state)
    return final_state
