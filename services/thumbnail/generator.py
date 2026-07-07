import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import textwrap

THUMB_LOGO_PATH = Path("assets/logos/ThumbnailLogo.png")


class ThumbnailGenerator:
    def __init__(self):
        self.brand = self._load_brand()
        self.width = 1280
        self.height = 720
        self.logo = self._load_logo()

    def _load_brand(self) -> dict:
        with open("config/brand.json") as f:
            return json.load(f)

    def _load_logo(self):
        if THUMB_LOGO_PATH.exists():
            try:
                logo = Image.open(THUMB_LOGO_PATH).convert("RGBA")
                logo.thumbnail((220, 80), Image.LANCZOS)
                return logo
            except Exception:
                pass
        return None

    def _get_font(self, size: int, bold: bool = False):
        font_name = "Bold" if bold else "Regular"
        candidates = [
            f"assets/fonts/Outfit-{font_name}.ttf",
            f"assets/fonts/Outfit-{font_name}.otf",
            # Windows system fonts
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        ]
        for fp in candidates:
            try:
                if Path(fp).exists():
                    return ImageFont.truetype(fp, size)
            except Exception:
                continue
        # final fallback
        try:
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            return ImageFont.load_default()

    def _hex_to_rgb(self, hex_color: str) -> tuple:
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def generate(self, title: str, topic: str, lesson_number: int, output_path: str) -> str:
        bg = self._hex_to_rgb(self.brand["primary_color"])
        accent = self._hex_to_rgb(self.brand["accent_color"])
        secondary = self._hex_to_rgb(self.brand["secondary_accent"])
        text_color = (255, 255, 255)
        muted = (160, 160, 160)

        img = Image.new("RGB", (self.width, self.height), bg)
        draw = ImageDraw.Draw(img)

        # background gradient effect (manual linear gradient)
        for y in range(self.height):
            factor = y / self.height
            r = int(13 + factor * 10)
            g = int(13 + factor * 5)
            b = int(13 + factor * 20)
            draw.line([(0, y), (self.width, y)], fill=(r, g, b))

        # accent rectangle (right side decorative block)
        draw.rectangle(
            [(self.width - 12, 0), (self.width, self.height)],
            fill=accent
        )

        # thin top accent line
        draw.rectangle([(0, 0), (self.width, 5)], fill=accent)

        # bottom accent line
        draw.rectangle([(0, self.height - 5), (self.width, self.height)], fill=secondary)

        # left bold vertical bar
        draw.rectangle([(0, 80), (8, self.height - 80)], fill=accent)

        # lesson number badge
        badge_font = self._get_font(22, bold=True)
        badge_text = f"LESSON {lesson_number:02d}"
        draw.rounded_rectangle(
            [(60, 60), (60 + 200, 60 + 44)],
            radius=22,
            fill=(*accent, 30),
            outline=accent,
        )
        draw.text((68, 70), badge_text, font=badge_font, fill=accent)

        # topic label
        topic_font = self._get_font(26, bold=True)
        draw.text((60, 130), topic.upper(), font=topic_font, fill=(*accent[:3], 180))

        # main title (word-wrapped)
        title_font = self._get_font(86, bold=True)
        wrapped = textwrap.wrap(title, width=22)
        y_pos = 220
        for line in wrapped[:3]:  # max 3 lines
            # subtle shadow
            draw.text((65, y_pos + 4), line, font=title_font, fill=(0, 0, 0))
            draw.text((60, y_pos), line, font=title_font, fill=text_color)
            bbox = draw.textbbox((0, 0), line, font=title_font)
            y_pos += (bbox[3] - bbox[1]) + 12

        # logo or channel name — bottom right
        if self.logo:
            # composite PNG logo onto JPEG base
            logo_x = self.width - self.logo.width - 40
            logo_y = self.height - self.logo.height - 30
            img.paste(self.logo, (logo_x, logo_y), self.logo)
        else:
            channel_font = self._get_font(28, bold=True)
            channel_text = "theTwoCubes Learning"
            bbox = draw.textbbox((0, 0), channel_text, font=channel_font)
            text_w = bbox[2] - bbox[0]
            draw.text(
                (self.width - text_w - 50, self.height - 65),
                channel_text,
                font=channel_font,
                fill=muted,
            )

        # decorative dots (top right)
        for dx, dy in [(1050, 80), (1100, 80), (1150, 80), (1050, 130), (1100, 130), (1150, 130)]:
            draw.ellipse([(dx, dy), (dx + 8, dy + 8)], fill=(*accent, 60))

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "JPEG", quality=95)
        return output_path
