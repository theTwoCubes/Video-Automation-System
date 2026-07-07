import json
from pathlib import Path
from agents.base_agent import BaseAgent
from services.diagram_renderer.mermaid import render_mermaid, generate_ascii_diagram


SYSTEM_PROMPT = """You are a diagram designer for theTwoCubes Learning.
Generate Mermaid diagram definitions for technical concepts.

Supported diagram types:
- flowchart TD: decision flows, algorithms
- sequenceDiagram: function call stacks, protocols
- graph LR: concept relationships, dependency graphs
- classDiagram: OOP relationships
- gitgraph: version control concepts

Rules:
- Mermaid syntax must be valid (no extra symbols).
- Keep diagrams simple: max 10 nodes for flowcharts.
- Use short labels (under 4 words per node).
- Output strictly valid JSON. No markdown."""

USER_TEMPLATE = """
Concept to diagram: {concept}
Lesson topic: {lesson_title}
Diagram type hint: {diagram_type}

Generate a diagram spec as JSON:
{{
  "id": "{diagram_id}",
  "type": "mermaid",
  "title": "short diagram title",
  "definition": "complete mermaid definition here as a single string",
  "ascii_fallback": ["line1", "line2", "..."]
}}

The ascii_fallback is a list of strings representing an ASCII art version,
used when Mermaid is not available.
"""


class DiagramAgent(BaseAgent):
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

        # also check lesson plan for sections needing diagrams
        for section in lesson_plan.get("sections", []):
            if section.get("needs_diagram"):
                did = f"diag_{section['id']}"
                if did not in diagram_refs:
                    diagram_refs[did] = section.get("title", lesson_title)

        output_dir = Path(state["output_dir"]) / "diagrams"
        output_dir.mkdir(parents=True, exist_ok=True)

        diagrams = []
        diagram_paths = {}

        for diag_id, concept in diagram_refs.items():
            print(f"  Generating {diag_id}: {concept[:60]}")
            spec = self._generate_diagram_spec(diag_id, lesson_title, concept)
            out_path = str(output_dir / f"{diag_id}.png")

            # try Mermaid first, fall back to ASCII
            rendered = render_mermaid(spec.get("definition", ""), out_path)
            if not rendered:
                ascii_lines = spec.get("ascii_fallback", [concept])
                rendered = generate_ascii_diagram(ascii_lines, out_path)

            spec["output_path"] = rendered or ""
            diagrams.append(spec)
            diagram_paths[diag_id] = rendered or ""

        state["diagrams"] = diagrams
        state["diagram_image_paths"] = diagram_paths
        print(f"  Generated {len(diagrams)} diagrams.")
        return state

    def _generate_diagram_spec(self, diag_id: str, lesson_title: str, concept: str) -> dict:
        # pick a sensible diagram type based on concept
        diagram_type = "flowchart TD"
        concept_lower = concept.lower()
        if any(w in concept_lower for w in ["call", "sequence", "protocol", "stack"]):
            diagram_type = "sequenceDiagram"
        elif any(w in concept_lower for w in ["class", "inheritance", "object"]):
            diagram_type = "classDiagram"
        elif any(w in concept_lower for w in ["relationship", "dependency", "graph"]):
            diagram_type = "graph LR"

        user_msg = USER_TEMPLATE.format(
            diagram_id=diag_id,
            concept=concept[:300],
            lesson_title=lesson_title,
            diagram_type=diagram_type,
        )

        try:
            return self.llm.complete_json(SYSTEM_PROMPT, user_msg)
        except Exception as e:
            print(f"  Diagram LLM error: {e}")
            return {
                "id": diag_id,
                "type": "ascii",
                "title": concept[:40],
                "definition": "",
                "ascii_fallback": [concept[:60]],
            }
