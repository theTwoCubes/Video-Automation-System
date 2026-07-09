import json
from agents.base_agent import BaseAgent

STYLE_GUIDE = """
STYLE GUIDE for theTwoCubes Learning:

Voice: Confident senior engineer teaching a smart junior. Direct, specific, no fluff.
Pace: 130-145 words per minute. Mix punchy sentences with longer explanations.
Sentence limit: Maximum 25 words per sentence. Active voice always.

OPENINGS: Never start with "In this lesson/video we will...".
Good: "You have seen a segfault. Today you learn exactly why it happens and how to prevent it."
Good: "Every C++ program you will ever write starts with exactly one thing."

ANALOGIES: Real-world analogy BEFORE formal definition. Always.
- Memory: a street with numbered houses (addresses)
- Pointers: a sticky note saying the answer is in drawer 42
- Stack: a stack of plates - last in first out
- Heap: a parking lot - park anywhere, remember where you parked

FORBIDDEN PHRASES: simply, just, easy, obviously, as you can see, let us go ahead,
straightforward, note that, it should be noted, basic, of course.

PAUSE MARKERS: Insert [PAUSE] between major topic transitions.
Example: "...and that is how pointers work.[PAUSE]Now let us look at references."

TRANSITIONS: Never use "Next let us talk about X".
Use: "Now that we know X, Y will make sense." or "Here is where it gets interesting."

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

CRITICAL INSTRUCTION ON DEPTH: The knowledge context provided may be brief or high-level. Do NOT limit your script to just summarizing it. You MUST expand on the context using your own expert knowledge to write a deep, thorough, perfectly explained technical script. Never hold back information just because the context didn't mention it.

Output strictly valid JSON. No markdown. No commentary."""

REVISION_SYSTEM = """You are a script editor for theTwoCubes Learning.
Revise a narration script for better pacing and clarity.

RULES:
- Max 25 words per sentence. Break long sentences.
- Active voice only. The compiler creates... not A copy is created...
- Remove forbidden words: simply, just, easy, obviously, straightforward, note that, basic.
- Add [PAUSE] between major section transitions only (not between every segment).
- Keep all slide_id assignments unchanged.
- Keep same JSON structure. Only modify text fields.
- Do NOT shorten segments below 60 words.

Output the same JSON structure with revised text fields only."""

USER_TEMPLATE = """
Lesson plan:
{lesson_plan}

Supplementary reference from the course PDF (exact sections declared for this lecture):

PRIORITY ORDER:
1. If a section directly and clearly covers the concept -> use it as ground truth
2. Use reference sections for background context only
3. Fill any gaps with your own expert knowledge
4. Never contradict the provided material

{section_text}

Write a complete script as JSON. MINIMUM {total_words} words total across all segments.
Each narration segment must be 80-150 words (never under 60, never over 160).

{{
  "lesson_id": "{lesson_id}",
  "segments": [
    {{
      "id": "seg_001",
      "slide_id": "slide_001",
      "type": "narration|code_demo",
      "text": "narration text here (80-150 words, max 25 words per sentence)",
      "duration_estimate_seconds": 35,
      "code_ref": "",
      "diagram_ref": ""
    }}
  ],
  "total_words": 0,
  "estimated_duration_seconds": 0
}}

Requirements:
- EVERY section in the lesson plan needs 3-6 narration segments.
- The hook must be 2-3 segments totaling 250+ words.
- The deep_dive section must have 6-10 segments totaling 700+ words.
- Code walkthrough: 1 segment for what the code does, 1 per key line block, 1 for output.
- Summary: 2 segments. Exercise: 1 segment. What is next: 1 segment.
- TOTAL must be at least {total_words} words ({duration} minutes at 140 wpm).
- Be SPECIFIC. Use actual values, actual output, actual error messages.
"""

REVISION_USER = """Here is the script to revise:

{script_json}

Apply all editing rules. Return the same JSON with improved text fields only.
Preserve all segment IDs, slide_ids, code_refs, and types exactly."""


class ScriptAgent(BaseAgent):
    def __init__(self):
        super().__init__()

    def run(self, state: dict) -> dict:
        print(f"[ScriptAgent] Writing script for: {state['lesson_title']}")

        lesson_id = state["lesson_id"]
        lesson_plan = state.get("lesson_plan", {})
        duration = lesson_plan.get("duration_estimate_minutes", 12)
        total_words = int(duration * 140)
        section_text = state.get("section_text", "No reference material available.")

        user_msg = USER_TEMPLATE.format(
            lesson_id=lesson_id,
            lesson_plan=json.dumps(lesson_plan, indent=2)[:3000],
            section_text=section_text[:4000],
            total_words=total_words,
            duration=duration,
        )

        # Pass 1: generate script
        script = self.llm.complete_json(SYSTEM_PROMPT, user_msg)

        # Pass 2: revise for pacing + SSML pauses
        try:
            print("  Pass 2: revising for pacing...")
            segs_json = json.dumps({"segments": script.get("segments", [])}, indent=2)[:6000]
            revised = self.llm.complete_json(
                REVISION_SYSTEM,
                REVISION_USER.format(script_json=segs_json),
            )
            if revised.get("segments") and len(revised["segments"]) == len(script.get("segments", [])):
                script["segments"] = revised["segments"]
                print("  Pass 2 complete.")
            else:
                print("  Pass 2 returned mismatched segments — using pass 1.")
        except Exception as e:
            print(f"  Pass 2 skipped: {e}")

        all_text = " ".join(s.get("text", "") for s in script.get("segments", []))
        script["total_words"] = len(all_text.split())
        script["estimated_duration_seconds"] = int(script["total_words"] / 2.33)

        state["script"] = script
        print(f"  Script: {script['total_words']} words, ~{script['estimated_duration_seconds']//60}m{script['estimated_duration_seconds']%60}s")
        return state
