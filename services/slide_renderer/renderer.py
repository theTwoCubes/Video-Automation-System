import asyncio
import base64
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from config.settings import settings

TEMPLATE_DIR = Path("services/slide_renderer/templates")
SLIDES_LOGO_PATH = Path("assets/logos/SlidesLogo.png")


class SlideRenderer:
    def __init__(self):
        self.env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
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
        data = {k: v for k, v in slide_data.items() if k not in ("left_label", "right_label")}
        return template.render(
            width=settings.SLIDE_WIDTH,
            height=settings.SLIDE_HEIGHT,
            bg=theme.get("background", self.brand.get("primary_color", "#0D0D0D")),
            text_color=self.brand.get("text_color", "#FFFFFF"),
            accent=self.brand.get("accent_color", "#00C896"),
            secondary_accent=self.brand.get("secondary_accent", "#FF6B35"),
            logo_b64=self.logo_b64,
            left_label=slide_data.get("left_label", ""),
            right_label=slide_data.get("right_label", ""),
            slide_index=slide_index,
            total_slides=total_slides,
            code_language=slide_data.get("code_language", "cpp"),
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
