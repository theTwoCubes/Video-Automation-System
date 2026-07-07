import httpx
from bs4 import BeautifulSoup
import re


def extract_url(url: str, timeout: int = 30) -> str:
    """Fetch and extract readable text from a URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; theTwoCubes/1.0; educational bot)"
    }
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # remove nav, footer, scripts, styles
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # extract main content area if available
    main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|main|body"))
    if main:
        text = main.get_text(separator="\n")
    else:
        text = soup.get_text(separator="\n")

    # clean up whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def extract_markdown_dir(dir_path: str) -> str:
    """Read all markdown files from a directory recursively."""
    from pathlib import Path
    parts = []
    for md_file in sorted(Path(dir_path).rglob("*.md")):
        parts.append(f"\n\n# File: {md_file.name}\n\n{md_file.read_text(encoding='utf-8', errors='ignore')}")
    return "\n".join(parts)
