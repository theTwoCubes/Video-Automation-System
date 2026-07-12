"""
The machine-readable design system + layout catalog - the single source of
truth for the presentation engine (blueprint Part II, esp. §12, §13, §22).

Three consumers read from here, so the rules can never drift apart:
  1. The slide agent (agents/slide_agent.py) is handed `design_brief_json()` so
     the LLM chooses a layout and emphasis the way a deck designer would, from a
     precise catalog rather than prose.
  2. The selection engine (services/slide_renderer/selection.py) uses the caps,
     families, and density capacities to narrow candidates and split/merge.
  3. The render linter (services/slide_validator/validator.py) enforces the
     caps and diversity/density rules so no off-system slide reaches Playwright.

Layout ids here match the templates the renderer actually supports, so any
layout the LLM picks is guaranteed to render.
"""
from __future__ import annotations

import json
from typing import Dict, List

# Global design system (canvas, floors, invariants) - blueprint §8-§11.
CANVAS = {
    "w": 1920, "h": 1080,
    "margin": 96, "grid_cols": 12, "gutter": 24, "baseline": 8,
}
TYPE_FLOOR_PX = 24          # hard minimum on-screen text size @1080p (§10)
CODE_FLOOR_PX = 22

# Fixed, non-negotiable bindings the selection engine applies first (§13).
HARD_BINDINGS = {
    "slide_1": "title",
    "last": "summary",
    "second_last": "exercise",
}

RULES = [
    "ONE idea per slide; ONE focal element.",
    "Bullets are KEYWORDS (<=14 words); narration must NOT read them verbatim.",
    "No two consecutive slides share a layout.",
    "The 'content' layout is at most ~35% of a lesson.",
    "prose, definition, and split_code each appear at least once per lesson.",
    "Insert a chapter_title/checkpoint 'breath' roughly every 5-6 slides.",
    "Accent color used at most ONCE per slide; status color is never the accent.",
    "Emphasis ladder: size > weight > color > space.",
]

# Density: a slide's estimated visual load, compared to a layout's capacity.
# score = chars*0.4 + bullets*8 + code_lines*6 + media*20  (blueprint §13)
DENSITY_WEIGHTS = {"chars": 0.4, "bullet": 8, "code_line": 6, "media": 20}

