import json
import re
from agents.base_agent import BaseAgent

STYLE_GUIDE = """
PERSONA: You are a senior engineer who has been doing this for 15 years.
You are at the whiteboard, talking to a smart junior who joined the team last week.
You use "I" and "you" constantly. "When I first saw this, I thought..." "You are going to run into this."
You care about them actually understanding it, not just memorizing it.

TEACHING SEQUENCE (non-negotiable):
1. Intuition FIRST. Before any definition, give a real-world analogy or mental model.
   - Pointers? "Think of a sticky note that says 'the answer is in drawer 42'."
   - Stack? "Last plate you put on is the first you take off."
   - Heap? "Parking lot. Park anywhere. Just remember where you left the car."
2. Then the formal definition or syntax.
3. Then a concrete example - real values, real output, real error messages.
4. Then the common mistake people make. Show the broken code first, then the fix.

VOICE: Confident, direct, with dry humor and cheerful. Never bland.
SENTENCE LENGTH: Mix punchy short sentences with longer explanations.
  Good: "That is it. One line. That is all a pointer is."
  Good: "What happens here is that the compiler creates a completely separate copy, 
         which means any changes you make inside the function are invisible to the caller."

OPENINGS: Hook immediately. No preamble. No "In this video we will learn..."
  Good: "Every C++ program you will ever write starts with exactly one thing."
  Good: "You have seen a segfault. Today you learn exactly why it happens."
  Good: "I want to show you something that tripped me up for three days when I was starting out."

TRANSITIONS: Never "Next let us talk about X".
  Use: "Now that you understand X, Y is going to make perfect sense."
  Use: "Here is where it gets interesting."
  Use: "This is the part most tutorials skip."

CODE NARRATION:
  - Announce WHAT you will write before writing it.
  - Then walk line by line: "This line declares an integer n and sets it to 42."
  - Then explain the output: "When you run this, you get exactly this on screen."
  - Always read the output aloud - EXCEPT raw binary/hex/machine-code digit sequences,
    which the NEVER WRITE OUT AS NARRATION rule below covers.

NEVER WRITE OUT RAW BINARY/HEX/MACHINE-CODE AS NARRATION (mandatory):
  Never put a literal sequence of binary digits (e.g. "01001000 01101001"), a raw hex
  dump, or a long machine-code byte sequence into narration `text` - a TTS voice reading
  each digit aloud sounds broken and teaches nothing. Instead:
  - Describe it in decimal or plain English: "that byte holds seventy-two, which is the
    ASCII code for the letter H" instead of "zero one zero zero one zero zero zero".
  - If the bit PATTERN itself is the point (e.g. explaining two's complement), describe
    it qualitatively: "seven zeros followed by a one" or "the high bit flips to one" -
    never dictate more than 8 raw digits in a row.
  - It is fine for the SLIDE to display the full binary/hex string visually (bullets/code
    blocks are not narration) - this rule only restricts what the narration text says
    aloud.

FORBIDDEN WORDS AND PHRASES: simply, just, easy, easily, obviously, as you can see,
let us go ahead, straightforward, note that, it should be noted, basic, of course,
in this lesson, in this video, we will be learning, today we will, let us begin,
great, awesome, it is worth noting, in the real world, it is important to understand,
general-purpose, powerful language, widely used, commonly used, let us explore,
let us look at, in summary, to summarize, as mentioned.

CONCRETE EXAMPLE RULE (mandatory):
Every time you introduce a concept, you MUST immediately follow with:
  - An actual value: not "an integer" but "the integer 42"
  - Actual syntax: not "a variable declaration" but "int x = 42;"
  - Actual output: not "it prints something" but "it prints: 42"
  - Actual error: not "you get an error" but "you get: error: use of undeclared identifier 'y'"

SPECIFICITY RULE:
- Never state a fact the viewer already knows. Every sentence must reveal:
  a mechanism, a number, a tradeoff, a failure mode, or a surprising behavior.
- Bad: "Variables store data in memory."
- Good: "An int on a 64-bit system lives on the stack frame at an 8-byte aligned address.
  If you print its address with &x, you see something like 0x7ffee12a4b2c."

PAUSE MARKERS: Insert [PAUSE] between major topic shifts only.
  Example: "...and that is how pointers work.[PAUSE]Now let us look at references."

ENDINGS: Name exactly 3 concrete things the viewer now knows. Then tease the next lesson
using ONLY the real next-lesson title given to you in the prompt below (in the
"Next lesson" field) - never invent, guess, or embellish what the next lesson covers.
Turn the given title into a natural spoken hook, e.g. if given "Basic Syntax and
Variables", say something like "Next time, we get our hands dirty with the actual
building blocks of every program: syntax and variables." If no next lesson title is
given (this is the final lesson of the course), congratulate the viewer on finishing
the course instead of teasing a next topic.
"""

