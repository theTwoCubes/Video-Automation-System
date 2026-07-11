from pathlib import Path
from agents.base_agent import BaseAgent


def _fmt_ts(seconds: float) -> str:
    """YouTube chapter timestamp. Uses H:MM:SS past an hour, else M:SS."""
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _compute_chapters(state: dict) -> list[dict]:
    """Derive YouTube chapters from the REAL audio timeline instead of letting
    the LLM invent timestamps. Narration audio is grouped by slide in script
    order (the same grouping the video uses); each new slide that carries a
    headline becomes a chapter at its measured start time.

    Honors YouTube's chapter rules: first chapter at 0:00, at least three
    chapters, and >= 10s between consecutive chapters (closer ones are merged).
    Returns [] if timings can't be read, so the caller can fall back.
    """
    script = state.get("script", {}) or {}
    segments = script.get("segments", []) or []
    audio_paths = state.get("audio_paths", []) or []
    slide_contents = state.get("slide_contents", []) or []
    if not segments or not audio_paths:
        return []

    try:
        from services.video_composer.composer import _get_ffmpeg, _get_audio_duration
        ffmpeg_exe = _get_ffmpeg()
    except Exception:
        return []

    headline_by_slide = {
        s.get("id", ""): (s.get("headline") or "").strip() for s in slide_contents
    }

    narration_segs = [
        s for s in segments
        if s.get("type") in ("narration", "code_demo") and s.get("text", "").strip()
    ]

    raw: list[tuple[float, str]] = []  # (start_seconds, title)
    cursor = 0.0
    last_slide = None
    for i, seg in enumerate(narration_segs):
        if i >= len(audio_paths):
            break
        path = audio_paths[i]
        sid = seg.get("slide_id", "")
        if sid != last_slide:
            title = headline_by_slide.get(sid, "")
            if title:
                raw.append((cursor, title))
            last_slide = sid
        try:
            cursor += _get_audio_duration(path, ffmpeg_exe) if Path(path).exists() else 0.0
        except Exception:
            pass

    if not raw:
        return []

    # Force the first chapter to 0:00, then keep only chapters >= 10s apart.
    raw[0] = (0.0, raw[0][1])
    chapters, last_t = [], -10.0
    for t, title in raw:
        if t - last_t >= 10.0 or not chapters:
            chapters.append({"timestamp": _fmt_ts(t), "title": title})
            last_t = t

    # YouTube needs at least three chapters to render the UI at all.
    return chapters if len(chapters) >= 3 else []


SYSTEM_PROMPT = """You are the SEO specialist for theTwoCubes Learning YouTube channel.
Generate optimized YouTube metadata for a technical educational video.

CHANNEL NAME: Always write "theTwoCubes Learning" - never "TwoCubes Learning", never "The Two Cubes".

Title rules:
- 60-70 characters max
- Include the primary keyword early
- Use power words: Complete, Explained, Mastery, Guide, in X Minutes
- Never use "learn" as the first word
- Format: "Topic + Angle + Outcome"

Description rules:
- 400-600 words
- First 2 sentences must be the hook (shown before "show more")
- Include timestamps as a table of contents
- End with: "Subscribe to theTwoCubes Learning for more."
- Naturally include 8-10 keywords

Tags: 15 tags, specific and varied (not all the same phrase)
Chapters: use 00:00 timestamps based on the lesson structure

Output strictly valid JSON. No markdown."""

USER_TEMPLATE = """
Lesson title: {title}
Topic tags: {tags}
Lesson position: {position}
Estimated duration: {duration} minutes
Course: {course_title}

Key sections from lesson plan:
{sections}

Script excerpt (first 500 chars):
{excerpt}

Generate YouTube metadata as JSON:
{{
  "lesson_id": "{lesson_id}",
  "title": "YouTube title here",
  "description": "Full description here",
  "tags": ["tag1", "tag2", ...],
  "chapters": [
    {{"timestamp": "00:00", "title": "Introduction"}},
    {{"timestamp": "00:45", "title": "Section title"}}
  ],
  "pinned_comment": "First pinned comment text with resources"
}}
"""


class SEOAgent(BaseAgent):
    def run(self, state: dict) -> dict:
        print("[SEOAgent] Generating SEO metadata...")

        lesson_id = state["lesson_id"]
        lesson_title = state["lesson_title"]
        tags = state.get("topic_tags", [])
        position = state.get("lesson_position", 1)
        lesson_plan = state.get("lesson_plan", {})
        script = state.get("script", {})
        course_title = state.get("course_title", "theTwoCubes Learning")
        duration = lesson_plan.get("duration_estimate_minutes", 12)

        sections = [
            s.get("title", "") for s in lesson_plan.get("sections", [])
        ]

        all_text = " ".join(s.get("text", "") for s in script.get("segments", []))
        excerpt = all_text[:500]

        user_msg = USER_TEMPLATE.format(
            lesson_id=lesson_id,
            title=lesson_title,
            tags=", ".join(tags),
            position=position,
            duration=duration,
            course_title=course_title,
            sections=", ".join(sections[:8]),
            excerpt=excerpt,
        )

        try:
            seo = self.llm.complete_json(SYSTEM_PROMPT, user_msg, thinking_budget=0)
        except Exception as e:
            seo = {
                "lesson_id": lesson_id,
                "title": lesson_title,
                "description": f"Learn {lesson_title} in this lesson from theTwoCubes Learning.",
                "tags": tags[:15],
                "chapters": [{"timestamp": "00:00", "title": "Introduction"}],
                "pinned_comment": f"Resources for this lesson: https://github.com/thetwocubes",
            }
            print(f"  SEO fallback due to error: {e}")

        # Replace the LLM's guessed chapter timestamps with ones measured from
        # the real audio timeline. The model cannot know true timings, so its
        # numbers point viewers to the wrong moments; only override when we
        # successfully computed at least three real chapters.
        measured = _compute_chapters(state)
        if measured:
            seo["chapters"] = measured
            print(f"  Chapters: {len(measured)} derived from real audio timings")

        # fix branding: normalize any LLM-generated channel name variants
        if isinstance(seo.get("description"), str):
            seo["description"] = (
                seo["description"]
                .replace("TwoCubes Learning", "theTwoCubes Learning")
                .replace("Two Cubes Learning", "theTwoCubes Learning")
                .replace("TheTwoCubes", "theTwoCubes")
            )
        if isinstance(seo.get("tags"), list):
            seo["tags"] = [
                t.replace("TwoCubes Learning", "theTwoCubes Learning")
                for t in seo["tags"]
            ]

        state["seo_metadata"] = seo
        print(f"  Title: {seo.get('title', '?')[:70]}")
        return state
