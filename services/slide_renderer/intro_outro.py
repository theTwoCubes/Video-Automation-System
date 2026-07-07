"""
Intro and Outro slide renderers for theTwoCubes Learning.
These produce static MP4 clips (not LLM-generated) that are prepended/appended to every video.
"""
import subprocess
import shutil
import base64
from pathlib import Path
from jinja2 import Environment, BaseLoader


INTRO_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;700;900&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: 1920px; height: 1080px;
    background: #080b10; font-family: 'Outfit', sans-serif;
    overflow: hidden; position: relative;
  }
  .bg-glow {
    position: absolute;
    width: 800px; height: 800px;
    background: radial-gradient(circle, rgba(0,200,150,0.12) 0%, transparent 70%);
    top: 50%; left: 50%; transform: translate(-50%, -50%);
    border-radius: 50%;
  }
  .bg-glow2 {
    position: absolute;
    width: 600px; height: 600px;
    background: radial-gradient(circle, rgba(255,107,53,0.08) 0%, transparent 70%);
    top: 30%; left: 70%; transform: translate(-50%, -50%);
    border-radius: 50%;
  }
  .left-bar { position: absolute; left: 0; top: 0; bottom: 0; width: 8px; background: linear-gradient(180deg, #00c896, #ff6b35); }
  .center { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; }
  .course-label { font-size: 16px; font-weight: 700; color: #00c896; letter-spacing: 0.2em; text-transform: uppercase; margin-bottom: 24px; opacity: 0.9; }
  .lesson-title { font-size: 72px; font-weight: 900; color: #fff; line-height: 1.1; max-width: 1400px; background: linear-gradient(135deg, #fff 40%, #00c896); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
  .lesson-num { font-size: 20px; color: rgba(255,255,255,0.35); margin-top: 24px; font-weight: 300; letter-spacing: 0.1em; }
  .channel { position: absolute; bottom: 40px; left: 50%; transform: translateX(-50%); font-size: 18px; font-weight: 700; color: #00c896; letter-spacing: 0.06em; opacity: 0.7; }
  {% if logo_b64 %}
  .logo { position: absolute; top: 36px; right: 50px; }
  .logo img { height: 50px; width: auto; opacity: 0.85; }
  {% endif %}
</style>
</head>
<body>
  <div class="bg-glow"></div>
  <div class="bg-glow2"></div>
  <div class="left-bar"></div>
  {% if logo_b64 %}
  <div class="logo"><img src="data:image/png;base64,{{ logo_b64 }}" /></div>
  {% endif %}
  <div class="center">
    <div class="course-label">{{ course_title }}</div>
    <div class="lesson-title">{{ lesson_title }}</div>
    <div class="lesson-num">Lesson {{ lesson_position }}</div>
  </div>
  <div class="channel">theTwoCubes Learning</div>
</body>
</html>
"""

OUTRO_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;600;700;900&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: 1920px; height: 1080px;
    background: #080b10; font-family: 'Outfit', sans-serif;
    overflow: hidden; position: relative;
  }
  .bg-glow { position: absolute; width: 900px; height: 900px; background: radial-gradient(circle, rgba(0,200,150,0.1) 0%, transparent 70%); top: 50%; left: 50%; transform: translate(-50%, -50%); border-radius: 50%; }
  .left-bar { position: absolute; left: 0; top: 0; bottom: 0; width: 8px; background: linear-gradient(180deg, #00c896, #ff6b35); }
  .center { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; width: 1600px; }
  .tag { font-size: 14px; font-weight: 700; color: #00c896; letter-spacing: 0.2em; text-transform: uppercase; margin-bottom: 20px; }
  .cta-text { font-size: 64px; font-weight: 900; color: #fff; line-height: 1.1; margin-bottom: 24px; }
  .cta-text span { color: #00c896; }
  .sub { font-size: 22px; color: rgba(255,255,255,0.45); margin-bottom: 40px; }
  .next-up { background: rgba(0,200,150,0.07); border: 1px solid rgba(0,200,150,0.2); border-radius: 12px; padding: 24px 40px; display: inline-block; }
  .next-label { font-size: 13px; font-weight: 700; color: #00c896; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 8px; }
  .next-title { font-size: 26px; font-weight: 600; color: #fff; }
  .channel { position: absolute; bottom: 36px; left: 50%; transform: translateX(-50%); font-size: 17px; font-weight: 700; color: rgba(255,255,255,0.25); letter-spacing: 0.06em; }
</style>
</head>
<body>
  <div class="bg-glow"></div>
  <div class="left-bar"></div>
  <div class="center">
    <div class="tag">theTwoCubes Learning</div>
    <div class="cta-text">Like · Share · <span>Subscribe</span></div>
    <div class="sub">More programming tutorials every week</div>
    {% if next_lesson_title %}
    <div class="next-up">
      <div class="next-label">▶ Up Next</div>
      <div class="next-title">{{ next_lesson_title }}</div>
    </div>
    {% endif %}
  </div>
  <div class="channel">theTwoCubes Learning</div>
</body>
</html>
"""


def _get_logo_b64() -> str:
    logo = Path("assets/logos/SlidesLogo.png")
    if logo.exists():
        return base64.b64encode(logo.read_bytes()).decode("utf-8")
    return ""


def _render_html_to_png(html: str, output_path: str, width: int = 1920, height: int = 1080):
    import asyncio
    from playwright.async_api import async_playwright

    async def _do():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": width, "height": height})
            await page.set_content(html, wait_until="domcontentloaded")
            await page.screenshot(path=output_path, type="png", full_page=False)
            await browser.close()

    try:
        asyncio.run(_do())
    except RuntimeError:
        import nest_asyncio
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_do())


def _png_to_video(
    png_path: str,
    audio_path: str | None,
    output_path: str,
    duration: float,
    ffmpeg_exe: str,
    fps: int = 30,
):
    """Convert a static PNG to a short MP4, optionally with audio."""

    def _fwd(p):
        return str(Path(p).resolve()).replace("\\", "/")

    if audio_path and Path(audio_path).exists():
        cmd = [
            ffmpeg_exe, "-y",
            "-loop", "1", "-i", _fwd(png_path),
            "-i", _fwd(audio_path),
            "-t", str(duration),
            "-vf", f"scale=1920:1080:flags=lanczos,fps={fps}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            _fwd(output_path),
        ]
    else:
        cmd = [
            ffmpeg_exe, "-y",
            "-loop", "1", "-i", _fwd(png_path),
            "-t", str(duration),
            "-vf", f"scale=1920:1080:flags=lanczos,fps={fps}",
            "-an",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            _fwd(output_path),
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"PNG→video failed: {result.stderr[-200:]}")


def render_intro(
    output_dir: str,
    course_title: str,
    lesson_title: str,
    lesson_position: int,
    ffmpeg_exe: str,
    duration: float = 4.0,
) -> str | None:
    """Render intro slide to MP4. Returns output path or None on failure."""
    try:
        out_dir = Path(output_dir)
        logo_b64 = _get_logo_b64()
        env = Environment(loader=BaseLoader())
        html = env.from_string(INTRO_HTML).render(
            course_title=course_title,
            lesson_title=lesson_title,
            lesson_position=lesson_position,
            logo_b64=logo_b64,
        )
        png_path = str(out_dir / "intro_slide.png")
        _render_html_to_png(html, png_path)

        # use intro music if available
        music = Path("assets/music/intro_music.mp3")
        audio_path = str(music) if music.exists() else None

        video_path = str(out_dir / "intro.mp4")
        _png_to_video(png_path, audio_path, video_path, duration, ffmpeg_exe)
        return video_path
    except Exception as e:
        print(f"  Intro render failed (skipping): {e}")
        return None


def render_outro(
    output_dir: str,
    next_lesson_title: str | None,
    ffmpeg_exe: str,
    duration: float = 6.0,
) -> str | None:
    """Render outro slide to MP4. Returns output path or None on failure."""
    try:
        out_dir = Path(output_dir)
        env = Environment(loader=BaseLoader())
        html = env.from_string(OUTRO_HTML).render(
            next_lesson_title=next_lesson_title or "",
        )
        png_path = str(out_dir / "outro_slide.png")
        _render_html_to_png(html, png_path)

        music = Path("assets/music/outro_music.mp3")
        audio_path = str(music) if music.exists() else None

        video_path = str(out_dir / "outro.mp4")
        _png_to_video(png_path, audio_path, video_path, duration, ffmpeg_exe)
        return video_path
    except Exception as e:
        print(f"  Outro render failed (skipping): {e}")
        return None
