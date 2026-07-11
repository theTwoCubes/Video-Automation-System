import json
from agents.base_agent import BaseAgent
from services.slide_renderer.renderer import SlideRenderer
from services.slide_validator.validator import validate_slides, auto_fix_slides, print_validation_report
from services.slide_renderer.layout_catalog import design_brief_json
from services.slide_renderer import selection

# Layout -> default transition when this slide is shown after a non-code slide
LAYOUT_TRANSITIONS = {
    "title":          "fade",
    "prose":          "fade",
    "split_code":     "wipeleft",
    "code":           "wipeleft",
    "terminal":       "wipeleft",
    "comparison":     "slideleft",
    "error_fix":      "slideleft",
    "two_column":     "slideleft",
    "numbered_steps": "fade",
    "summary":        "fade",
    "exercise":       "fade",
    "definition":     "fade",
    "chapter_title":  "fade",
    "agenda":         "fade",
    "hook":           "fade",
    "key_insight":    "fade",
    "big_number":     "fade",
    "quote":          "fade",
    "analogy":        "slideleft",
    "code_output":    "wipeleft",
    "code_evolution": "wipeleft",
    "snippet":        "wipeleft",
    "pros_cons":      "slideleft",
    "table":          "slideleft",
    "timeline":       "fade",
    "cycle":          "fade",
    "bar_chart":      "fade",
    "quiz":           "fade",
    "think_pause":    "fade",
    "warning":        "fade",
    "tip":            "fade",
    "checkpoint":     "fade",
    "mental_model":   "fade",
    "resources":      "fade",
    "default":        "fade",
}