# The layout catalog. Every entry: id, family, use_when, caps, density_capacity,
# motion/transition defaults. Families group layouts for diversity/rhythm rules.
LAYOUTS: List[Dict] = [
    # -- opening / structural --
    {"id": "title", "family": "opening", "use_when": "slide 1 / lesson open",
     "caps": {"headline_words": 10}, "density_capacity": 40,
     "motion": "intro_sequence", "transition": "fadeblack"},
    {"id": "agenda", "family": "opening", "use_when": "roadmap right after the hook",
     "caps": {"items": 7}, "density_capacity": 80, "motion": "stagger_in", "transition": "slideleft"},
    {"id": "chapter_title", "family": "opening", "use_when": "major sub-topic change (a pacing breath)",
     "caps": {"headline_words": 6}, "density_capacity": 40, "motion": "scene_dip", "transition": "fadeblack"},
    {"id": "hook", "family": "opening", "use_when": "provocation before explaining",
     "caps": {"headline_words": 15}, "density_capacity": 50, "motion": "word_emphasis", "transition": "fadeblack"},

    # -- concept / explanation --
    {"id": "content", "family": "concept", "use_when": "general point; the fallback (<=35% of lesson)",
     "caps": {"bullets": 4, "bullet_words": 14}, "density_capacity": 110,
     "motion": "bullet_stagger", "transition": "fade", "forbidden_after": ["content"]},
    {"id": "prose", "family": "concept", "use_when": "intuition BEFORE mechanics (most 'concept' sections)",
     "caps": {"paragraph_sentences": 3, "bullets": 3, "bullet_words": 14}, "density_capacity": 90,
     "motion": "para_then_bullets", "transition": "fade", "forbidden_after": ["prose"]},
    {"id": "definition", "family": "concept", "use_when": "introduce ONE formal term",
     "caps": {"lines": 2}, "density_capacity": 60, "motion": "term_scale_in", "transition": "fade"},
    {"id": "key_insight", "family": "concept", "use_when": "one memorable 'aha' sentence (mid-lesson)",
     "caps": {"sentences": 1}, "density_capacity": 45, "motion": "type_emphasis", "transition": "dissolve"},
    {"id": "mental_model", "family": "concept", "use_when": "closing carry-away rule (end of lesson)",
     "caps": {"sentences": 1}, "density_capacity": 45, "motion": "type_emphasis", "transition": "smoothleft"},
    {"id": "big_number", "family": "concept", "use_when": "one tangible metric",
     "caps": {"context_lines": 1}, "density_capacity": 40, "motion": "count_up", "transition": "zoomin"},
    {"id": "quote", "family": "concept", "use_when": "cite the spec / docs / an authority",
     "caps": {"quote_words": 40}, "density_capacity": 70, "motion": "dissolve_in", "transition": "dissolve"},
    {"id": "analogy", "family": "concept", "use_when": "real-world <-> technical mapping",
     "caps": {"panels": 2}, "density_capacity": 100, "motion": "panels_then_link", "transition": "smoothleft"},

    # -- code / technical --
    {"id": "code", "family": "code", "use_when": "self-contained code, no separate explanation beat",
     "caps": {"code_lines": 22}, "density_capacity": 150, "motion": "code_line_reveal",
     "transition": "wipedown", "a11y": f"code_floor_px:{CODE_FLOOR_PX}"},
    {"id": "split_code", "family": "code", "use_when": "explain a mechanism AND show its code (workhorse)",
     "caps": {"bullets": 3, "code_lines": 18}, "density_capacity": 140, "motion": "code_line_reveal",
     "transition": "wipeleft", "a11y": f"code_floor_px:{CODE_FLOOR_PX}"},
    {"id": "code_output", "family": "code", "use_when": "code + what it prints (REAL output only)",
     "caps": {"code_lines": 16, "output_lines": 8}, "density_capacity": 150, "motion": "reveal_then_output",
     "transition": "wipedown"},
    {"id": "code_evolution", "family": "code", "use_when": "before/after refactor (not a bug)",
     "caps": {"code_lines": 14}, "density_capacity": 150, "motion": "diff_reveal", "transition": "wipeleft"},
    {"id": "snippet", "family": "code", "use_when": "1-5 line inline fragment, no chrome",
     "caps": {"code_lines": 5}, "density_capacity": 60, "motion": "fade_up", "transition": "wipeleft"},
    {"id": "terminal", "family": "code", "use_when": "shell usage / program output",
     "caps": {"lines": 10}, "density_capacity": 120, "motion": "line_reveal", "transition": "wipedown"},
    {"id": "error_fix", "family": "code", "use_when": "broken vs corrected code",
     "caps": {"lines": 10}, "density_capacity": 140, "motion": "reveal", "transition": "slideleft"},

    # -- comparison / data --
    {"id": "two_column", "family": "compare", "use_when": "two options/versions/styles side by side",
     "caps": {"bullets_per_side": 4}, "density_capacity": 130, "motion": "columns_in", "transition": "wipeleft",
     "forbidden_after": ["comparison"]},
    {"id": "comparison", "family": "compare", "use_when": "structured A-vs-B (more structure than two_column)",
     "caps": {"bullets_per_side": 4}, "density_capacity": 130, "motion": "columns_in", "transition": "wipeleft",
     "forbidden_after": ["two_column"]},
    {"id": "pros_cons", "family": "compare", "use_when": "tradeoffs of one thing",
     "caps": {"pros": 4, "cons": 4}, "density_capacity": 120, "motion": "columns_in", "transition": "slideleft"},
    {"id": "table", "family": "compare", "use_when": "naturally tabular data",
     "caps": {"cols": 4, "rows": 6}, "density_capacity": 160, "motion": "rows_in", "transition": "fade"},
    {"id": "timeline", "family": "compare", "use_when": "chronological progression",
     "caps": {"events": 6}, "density_capacity": 130, "motion": "nodes_in", "transition": "slideleft"},
    {"id": "bar_chart", "family": "compare", "use_when": "compare a few numbers",
     "caps": {"bars": 6}, "density_capacity": 110, "motion": "bars_grow", "transition": "slideup"},

    # -- process --
    {"id": "numbered_steps", "family": "process", "use_when": "ordered procedure (3+ steps)",
     "caps": {"steps": 5}, "density_capacity": 120, "motion": "steps_in", "transition": "slideleft"},
    {"id": "cycle", "family": "process", "use_when": "repeating circular process",
     "caps": {"steps": 6}, "density_capacity": 110, "motion": "nodes_in", "transition": "circlecrop"},

    # -- engagement --
    {"id": "quiz", "family": "engagement", "use_when": "multiple-choice knowledge check",
     "caps": {"options": 4}, "density_capacity": 120, "motion": "options_in", "transition": "slideup"},
    {"id": "think_pause", "family": "engagement", "use_when": "ask the viewer to pause and predict",
     "caps": {"headline_words": 15}, "density_capacity": 50, "motion": "hold_countdown", "transition": "dissolve"},

    # -- callouts --
    {"id": "warning", "family": "callout", "use_when": "danger/pitfall (crit accent, no fix shown)",
     "caps": {"bullets": 3}, "density_capacity": 90, "motion": "fade_up", "transition": "fade"},
    {"id": "tip", "family": "callout", "use_when": "best-practice / pro tip (info accent)",
     "caps": {"bullets": 3}, "density_capacity": 90, "motion": "fade_up", "transition": "fade"},

    # -- closing --
    {"id": "checkpoint", "family": "closing", "use_when": "mid-lesson recap ('So far')",
     "caps": {"bullets": 4}, "density_capacity": 100, "motion": "bullet_stagger", "transition": "fade"},
    {"id": "summary", "family": "closing", "use_when": "final takeaways + next teaser (always last)",
     "caps": {"bullets": 5}, "density_capacity": 110, "motion": "bullet_stagger", "transition": "fadeblack"},
    {"id": "exercise", "family": "closing", "use_when": "challenge (second-to-last; the one amber moment)",
     "caps": {"bullets": 3}, "density_capacity": 90, "motion": "fade_up", "transition": "fade"},
    {"id": "resources", "family": "closing", "use_when": "further reading pointers",
     "caps": {"items": 5}, "density_capacity": 100, "motion": "stagger_in", "transition": "fade"},
]

