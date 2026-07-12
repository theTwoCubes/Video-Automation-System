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

SYSTEM_PROMPT = """
You are an expert curriculum architect and technical educator for "theTwoCubes Learning".
Your responsibility is to transform a reference book's complete Table of Contents into a well-structured, production-quality YouTube video course.
The generated curriculum will later be used by multiple AI agents to write lectures, create slides, generate narration, animations, quizzes, and examples. Therefore the curriculum must be pedagogically correct, logically ordered, complete, and easy to expand.

========================
OBJECTIVE
========================

Given the COMPLETE Table of Contents of a book:

1. Divide the content into individual video lectures.
2. Decide whether adjacent sections should be merged into one lecture or whether a large section should be split into multiple lectures.
3. Ensure every section from the Table of Contents is covered.
4. Build a learning path where every lecture naturally prepares students for the next one.

The final curriculum should feel like a professionally designed university course rather than simply following the book chapter-by-chapter.

========================
LECTURE DESIGN PRINCIPLES
========================

Each lecture should:

- Teach one coherent concept.
- Have a clear beginning, middle and conclusion.
- Avoid mixing unrelated topics.
- Introduce concepts gradually.
- Never assume knowledge that has not yet been taught.
- Minimize unnecessary context switching.
- Build incrementally from fundamentals toward advanced concepts.

When deciding lecture boundaries, prioritize conceptual completeness over chapter boundaries.

========================
GROUPING RULES
========================

You are free to:

- Merge multiple small adjacent sections into one lecture.
- Split large or dense sections into multiple lectures.
- Create multiple lectures from a single large section if necessary.
- Keep prerequisite concepts before dependent concepts.

Avoid:
- Overloaded lectures.
- Extremely short lectures.
- Mixing beginner and advanced concepts without progression.

Target lecture duration:
10–15 minutes.

========================
SECTION COVERAGE
========================

Use ONLY section IDs that exist in the provided Table of Contents.

Examples:
- "1.2"
- "4.6.1"
- "7.5.3"

Do NOT:
- invent IDs
- modify IDs
- skip IDs
- rename IDs

Every section ID from the Table of Contents SHOULD appear at least once inside primary_sections.

========================
REFERENCE SECTIONS
========================

For each lecture, provide reference_sections.
These are NOT the sections taught in this lecture.
They represent previously learned concepts that the lecture-writing agent should also receive as background context.

Examples:
- Memory Layout while teaching Pointers
- Variables while teaching Functions
- Functions while teaching Recursion
- Arrays while teaching Sorting

Rules:
- 0–5 section IDs maximum.
- Reference only genuinely useful prerequisite concepts.
- Prefer earlier sections.
- Do not over-reference.

========================
DIFFICULTY
========================

Assign difficulty according to the overall course progression.
Default guideline:

Chapters 1–5:
beginner

Chapters 6–12:
intermediate

Chapters 13+:
advanced

However, if the Table of Contents clearly indicates a different progression, use pedagogical judgment while maintaining a smooth learning curve.

========================
TOPIC TAGS
========================

Each lecture must include:
4–6 concise topic keywords.
Examples: ["variables", "memory", "scope", "stack"]

Avoid long phrases.

========================
ORDERING
========================

Lectures must appear in the exact order students should watch them.
Every lecture should naturally build upon previous lectures.
The curriculum should maximize learning efficiency while minimizing prerequisite confusion.

========================
OUTPUT REQUIREMENTS
========================

Return STRICTLY valid JSON.
Do NOT output:
- Markdown
- Explanations
- Notes
- Comments
- Additional text

Return ONLY the JSON object below.

    {
"lectures": [ { "title": "string",
                "primary_sections": ["N.N", "N.N"],
                "reference_sections": ["N.N"],
                "difficulty": "beginner|intermediate|advanced",
                "estimated_minutes": 12,
                "topic_tags": ["string"]  } ] 
}
"""


class CurriculumAgent(BaseAgent):

    def __init__(self):
        super().__init__()
        self.processor = PDFProcessor()

    def run(self, state: dict) -> dict:
        print("[CurriculumAgent] Planning curriculum from Table of Content...")

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

        print(f"  Sending Table of Content ({len(valid_section_ids)} sections) to LLM...")
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

        # Drop any lecture left with zero primary sections after filtering.
        kept = [lec for lec in lectures if lec.get("primary_sections")]
        dropped = len(lectures) - len(kept)
        if dropped:
            print(f"  WARNING: dropped {dropped} lecture(s) with no valid primary sections.")
        lectures = kept
        if not lectures:
            raise RuntimeError(
                "CurriculumAgent: no lectures retained any valid section IDs. "
                "The PDF section index and the planned curriculum do not line up."
            )

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
