import asyncio
import base64
import json
import re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape
from config.settings import settings

TEMPLATE_DIR = Path("services/slide_renderer/templates")
SLIDES_LOGO_PATH = Path("assets/logos/SlidesLogo.png")

_MD_CODE_RE = re.compile(r'`([^`]+?)`')
_MD_BOLD_RE = re.compile(r'\*\*(.+?)\*\*')
_MD_ITALIC_RE = re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)')
_LEADING_NUMBER_RE = re.compile(r'^\s*\d+[.)]\s+')
_LEADING_NEXT_RE = re.compile(r'^\s*next\s*(lesson|time|up)?\s*[:,-]\s*', re.IGNORECASE)


def render_inline_markdown(text) -> Markup:
    """Escape raw text for safe HTML embedding, then convert a small set of
    inline markdown (`code`, **bold**, *italic*) into real tags. Escaping
    happens first, so any literal '<'/'>' in the source text (e.g. code
    fragments like `#include <iostream>`) survive as visible text instead of
    being parsed as HTML tags and silently dropped."""
    if text is None:
        return Markup("")
    out = str(escape(str(text)))
    out = _MD_CODE_RE.sub(lambda m: f"<code>{m.group(1)}</code>", out)
    out = _MD_BOLD_RE.sub(r"<strong>\1</strong>", out)
    out = _MD_ITALIC_RE.sub(r"<em>\1</em>", out)
    return Markup(out)


def strip_leading_number(text) -> str:
    """Strip a leading '1. '/'1) ' the LLM sometimes bakes into list item text,
    so it doesn't double up with the renderer's own numbered badge."""
    if text is None:
        return ""
    return _LEADING_NUMBER_RE.sub("", str(text))


def strip_next_prefix(text) -> str:
    """Strip a leading 'Next:'/'Next lesson:'/'Next up,' the LLM sometimes bakes
    into whats_next text, so it doesn't double up with the renderer's own
    hardcoded 'Next:' prefix on the summary slide."""
    if text is None:
        return ""
    return _LEADING_NEXT_RE.sub("", str(text))


def hex_to_rgb(hex_color: str) -> str:
    """Convert '#RRGGBB' to 'R,G,B' so a brand color can be dropped into a CSS
    rgba(...) call for translucent tints - CSS rgba() takes numeric components,
    not a hex literal, so templates can't interpolate {{ accent }} directly."""
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        return "0,0,0"
    try:
        return f"{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)}"
    except ValueError:
        return "0,0,0"


class SlideRenderer:
    def __init__(self):
        self.env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
        self.env.filters["md"] = render_inline_markdown
        self.env.filters["strip_leading_number"] = strip_leading_number
        self.env.filters["strip_next_prefix"] = strip_next_prefix
        self.brand = self._load_brand()
        self.logo_b64 = self._load_logo()

    def _load_brand(self) -> dict:
        with open("config/brand.json") as f:
            return json.load(f)

    def _load_logo(self) -> str:
        """Return base64-encoded logo PNG if the file exists, else empty string."""
        if SLIDES_LOGO_PATH.exists():
            data = SLIDES_LOGO_PATH.read_bytes()
            return base64.b64encode(data).decode("utf-8")
        return ""

    def _render_html(self, slide_data: dict, slide_index: int = 0, total_slides: int = 0) -> str:
        template = self.env.get_template("slide.html")
        theme = self.brand.get("slide_themes", {}).get("dark", {})
        data = {k: v for k, v in slide_data.items() if k not in ("left_label", "right_label", "code_language")}

        # Every code-bearing field a layout might use, keyed by the same name the
        # template gives its <pre data-code-id="..."> element. Layouts with a single
        # code block (code, split_code) only populate code_content; multi-block
        # layouts (code_evolution) populate left_code/right_code too. Empty values
        # are dropped so the JS highlighter has nothing to iterate for them.
        code_blocks = {
            key: slide_data[key]
            for key in ("code_content", "left_code", "right_code")
            if slide_data.get(key)
        }

        accent = self.brand.get("accent_color", "#00C896")
        secondary_accent = self.brand.get("secondary_accent", "#FF6B35")
        warning_color = self.brand.get("warning_color", "#EF4444")
        tip_color = self.brand.get("tip_color", "#3B82F6")
        caution_color = self.brand.get("caution_color", "#F59E0B")

        return template.render(
            width=settings.SLIDE_WIDTH,
            height=settings.SLIDE_HEIGHT,
            bg=theme.get("background", self.brand.get("primary_color", "#0D0D0D")),
            text_color=self.brand.get("text_color", "#FFFFFF"),
            accent=accent,
            secondary_accent=secondary_accent,
            warning_color=warning_color,
            tip_color=tip_color,
            caution_color=caution_color,
            accent_rgb=hex_to_rgb(accent),
            secondary_accent_rgb=hex_to_rgb(secondary_accent),
            warning_color_rgb=hex_to_rgb(warning_color),
            tip_color_rgb=hex_to_rgb(tip_color),
            caution_color_rgb=hex_to_rgb(caution_color),
            logo_b64=self.logo_b64,
            left_label=slide_data.get("left_label", ""),
            right_label=slide_data.get("right_label", ""),
            slide_index=slide_index,
            total_slides=total_slides,
            code_language=slide_data.get("code_language", "cpp"),
            code_blocks=code_blocks,
            **data,
        )

    async def render_slide_async(
        self, slide_data: dict, output_path: str,
        slide_index: int = 0, total_slides: int = 0,
        browser=None,
    ) -> str:
        html = self._render_html(slide_data, slide_index, total_slides)
        if browser is not None:
            page = await browser.new_page(
                viewport={"width": settings.SLIDE_WIDTH, "height": settings.SLIDE_HEIGHT}
            )
            await page.set_content(html, wait_until="networkidle")
            await page.screenshot(path=output_path, type="png", full_page=False)
            await page.close()
            return output_path
        # fallback: own browser context
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            b = await p.chromium.launch()
            page = await b.new_page(
                viewport={"width": settings.SLIDE_WIDTH, "height": settings.SLIDE_HEIGHT}
            )
            await page.set_content(html, wait_until="networkidle")
            await page.screenshot(path=output_path, type="png", full_page=False)
            await b.close()
        return output_path

    async def _render_slides_async(self, slides: list, output_dir: str) -> list:
        """Render all slides in a single shared Playwright browser session."""
        from playwright.async_api import async_playwright
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        total = len(slides)
        paths = []
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            for i, slide_data in enumerate(slides):
                out = str(Path(output_dir) / f"slide_{i:04d}.png")
                await self.render_slide_async(slide_data, out, slide_index=i, total_slides=total, browser=browser)
                paths.append(out)
                print(f"  Rendered slide {i + 1}/{total}")
            await browser.close()
        return paths

    def render_slide(self, slide_data: dict, output_path: str, slide_index: int = 0, total_slides: int = 0) -> str:
        return asyncio.run(self.render_slide_async(slide_data, output_path, slide_index, total_slides))

    def render_slides(self, slides: list[dict], output_dir: str) -> list[str]:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(self._render_slides_async(slides, output_dir))
            else:
                return asyncio.run(self._render_slides_async(slides, output_dir))
        except Exception:
            return asyncio.run(self._render_slides_async(slides, output_dir))
