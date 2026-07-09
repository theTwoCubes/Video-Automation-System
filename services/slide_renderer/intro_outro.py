"""
Intro and Outro slide renderers for theTwoCubes Learning.
These produce static MP4 clips (not LLM-generated) that are prepended/appended to every video.
"""
import subprocess
import base64
from pathlib import Path
from jinja2 import Environment, BaseLoader


INTRO_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;500;700;900&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: 1920px; height: 1080px;
    background: #000000; font-family: 'Outfit', sans-serif;
    overflow: hidden; position: relative;
    display: flex; flex-direction: column; justify-content: center; align-items: center;
  }
  .center { text-align: center; max-width: 1400px; }
  .course-label { font-size: 20px; font-weight: 600; color: #a1a1aa; letter-spacing: 0.25em; text-transform: uppercase; margin-bottom: 32px; }
  .lesson-title { font-size: 96px; font-weight: 800; color: #ffffff; line-height: 1.1; letter-spacing: -0.02em; }
  .lesson-num { font-size: 24px; color: #52525b; margin-top: 32px; font-weight: 500; letter-spacing: 0.1em; text-transform: uppercase; }
  .channel { position: absolute; bottom: 60px; font-size: 20px; font-weight: 600; color: #a1a1aa; letter-spacing: 0.1em; }
  {% if logo_b64 %}
  .logo { position: absolute; top: 60px; }
  .logo img { height: 48px; width: auto; opacity: 0.8; filter: grayscale(100%) brightness(200%); }
  {% endif %}
</style>
</head>
<body>
  {% if logo_b64 %}
  <div class="logo"><img src="data:image/png;base64,{{ logo_b64 }}" /></div>
  {% endif %}
  <div class="center">
    <div class="course-label">{{ course_title }}</div>
    <div class="lesson-title">{{ lesson_title }}</div>
    <div class="lesson-num">Lesson {{ lesson_position }}</div>
  </div>
  <div class="channel">theTwoCubes</div>
</body>
</html>
"""

OUTRO_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;500;600;700;800&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: 1920px; height: 1080px;
    background: #000000; font-family: 'Outfit', sans-serif;
    overflow: hidden; position: relative;
    display: flex; flex-direction: column; justify-content: center; align-items: center;
  }
  .center { text-align: center; width: 1600px; }
  .tag { font-size: 18px; font-weight: 600; color: #a1a1aa; letter-spacing: 0.25em; text-transform: uppercase; margin-bottom: 40px; }
  .cta-text { font-size: 80px; font-weight: 800; color: #ffffff; line-height: 1.1; margin-bottom: 24px; letter-spacing: -0.02em; }
  .cta-text span { color: #ffffff; }
  .sub { font-size: 28px; color: #71717a; margin-bottom: 60px; font-weight: 400; }
  
  {% if next_lesson_title %}
  .next-up { 
    background: #0a0a0a; border: 1px solid #27272a; 
    border-radius: 12px; padding: 40px 60px; 
    display: inline-block; text-align: left;
    box-shadow: 0 20px 40px rgba(0,0,0,0.5);
  }
  .next-label { font-size: 16px; font-weight: 600; color: #a1a1aa; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 12px; }
  .next-title { font-size: 36px; font-weight: 600; color: #ffffff; }
  {% endif %}
  
  .channel { position: absolute; bottom: 60px; font-size: 20px; font-weight: 600; color: #52525b; letter-spacing: 0.1em; text-transform: uppercase; }
</style>
</head>
<body>
  <div class="center">
    <div class="tag">theTwoCubes</div>
    <div class="cta-text">Like · Share · Subscribe</div>
    <div class="sub">Advanced Programming Tutorials</div>
    
    {% if next_lesson_title %}
    <div class="next-up">
      <div class="next-label">Coming Up Next</div>
      <div class="next-title">{{ next_lesson_title }}</div>
    </div>
    {% endif %}
  </div>
  <div class="channel">END OF LESSON</div>
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
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "22",
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
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "22",
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
