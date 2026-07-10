"""
Curriculum Agent - Deterministic Section-Based Architecture.

Flow:
  1. Receive the synthesized TOC text (extracted from the processed PDF).
  2. Ask LLM to plan N lectures by declaring exact section IDs for each.
  3. Validate all declared section IDs actually exist in the processed PDF.
  4. Persist the lecture plan to state.
"""
from agents.base_agent import BaseAgent
from services.knowledge.pdf_processor import PDFProcessor


SYSTEM_PROMPT = """You are a curriculum designer for theTwoCubes Learning.
Your job is to plan a complete video course from a reference PDF's Table of Contents.

TASK:
Given the full TOC, divide all sections into individual lectures.
You control how sections are grouped - you can MERGE adjacent short sections into one lecture,
or SPLIT a large section across multiple lectures. Every section must appear in at least one lecture.

For each lecture, also declare "reference_sections" - other sections the LLM will need
as background context while writing this lecture (e.g., when teaching Pointers, reference the
Memory Layout section even if it was covered earlier).

RULES:
- Use EXACT section IDs from the TOC (e.g., "7.5", "1.7.3"). Do NOT invent IDs.
- Every section ID in the TOC must appear in at least one lecture's primary_sections.
- reference_sections should be 0-3 IDs max. Do not over-reference.
- Each lecture should be teachable in 10-15 minutes.
- Difficulty: beginner for chapters 1-5, intermediate for 6-12, advanced for 13+.
- topic_tags: 4-6 keywords per lecture.
- Order lectures logically - build concepts incrementally.

OUTPUT: Strictly valid JSON. No markdown. No commentary.

{
  "lectures": [
    {
      "title": "string",
      "primary_sections": ["N.N", "N.N"],
      "reference_sections": ["N.N"],
      "difficulty": "beginner|intermediate|advanced",
      "estimated_minutes": 12,
      "topic_tags": ["string"]
    }
  ]
}"""


class CurriculumAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.processor = PDFProcessor()

    def run(self, state: dict) -> dict:
        print("[CurriculumAgent] Planning curriculum from TOC...")

        source_id = state.get("source_id", "")
        topic = state.get("topic", "Programming")
        audience = state.get("target_audience", "beginners")
        min_lectures = state.get("min_lessons", 30)

        # Load TOC and section IDs from the processed PDF
        toc_text = self.processor.get_toc(source_id)
        valid_section_ids = set(self.processor.list_section_ids(source_id))

        user_msg = (
            f"Topic: {topic}\n"
            f"Target audience: {audience}\n"
            f"Minimum lectures: {min_lectures}\n\n"
            f"Table of Contents:\n{toc_text}\n\n"
            f"Plan the complete lecture series now."
        )

        print(f"  Sending TOC ({len(toc_text)} chars, {len(valid_section_ids)} sections) to LLM...")
        result = self.llm.complete_json(SYSTEM_PROMPT, user_msg)
        lectures = result.get("lectures", [])

        if not lectures:
            raise RuntimeError("CurriculumAgent: LLM returned no lectures.")

        # Validate all section IDs
        invalid_found = []
        for lec in lectures:
            for sid in lec.get("primary_sections", []) + lec.get("reference_sections", []):
                if sid not in valid_section_ids:
                    invalid_found.append(sid)

        if invalid_found:
            print(f"  WARNING: LLM used {len(invalid_found)} invalid section IDs: {invalid_found[:10]}")
            # Remove invalid IDs rather than hard-failing
            for lec in lectures:
                lec["primary_sections"] = [s for s in lec.get("primary_sections", []) if s in valid_section_ids]
                lec["reference_sections"] = [s for s in lec.get("reference_sections", []) if s in valid_section_ids]

        # Assign positions
        for i, lec in enumerate(lectures):
            lec["position"] = i + 1

        curriculum = {
            "source_id": source_id,
            "total_lectures": len(lectures),
            "lectures": lectures,
        }

        state["curriculum"] = curriculum
        print(f"  Planned {len(lectures)} lectures covering {len(valid_section_ids)} sections.")
        return state
