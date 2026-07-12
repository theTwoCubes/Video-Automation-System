import base64
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from config.settings import settings
from services.slide_renderer.renderer import render_inline_markdown, hex_to_rgb

TEMPLATE_DIR = Path("services/diagram_renderer/templates")
SLIDE_TEMPLATE_DIR = Path("services/slide_renderer/templates")  # shared _fonts.html partial
SLIDES_LOGO_PATH = Path("assets/logos/SlidesLogo.png")

VALID_DIAGRAM_TYPES = {
    "pipeline", "memory_layout", "call_stack", "iteration", "flow",
    "tree", "state_machine", "layers_diagram",
}


class DiagramRenderer:
    """Renders structured diagram content into self-contained animated HTML,
    using the same Jinja2 templating + brand design tokens as SlideRenderer."""

    def __init__(self):
        # autoescape on: every diagram field (labels, sublabels, detail text) is
        # plain LLM-generated text rendered with a raw {{ }}, never |safe/|md -
        # without this, a label containing '<' or '&' (e.g. "vector<int>")
        # corrupts the rendered HTML instead of displaying as literal text.
        self.env = Environment(
            loader=FileSystemLoader([str(TEMPLATE_DIR), str(SLIDE_TEMPLATE_DIR)]),
            autoescape=True,
        )
        self.env.filters["md"] = render_inline_markdown
        self.brand = self._load_brand()
        self.logo_b64 = self._load_logo()

    def _load_brand(self) -> dict:
        with open("config/brand.json") as f:
            return json.load(f)

    def _load_logo(self) -> str:
        if SLIDES_LOGO_PATH.exists():
            return base64.b64encode(SLIDES_LOGO_PATH.read_bytes()).decode("utf-8")
        return ""

    def render_html(self, diagram_type: str, content: dict) -> str:
        diagram_type = diagram_type if diagram_type in VALID_DIAGRAM_TYPES else "flow"
        template = self.env.get_template(f"{diagram_type}.html")

        accent = self.brand.get("accent_color", "#00C896")
        render_kwargs = dict(
            width=settings.SLIDE_WIDTH,
            height=settings.SLIDE_HEIGHT,
            bg=self.brand.get("primary_color", "#0D0D0D"),
            accent=accent,
            accent_rgb=hex_to_rgb(accent),
            secondary_accent=self.brand.get("secondary_accent", "#FF6B35"),
            text_color=self.brand.get("text_color", "#FFFFFF"),
            channel_name=self.brand.get("channel_name", "theTwoCubes"),
            logo_b64=self.logo_b64,
            **content,
        )

        if diagram_type == "iteration":
            render_kwargs["items"] = self._compute_iteration_delays(
                content.get("items", []), content.get("highlight_sequence", [])
            )
        elif diagram_type == "tree":
            levels, flat_nodes = self._compute_tree_layout(content.get("root", ""), content.get("children", []))
            render_kwargs["levels"] = levels
            render_kwargs["flat_nodes"] = flat_nodes

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

    @staticmethod
    def _compute_tree_layout(root: str, children: list) -> tuple[list, list]:
        """Breadth-first flatten a {root, children:[{label, children}]} tree into
        per-depth levels for rendering, plus a flat list carrying each node's
        global index (used for staggered animation-delay keyed by depth)."""
        flat_nodes = []
        levels = []
        current_level = [{"label": root, "children": children}]
        depth = 0
        while current_level:
            level_out = []
            next_level = []
            for node in current_level:
                flat_index = len(flat_nodes)
                entry = {"label": node.get("label", ""), "flat_index": flat_index, "depth": depth, "is_root": depth == 0}
                flat_nodes.append(entry)
                level_out.append(entry)
                next_level.extend(node.get("children") or [])
            levels.append(level_out)
            current_level = next_level
            depth += 1
        return levels, flat_nodes
