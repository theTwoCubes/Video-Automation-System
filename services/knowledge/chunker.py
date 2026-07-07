import re
from typing import List


def chunk_text(text: str, max_tokens: int = 500, overlap: int = 50) -> List[str]:
    """
    Semantic-aware chunker. Splits on paragraph boundaries first,
    then sentence boundaries, targeting max_tokens (~4 chars/token).
    """
    max_chars = max_tokens * 4
    overlap_chars = overlap * 4

    # split on double newlines (paragraph breaks)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) <= max_chars:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            if len(para) <= max_chars:
                current = para
            else:
                # split long paragraph by sentences
                sentences = re.split(r"(?<=[.!?])\s+", para)
                for sent in sentences:
                    if len(current) + len(sent) <= max_chars:
                        current = (current + " " + sent).strip()
                    else:
                        if current:
                            chunks.append(current)
                        current = sent

    if current:
        chunks.append(current)

    # add overlap: prepend tail of previous chunk
    if overlap_chars > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-overlap_chars:]
            overlapped.append(tail + " " + chunks[i])
        return overlapped

    return chunks


def extract_code_blocks(text: str) -> tuple[str, List[str]]:
    """
    Extract code blocks from markdown text.
    Returns (text_without_code, [code_blocks]).
    Code blocks are never split by the chunker.
    """
    code_pattern = re.compile(r"```[\w]*\n(.*?)```", re.DOTALL)
    code_blocks = code_pattern.findall(text)
    clean_text = code_pattern.sub("[CODE_BLOCK]", text)
    return clean_text, code_blocks
