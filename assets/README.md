# Assets Directory

This directory stores all static assets used by the video generation pipeline.

## Required Structure

```
assets/
├── fonts/          # TrueType (.ttf) or OpenType (.otf) fonts
│   ├── Outfit-Regular.ttf      (Required for general UI/text)
│   ├── Outfit-SemiBold.ttf     (Required for headers)
│   └── FiraCode-Regular.ttf    (Optional, recommended for code blocks)
├── logos/    
├── music/          # Audio tracks mixed into the final video
│   ├── bg_track.mp3            (Low volume background loop)
│   ├── intro_music.mp3         (Plays during title slides)
│   └── outro_music.mp3         (Plays during summary/outro slides)
```

# Logo Files

Place your brand logo PNGs here. The system looks for these exact filenames:

| File                   | Used in                    | Recommended size           |
| ---------------------- | -------------------------- | -------------------------- |
| `SlidesLogo.png`     | Top-right of every slide   | 300x100 px, transparent bg |
| `ThumbnailLogo.png`  | Bottom-right of thumbnails | 300x100 px, transparent bg |
| `MainScreenLogo.png` | title cards                | 400x140 px, transparent bg |
| `EndSlideLogo.png`   | end-screen slide           | 400x140 px, transparent bg |

All logos must be **PNG with transparent background**.
The system falls back gracefully to text branding when any file is missing.

## Why this is necessary

- **Fonts**: Playwright renders the HTML slides locally in a headless browser. Since it operates in a sandbox without guaranteed access to system fonts, explicitly loading fonts from the `assets/fonts/` directory ensures consistent typography across all operating systems.
- **Logos**: Embedded directly into the slide templates.
- **Music**: Mixed dynamically by FFmpeg based on the lesson's duration and flow.