SYSTEM_PROMPT = """You are a senior slide designer for theTwoCubes Learning, a technical YouTube channel.
Your job: convert narrated script segments into visually diverse, pedagogically excellent slide specifications.

You have CREATIVE AUTHORITY. Do not just mechanically pick templates.
Think carefully: which layout will make this concept land hardest?
If a concept needs something novel, invent it by combining or adapting the provided layouts.


## CONTENT QUALITY (non-negotiable)

- Every bullet must teach something SPECIFIC: a real value, real syntax, a runtime behavior, a tradeoff, or a failure mode.
  BAD:  "C++ is a powerful language"
  GOOD: "C++ compiles to native machine code - runs 10-100x faster than Python/JS in compute-bound work"
  BAD:  "Variables store data"
  GOOD: "`int x = 42;` occupies exactly 4 bytes on the stack at address ~0x7ffe12345678"
- Headlines: specific, max 8 words, no filler words ("Introduction to...", "Overview of...").
- Code slides: COMPLETE, runnable code. Never use placeholder `...`.
- Max 4 bullets per content/prose slide. Max 3 bullets for split_code left column.
- Max 3 sentences in any `paragraph` field.
- If a bullet mentions syntax, wrap the syntax in backtick notation: use `code` inline notation.
- Never use: "In summary", "As we can see", "It is important to", "Let us explore", "Simply put".


## LAYOUT DIVERSITY RULES (CRITICAL - enforce strictly)

- NO TWO CONSECUTIVE SLIDES may use the same layout.
- Max 35% of all slides may use the `content` layout.
- For every 3 `content` slides, at least 1 must be `split_code` or `code`.
- `prose` is REQUIRED at least once per lesson for the first major concept (explain WHY before WHAT).
- `definition` is REQUIRED at least once per lesson when a new term is formally introduced.
- `split_code` is REQUIRED whenever the script explains a concept AND shows code for it.
- `two_column` or `comparison` is REQUIRED whenever contrasting two approaches or types.
- `exercise` MUST be the second-to-last slide.
- `summary` MUST be the very last slide.
- `numbered_steps` must be used when any section has 3+ sequential steps.
- `terminal` must be used when showing shell/command usage.


## ALL 13 LAYOUTS

1. **title** - Opening slide.
   Fields: headline (lesson title), subtitle (what the viewer will learn), lesson_number.

2. **content** - Conceptual bullet-point slide. Max 4 bullets.
   Fields: headline, bullets (max 4), tag, callout (optional: one key insight in a highlighted box).

3. **prose** - Explain the INTUITION first, then give evidence bullets.
   Fields: headline, paragraph (2-3 sentence explanation of why/intuition), bullets (2-3 specific evidence bullets).
   USE WHEN: introducing concepts where the viewer needs the mental model before the details.

4. **code** - Large code block with headline. For code-heavy segments.
   Fields: headline, code_content (complete runnable code), code_language, code_filename (optional), caption (optional 1-line note).

5. **split_code** - Left: explanation, Right: code. Best for teaching code in context.
   Fields: headline, paragraph (explanation), bullets (2-3 bullets on left), code_content, code_language, code_filename.
   USE WHEN: the script explains something and immediately shows code for it.

6. **two_column** - Side-by-side comparison of two approaches/ideas.
   Fields: headline, left_label, left_bullets (3-4), right_label, right_bullets (3-4).
   USE WHEN: contrasting two options, two versions, two styles.

7. **numbered_steps** - Sequential procedure with numbered teal circles.
   Fields: headline, bullets (each bullet is a step, max 5).
   USE WHEN: installation, compilation, setup, or any ordered procedure.

8. **summary** - Key Takeaways slide, always last.
   Fields: headline ("Key Takeaways" or custom), bullets (3-5 SPECIFIC things the viewer now knows), whats_next (optional teaser for next lesson).
   whats_next MUST be based only on the real "Next lesson" title given to you below - never invent a topic. Leave it empty if none is given.
   whats_next must be ONLY the teaser sentence itself - do NOT start it with "Next:", "Next lesson:", "Next up," or
   similar, the renderer already prepends "Next: " in front of whatever you write (e.g. write
   "we tackle pointers and what that asterisk actually means" - not "Next: we tackle pointers...").

9. **definition** - Ultra-minimal spotlight on a single term.
   Fields: headline (the term being defined), bullets[0] (the concise definition or equation), bullets[1] (optional expanded explanation), context (optional 1-line real-world usage), tag.

10. **terminal** - Shell command demonstration.
    Fields: headline, bullets (each is a shell command or output; lines starting with # or // are output/comments).

11. **error_fix** - Wrong vs. correct code side by side.
    Fields: headline, left_bullets (lines of broken code), right_bullets (lines of fixed code).

12. **comparison** - Any two alternatives side by side (types, approaches, APIs).
    Fields: headline, left_label, left_bullets, right_label, right_bullets.

13. **exercise** - Challenge for the viewer. Second-to-last slide.
    Fields: headline (the challenge title), bullets (2-3 specific tasks), hint (optional help text).
    NOTE: exercise uses an ORANGE accent color, not teal.
    NOTE: do NOT prefix bullets with "1.", "2." etc - the renderer numbers them automatically.


## EXTENDED LAYOUT LIBRARY (use these for variety, not just the 13 core layouts above)

**Opening/structural**
14. **chapter_title** - section divider within a lesson. Fields: headline (2-5 words), subtitle (one-line preview).
    USE WHEN: moving from one major sub-topic to another within the same lesson.
15. **agenda** - lesson roadmap. Fields: headline, items (4-7 short section names).
    USE WHEN: slide 2, right after title, previewing what the lesson covers.
16. **hook** - attention-grabbing question/statement. Fields: headline (up to 15 words), subtitle (optional).
    USE WHEN: early in the lesson, to create intrigue before explaining.

**Concept/explanation**
17. **key_insight** - one powerful memorable statement. Fields: headline (use **bold** to accent key words), subtitle (optional).
    USE WHEN: a single sentence captures the "aha moment" of the section. Use sparingly (max 1-2 per lesson).
18. **big_number** - spotlight one impressive metric. Fields: number (e.g. "4 bytes"), label, context.
    USE WHEN: a concrete number makes the concept tangible.
19. **quote** - attributed quote from spec/docs/authority. Fields: headline (optional context), text, attribution.
20. **analogy** - real-world metaphor mapped to technical concept. Fields: headline, left_label, left_content, right_label, right_content, connection.

**Code/technical**
21. **code_output** - code block + its terminal output together. Fields: headline, code_content, code_language, code_filename, output_lines (list).
    USE WHEN: the narrator shows what running the code produces.
22. **code_evolution** - before/after code transformation (refactor/optimize, NOT a mistake). Fields: headline, left_label, left_code, right_label, right_code, code_language.
23. **snippet** - tiny code fragment (1-5 lines) without window chrome, for inline syntax reference. Fields: headline, code_content, code_language, explanation.

**Comparison/data**
24. **pros_cons** - advantages vs disadvantages. Fields: headline, pros (list, max 4), cons (list, max 4).
25. **table** - structured data grid. Fields: headline, headers (max 4), rows (list of lists, max 6).
26. **timeline** - chronological progression. Fields: headline, events (list of {label, description}, max 6).

**Process**
27. **cycle** - repeating circular process. Fields: headline, steps (list, 3-6 items).
28. **bar_chart** - horizontal comparison bars. Fields: headline, bars (list of {label, value (0-100), display_value}, max 6).

**Engagement**
29. **quiz** - multiple choice knowledge check. Fields: headline, question, options (list of {label, text}, max 4), answer (correct label).
30. **think_pause** - reflective prompt, pause icon. Fields: headline (the question), subtitle (optional).

**Warnings/callouts**
31. **warning** - danger/critical mistake to avoid (red accent, no "fix" side - use error_fix for that). Fields: headline, bullets (2-3).
32. **tip** - pro-tip/best practice (blue accent). Fields: headline, bullets (2-3), callout (optional summary).

**Closing**
33. **checkpoint** - mid-lesson recap before moving to the next section. Fields: headline (default "So Far"), bullets (2-4), transition (preview of what's next).
34. **mental_model** - closing rule/heuristic distilling the whole lesson. Fields: headline (the rule as a sentence), explanation (optional).
35. **resources** - further reading pointers. Fields: headline, items (list of {title, description}, max 5).


## AUTONOMOUS CREATIVITY MANDATE

Do not restrict yourself strictly to the rules above if a better pedagogical method exists.
You MUST autonomously think of, and implement, improvement techniques that are not explicitly listed:
- Use creative metaphors in paragraph fields to make abstract concepts concrete.
- Mix unexpected layout combinations (e.g., a definition slide immediately followed by a split_code).
- Add callout boxes to content slides for "aha moment" insights.
- Use whats_next in the summary to build anticipation for the real next lesson given below.
- If a slide would benefit from a visual structure not captured by the above, describe it in an
  extended field like `custom_note` and the renderer will use it as a callout.

Output STRICTLY valid JSON. No markdown. No commentary outside the JSON."""

