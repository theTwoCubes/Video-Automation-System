# Assets Directory

This directory stores all static assets used by the video generation pipeline.

## Required Structure

```
assets/
├── fonts/          # TrueType (.ttf) or OpenType (.otf) fonts
│   ├── Outfit-Regular.ttf      (Required for general UI/text)
│   ├── Outfit-SemiBold.ttf     (Required for headers)
│   └── FiraCode-Regular.ttf    (Optional, recommended for code blocks)
├── logos/          # Branding graphics
│   ├── brand_logo_light.png    (Used on dark background slides)
│   └── brand_logo_dark.png     (Used on light background slides)
├── music/          # Audio tracks mixed into the final video
│   ├── bg_track.mp3            (Low volume background loop)
│   ├── intro_sting.mp3         (Plays during title slides)
│   └── outro_music.mp3         (Plays during summary/outro slides)
```

## Why this is necessary
- **Fonts**: Playwright renders the HTML slides locally in a headless browser. Since it operates in a sandbox without guaranteed access to system fonts, explicitly loading fonts from the `assets/fonts/` directory ensures consistent typography across all operating systems.
- **Logos**: Embedded directly into the slide templates.
- **Music**: Mixed dynamically by FFmpeg based on the lesson's duration and flow.
