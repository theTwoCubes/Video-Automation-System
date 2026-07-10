import json
from pathlib import Path
from agents.base_agent import BaseAgent
from services.diagram_renderer.renderer import DiagramRenderer, VALID_DIAGRAM_TYPES


SYSTEM_PROMPT = """You are a diagram content designer for theTwoCubes Learning.
You do NOT write HTML or CSS. You only supply structured content for a fixed diagram template.

Given a diagram_type, output ONLY the JSON fields that template needs:

- pipeline: {"title": str, "steps": [{"label": str, "sublabel": str}], "accent": "primary"|"secondary"}
- memory_layout: {"title": str, "columns": [{"label": str, "accent": "primary"|"secondary", "items": [{"text": str, "addr": str}]}]}
- call_stack: {"title": str, "frames": [{"label": str, "detail": str}], "mode": "push"|"pop"|"push_pop"}
- iteration: {"title": str, "items": [str], "highlight_sequence": [int]}
- flow: {"title": str, "nodes": [{"label": str, "sublabel": str}]}
- tree: {"title": str, "root": str, "children": [{"label": str, "children": [...]}]} (recursive, max depth 3, max ~10 nodes total)
  USE WHEN: hierarchical parent-child relationships (inheritance, file systems, expression trees).
- state_machine: {"title": str, "states": [{"label": str, "is_start": bool, "is_end": bool}], "transitions": [{"label": str}]}
  USE WHEN: states with labeled transitions (parser/game/protocol states). List transitions in the order they fire.
- layers_diagram: {"title": str, "layers": [{"label": str, "detail": str}]} (bottom to top, max 6)
  USE WHEN: stacked abstraction layers (memory segments, network stack, architecture layers).

RULES:
- Use REAL, concrete example values (real addresses like 0x7ffe..., real variable names, real function names) - never placeholders.
- title: max 6 words.
- Match the diagram_type given exactly; do not invent new fields.
- 3-5 items/steps/frames/nodes per diagram - enough to teach the concept, not so many it gets crowded.

Output strictly valid JSON: {"diagram_type": "...", "content": {...}}"""

USER_TEMPLATE = """
Concept: {concept}
Lesson: {lesson_title}
Diagram type: {diagram_type}

Supply the JSON content for this diagram_type only.
"""

# Deterministic fallback content for every diagram_type - used when the LLM call
# fails or ffmpeg is unavailable, so every type always has a working render path.
_FALLBACK_CONTENT = {
    "memory_layout": {
        "title": "Memory Layout: Stack vs Heap",
        "columns": [
            {"label": "Stack", "accent": "primary", "items": [
                {"text": "int x = 42", "addr": "0x7ffe...a4"},
                {"text": "int y = 10", "addr": "0x7ffe...a0"},
                {"text": "char c = 'A'", "addr": "0x7ffe...9f"},
            ]},
            {"label": "Heap", "accent": "secondary", "items": [
                {"text": "new int[100]", "addr": "0x55f3...c0"},
                {"text": "new Node()", "addr": "0x55f3...e8"},
            ]},
        ],
    },
    "pipeline": {
        "title": "C++ Compilation Pipeline",
        "steps": [
            {"label": "Source", "sublabel": "main.cpp"},
            {"label": "Preprocessor", "sublabel": "main.i"},
            {"label": "Compiler", "sublabel": "main.s"},
            {"label": "Assembler", "sublabel": "main.o"},
            {"label": "Linker", "sublabel": "program.exe", "accent": "secondary"},
        ],
    },
    "call_stack": {
        "title": "Recursive Call Stack: factorial(4)",
        "mode": "push",
        "frames": [
            {"label": "factorial(4)", "detail": "waiting on factorial(3)"},
            {"label": "factorial(3)", "detail": "waiting on factorial(2)"},
            {"label": "factorial(2)", "detail": "waiting on factorial(1)"},
            {"label": "factorial(1)", "detail": "base case, returns 1"},
        ],
    },
    "iteration": {
        "title": "for (int i = 0; i < 5; i++)",
        "items": ["i=0", "i=1", "i=2", "i=3", "i=4"],
        "highlight_sequence": [0, 1, 2, 3, 4],
    },
    "flow": {
        "title": "How a Header File Gets Included",
        "nodes": [
            {"label": "#include", "sublabel": "directive"},
            {"label": "Preprocessor", "sublabel": "text substitution"},
            {"label": "Expanded Source", "sublabel": "ready to compile"},
        ],
    },
    "tree": {
        "title": "Class Inheritance: Animal Hierarchy",
        "root": "Animal",
        "children": [
            {"label": "Mammal", "children": [{"label": "Dog"}, {"label": "Cat"}]},
            {"label": "Bird", "children": [{"label": "Eagle"}]},
        ],
    },
    "state_machine": {
        "title": "Traffic Light State Machine",
        "states": [
            {"label": "Red", "is_start": True, "is_end": False},
            {"label": "Green", "is_start": False, "is_end": False},
            {"label": "Yellow", "is_start": False, "is_end": True},
        ],
        "transitions": [
            {"label": "Red -> Green"},
            {"label": "Green -> Yellow"},
            {"label": "Yellow -> Red"},
        ],
    },
    "layers_diagram": {
        "title": "Memory Segments: Bottom to Top",
        "layers": [
            {"label": "Text (Code)", "detail": "compiled instructions"},
            {"label": "Data", "detail": "global/static variables"},
            {"label": "Heap", "detail": "grows upward, dynamic allocation"},
            {"label": "Stack", "detail": "grows downward, local variables"},
        ],
    },
}


class DiagramAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.renderer = DiagramRenderer()

    def run(self, state: dict) -> dict:
        print("[DiagramAgent] Generating diagrams...")

        script = state.get("script", {})
        segments = script.get("segments", [])
        lesson_title = state["lesson_title"]
        lesson_plan = state.get("lesson_plan", {})

        # collect diagram refs from script
        diagram_refs = {}
        for seg in segments:
            if seg.get("type") == "diagram" and seg.get("diagram_ref"):
                diagram_refs[seg["diagram_ref"]] = seg.get("text", seg["diagram_ref"])

        # also check lesson plan, and remember the planner's diagram type guess
        # per section so it can be used ahead of the blunt keyword classifier
        planned_diagram_types: dict[str, str] = {}
        for section in lesson_plan.get("sections", []):
            did = f"diag_{section.get('id', '')}"
            recommended = section.get("recommended_diagram_type", "")
            if recommended and recommended in VALID_DIAGRAM_TYPES:
                planned_diagram_types[did] = recommended
            if section.get("needs_diagram") and did not in diagram_refs:
                diagram_refs[did] = section.get("title", lesson_title)

        output_dir = Path(state["output_dir"]) / "diagrams"
        output_dir.mkdir(parents=True, exist_ok=True)

        diagrams = []
        diagram_paths = {}

        try:
            from services.video_composer.composer import _get_ffmpeg
            ffmpeg_exe = _get_ffmpeg()
        except Exception:
            ffmpeg_exe = None

        for diag_id, concept in diagram_refs.items():
            print(f"  Generating {diag_id}: {concept[:60]}")
            out_video = str(output_dir / f"{diag_id}.mp4")
            diagram_type = planned_diagram_types.get(diag_id) or self._classify_diagram_type(concept)

            html_content = self._generate_diagram_html(diag_id, lesson_title, concept, diagram_type)

            if html_content and ffmpeg_exe:
                from services.diagram_renderer.html_animator import render_animated_diagram
                video_path = render_animated_diagram(
                    html_content, out_video, ffmpeg_exe, duration_sec=4.0, capture_fps=15
                )
                if video_path:
                    diagrams.append({"id": diag_id, "title": concept[:60], "type": "animated", "path": video_path})
                    diagram_paths[diag_id] = video_path
                    print(f"  Animated diagram: {diag_id}")
                    continue

            # fallback: deterministic content through the same template, still animated
            fallback_html = self._get_fallback_html(diagram_type)
            if fallback_html and ffmpeg_exe:
                try:
                    from services.diagram_renderer.html_animator import render_animated_diagram
                    video_path = render_animated_diagram(
                        fallback_html, out_video, ffmpeg_exe, duration_sec=4.0, capture_fps=15
                    )
                    if video_path:
                        diagrams.append({"id": diag_id, "title": concept[:60], "type": "fallback", "path": video_path})
                        diagram_paths[diag_id] = video_path
                        continue
                except Exception as e:
                    print(f"  Fallback diagram error: {e}")

            print(f"  Skipped diagram {diag_id}")

        state["diagrams"] = diagrams
        state["diagram_image_paths"] = diagram_paths
        print(f"  Generated {len(diagrams)} diagrams.")
        return state

    def _classify_diagram_type(self, concept: str) -> str:
        concept_lower = concept.lower()
        if any(w in concept_lower for w in ["inherit", "hierarchy", "tree", "parent", "subclass", "derived"]):
            return "tree"
        if any(w in concept_lower for w in ["state", "transition", "protocol", "parser"]):
            return "state_machine"
        if any(w in concept_lower for w in ["layer", "abstraction", "segment", "network stack"]):
            return "layers_diagram"
        if any(w in concept_lower for w in ["stack", "heap", "memory", "pointer", "array"]):
            return "memory_layout"
        if any(w in concept_lower for w in ["compil", "link", "preprocess", "build"]):
            return "pipeline"
        if any(w in concept_lower for w in ["call", "function", "recursi"]):
            return "call_stack"
        if any(w in concept_lower for w in ["loop", "iteration", "for", "while"]):
            return "iteration"
        return "flow"

    def _generate_diagram_html(self, diag_id: str, lesson_title: str, concept: str, diagram_type: str) -> str:
        """Ask LLM for structured content matching diagram_type's schema, then render
        it through the shared DiagramRenderer template. Returns HTML string or empty."""
        user_msg = USER_TEMPLATE.format(
            concept=concept[:300],
            lesson_title=lesson_title,
            diagram_type=diagram_type,
        )
        try:
            result = self.llm.complete_json(SYSTEM_PROMPT, user_msg)
            content = result.get("content", {})
            returned_type = result.get("diagram_type", diagram_type)
            if returned_type not in VALID_DIAGRAM_TYPES:
                returned_type = diagram_type
            if not content:
                return ""
            return self.renderer.render_html(returned_type, content)
        except Exception as e:
            print(f"  Diagram LLM error: {e}")
            return ""

    def _get_fallback_html(self, diagram_type: str) -> str:
        """Render deterministic fallback content for diagram_type through the same template."""
        content = _FALLBACK_CONTENT.get(diagram_type, _FALLBACK_CONTENT["flow"])
        return self.renderer.render_html(diagram_type, content)