SYSTEM_PROMPT = f"""
You are the script writer for "theTwoCubes Learning", a technical YouTube channel.
Write a FULL narration script based on a lesson plan and knowledge context.

{STYLE_GUIDE}

SLIDE ASSIGNMENTS:
Each segment must have a slide_id. Multiple segments share the same slide_id
when narrating the same visual. A new slide_id = a slide change.
Format: "slide_001", "slide_002", etc.
- Title slide: "slide_001" (1-2 segments ONLY - do not dump multiple concepts onto
  the title slide, that leaves the viewer staring at a static screen for too long).
- Each concept/section: 2-4 segments per slide
- Code slides: 3-5 segments (intro → line-by-line → output)
- Summary slide: last 1-2 segments
- RULE OF THUMB: a single slide_id should rarely carry more than ~30-45 seconds of
  combined narration (roughly 5-6 segments at normal length). If a section has more
  to say than that, split it across multiple slide_ids so the visual changes to match
  what is being discussed - the audio and the visual must stay in sync, not just the
  audio droning on over one frozen slide.

VISUAL SYNCHRONIZATION & DIAGRAM PACING:
You are the central authority for the lesson. Your narration script drives what code and diagrams will be generated later. 
If the lesson plan marks a section with `needs_diagram: true` or `needs_code: true`, you MUST explicitly narrate what is happening in that visual.
- For code: narrate the variable names, the function logic, and the expected output you want the Code Generator to write.
- For diagrams: narrate the shapes, the flow, and the visual metaphor you want the Diagram Generator to draw.
Your spoken words will be passed directly to the Code and Diagram AI to ensure they build exactly what you described.

CRITICAL DIAGRAM PACING RULE:
A diagram is effectively a COMPLETELY DIFFERENT SLIDE visually. When you tag a segment with `diagram_ref`, the video cuts away from the text slide and fills the screen with the diagram. When you leave `diagram_ref` empty, it cuts back to the text slide.
- You have absolute control over this pacing. You can show the diagram before explaining the slide, during it, or after.
- If you want the diagram to stay on screen for multiple sentences, you MUST tag ALL of those consecutive segments with the SAME `diagram_ref`.
- Use this capability purposefully and deliberately. Do not toggle erratically back and forth between the slide and the diagram every single sentence, as rapid visual flashing will disorient the viewer. Group your diagram-focused sentences together smoothly.

DEPTH REQUIREMENT: The reference material may be brief. You MUST go into deep, technical depth, but FOCUS EXCLUSIVELY ON WHAT IS IMPORTANT. 
Do NOT generate vague filler, repetitive fluff, or unnecessarily drawn-out explanations just to increase length. Teach the hard, complex parts with absolute clarity and precision. 
The viewer paused to watch this—give them high signal-to-noise ratio insights they could not get from a generic textbook.

FACTUAL ACCURACY:  If the reference material explicitly defines a concept, treat it as ground truth. Only expand using well-established computer science knowledge.
Never invent APIs, compiler behavior, language rules, memory layouts, performance numbers, or implementation details.
When multiple implementations exist, state that explicitly rather than pretending one is universal. Output strictly valid JSON. No markdown fences. Do NOT output raw markdown symbols (like **, *, or `) inside the narration text itself, as it will be read aloud by TTS. No commentary outside the JSON."""

