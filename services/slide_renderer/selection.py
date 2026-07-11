"""
Layout selection engine (blueprint §13).

The LLM slide agent chooses layouts, but it chooses WITHIN a system this module
defines and checks. Two responsibilities:

  * classify(slide)  - the content-shape -> candidate-layout mapping, so the
    engine (or a future deterministic picker) can narrow choices the way the
    rules do, and so the linter knows what a slide "could" have been.
  * audit(slides)    - a whole-deck check of the diversity / rhythm / density
    invariants the design brief only *requests* of the LLM. Its findings feed
    the render linter (services/slide_validator) and the pipeline logs.

Deliberately conservative: it REPORTS violations rather than blindly rewriting a
slide's layout (which could orphan content a template needs). Auto-repair is
limited to the safe, mechanical fixes in slide_validator.auto_fix_slides.
"""
from __future__ import annotations

from typing import Dict, List

from services.slide_renderer.layout_catalog import (
    CATALOG, density_score, capacity,
)

# Fraction of a lesson the generic 'content' layout may occupy (§13).
MAX_CONTENT_FRACTION = 0.35
# Layouts that must appear at least once in every lesson (§13).
REQUIRED_ONCE = ("prose", "definition", "split_code")
# How many slides may pass between "breath" dividers before we flag monotony.
BREATH_EVERY = 6
BREATH_LAYOUTS = ("chapter_title", "checkpoint", "agenda")


def _has(slide: dict, key: str) -> bool:
    v = slide.get(key)
    return bool(v.strip()) if isinstance(v, str) else bool(v)


def classify(slide: dict) -> List[str]:
    """Return candidate layout ids that fit this slide's content shape. Used for
    diagnostics and as the narrowing step a deterministic picker would apply."""
    cands: List[str] = []
    if _has(slide, "code_content") or _has(slide, "left_code"):
        cands += ["split_code", "code", "code_output", "code_evolution", "snippet"]
    if slide.get("rows"):
        cands.append("table")
    if slide.get("bars"):
        cands.append("bar_chart")
    if slide.get("events"):
        cands.append("timeline")
    if slide.get("steps"):
        cands += ["numbered_steps", "cycle"]
    if slide.get("options") or _has(slide, "question"):
        cands.append("quiz")
    if _has(slide, "left_content") and _has(slide, "right_content"):
        cands.append("analogy")
    if slide.get("left_bullets") or slide.get("right_bullets"):
        cands += ["two_column", "comparison"]
    if slide.get("pros") or slide.get("cons"):
        cands.append("pros_cons")
    if _has(slide, "number"):
        cands.append("big_number")
    if _has(slide, "paragraph"):
        cands += ["prose", "definition"]
    if slide.get("bullets"):
        cands += ["content", "prose"]
    # de-dup, keep order, keep only real layouts
    seen, out = set(), []
    for c in cands:
        if c in CATALOG and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def audit(slides: List[dict]) -> List[Dict]:
    """Report deck-level design-system violations. Each item is
    {slide_id, kind, detail}."""
    issues: List[Dict] = []
    n = len(slides)
    if n == 0:
        return issues

    layouts = [s.get("layout", "content") for s in slides]

    # 1. no two consecutive slides share a layout
    for i in range(1, n):
        if layouts[i] == layouts[i - 1]:
            issues.append({"slide_id": slides[i].get("id", f"#{i}"),
                           "kind": "consecutive-layout",
                           "detail": f"same layout '{layouts[i]}' as previous slide"})
    # explicit forbidden_after pairs from the catalog (e.g. two_column<->comparison)
    for i in range(1, n):
        forbidden = CATALOG.get(layouts[i], {}).get("forbidden_after", [])
        if layouts[i - 1] in forbidden:
            issues.append({"slide_id": slides[i].get("id", f"#{i}"),
                           "kind": "forbidden-adjacency",
                           "detail": f"'{layouts[i]}' should not follow '{layouts[i-1]}'"})

    # 2. content overuse
    content_frac = layouts.count("content") / n
    if content_frac > MAX_CONTENT_FRACTION:
        issues.append({"slide_id": "*", "kind": "content-overuse",
                       "detail": f"'content' is {content_frac:.0%} of the lesson (max {MAX_CONTENT_FRACTION:.0%})"})

    # 3. required-once layouts (only meaningful for a full lesson, >6 slides)
    if n > 6:
        present = set(layouts)
        for req in REQUIRED_ONCE:
            if req not in present:
                issues.append({"slide_id": "*", "kind": "missing-required",
                               "detail": f"lesson never uses '{req}'"})

    # 4. pacing breaths
    if n > BREATH_EVERY + 1:
        last_breath = -1
        for i, lay in enumerate(layouts):
            if lay in BREATH_LAYOUTS:
                last_breath = i
            elif i - last_breath > BREATH_EVERY:
                issues.append({"slide_id": slides[i].get("id", f"#{i}"),
                               "kind": "no-breath",
                               "detail": f"{i - last_breath} slides since a chapter_title/checkpoint breath"})
                last_breath = i  # report once per run of monotony

    # 5. density over budget
    for s in slides:
        score = density_score(s)
        cap = capacity(s.get("layout", "content"))
        if score > cap:
            issues.append({"slide_id": s.get("id", "?"), "kind": "over-density",
                           "detail": f"density {score:.0f} exceeds '{s.get('layout')}' capacity {cap:.0f} - split this slide"})

    return issues


def audit_summary(slides: List[dict]) -> str:
    issues = audit(slides)
    if not issues:
        return "  ✓ Layout audit: deck satisfies diversity/density rules"
    lines = [f"  ⚠ Layout audit: {len(issues)} issue(s)"]
    for it in issues[:12]:
        lines.append(f"    [{it['slide_id']}] {it['kind']}: {it['detail']}")
    return "\n".join(lines)
