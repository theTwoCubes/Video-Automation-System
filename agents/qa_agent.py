from agents.base_agent import BaseAgent


SYSTEM_PROMPT = """You are a QA reviewer for theTwoCubes Learning.
Review lesson content and flag issues. Be strict but fair.
Output strictly valid JSON. No markdown."""

USER_TEMPLATE = """
Review this lesson:

Title: {title}
Script word count: {word_count}
Target duration minutes: {target_duration}
Number of code examples: {code_count}
Validated code examples: {validated_count}
Number of slides: {slide_count}
Number of audio files: {audio_count}

Section types present in lesson plan: {section_types}
Segment types in script: {segment_types}
Forbidden phrases found: {forbidden_phrases}

Script sample (opening 400 chars):
{script_start}

Script sample (middle 400 chars):
{script_mid}

Script sample (ending 400 chars):
{script_end}

Perform these checks and output a QA report:
{{
  "score": number (0-100),
  "checks": {{
    "has_hook": boolean,
    "has_objectives": boolean,
    "has_code_examples": boolean,
    "all_code_validated": boolean,
    "has_summary": boolean,
    "has_exercise": boolean,
    "word_count_ok": boolean,
    "forbidden_phrases_found": [],
    "slides_present": boolean,
    "audio_present": boolean
  }},
  "issues": ["list of specific issues found"],
  "requires_human_review": boolean
}}

Score: each passing check = +10 pts.
IMPORTANT: "has_objectives" is true if section_types contains "objectives".
"has_summary" is true if section_types contains "summary".
"has_exercise" is true if section_types contains "exercise".
requires_human_review: true only if score < 70 or all_code_validated is false.
"""

FORBIDDEN = [
    "simply", "just ", "easy", "obviously", "as you can see",
    "let's go ahead", "straightforward", "note that", "it should be noted",
]


class QAAgent(BaseAgent):
    def run(self, state: dict) -> dict:
        print("[QAAgent] Running quality checks...")

        script = state.get("script", {})
        segments = script.get("segments", [])
        code_examples = state.get("code_examples", [])
        slide_paths = state.get("slide_image_paths", [])
        audio_paths = state.get("audio_paths", [])
        lesson_plan = state.get("lesson_plan", {})

        all_text = " ".join(s.get("text", "") for s in segments)
        total = len(all_text)
        script_start = all_text[:400]
        script_mid = all_text[total // 2: total // 2 + 400] if total > 800 else ""
        script_end = all_text[-400:] if total > 400 else ""

        validated_count = sum(1 for e in code_examples if e.get("is_validated", False))
        found_forbidden = [p.strip() for p in FORBIDDEN if p.lower() in all_text.lower()]

        # collect section types from lesson plan (the ground truth)
        section_types = list({s.get("type", "") for s in lesson_plan.get("sections", [])})
        segment_types = list({s.get("type", "") for s in segments})

        user_msg = USER_TEMPLATE.format(
            title=state["lesson_title"],
            word_count=script.get("total_words", 0),
            target_duration=lesson_plan.get("duration_estimate_minutes", 12),
            code_count=len(code_examples),
            validated_count=validated_count,
            slide_count=len(slide_paths),
            audio_count=len(audio_paths),
            section_types=", ".join(section_types),
            segment_types=", ".join(segment_types),
            forbidden_phrases=", ".join(found_forbidden) or "none",
            script_start=script_start,
            script_mid=script_mid,
            script_end=script_end,
        )

        try:
            qa_result = self.llm.complete_json(SYSTEM_PROMPT, user_msg)
        except Exception as e:
            qa_result = {
                "score": 50,
                "checks": {},
                "issues": [f"QA agent error: {e}"],
                "requires_human_review": True,
            }

        if found_forbidden:
            qa_result.setdefault("checks", {})["forbidden_phrases_found"] = found_forbidden
            qa_result.setdefault("issues", []).append(
                f"Forbidden phrases: {', '.join(found_forbidden)}"
            )

        score = qa_result.get("score", 0)
        print(f"  QA Score: {score}/100")
        if qa_result.get("issues"):
            for issue in qa_result["issues"][:3]:
                print(f"  Issue: {issue}")

        state["qa_report"] = qa_result
        return state
