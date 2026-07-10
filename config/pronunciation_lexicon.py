import re
import json
from pathlib import Path

_lexicon = None


def load_lexicon() -> dict:
    global _lexicon
    if _lexicon is None:
        lex_path = Path("config/pronunciation_lexicon.json")
        with open(lex_path) as f:
            _lexicon = json.load(f)
    return _lexicon


def preprocess_for_tts(text: str) -> str:
    lexicon = load_lexicon()
    for term, phonetic in lexicon.items():
        text = re.sub(r"\b" + re.escape(term) + r"\b", phonetic, text)
    return text
