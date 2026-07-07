import json
import re
from agents.base_agent import BaseAgent
from services.knowledge.ingestion import KnowledgeIngestionService

STYLE_GUIDE = """
STYLE GUIDE for theTwoCubes Learning:

Voice: Confident senior engineer teaching a smart junior. Direct, specific, no fluff.
Pace: 130-145 words per minute. Mix punchy sentences with longer explanations.

OPENINGS: Never start with "In this lesson/video we will...".
Good: "You've seen a segfault. Today you learn exactly why it happens and how to prevent it."
Good: "Every C++ program you will ever write starts with exactly one thing."

ANALOGIES: Real-world analogy BEFORE formal definition. Always.
- Memory: a street with numbered houses (addresses)
- Pointers: a sticky note saying "the answer is in drawer 42"
- Stack: a stack of plates - last in first out
- Heap: a parking lot - park anywhere, remember where you parked

FORBIDDEN PHRASES — NEVER use these words or you fail QA:
"simply", "just", "easy", "obviously", "as you can see", "let's go ahead",
"straightforward", "note that", "it should be noted", "basic", "of course".
Replace "just" → omit or use "exactly / only / precisely".
Replace "simply" → omit or restructure the sentence.

TRANSITIONS: Never "Next let's talk about X".
Use: "Now that we know X, Y will make sense." / "Here is where it gets interesting."

CODE: Explain WHAT you will write BEFORE writing it. Then explain the output line by line.

ENDINGS: State exactly 3 things the viewer now knows. Tease next lesson specifically.

DEPTH: Be specific. Use real numbers, real output, real error messages. No vague statements.
"""

SYSTEM_PROMPT = f"""You are the script writer for theTwoCubes Learning, a technical YouTube channel.
Write a FULL narration script based on a lesson plan and knowledge context.

{STYLE_GUIDE}

CRITICAL: Each segment must have a slide_id. Multiple segments share the same slide_id
when they are narrating the same visual. A new slide_id means a slide change.
The slide_id format is "slide_001", "slide_002", etc. Assign them logically:
- Title slide: "slide_001" (1-2 segments)
- Each concept/section: 2-4 segments per slide
- Code slides: 3-5 segments (describe before, during, after)
- Summary slide: 1-2 segments

Output strictly valid JSON. No markdown. No commentary."""

USER_TEMPLATE = """
Lesson plan:
{lesson_plan}

Knowledge context (use ONLY this for factual claims):
{rag_context}

Write a complete script as JSON. MINIMUM {total_words} words total across all segments.
Each narration segment must be 80-150 words (never under 60, never over 160).

{{
  "lesson_id": "{lesson_id}",
  "segments": [
    {{
      "id": "seg_001",
      "slide_id": "slide_001",
      "type": "narration|code_demo",
      "text": "narration text here (80-150 words)",
      "duration_estimate_seconds": number,
      "code_ref": "code_example_id or empty string",
      "diagram_ref": "diagram_id or empty string"
    }}
  ],
  "total_words": number,
  "estimated_duration_seconds": number
}}

Requirements:
- EVERY section in the lesson plan needs 3-6 narration segments.
- The hook must be 2-3 segments totaling 250+ words.
- The deep_dive / concept section must have 6-10 segments totaling 700+ words.
- Code walkthrough: 1 segment explaining what the code does, 1 segment for each key line or block, 1 segment explaining the output.
- Summary: 2 segments. Exercise/challenge: 1 segment. What's next: 1 segment.
- TOTAL must be at least {total_words} words ({duration} minutes at 140 wpm).
- Be SPECIFIC. Use actual values, actual output, actual error messages.
"""


class ScriptAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.ingestion = KnowledgeIngestionService()

    def run(self, state: dict) -> dict:
        print(f"[ScriptAgent] Writing script for: {state['lesson_title']}")

        source_id = state["source_id"]
        lesson_id = state["lesson_id"]
        lesson_plan = state.get("lesson_plan", {})
        duration = lesson_plan.get("duration_estimate_minutes", 12)
        total_words = int(duration * 140)

        key_concepts = lesson_plan.get("key_concepts", [state["lesson_title"]])
        chunks = []
        for concept in key_concepts[:4]:
            chunks.extend(self.ingestion.query(source_id, concept, n_results=3))

        seen = set()
        unique_chunks = []
        for c in chunks:
            key = c[:100]
            if key not in seen:
                seen.add(key)
                unique_chunks.append(c)

        rag_context = "\n\n---\n\n".join(unique_chunks[:10])

        user_msg = USER_TEMPLATE.format(
            lesson_id=lesson_id,
            lesson_plan=json.dumps(lesson_plan, indent=2)[:2500],
            rag_context=rag_context[:2500],
            total_words=total_words,
            duration=duration,
        )

        script = self.llm.complete_json(SYSTEM_PROMPT, user_msg)

        all_text = " ".join(s.get("text", "") for s in script.get("segments", []))
        script["total_words"] = len(all_text.split())
        script["estimated_duration_seconds"] = int(script["total_words"] / 2.33)

        state["script"] = script
        print(f"  Script: {script['total_words']} words, ~{script['estimated_duration_seconds']//60}m{script['estimated_duration_seconds']%60}s")
        return state
