"""
Slide layout stress test - D.3 from FuturePLAN.md

Renders every slide layout with maximal content (long headline, 5 bullets, 20-line code)
to catch font overflow and layout break issues.

Usage:
    python scripts/stress_test_layouts.py
    python scripts/stress_test_layouts.py --out-dir output/layout_tests
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.slide_renderer.renderer import SlideRenderer

LONG_HEADLINE = "Understanding Memory Allocation and Pointer Arithmetic in Modern C++"
SHORT_HEADLINE = "Pointers and Memory"

LONG_BULLETS = [
    "A pointer stores the memory address of another variable, not the value itself",
    "Dereferencing a null pointer causes undefined behavior and crashes at runtime",
    "Pointer arithmetic moves by the size of the pointed type, not by bytes directly",
    "Smart pointers like unique_ptr automatically free memory when scope ends",
    "Raw pointers should only be used when you need manual memory management",
]

LONG_CODE = """#include <iostream>
#include <memory>
using namespace std;

int main() {
    // Stack allocation
    int x = 42;
    int* p = &x;

    cout << "Value: " << *p << endl;
    cout << "Address: " << p << endl;

    // Heap allocation
    int* heap = new int(100);
    cout << "Heap value: " << *heap << endl;
    delete heap;

    // Smart pointer
    auto smart = make_unique<int>(200);
    cout << "Smart: " << *smart << endl;

    return 0;
}"""

LAYOUTS = [
    ("title",          {"headline": LONG_HEADLINE, "bullets": [], "code_content": ""}),
    ("content",        {"headline": SHORT_HEADLINE, "bullets": LONG_BULLETS, "code_content": ""}),
    ("code",           {"headline": "Pointer Demo", "bullets": [], "code_content": LONG_CODE}),
    ("numbered_steps", {"headline": "How to Use Pointers", "bullets": LONG_BULLETS[:4], "code_content": ""}),
    ("checklist",      {"headline": "Memory Safety Checklist", "bullets": LONG_BULLETS, "code_content": ""}),
    ("comparison",     {
        "headline": "Stack vs Heap",
        "left_label": "Stack", "right_label": "Heap",
        "left_bullets": LONG_BULLETS[:2],
        "right_bullets": LONG_BULLETS[2:4],
        "bullets": [], "code_content": "",
    }),
    ("error_fix",      {
        "headline": "Memory Leak: Wrong vs Right",
        "left_label": "Wrong", "right_label": "Fixed",
        "left_bullets": ["int* p = new int(5);", "// forgot delete"],
        "right_bullets": ["auto p = make_unique<int>(5);", "// auto-freed"],
        "bullets": [],
        "code_content": "int* p = new int(5);\n// WRONG: memory leak\n\nauto p = make_unique<int>(5);\n// RIGHT: auto cleanup",
    }),
    ("terminal",       {
        "headline": "Compilation Output",
        "bullets": [],
        "code_content": "$ g++ -std=c++17 -Wall pointer.cpp -o pointer\n$ ./pointer\nValue: 42\nAddress: 0x7ffe4c2b1234\nHeap value: 100\nSmart: 200",
    }),
    ("summary",        {"headline": "Key Takeaways", "bullets": LONG_BULLETS[:3], "code_content": ""}),
    ("two_column",     {
        "headline": "References vs Pointers",
        "left_label": "Reference", "right_label": "Pointer",
        "left_bullets": ["Cannot be null", "Cannot be reassigned", "No dereferencing needed"],
        "right_bullets": ["Can be null", "Can point to different objects", "Must be dereferenced with *"],
        "bullets": [], "code_content": "",
    }),
    ("exercise",       {
        "headline": "Challenge: Fix the Memory Leak",
        "bullets": [
            "Given: int* arr = new int[10];",
            "Task: Free the array correctly",
            "Bonus: Rewrite using a smart pointer",
        ],
        "code_content": "int* arr = new int[10];\n// fill array...\n// TODO: free memory",
    }),
]


def main():
    parser = argparse.ArgumentParser(description="Stress-test all slide layouts")
    parser.add_argument("--out-dir", default="output/layout_tests", help="Output directory for PNGs")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    renderer = SlideRenderer()
    total = len(LAYOUTS)
    passed = 0

    print(f"Rendering {total} layout variants to {out_dir}/")
    for i, (layout, data) in enumerate(LAYOUTS):
        slide_data = {
            "id": f"stress_{i:03d}",
            "layout": layout,
            "tag": "CONCEPT",
            "lesson_number": 1,
            **data,
        }
        out_path = str(out_dir / f"{i+1:02d}_{layout}.png")
        try:
            renderer.render_slide(slide_data, out_path, slide_index=i, total_slides=total)
            size_kb = Path(out_path).stat().st_size // 1024
            print(f"  [{i+1}/{total}] {layout:20s} OK  {size_kb} KB")
            passed += 1
        except Exception as e:
            print(f"  [{i+1}/{total}] {layout:20s} FAIL: {e}")

    print(f"\n{passed}/{total} layouts rendered successfully.")
    if passed < total:
        print("  Check failed layouts above for template issues.")
    else:
        print(f"  All layouts pass. Images saved to: {out_dir}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
