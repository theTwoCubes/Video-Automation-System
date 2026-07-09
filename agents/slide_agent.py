import json
from agents.base_agent import BaseAgent
from services.slide_renderer.renderer import SlideRenderer
from services.slide_validator.validator import validate_slides, auto_fix_slides, print_validation_report

# Layout -> default transition when this slide is shown after a non-code slide
LAYOUT_TRANSITIONS = {
    "title":          "fade",
    "code":           "wipeleft",
    "terminal":       "wipeleft",
    "comparison":     "slideleft",
    "error_fix":      "slideleft",
    "summary":        "fade",
    "exercise":       "fade",
    "definition":     "fade",
    "default":        "fade",
}


SYSTEM_PROMPT = """You are a slide designer for theTwoCubes Learning technical YouTube channel.
Convert script segments into visually rich, information-dense slide specs.

SLIDE QUALITY RULES:
- Every slide must teach something SPECIFIC and CONCRETE.
- Bullets must contain actual technical details: real values, real syntax, real output.
  BAD: "C++ is a powerful language"
  GOOD: "C++ compiles to native machine code — runs 10-100x faster than interpreted languages"
  BAD: "Variables store data"
  GOOD: "int x = 42; // 4 bytes on stack, address ~0x7ffe12345678"
- Code slides: show COMPLETE, runnable code. Never use placeholder \"...\".
- Headlines: clear and specific. Max 8 words.
- Max 5 bullets. Each bullet max 14 words. Dense, punchy.
- Use the tag field for context (HOOK, CONCEPT, DEEP DIVE, CODE, MISTAKES, SUMMARY, EXERCISE).

LAYOUT DIVERSITY RULES (CRITICAL — enforce these strictly):
- No more than 40% of all slides may use the 'content' layout.
- Every lesson MUST have at least one 'two_column' or 'numbered_steps' slide.
- Use 'definition' for slides that introduce a single precise concept.
- Use 'numbered_steps' when there is a sequence of 3+ ordered actions.
- Use 'two_column' for before/after, wrong/right, old/new comparisons.
- Use 'error_fix' when showing a common mistake and its correction.
- Use 'terminal' for command-line demos and shell output.
- Use 'code' only when showing actual runnable code samples.
- 'summary' layout ALWAYS for the final takeaways slide — never use 'content'.
- 'exercise' layout for challenge slides.

ALL AVAILABLE LAYOUTS:
- title: opening slide (lesson_number + headline + subtitle)
- content: headline + bullets (concept explanations)
- code: headline + code_content (runnable code) + code_language
- two_column: headline + left_label + left_bullets + right_label + right_bullets
- numbered_steps: headline + bullets (shown as numbered circles)
- summary: Key Takeaways with checkmarks (3-5 specific bullets)
- exercise: challenge prompt with numbered tasks
- definition: single concept as an equation or precise statement
- terminal: command-line demo with $ prompts and output
- error_fix: side-by-side mistake vs correct code
- comparison: side-by-side any two alternatives

Output STRICTLY valid JSON. No markdown. No commentary."""

USER_TEMPLATE = """
Lesson title: {lesson_title}
Lesson position: {position}

You MUST generate exactly one slide for EACH of these slide_ids (in this order):
{required_slide_ids}

Total slides required: {slide_count}

Segments grouped by slide_id:
{grouped_segments}

Code examples available:
{code_refs}

Rules:
- slide_001 is ALWAYS the title layout.
- Generate EXACTLY {slide_count} slides — one per slide_id listed above.
- DIVERSITY: max 40% content layout. Force at least 1 two_column or numbered_steps.
- Each slide headline must be specific to that segment's content.
- For code layout: use the actual code from code examples.
- For two_column: fill both left_bullets and right_bullets with 3-4 items each.
- For numbered_steps: bullets are the steps (shown with numbers).
- For definition: bullets[0] is the equation/statement, bullets[1] is the explanation.
- For error_fix: left_bullets = broken code lines, right_bullets = fixed code lines.
- For terminal: bullets = command lines (lines starting with # are comments/output).
- Summary slide: bullets must list 3-5 specific concrete things the viewer now knows.
- Exercise slide: bullets list 2-3 specific tasks with concrete requirements.

Output JSON:
{{
  "slides": [
    {{
      "id": "slide_001",
      "layout": "title|content|code|two_column|numbered_steps|summary|exercise|definition|terminal|error_fix|comparison",
      "headline": "string (specific, max 8 words)",
      "subtitle": "string (title layout only)",
      "bullets": ["concrete bullet", ...],
      "left_bullets": [],
      "right_bullets": [],
      "left_label": "",
      "right_label": "",
      "code_content": "complete runnable code (code layout only)",
      "code_language": "cpp",
      "tag": "HOOK|CONCEPT|DEEP DIVE|CODE|MISTAKES|SUMMARY|EXERCISE",
      "lesson_number": {position},
      "transition_hint": "fade"
    }}
  ]
}}
"""


class SlideAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.renderer = SlideRenderer()

    def run(self, state: dict) -> dict:
        print("[SlideAgent] Generating slides...")

        lesson_title = state["lesson_title"]
        position = state.get("lesson_position", 1)
        script = state.get("script", {})
        code_examples = state.get("code_examples", [])
        output_dir = state["output_dir"]

        code_refs = {ex["id"]: ex.get("source_code", "")[:600] for ex in code_examples}

        segments = script.get("segments", [])

        # collect unique slide_ids in script order
        seen_ids: list[str] = []
        for seg in segments:
            sid = seg.get("slide_id", "slide_001")
            if sid not in seen_ids:
                seen_ids.append(sid)

        print(f"  Script references {len(seen_ids)} unique slides")

        # group segments by slide_id for the prompt
        grouped: dict[str, list[dict]] = {}
        for seg in segments:
            sid = seg.get("slide_id", "slide_001")
            grouped.setdefault(sid, []).append({
                "type": seg.get("type"),
                "text_preview": seg.get("text", "")[:120],
                "code_ref": seg.get("code_ref", ""),
            })

        grouped_summary = json.dumps(
            {sid: grouped.get(sid, []) for sid in seen_ids},
            indent=2,
        )[:3500]

        user_msg = USER_TEMPLATE.format(
            lesson_title=lesson_title,
            position=position,
            required_slide_ids="\n".join(f"  - {sid}" for sid in seen_ids),
            slide_count=len(seen_ids),
            grouped_segments=grouped_summary,
            code_refs=json.dumps(code_refs)[:1500],
        )

        result = self.llm.complete_json(SYSTEM_PROMPT, user_msg)
        slides_spec = result.get("slides", [])

        # build id → spec map from LLM response
        llm_slide_map: dict[str, dict] = {s.get("id", ""): s for s in slides_spec}

        # ensure every required slide_id has a slide — fill gaps with fallback
        final_slides: list[dict] = []
        for i, sid in enumerate(seen_ids):
            if sid in llm_slide_map:
                slide = llm_slide_map[sid]
            else:
                # create a content slide from the grouped segments
                segs_for_slide = grouped.get(sid, [])
                bullets = [s["text_preview"] for s in segs_for_slide[:4] if s.get("text_preview")]
                slide = {
                    "id": sid,
                    "layout": "content",
                    "headline": lesson_title if i == 0 else f"Part {i + 1}",
                    "subtitle": "",
                    "bullets": bullets[:4] or [lesson_title],
                    "left_bullets": [],
                    "right_bullets": [],
                    "left_label": "",
                    "right_label": "",
                    "code_content": "",
                    "tag": "",
                    "lesson_number": position,
                }
                print(f"  Auto-generated fallback slide for {sid}")

            # ensure all required fields
            slide.setdefault("lesson_number", position)
            slide.setdefault("bullets", [])
            slide.setdefault("left_bullets", [])
            slide.setdefault("right_bullets", [])
            slide.setdefault("left_label", "")
            slide.setdefault("right_label", "")
            slide.setdefault("subtitle", "")
            slide.setdefault("tag", "")
            slide.setdefault("code_content", "")
            final_slides.append(slide)

        print(f"  Rendering {len(final_slides)} slides to PNG...")

        # add transition hints before rendering
        for slide in final_slides:
            layout = slide.get("layout", "content")
            slide["transition_hint"] = LAYOUT_TRANSITIONS.get(layout, LAYOUT_TRANSITIONS["default"])

        # validate before rendering
        issues = validate_slides(final_slides)
        print_validation_report(issues)
        if issues:
            print("  Auto-fixing simple issues...")
            final_slides = auto_fix_slides(final_slides)

        slide_dir = f"{output_dir}/slides"
        slide_paths = self.renderer.render_slides(final_slides, slide_dir)

        # build id -> path mapping
        slide_id_to_path: dict[str, str] = {}
        for slide_data, img_path in zip(final_slides, slide_paths):
            slide_id_to_path[slide_data.get("id", "")] = img_path

        state["slide_contents"] = final_slides
        state["slide_image_paths"] = slide_paths
        state["slide_id_to_path"] = slide_id_to_path
        state["slide_validation_issues"] = issues
        print(f"  Rendered {len(slide_paths)} slides.")
        return state
