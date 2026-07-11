"""
Golden layout gallery - renders EVERY layout in the catalog with a
representative fixture, so a template change can be diffed layout-by-layout
before it ships (blueprint "golden-output suite"). Doubles as a smoke test:
it fails if any catalog layout can't render.

Usage:
    python scripts/render_layout_gallery.py
    python scripts/render_layout_gallery.py --out-dir output/_layout_gallery
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.slide_renderer.renderer import SlideRenderer
from services.slide_renderer.layout_catalog import LAYOUTS as CATALOG_LAYOUTS

# Every optional field a template might touch, defaulted so Jinja never iterates
# an undefined value (mirrors the SlideAgent's own setdefault block).
DEFAULTS = {
    "bullets": [], "paragraph": "", "callout": "", "whats_next": "", "context": "",
    "hint": "", "left_bullets": [], "right_bullets": [], "left_label": "", "right_label": "",
    "subtitle": "", "tag": "", "code_content": "", "code_filename": "", "code_language": "cpp",
    "caption": "", "items": [], "number": "", "label": "", "text": "", "attribution": "",
    "left_content": "", "right_content": "", "connection": "", "explanation": "",
    "output_lines": [], "left_code": "", "right_code": "", "pros": [], "cons": [],
    "headers": [], "rows": [], "events": [], "steps": [], "bars": [], "question": "",
    "options": [], "answer": "", "transition": "", "lesson_number": 1,
}

_CODE = ("#include <iostream>\nint main() {\n    int x = 42;\n"
         "    int* p = &x;\n    std::cout << *p << std::endl;\n    return 0;\n}")

# One representative fixture per layout. Keyed by layout id from the catalog.
FIXTURES = {
    "title": {"headline": "Introduction to Pointers", "subtitle": "How memory addresses actually work"},
    "agenda": {"headline": "What You'll Master", "items": ["Why pointers exist", "The address-of operator", "Dereferencing", "Pointer arithmetic"]},
    "chapter_title": {"headline": "The Stack", "subtitle": "Where local variables live"},
    "hook": {"headline": "Every segfault you have ever seen comes from one mistake"},
    "content": {"headline": "What a pointer holds", "bullets": ["Stores an address like 0x7ffe1234", "Not the value - the location", "8 bytes on a 64-bit system", "Dereference with the star operator"]},
    "prose": {"headline": "The sticky-note model", "paragraph": "A pointer is a variable that stores a memory address. Think of a sticky note that says 'the answer is in drawer 42'.", "bullets": ["Holds an address, not a value", "sizeof(p) is 8 on 64-bit"]},
    "definition": {"headline": "Dereference", "bullets": ["Following a pointer to read the value it points at", "Written *p"], "context": "cout << *p reads the int at p's address"},
    "key_insight": {"headline": "A pointer is **just a number** that happens to be an address"},
    "mental_model": {"headline": "If you allocate it, you free it", "explanation": "Every new needs a delete; every malloc needs a free."},
    "big_number": {"number": "8 bytes", "label": "size of any pointer on 64-bit", "context": "Regardless of what type it points to"},
    "quote": {"text": "A pointer is a variable whose value is the address of another variable.", "attribution": "K&R, The C Programming Language", "headline": "From the source"},
    "analogy": {"headline": "Pointers, explained", "left_label": "Real world", "left_content": "A house address on an envelope - it tells you where to go, it is not the house.", "right_label": "In code", "right_content": "int* p holds 0x7ffe1234 - the location of x, not x itself.", "connection": "The address points you to the data, the same way an envelope points you to a house."},
    "code": {"headline": "Reading a pointer", "code_content": _CODE, "code_filename": "main.cpp"},
    "split_code": {"headline": "Address-of and dereference", "paragraph": "&x gives the address of x; *p reads the value back.", "bullets": ["& takes an address", "* follows one"], "code_content": _CODE, "code_filename": "main.cpp"},
    "code_output": {"headline": "What it prints", "code_content": _CODE, "output_lines": ["42"]},
    "code_evolution": {"headline": "Raw to smart pointer", "left_label": "Before", "left_code": "int* p = new int(5);\n// ... forgot delete", "right_label": "After", "right_code": "auto p = std::make_unique<int>(5);\n// freed automatically"},
    "snippet": {"headline": "The two operators", "code_content": "int* p = &x;\nint v = *p;", "explanation": "& takes an address, * follows it."},
    "terminal": {"headline": "Compile and run", "bullets": ["$ g++ -std=c++17 main.cpp -o main", "$ ./main", "# 42"]},
    "error_fix": {"headline": "Wrong vs right", "left_label": "Leak", "left_bullets": ["int* p = new int(5);", "// no delete"], "right_label": "Fixed", "right_bullets": ["auto p = make_unique<int>(5);", "// auto-freed"]},
    "two_column": {"headline": "Reference vs pointer", "left_label": "Reference", "left_bullets": ["Cannot be null", "Cannot be reseated", "No dereference syntax"], "right_label": "Pointer", "right_bullets": ["Can be null", "Can be reassigned", "Dereference with *"]},
    "comparison": {"headline": "Stack vs heap", "left_label": "Stack", "left_bullets": ["Automatic lifetime", "Fast", "Limited size"], "right_label": "Heap", "right_bullets": ["Manual lifetime", "Slower", "Large"]},
    "pros_cons": {"headline": "Raw pointers", "pros": ["Zero overhead", "Full control"], "cons": ["Easy to leak", "Dangling risk", "No ownership signal"]},
    "table": {"headline": "Type sizes on 64-bit", "headers": ["Type", "Bytes"], "rows": [["char", "1"], ["int", "4"], ["double", "8"], ["pointer", "8"]]},
    "timeline": {"headline": "Evolution of memory management", "events": [{"label": "1972", "description": "C introduces malloc/free"}, {"label": "1985", "description": "C++ adds new/delete"}, {"label": "2011", "description": "C++11 smart pointers"}]},
    "bar_chart": {"headline": "Relative access speed", "bars": [{"label": "Register", "value": 100, "display_value": "1x"}, {"label": "Cache", "value": 60, "display_value": "10x"}, {"label": "RAM", "value": 20, "display_value": "100x"}]},
    "numbered_steps": {"headline": "Using a pointer", "bullets": ["Declare: int* p", "Assign: p = &x", "Dereference: *p", "Never leave it dangling"]},
    "cycle": {"headline": "The edit-compile-run loop", "steps": ["Edit", "Compile", "Run", "Debug"]},
    "quiz": {"headline": "Quick check", "question": "What does sizeof(int*) return on 64-bit?", "options": [{"label": "A", "text": "4"}, {"label": "B", "text": "8"}, {"label": "C", "text": "depends on the pointee"}], "answer": "B"},
    "think_pause": {"headline": "What happens if you dereference a null pointer?"},
    "warning": {"headline": "Never do this", "bullets": ["Dereferencing a freed pointer is undefined behavior", "It may 'work' in testing and crash in production"]},
    "tip": {"headline": "Prefer smart pointers", "bullets": ["unique_ptr for sole ownership", "shared_ptr when ownership is shared"], "callout": "Reach for raw pointers only for non-owning views."},
    "checkpoint": {"headline": "So far", "bullets": ["A pointer stores an address", "& takes one, * follows one", "Pointers are 8 bytes on 64-bit"], "transition": "Next: pointer arithmetic."},
    "summary": {"headline": "Key takeaways", "bullets": ["Pointers store addresses, not values", "& and * are inverse operations", "Smart pointers manage lifetime for you"], "whats_next": "we dig into pointer arithmetic and arrays."},
    "exercise": {"headline": "Challenge: fix the leak", "bullets": ["Given int* arr = new int[10];", "Free it correctly", "Bonus: rewrite with a smart pointer"], "hint": "delete[] for arrays, not delete."},
    "resources": {"headline": "Go deeper", "items": [{"title": "cppreference: pointers", "description": "The canonical reference"}, {"title": "C++ Core Guidelines", "description": "Ownership and lifetime rules"}]},
}


def main():
    parser = argparse.ArgumentParser(description="Render the golden layout gallery")
    parser.add_argument("--out-dir", default="output/_layout_gallery")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    renderer = SlideRenderer()

    layout_ids = [layout["id"] for layout in CATALOG_LAYOUTS]
    total = len(layout_ids)
    passed = 0
    print(f"Rendering {total} catalog layouts to {out_dir}/")
    for i, layout in enumerate(layout_ids):
        slide = {"id": f"gallery_{i:03d}", "layout": layout, "tag": "CONCEPT"}
        slide.update(DEFAULTS)
        slide.update(FIXTURES.get(layout, {"headline": layout.replace("_", " ").title(),
                                            "bullets": ["Representative content for this layout"]}))
        out_path = str(out_dir / f"{i+1:02d}_{layout}.png")
        try:
            renderer.render_slide(slide, out_path, slide_index=i, total_slides=total)
            print(f"  [{i+1:02d}/{total}] {layout:16s} OK  {Path(out_path).stat().st_size // 1024} KB")
            passed += 1
        except Exception as e:
            print(f"  [{i+1:02d}/{total}] {layout:16s} FAIL: {e}")

    print(f"\n{passed}/{total} layouts rendered. Gallery: {out_dir}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
