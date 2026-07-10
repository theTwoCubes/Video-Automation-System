import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from config.settings import settings
from services.slide_renderer.renderer import render_inline_markdown

TEMPLATE_DIR = Path("services/diagram_renderer/templates")
SLIDE_TEMPLATE_DIR = Path("services/slide_renderer/templates")  # shared _fonts.html partial

VALID_DIAGRAM_TYPES = {"pipeline", "memory_layout", "call_stack", "iteration", "flow"}


class DiagramRenderer:
    """Renders structured diagram content into self-contained animated HTML,
    using the same Jinja2 templating + brand design tokens as SlideRenderer."""

    def __init__(self):
        self.env = Environment(loader=FileSystemLoader([str(TEMPLATE_DIR), str(SLIDE_TEMPLATE_DIR)]))
        self.env.filters["md"] = render_inline_markdown
        self.brand = self._load_brand()

    def _load_brand(self) -> dict:
        with open("config/brand.json") as f:
            return json.load(f)

    def render_html(self, diagram_type: str, content: dict) -> str:
        diagram_type = diagram_type if diagram_type in VALID_DIAGRAM_TYPES else "flow"
        template = self.env.get_template(f"{diagram_type}.html")

        render_kwargs = dict(
            width=settings.SLIDE_WIDTH,
            height=settings.SLIDE_HEIGHT,
            bg=self.brand.get("primary_color", "#0D0D0D"),
            accent=self.brand.get("accent_color", "#00C896"),
            secondary_accent=self.brand.get("secondary_accent", "#FF6B35"),
            text_color=self.brand.get("text_color", "#FFFFFF"),
            channel_name=self.brand.get("channel_name", "theTwoCubes"),
            **content,
        )

        if diagram_type == "iteration":
            render_kwargs["items"] = self._compute_iteration_delays(
                content.get("items", []), content.get("highlight_sequence", [])
            )

        return template.render(**render_kwargs)

    @staticmethod
    def _compute_iteration_delays(items: list, highlight_sequence: list) -> list[dict]:
        """Assign each item an animation-delay based on its first position in
        highlight_sequence, so boxes pulse in the order the loop visits them."""
        delays = [None] * len(items)
        for position, idx in enumerate(highlight_sequence):
            if 0 <= idx < len(items) and delays[idx] is None:
                delays[idx] = round(0.3 + position * 0.5, 2)
        return [
            {"text": text, "delay": delays[i] if delays[i] is not None else round(0.3 + i * 0.5, 2)}
            for i, text in enumerate(items)
        ]
