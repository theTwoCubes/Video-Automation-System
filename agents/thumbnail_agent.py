from pathlib import Path
from agents.base_agent import BaseAgent
from services.thumbnail.generator import ThumbnailGenerator


class ThumbnailAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.generator = ThumbnailGenerator()

    def run(self, state: dict) -> dict:
        print("[ThumbnailAgent] Generating thumbnail...")

        lesson_title = state["lesson_title"]
        lesson_position = state.get("lesson_position", 1)
        tags = state.get("topic_tags", [])
        output_dir = state["output_dir"]

        # derive a short topic label from tags
        topic = tags[0].upper() if tags else "CS"

        # shorten title for thumbnail if too long
        display_title = lesson_title
        if len(lesson_title) > 40:
            display_title = lesson_title[:37] + "..."

        out_path = str(Path(output_dir) / "thumbnail.jpg")

        self.generator.generate(
            title=display_title,
            topic=topic,
            lesson_number=lesson_position,
            output_path=out_path,
        )

        state["thumbnail_path"] = out_path
        print(f"  Thumbnail: {out_path}")
        return state
