import httpx
from bs4 import BeautifulSoup
import re


def extract_url(url: str, timeout: int = 30) -> str:
    """Fetch and extract readable text from a URL using Playwright for CSR support."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            # wait until network is mostly idle to ensure JS framework has rendered
            page.goto(url, timeout=timeout * 1000, wait_until="networkidle")
            
            # extract main content or body text, removing scripts/styles
            text = page.evaluate("""() => {
                const clones = document.body.cloneNode(true);
                clones.querySelectorAll('script, style, nav, footer, header, aside').forEach(el => el.remove());
                const main = clones.querySelector('main') || clones.querySelector('article') || clones;
                return main.innerText;
            }""")
            
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return "\n".join(lines)
        finally:
            browser.close()


def extract_markdown_dir(dir_path: str) -> str:
    """Read all markdown files from a directory recursively."""
    from pathlib import Path
    parts = []
    for md_file in sorted(Path(dir_path).rglob("*.md")):
        parts.append(f"\n\n# File: {md_file.name}\n\n{md_file.read_text(encoding='utf-8', errors='ignore')}")
    return "\n".join(parts)