REVISION_SYSTEM = """
You are the final script editor for "theTwoCubes Learning."
Your job is NOT to rewrite the lesson. Your job is to make it sound like an experienced software engineer naturally explaining a concept to a junior developer.

EDITING RULES:

1. Conversational
- Pass the "Coffee Shop Test"—it should sound spoken, not written.
- Use "I", "you", and "we" naturally.
- Keep the tone confident, direct, and engaging.

2. Pacing
- Break long sentences into shorter ones.
- Vary sentence length to create a natural rhythm.
- Add at most 3 "[PAUSE]" markers between major topic shifts.

3. Clarity
- Use active voice.
- Remove robotic or academic wording.
- Remove repetition unless it reinforces an important idea.
- Preserve all technical accuracy and examples.

4. TTS Friendly
- Write exactly how a human would speak.
- Avoid awkward punctuation, nested clauses, and tongue twisters.
- Ensure transitions between ideas feel smooth.

5. Integrity
- Do NOT change slide_id, id, type, code_ref, diagram_ref, or the JSON structure.
- Modify ONLY the narration text.
- Return strictly valid JSON. No markdown or commentary.
"""

USER_TEMPLATE = """
Lesson plan:
{lesson_plan}

Next lesson: {next_lesson_title}
(If this says "(none - this is the final lesson)", do NOT tease a next topic - close
by congratulating the viewer on completing the course instead.)

Reference material from the course PDF:

PRIORITY:
1. If a section directly covers the concept → use it as ground truth
2. Use reference for background context
3. Fill gaps with your own expert knowledge
4. Never contradict the provided material

{section_text}

Write a complete script as JSON. Write as many words as the material demands - 
do NOT target a word count, just teach the topic thoroughly.
Every narration segment: 80-200 words. Aim for 3-5 segments per lesson section.

{{
  "lesson_id": "{lesson_id}",
  "segments": [
    {{
      "id": "seg_001",
      "slide_id": "slide_001",
      "type": "narration",
      "text": "narration text here",
      "code_ref": "",
      "diagram_ref": ""
    }}
  ],
  "total_words": 0,
  "estimated_duration_seconds": 0
}}

Requirements:
- EVERY lesson section needs 3-6 narration segments with real depth.
- Hook: 2-3 segments. Open with the WHY this matters today.
- Deep dive: 5-10 segments. Show broken approach before correct one.
- Code walkthrough: Intro segment + 1 segment per key block + output segment.
- Summary: 2 segments listing exactly what changed in viewer's understanding.
- Exercise: 1 segment framing the challenge as a real engineering problem.
- Be SPECIFIC: use actual values, actual output, actual error messages.
"""

def _backfill_diagram_refs(script: dict, lesson_plan: dict) -> None:
    """The DIAGRAM_REF LINKING instruction asks the LLM to tag the right narration
    segment(s) with diagram_ref. However, the LLM sometimes hallucinates section IDs
    or assigns them out of chronological order (e.g. putting the summary diagram on
    the roadmap slide). A naive global word-overlap search also causes severe
    sequence mismatch.
    
    This method deterministically assigns diagram references using a monotonic 
    search: ensuring diagrams always appear in the exact chronological sequence
    dictated by the lesson plan."""
    segments = script.get("segments", [])
    if not segments:
        return
        
    # Trust the LLM's placement first! We no longer wipe them.
    # We will only backfill if a required diagram is missing entirely.

    last_assigned_idx = 0
    sections = lesson_plan.get("sections", [])
    
    for sec_idx, section in enumerate(sections):
        if not section.get("needs_diagram") or not section.get("id"):
            continue
            
        want_ref = f"diag_{section['id']}"
        
        # Check if the AI already successfully placed this diagram
        if any(s.get("diagram_ref") == want_ref for s in segments):
            print(f"  [ScriptAgent] AI successfully placed {want_ref} on its own. Trusting AI timing.")
            continue
            
        section_text = section.get("title", "") + " " + " ".join(section.get("key_points", []))
        section_words = set(re.findall(r"[a-z0-9']+", section_text.lower()))
        if not section_words:
            continue

        best_seg, best_score, best_idx = None, -9999, -1
        
        # Expected relative position in the script
        expected_ratio = sec_idx / max(1, len(sections))
        expected_seg_idx = int(expected_ratio * len(segments))
        
        for i, seg in enumerate(segments):
            if seg.get("diagram_ref") or seg.get("type") not in ("narration", "code_demo"):
                continue
                
            # Enforce strict sequence: diagrams cannot jump backwards in time
            if i < last_assigned_idx:
                continue
                
            seg_words = set(re.findall(r"[a-z0-9']+", seg.get("text", "").lower()))
            overlap = len(section_words & seg_words)
            
            # Penalize jumping too far from the expected chronological position
            distance = abs(i - expected_seg_idx)
            score = overlap - (distance * 0.1)
            
            if score > best_score:
                best_score = score
                best_seg = seg
                best_idx = i

        if best_seg is not None:
            best_seg["diagram_ref"] = want_ref
            last_assigned_idx = best_idx
            print(f"  [ScriptAgent] Chronologically mapped {want_ref} to segment {best_seg.get('id', '?')}")