CATALOG: Dict[str, Dict] = {layout["id"]: layout for layout in LAYOUTS}
VALID_LAYOUTS = set(CATALOG)
FAMILIES = sorted({layout["family"] for layout in LAYOUTS})

# Content mapping the LLM must follow (blueprint §20).
CONTENT_MAPPING = {
    "title": "the CLAIM (<=8 words)",
    "bullets": "2-4 keywords, NOT sentences (<=14 words each)",
    "emphasis_term": "the single word/phrase the narrator stresses",
    "code": "complete, runnable; real captured output only",
}


def _count_code_lines(slide: dict) -> int:
    lines = 0
    for key in ("code_content", "left_code", "right_code"):
        v = slide.get(key) or ""
        if v.strip():
            lines += len([ln for ln in v.split("\n") if ln.strip()])
    return lines


def _count_bullets(slide: dict) -> int:
    return sum(len(slide.get(k) or []) for k in
               ("bullets", "left_bullets", "right_bullets", "items", "pros", "cons",
                "steps", "events", "bars", "options", "rows"))


def _count_chars(slide: dict) -> int:
    parts = [slide.get("headline", ""), slide.get("paragraph", ""),
             slide.get("subtitle", ""), slide.get("callout", ""),
             slide.get("text", ""), slide.get("connection", "")]
    for k in ("bullets", "left_bullets", "right_bullets", "items"):
        parts += [str(x) for x in (slide.get(k) or [])]
    return sum(len(str(p)) for p in parts)


def _has_media(slide: dict) -> int:
    return 1 if (slide.get("diagram_ref") or slide.get("media_path")) else 0


def density_score(slide: dict) -> float:
    """Estimated visual load of a slide, per the blueprint density formula."""
    w = DENSITY_WEIGHTS
    return (_count_chars(slide) * w["chars"]
            + _count_bullets(slide) * w["bullet"]
            + _count_code_lines(slide) * w["code_line"]
            + _has_media(slide) * w["media"])


def capacity(layout: str) -> float:
    return CATALOG.get(layout, {}).get("density_capacity", 110)


def is_over_budget(slide: dict) -> bool:
    return density_score(slide) > capacity(slide.get("layout", "content"))


def design_brief() -> dict:
    """The full machine-readable design system handed to the slide LLM."""
    return {
        "canvas": CANVAS,
        "type_floor_px": TYPE_FLOOR_PX,
        "rules": RULES,
        "hard_bindings": HARD_BINDINGS,
        "density_formula": "chars*0.4 + bullets*8 + code_lines*6 + media*20 (vs a layout's density_capacity)",
        "content_mapping": CONTENT_MAPPING,
        "families": FAMILIES,
        "layouts": [
            {k: v for k, v in layout.items() if k in
             ("id", "family", "use_when", "caps", "density_capacity", "forbidden_after")}
            for layout in LAYOUTS
        ],
    }


def design_brief_json() -> str:
    return json.dumps(design_brief(), indent=2)