USER_TEMPLATE = """
Lesson title: {lesson_title}
Lesson position: {position}
Next lesson: {next_lesson_title}

You MUST generate exactly one slide for EACH of these slide_ids (in this order):
{required_slide_ids}

Total slides required: {slide_count}

Segments grouped by slide_id:
{grouped_segments}

Lesson plan sections, in original order (each section became roughly one slide_id above, in the
same sequence). The planner already picked a `recommended_layout` per section after weighing its
content shape against the layout catalog - default to it unless the actual segment text clearly
calls for something else (e.g. planner said "content" but the segment turns out to be a sequential
procedure - use numbered_steps instead):
{planner_sections}

Code examples available:
{code_refs}

Rules:
- slide_001 is ALWAYS the title layout.
- Generate EXACTLY {slide_count} slides, one per slide_id listed above.
- DIVERSITY: max 35% content layout. No two consecutive slides the same layout.
- Force at least one split_code, one prose, one definition in the lesson.
- exercise is always the second-to-last slide, summary always last.

JSON schema (include ALL fields you use for the chosen layout, use empty string/list/omit for unused fields):
{{
  "slides": [
    {{
      "id": "slide_001",
      "layout": "title|content|prose|code|split_code|two_column|numbered_steps|summary|exercise|definition|terminal|error_fix|comparison|chapter_title|agenda|hook|key_insight|big_number|quote|analogy|code_output|code_evolution|snippet|pros_cons|table|timeline|cycle|bar_chart|quiz|think_pause|warning|tip|checkpoint|mental_model|resources",
      "headline": "Specific headline, max 8 words (most layouts)",
      "subtitle": "title/chapter_title/hook/key_insight/think_pause layout",
      "paragraph": "prose/split_code: 2-3 sentence explanation",
      "bullets": ["concrete bullet with real values - used by many layouts as the generic list field"],
      "callout": "content/tip layout only: optional key insight highlighted in a box",
      "whats_next": "summary layout only: teaser for next lesson",
      "left_label": "",
      "left_bullets": [],
      "right_label": "",
      "right_bullets": [],
      "code_content": "complete runnable code (code/split_code/code_output/snippet layout only)",
      "code_language": "cpp",
      "code_filename": "main.cpp",
      "caption": "code layout only: optional 1-line note below code block",
      "context": "definition/big_number layout only: real-world usage example",
      "hint": "exercise layout only: optional hint text",
      "items": "agenda/resources layout: list of strings, or list of {{title, description}} for resources",
      "number": "big_number layout: the value to display large, e.g. '4 bytes'",
      "label": "big_number layout: what the number represents",
      "text": "quote layout: the quote text",
      "attribution": "quote layout: who said it or where it is from",
      "left_content": "analogy layout: real-world side, 1-2 sentences",
      "right_content": "analogy layout: technical side, 1-2 sentences",
      "connection": "analogy layout: one sentence linking the two sides",
      "explanation": "snippet/mental_model layout: elaboration text",
      "output_lines": "code_output layout: list of output/terminal lines",
      "left_code": "code_evolution layout: the 'before' code",
      "right_code": "code_evolution layout: the 'after' code",
      "pros": "pros_cons layout: list of advantage strings, max 4",
      "cons": "pros_cons layout: list of disadvantage strings, max 4",
      "headers": "table layout: list of column header strings, max 4",
      "rows": "table layout: list of row lists, each with one string per header, max 6",
      "events": "timeline layout: list of {{label, description}}, max 6",
      "steps": "cycle layout: list of step label strings, 3-6",
      "bars": "bar_chart layout: list of {{label, value (0-100 int), display_value}}, max 6",
      "question": "quiz layout: the question text",
      "options": "quiz layout: list of {{label: 'A', text: '...'}}, max 4",
      "answer": "quiz layout: the correct option's label",
      "transition": "checkpoint layout: one sentence previewing what comes next",
      "tag": "HOOK|CONCEPT|DEEP DIVE|CODE|MISTAKE|COMPARISON|SUMMARY|CHALLENGE",
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

        # Cap segments PER slide_id rather than slicing the whole serialized JSON
        # blob to a flat character limit - a flat [:3500] cut silently dropped the
        # segment context for whichever slide_ids happened to serialize later,
        # starving them of real narration text and causing the LLM to invent
        # slide content unmoored from what that slide's audio actually says.
        # Capping per-slide instead guarantees every slide_id gets real context
        # regardless of its position in the lesson.
        MAX_SEGMENTS_PER_SLIDE = 4
        grouped_for_prompt = {
            sid: grouped.get(sid, [])[:MAX_SEGMENTS_PER_SLIDE] for sid in seen_ids
        }
        grouped_summary = json.dumps(grouped_for_prompt, indent=2)[:8000]

        next_lesson_title = state.get("next_lesson_title") or "(none - this is the final lesson)"

        lesson_plan = state.get("lesson_plan", {})
        planner_sections = [
            {
                "type": sec.get("type", ""),
                "title": sec.get("title", ""),
                "recommended_layout": sec.get("recommended_layout", ""),
            }
            for sec in lesson_plan.get("sections", [])
        ]
        planner_summary = json.dumps(planner_sections, indent=2)[:3000]

        user_msg = USER_TEMPLATE.format(
            lesson_title=lesson_title,
            position=position,
            next_lesson_title=next_lesson_title,
            required_slide_ids="\n".join(f"  - {sid}" for sid in seen_ids),
            slide_count=len(seen_ids),
            grouped_segments=grouped_summary,
            planner_sections=planner_summary,
            code_refs=json.dumps(code_refs)[:1500],
        )

        # Hand the LLM the machine-readable design system (blueprint §22): the
        # per-layout caps, families, density budgets, and hard rules as data, so
        # it chooses like a deck designer working within a system rather than
        # improvising. Reasoning is enabled for this call via the provider
        # default (BUG-07), which is what lets it weigh the rubric.
        user_msg += (
            "\n\nMACHINE-READABLE DESIGN SYSTEM - obey these layout caps, "
            "families, density budgets, and rules exactly:\n" + design_brief_json()
        )

        result = self.llm.complete_json(SYSTEM_PROMPT, user_msg)
        slides_spec = result.get("slides", [])

        # build id → spec map from LLM response
        llm_slide_map: dict[str, dict] = {s.get("id", ""): s for s in slides_spec}

        # ensure every required slide_id has a slide - fill gaps with fallback
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

            slide.setdefault("lesson_number", position)
            slide.setdefault("bullets", [])
            slide.setdefault("paragraph", "")
            slide.setdefault("callout", "")
            slide.setdefault("whats_next", "")
            slide.setdefault("context", "")
            slide.setdefault("hint", "")
            slide.setdefault("left_bullets", [])
            slide.setdefault("right_bullets", [])
            slide.setdefault("left_label", "")
            slide.setdefault("right_label", "")
            slide.setdefault("subtitle", "")
            slide.setdefault("tag", "")
            slide.setdefault("code_content", "")
            slide.setdefault("code_filename", "")
            slide.setdefault("caption", "")
            # Defaults for the new category A-J layouts so Jinja never iterates
            # or indexes an undefined variable (iterating Undefined raises, it
            # does not just render blank like a printed Undefined would).
            slide.setdefault("items", [])
            slide.setdefault("number", "")
            slide.setdefault("label", "")
            slide.setdefault("text", "")
            slide.setdefault("attribution", "")
            slide.setdefault("left_content", "")
            slide.setdefault("right_content", "")
            slide.setdefault("connection", "")
            slide.setdefault("explanation", "")
            slide.setdefault("output_lines", [])
            slide.setdefault("left_code", "")
            slide.setdefault("right_code", "")
            slide.setdefault("pros", [])
            slide.setdefault("cons", [])
            slide.setdefault("headers", [])
            slide.setdefault("rows", [])
            slide.setdefault("events", [])
            slide.setdefault("steps", [])
            slide.setdefault("bars", [])
            slide.setdefault("question", "")
            slide.setdefault("options", [])
            slide.setdefault("answer", "")
            slide.setdefault("transition", "")
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

        # Deck-level design-system audit (diversity, rhythm, density) - reports
        # violations of the rules the brief asks the LLM to follow, so they show
        # up in the pipeline log and can be tracked over time.
        print(selection.audit_summary(final_slides))
        state["layout_audit"] = selection.audit(final_slides)

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
