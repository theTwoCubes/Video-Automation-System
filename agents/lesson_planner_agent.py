"""
Lesson Planner Agent — Deterministic Section-Based Architecture.

Receives pre-loaded section text from the PDF processor.
No embeddings, no vector search — the exact relevant sections are injected directly.
"""
from agents.base_agent import BaseAgent


SYSTEM_PROMPT = """You are a lesson planner for theTwoCubes Learning.
Create a detailed lesson plan that a script writer will follow.

Every lesson follows this exact structure:
1. HOOK (30-60s): provocative question or surprising fact
2. OBJECTIVES (30s): 3-4 clear, measurable outcomes
3. CONCEPT (2-3 min): real-world analogy first, then formal definition
4. DEEP_DIVE (5-7 min): step-by-step with code examples
5. MISTAKES (1-2 min): 2-3 common errors and how to avoid them
6. SUMMARY (1 min): 3 key takeaways
7. EXERCISE (30s): one concrete challenge
8. WHATS_NEXT (30s): preview of next lesson

Rules:
- Keep hooks engaging and non-generic. Never start with "In this lesson we will learn..."
- Objectives must be specific and measurable.
- needs_diagram: true only for spatial/structural concepts (memory layout, trees, networks).
- needs_code: true when code is the best way to illustrate the concept.
- CRITICAL: The reference PDF sections provided are just an outline or foundation. You MUST aggressively expand on them using your own expert knowledge. Never generate a short, shallow lesson just because the PDF section is short. The final lesson MUST be exhaustive, perfect, and highly detailed.
- Output strictly valid JSON. No markdown. No commentary."""

USER_TEMPLATE = """
Lesson: {title}
Position: {position} in the course
Difficulty: {difficulty}
Target audience: {audience}
Target duration: {duration} minutes

{continuity_block}

--- REFERENCE MATERIAL (exact sections from the course PDF) ---

PRIORITY ORDER for content decisions:
1. Use the provided PDF sections as your foundation and structural guide.
2. CRITICAL: The PDF may be brief. You MUST expand upon it significantly using your own expert knowledge to ensure a deep, exhaustive, and perfectly explained lesson. Do not limit your depth to what is written in the PDF.
3. If the PDF lacks detail on an essential concept, aggressively fill the gaps with your own advanced technical knowledge.
4. Never contradict the reference material, but ALWAYS improve, expand, and perfect it.

{section_text}

--- END OF REFERENCE MATERIAL ---

Generate a lesson plan matching this schema:
{{
  "lesson_id": "{lesson_id}",
  "title": "string",
  "objectives": ["string", ...],
  "key_concepts": ["string", ...],
  "difficulty": "beginner|intermediate|advanced",
  "duration_estimate_minutes": number,
  "prerequisites": ["string"],
  "sections": [
    {{
      "id": "sec_001",
      "title": "string",
      "type": "hook|concept|deep_dive|code_demo|mistakes|summary|exercise|whats_next",
      "duration_seconds": number,
      "needs_diagram": boolean,
      "needs_code": boolean,
      "key_points": ["string"]
    }}
  ]
}}
"""


class LessonPlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__()

    def run(self, state: dict) -> dict:
        print(f"[LessonPlannerAgent] Planning: {state['lesson_title']}")

        lesson_id = state["lesson_id"]
        title = state["lesson_title"]
        audience = state.get("target_audience", "beginners")
        duration = state.get("estimated_duration_minutes", 12)
        position = state.get("lesson_position", 1)
        difficulty = state.get("difficulty", "beginner")
        section_text = state.get("section_text", "No reference material available.")

        # Lesson continuity — inject previous lesson's summary
        prev_summary = state.get("previous_lesson_summary")
        if prev_summary:
            bullets = prev_summary.get("key_takeaways", [])
            prev_title = prev_summary.get("title", "")
            continuity_block = (
                f"PREVIOUS LESSON ({prev_title}) ALREADY COVERED — do NOT re-explain:\n"
                + "\n".join(f"  - {b}" for b in bullets[:5])
                + "\n\nBuild ON these concepts. Reference them briefly but never re-teach.\n"
            )
        else:
            continuity_block = ""

        user_msg = USER_TEMPLATE.format(
            lesson_id=lesson_id,
            title=title,
            position=position,
            difficulty=difficulty,
            audience=audience,
            duration=duration,
            section_text=section_text[:8000],  # hard cap to stay within context
            continuity_block=continuity_block,
        )

        lesson_plan = self.llm.complete_json(SYSTEM_PROMPT, user_msg)

        # Guarantee required sections are always present
        sections = lesson_plan.get("sections", [])
        section_types = {s.get("type") for s in sections}

        required = [
            ("objectives", "objectives_auto", f"By the end of this lesson you will understand: {title}", 30, False, False),
            ("summary",    "summary_auto",    "Key Takeaways", 60, False, False),
            ("exercise",   "exercise_auto",   f"Practice challenge for {title}", 45, False, True),
        ]

        for sec_type, sec_id, title_str, dur, diag, code in required:
            if sec_type not in section_types:
                sections.append({
                    "id": sec_id,
                    "title": title_str,
                    "type": sec_type,
                    "duration_seconds": dur,
                    "needs_diagram": diag,
                    "needs_code": code,
                    "key_points": [],
                })

        lesson_plan["sections"] = sections
        state["lesson_plan"] = lesson_plan
        print(f"  Planned {len(sections)} sections.")
        return state
