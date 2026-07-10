"""
PDF Section Processor for theTwoCubes Learning.

Deterministically parses a structured LaTeX-generated PDF into an indexed
section store. No embeddings, no vector DB - pure text retrieval by section ID.

Expected PDF format (as produced by the LaTeX generation prompt):
  - Chapter-level: "Chapter N\\nChapter Title"
  - Section-level: "N.N\\nSection Title"  
  - Subsection-level: "N.N.N\\nSubsection Title"
  - Max depth: 3 levels
  - No TOC page - content starts immediately
"""

import re
import json
import hashlib
from pathlib import Path
import fitz  # PyMuPDF

# Where processed section stores live
PROCESSED_DIR = Path("data/processed")


class PDFProcessor:
    """
    Parses a structured LaTeX PDF into a deterministic section index.

    Produces:
      data/processed/{source_id}/sections.json  : {section_id: {title, text, children}}
      data/processed/{source_id}/toc.txt        : human-readable Table of Contents
    """

    # Regex for heading patterns in extracted text.
    # Matches: "1", "1.1", "1.7.3" at the start of a line.
    SECTION_RE = re.compile(
        r'^(\d{1,2}(?:\.\d{1,2}){0,2})\s*\n(.+)',
        re.MULTILINE
    )
    # Chapter heading: "Chapter N\nTitle"
    CHAPTER_RE = re.compile(
        r'^Chapter\s+(\d{1,2})\s*\n(.+)',
        re.MULTILINE
    )

    def process(self, file_path: str) -> tuple[dict, str, str]:
        """
        Process a PDF and return (sections_dict, toc_text, source_id).

        sections_dict schema:
          {
            "1":   {"title": "...", "text": "...", "children": ["1.1", "1.2"]},
            "1.1": {"title": "...", "text": "...", "children": []},
            ...
          }
        """
        pdf_path = Path(file_path)
        raw_text = self._extract_raw(pdf_path)

        # Compute a stable source_id from file content
        source_id = hashlib.sha256(raw_text.encode()).hexdigest()[:12]

        # Check if already processed (idempotent)
        out_dir = PROCESSED_DIR / source_id
        sections_file = out_dir / "sections.json"
        toc_file = out_dir / "toc.txt"

        if sections_file.exists() and toc_file.exists():
            sections = json.loads(sections_file.read_text(encoding="utf-8"))
            toc_text = toc_file.read_text(encoding="utf-8")
            print(f"[PDFProcessor] Cache hit: {source_id} ({len(sections)} sections)")
            return sections, toc_text, source_id

        print(f"[PDFProcessor] Processing {pdf_path.name} -> source_id={source_id}")

        # Clean the raw text
        clean = self._clean(raw_text)

        # Find all heading positions
        headings = self._find_headings(clean)

        if not headings:
            raise ValueError(
                "No section headings found. "
                "Ensure the PDF follows the required LaTeX structure."
            )

        # Slice text between headings to get each section's body
        sections = self._build_sections(clean, headings)

        # Wire up parent→children relationships
        sections = self._build_hierarchy(sections)

        # Generate TOC text
        toc_text = self._build_toc(sections)

        # Persist
        out_dir.mkdir(parents=True, exist_ok=True)
        sections_file.write_text(json.dumps(sections, indent=2, ensure_ascii=False), encoding="utf-8")
        toc_file.write_text(toc_text, encoding="utf-8")

        print(f"[PDFProcessor] Done: {len(sections)} sections, saved to {out_dir}")
        return sections, toc_text, source_id

    def get_sections(self, source_id: str, section_ids: list[str], labeled: bool = True) -> str:
        """
        Retrieve and concatenate text for the given section IDs.
        Returns formatted string ready to inject into an LLM prompt.
        """
        sections_file = PROCESSED_DIR / source_id / "sections.json"
        if not sections_file.exists():
            raise FileNotFoundError(f"No processed data for source_id={source_id}")

        sections = json.loads(sections_file.read_text(encoding="utf-8"))
        parts = []

        for sid in section_ids:
            if sid not in sections:
                # Try prefix match (e.g., "7" → return all 7.x children)
                matching = {k: v for k, v in sections.items() if k == sid or k.startswith(f"{sid}.")}
                if not matching:
                    parts.append(f"[Section {sid}: NOT FOUND IN DOCUMENT]")
                    continue
                for k, v in sorted(matching.items()):
                    if labeled:
                        parts.append(f"[SECTION {k} - {v['title']}]\n{v['text']}")
                    else:
                        parts.append(v['text'])
            else:
                sec = sections[sid]
                if labeled:
                    parts.append(f"[SECTION {sid} - {sec['title']}]\n{sec['text']}")
                else:
                    parts.append(sec['text'])

        return "\n\n***\n\n".join(parts)

    def get_toc(self, source_id: str) -> str:
        """Return the synthesized TOC text for a processed source."""
        toc_file = PROCESSED_DIR / source_id / "toc.txt"
        if not toc_file.exists():
            raise FileNotFoundError(f"No TOC for source_id={source_id}")
        return toc_file.read_text(encoding="utf-8")

    def list_section_ids(self, source_id: str) -> list[str]:
        """Return all section IDs in order."""
        sections_file = PROCESSED_DIR / source_id / "sections.json"
        if not sections_file.exists():
            return []
        sections = json.loads(sections_file.read_text(encoding="utf-8"))
        return sorted(sections.keys(), key=lambda x: [int(p) for p in x.split(".")])

    # Private helpers

    def _extract_raw(self, pdf_path: Path) -> str:
        doc = fitz.open(str(pdf_path))
        pages = [page.get_text("text") for page in doc]
        doc.close()
        return "\n\n".join(pages)

    def _clean(self, text: str) -> str:
        """Fix PDF extraction artefacts."""
        # Rejoin soft-hyphenated line breaks: "word-\nrest" → "wordrest"
        text = re.sub(r'-\n(\w)', r'\1', text)
        return text

    def _find_headings(self, text: str) -> list[tuple[int, str, str]]:
        """
        Return list of (char_offset, section_id, title) sorted by offset.
        Handles both:
          "Chapter N\\nTitle"  →  section_id = "N"
          "N.N\\nTitle"        →  section_id = "N.N"
          "N.N.N\\nTitle"      →  section_id = "N.N.N"
        """
        found = {}  # section_id -> (offset, title) (dedup by ID, keep first occurrence)

        # Chapter headings
        for m in self.CHAPTER_RE.finditer(text):
            sid = m.group(1)  # e.g. "1"
            title = m.group(2).strip()
            if sid not in found:
                found[sid] = (m.start(), title)

        # Numbered section headings (N.N or N.N.N only, not bare chapter numbers)
        for m in self.SECTION_RE.finditer(text):
            sid = m.group(1)
            # Skip bare integers that might be year numbers (e.g. "2011")
            if "." not in sid and int(sid) > 20:
                continue
            title = m.group(2).strip()
            if sid not in found:
                found[sid] = (m.start(), title)

        # Sort by character offset
        return sorted(
            [(offset, sid, title) for sid, (offset, title) in found.items()],
            key=lambda x: x[0]
        )

    def _build_sections(self, text: str, headings: list[tuple]) -> dict:
        """
        Slice the text between heading boundaries to extract each section's body.
        """
        sections = {}
        for i, (offset, sid, title) in enumerate(headings):
            # Find where this section's content starts (after the title line)
            # Skip past the heading match itself
            content_start = text.find('\n', offset) + 1
            if i + 1 < len(headings):
                content_end = headings[i + 1][0]
            else:
                content_end = len(text)

            body = text[content_start:content_end].strip()

            # Remove the section number + title from the very start if duplicated
            body = re.sub(r'^\s*' + re.escape(title) + r'\s*\n?', '', body).strip()

            sections[sid] = {
                "title": title,
                "text": body,
                "children": []
            }

        return sections

    def _build_hierarchy(self, sections: dict) -> dict:
        """Wire parent → children based on section ID prefix."""
        ids = sorted(sections.keys(), key=lambda x: [int(p) for p in x.split(".")])
        for sid in ids:
            parts = sid.split(".")
            if len(parts) > 1:
                parent_id = ".".join(parts[:-1])
                if parent_id in sections:
                    sections[parent_id]["children"].append(sid)
        return sections

    def _build_toc(self, sections: dict) -> str:
        """Generate a clean, hierarchical TOC string."""
        ids = sorted(sections.keys(), key=lambda x: [int(p) for p in x.split(".")])
        lines = []
        for sid in ids:
            depth = sid.count(".")
            indent = "  " * depth
            title = sections[sid]["title"]
            lines.append(f"{indent}{sid}  {title}")
        return "\n".join(lines)
