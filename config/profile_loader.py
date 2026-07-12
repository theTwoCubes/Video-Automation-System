"""
Profile loader - reads YAML profiles from config/profiles/ and provides a merged configuration that can override base Settings values.
"""
from __future__ import annotations

import copy
from pathlib import Path


try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

PROFILES_DIR = Path(__file__).parent / "profiles"

# 6 curated voice options for the Testing Studio selector
VOICE_OPTIONS = [
    {"id": "en-US-AndrewNeural",  "name": "Andrew",  "description": "Warm, engaging (Recommended)"},
    {"id": "en-US-GuyNeural",     "name": "Guy",     "description": "Neutral American male"},
    {"id": "en-US-EricNeural",    "name": "Eric",    "description": "Deep, authoritative"},
    {"id": "en-GB-RyanNeural",    "name": "Ryan",    "description": "British, professional"},
    {"id": "en-US-JennyNeural",   "name": "Jenny",   "description": "Clear, friendly female"},
    {"id": "en-AU-WilliamNeural", "name": "William", "description": "Australian, relaxed"},
]

_DEFAULT_PROFILE = {
    "name": "default",
    "description": "Standard profile",
    "voice": {
        "name": "en-US-AndrewNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
    },
    "music": {
        "bg_track": "assets/music/bg_track.mp3",
        "intro_sting": "assets/music/intro_sting.mp3",
        "outro_music": "assets/music/outro_music.mp3",
        "bg_volume": 0.15,
        "ducking_ratio": 14.0,
        "use_intro": True,
        "use_outro": True,
    },
    "slides": {
        "theme": "dark",
        "animation_preset": "smooth",
        "ken_burns": False,
    },
    "rendering": {
        "fps": 30,
        "crf": 22,
        "preset": "fast",
        "bitrate": "8000k",
    },
}


def _load_yaml(path: Path) -> dict:
    if yaml is None:
        raise ImportError("PyYAML is required: pip install pyyaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def list_profiles() -> list[dict]:
    """Return all available profile summaries."""
    profiles = []
    if PROFILES_DIR.exists():
        for f in sorted(PROFILES_DIR.glob("*.yaml")):
            try:
                data = _load_yaml(f)
                profiles.append({
                    "name": data.get("name", f.stem),
                    "description": data.get("description", ""),
                    "filename": f.name,
                })
            except Exception:
                pass
    return profiles


def load_profile(name: str) -> dict:
    """
    Load a profile by name (filename stem).
    Returns a merged dict (default merged with the requested profile).
    """
    path = PROFILES_DIR / f"{name}.yaml"
    if not path.exists():
        return copy.deepcopy(_DEFAULT_PROFILE)
    data = _load_yaml(path)
    return _deep_merge(_DEFAULT_PROFILE, data)


def save_profile(name: str, data: dict) -> Path:
    """Save a profile to YAML. Returns the written path."""
    if yaml is None:
        raise ImportError("PyYAML is required")
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    # ensure name field matches filename
    data = copy.deepcopy(data)
    data["name"] = name
    path = PROFILES_DIR / f"{name}.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return path


def delete_profile(name: str) -> bool:
    """Delete a profile by name. Returns True if deleted."""
    path = PROFILES_DIR / f"{name}.yaml"
    if path.exists() and name not in ("default",):
        path.unlink()
        return True
    return False


def get_voice_options() -> list[dict]:
    return VOICE_OPTIONS
