import json
from agents.base_agent import BaseAgent
from services.knowledge.ingestion import KnowledgeIngestionService


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
- objectives must be specific and measurable.
- needs_diagram: true only for spatial/structural concepts (memory layout, trees, networks).
- needs_code: true when code is the best way to illustrate the concept.
- Output strictly valid JSON. No markdown. No commentary."""

USER_TEMPLATE = """
Lesson: {title}
Position: {position} in the course
Topic tags: {tags}
Prerequisites already covered: {prerequisites}
Target audience: {audience}
Target duration: {duration} minutes

{continuity_block}
Retrieved knowledge context:
{rag_context}

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
        self.ingestion = KnowledgeIngestionService()

    def run(self, state: dict) -> dict:
        print(f"[LessonPlannerAgent] Planning: {state['lesson_title']}")

        source_id = state["source_id"]
        lesson_id = state["lesson_id"]
        title = state["lesson_title"]
        tags = ", ".join(state.get("topic_tags", []))
        prereqs = ", ".join(state.get("prerequisites", [])) or "None"
        audience = state.get("target_audience", "beginners")
        duration = state.get("estimated_duration_minutes", 12)
        position = state.get("lesson_position", 1)

        # A.3: Lesson continuity — inject previous lesson's summary
        prev_summary = state.get("previous_lesson_summary")
        if prev_summary:
            bullets = prev_summary.get("key_takeaways", [])
            prev_title = prev_summary.get("title", "")
            continuity_block = (
                f"PREVIOUS LESSON ({prev_title}) ALREADY COVERED — do NOT re-explain:\n"
                + "\n".join(f"  - {b}" for b in bullets[:5])
                + "\n\nBuild ON these concepts. Reference them briefly but never re-teach.\n\n"
            )
        else:
            continuity_block = ""

        # RAG context for this specific topic
        chunks = self.ingestion.query(source_id, title, n_results=6)
        rag_context = "\n\n---\n\n".join(chunks) if chunks else "No context available."

        user_msg = USER_TEMPLATE.format(
            lesson_id=lesson_id,
            title=title,
            position=position,
            tags=tags,
            prerequisites=prereqs,
            audience=audience,
            duration=duration,
            rag_context=rag_context[:5000],
            continuity_block=continuity_block,
        )

        lesson_plan = self.llm.complete_json(SYSTEM_PROMPT, user_msg)

        # guarantee required sections are always present
        sections = lesson_plan.get("sections", [])
        section_types = {s.get("type") for s in sections}

        required = [
            ("objectives", "objectives",
             f"By the end of this lesson you will understand: {title}",
             30, False, False),
            ("summary", "summary",
             "Key Takeaways", 60, False, False),
            ("exercise", "exercise",
             f"Practice challenge for {title}", 45, False, True),
        ]

        for sec_type, sec_id_prefix, title_str, dur, diag, code in required:
            if sec_type not in section_types:
                sections.append({
                    "id": f"{sec_id_prefix}_auto",
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