def _backfill_code_refs(script: dict, lesson_plan: dict) -> None:
    """Deterministically assigns code references using monotonic sequence mapping,
    ensuring code references appear chronologically and match the lesson plan's needs_code flags."""
    segments = script.get("segments", [])
    # Trust the LLM's placement first!
    # We will only backfill if a required code block is missing entirely.

    last_assigned_idx = 0
    sections = lesson_plan.get("sections", [])
    
    for sec_idx, section in enumerate(sections):
        if not section.get("needs_code") or not section.get("id"):
            continue
            
        want_ref = f"code_{section['id']}"
        
        # Check if the AI already successfully placed this code
        if any(s.get("code_ref") == want_ref for s in segments):
            print(f"  [ScriptAgent] AI successfully placed {want_ref} on its own. Trusting AI timing.")
            continue
            
        section_text = section.get("title", "") + " " + " ".join(section.get("key_points", []))
        section_words = set(re.findall(r"[a-z0-9']+", section_text.lower()))
        if not section_words:
            continue

        best_seg, best_score, best_idx = None, -9999, -1
        
        expected_ratio = sec_idx / max(1, len(sections))
        expected_seg_idx = int(expected_ratio * len(segments))
        
        for i, seg in enumerate(segments):
            if seg.get("code_ref") or seg.get("type") not in ("narration", "code_demo"):
                continue
                
            if i < last_assigned_idx:
                continue
                
            seg_words = set(re.findall(r"[a-z0-9']+", seg.get("text", "").lower()))
            overlap = len(section_words & seg_words)
            
            distance = abs(i - expected_seg_idx)
            score = overlap - (distance * 0.1)
            
            if score > best_score:
                best_score = score
                best_seg = seg
                best_idx = i

        if best_seg is not None:
            best_seg["code_ref"] = want_ref
            last_assigned_idx = best_idx
            print(f"  [ScriptAgent] Chronologically mapped {want_ref} to segment {best_seg.get('id', '?')}")


REVISION_USER = """
Here is the script to revise:

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
        section_text = state.get("section_text", "No reference material available.")
        next_lesson_title = state.get("next_lesson_title") or "(none - this is the final lesson)"

        user_msg = USER_TEMPLATE.format(
            lesson_id=lesson_id,
            lesson_plan=json.dumps(lesson_plan, indent=2)[:3000],
            next_lesson_title=next_lesson_title,
            section_text=section_text[:4000],
        )

        # Pass 1: generate script
        script = self.llm.complete_json(SYSTEM_PROMPT, user_msg)

        # Pass 2: revise for voice and pacing
        try:
            print("  Pass 2: revising for voice + pacing...")
            segs_json = json.dumps({"segments": script.get("segments", [])}, indent=2)[:6000]
            revised = self.llm.complete_json(
                REVISION_SYSTEM,
                REVISION_USER.format(script_json=segs_json),
            )
            if revised.get("segments") and len(revised["segments"]) == len(script.get("segments", [])):
                script["segments"] = revised["segments"]
                print("  Pass 2 complete.")
            else:
                print("  Pass 2 returned mismatched segments - using pass 1.")
        except Exception as e:
            print(f"  Pass 2 skipped: {e}")

        _backfill_diagram_refs(script, lesson_plan)
        _backfill_code_refs(script, lesson_plan)

        all_text = " ".join(s.get("text", "") for s in script.get("segments", []))
        script["total_words"] = len(all_text.split())
        script["estimated_duration_seconds"] = int(script["total_words"] / 2.33)

        state["script"] = script
        wpm_dur = script["estimated_duration_seconds"]
        print(f"  Script: {script['total_words']} words, ~{wpm_dur // 60}m{wpm_dur % 60}s")
        return state
