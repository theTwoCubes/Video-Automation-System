"""
Slide Content Validator - A.2 from FuturePLAN.md

Validates slide specs BEFORE rendering (saves Playwright time on bad slides).
Returns detailed issues list. Also provides auto_fix_slides() for simple repairs.
"""
from __future__ import annotations

VAGUE_WORDS = {
    "understanding", "exploring", "introduction", "overview", "basics",
    "aspects", "elements", "things", "various", "looking", "discussing",
    "examining", "covering", "learning", "seeing",
}

LAYOUT_BULLET_LIMITS = {
    "content":        (3, 5),
    "numbered_steps": (2, 6),
    "checklist":      (2, 7),
    "summary":        (2, 4),
    "warning":        (2, 3),
    "tip":            (2, 3),
    "checkpoint":     (2, 4),
}

# Layouts whose primary content lives in fields other than `bullets` - the
# generic bullet-count check is skipped for these so it doesn't flag e.g. a
# `quiz` slide (content lives in `question`/`options`) as having 0 bullets.
NON_BULLET_LAYOUTS = {
    "title", "prose", "code", "split_code", "definition", "terminal",
    "chapter_title", "agenda", "hook", "key_insight", "big_number", "quote",
    "analogy", "code_output", "code_evolution", "snippet", "pros_cons",
    "table", "timeline", "cycle", "bar_chart", "quiz", "think_pause",
    "mental_model", "resources", "two_column", "comparison", "error_fix",
    "exercise",
}


def validate_slides(slides: list[dict]) -> list[dict]:
    """
    Validate a list of slide spec dicts.
    Returns a list of {slide_id, issues:[str]} - empty list means all slides pass.
    """
    all_issues = []

    for slide in slides:
        problems: list[str] = []
        layout  = slide.get("layout", "content")
        headline = (slide.get("headline") or "").strip()
        bullets  = slide.get("bullets", []) or []
        left_b   = slide.get("left_bullets", []) or []
        right_b  = slide.get("right_bullets", []) or []
        code     = (slide.get("code_content") or "").strip()

        #  Headline 
        if not headline:
            problems.append("Missing headline")
        else:
            words = headline.split()
            if len(words) > 10:
                problems.append(f"Headline too long ({len(words)} words, max 8)")
            vague = [w for w in words if w.lower().rstrip(".,;:") in VAGUE_WORDS]
            if vague:
                problems.append(f"Vague headline word(s): {', '.join(vague)}")

        #  Bullets
        if layout not in NON_BULLET_LAYOUTS:
            lo, hi = LAYOUT_BULLET_LIMITS.get(layout, (0, 6))
            if lo and len(bullets) < lo:
                problems.append(f"{layout} slide has {len(bullets)} bullet(s) (min {lo})")
            if hi and len(bullets) > hi:
                problems.append(f"{layout} slide has {len(bullets)} bullet(s) (max {hi})")

        for i, b in enumerate(bullets):
            clean = b.replace("`", "").strip()
            wc = len(clean.split())
            if wc < 3:
                problems.append(f"Bullet {i+1} too short ({wc} words)")
            if wc > 25:
                problems.append(f"Bullet {i+1} too long ({wc} words, max 25)")

        #  Code 
        if layout == "code":
            if not code:
                problems.append("Code layout has empty code_content")
            else:
                lines = [l.strip() for l in code.split("\n") if l.strip()]
                if len(lines) < 2:
                    problems.append("Code block has fewer than 2 non-empty lines")

        #  Two-column / comparison
        if layout in ("two_column", "comparison"):
            if not left_b and not right_b:
                problems.append(f"{layout} slide has no left_bullets or right_bullets")

        #  New layout structural requirements
        if layout == "code_evolution":
            if not (slide.get("left_code") or "").strip() or not (slide.get("right_code") or "").strip():
                problems.append("code_evolution slide is missing left_code or right_code")
        if layout == "quiz":
            if not (slide.get("question") or "").strip():
                problems.append("quiz slide is missing question")
            options = slide.get("options") or []
            if len(options) < 2:
                problems.append(f"quiz slide has {len(options)} option(s) (min 2)")
            if not slide.get("answer"):
                problems.append("quiz slide is missing answer")
        if layout == "table":
            rows = slide.get("rows") or []
            if not rows:
                problems.append("table slide has no rows")
        if layout == "bar_chart":
            bars = slide.get("bars") or []
            if not bars:
                problems.append("bar_chart slide has no bars")
        if layout == "timeline":
            events = slide.get("events") or []
            if not events:
                problems.append("timeline slide has no events")
        if layout == "pros_cons":
            if not slide.get("pros") and not slide.get("cons"):
                problems.append("pros_cons slide has no pros or cons")
        if layout == "agenda":
            items = slide.get("items") or bullets
            if not items:
                problems.append("agenda slide has no items")

        if problems:
            all_issues.append({
                "slide_id": slide.get("id", "unknown"),
                "layout":   layout,
                "headline": headline[:50],
                "issues":   problems,
            })

    return all_issues


def auto_fix_slides(slides: list[dict]) -> list[dict]:
    """
    Apply non-destructive auto-fixes to slide specs:
      - Truncate headlines > 9 words with ellipsis
      - Cap bullet list length to layout maximum
      - Strip trailing whitespace from bullets

    Never changes layout or removes code - those need manual or LLM review.
    """
    fixed = []
    for slide in slides:
        s = dict(slide)

        # headline truncation
        words = (s.get("headline") or "").split()
        if len(words) > 9:
            s["headline"] = " ".join(words[:8]) + "…"

        # bullet cap
        layout = s.get("layout", "content")
        _, hi = LAYOUT_BULLET_LIMITS.get(layout, (0, 6))
        if hi and len(s.get("bullets", [])) > hi:
            s["bullets"] = s["bullets"][:hi]

        # clean bullets
        s["bullets"] = [b.strip() for b in s.get("bullets", [])]

        fixed.append(s)
    return fixed


def print_validation_report(issues: list[dict]) -> None:
    if not issues:
        print("  ✓ All slides passed validation")
        return
    print(f"  ⚠ {len(issues)} slide(s) have issues:")
    for item in issues:
        print(f"    [{item['slide_id']}] {item['headline'][:40]}")
        for issue in item["issues"]:
            print(f"      • {issue}")
