import json
from agents.base_agent import BaseAgent


SYSTEM_PROMPT = """You are the SEO specialist for theTwoCubes Learning YouTube channel.
Generate optimized YouTube metadata for a technical educational video.

CHANNEL NAME: Always write "theTwoCubes Learning" — never "TwoCubes Learning", never "The Two Cubes".

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
            seo = self.llm.complete_json(SYSTEM_PROMPT, user_msg)
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
