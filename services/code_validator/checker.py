"""
Code static checker — A.4 from FuturePLAN.md

Fast regex-based sanity checks on generated C++/Python code.
No compilation needed — catches the most common LLM code mistakes.
"""
from __future__ import annotations
import re


def check_cpp(code: str) -> list[str]:
    """Check C++ code for common mistakes. Returns list of issue strings."""
    issues = []

    if not code.strip():
        return ["Code is empty"]

    lines = code.split("\n")
    non_blank = [l.strip() for l in lines if l.strip()]

    # Brace balance
    opens  = code.count("{")
    closes = code.count("}")
    if opens != closes:
        issues.append(f"Unbalanced braces: {opens} open vs {closes} close")

    # main() present?
    has_main = any(re.search(r'\bmain\s*\(', l) for l in lines)

    if has_main:
        # return 0 in main
        if "return 0" not in code and "return 1" not in code:
            issues.append("main() should have 'return 0;'")

    # iostream required for cout/cin
    uses_cout = "cout" in code or "cin" in code or "endl" in code
    has_iostream = "#include <iostream>" in code or '#include<iostream>' in code
    if uses_cout and not has_iostream:
        issues.append("Uses cout/cin/endl but missing #include <iostream>")

    # string required for std::string
    uses_string_type = bool(re.search(r'\bstring\b', code))
    has_string_include = "#include <string>" in code
    if uses_string_type and not has_string_include and not has_iostream:
        issues.append("Uses string but missing #include <string>")

    # semicolon after every non-preprocessor, non-brace, non-comment line
    # (light heuristic only)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("//", "#", "/*", "*")):
            continue
        if stripped.endswith(("{", "}", ",", ";", ":", "\\")):
            continue
        if re.match(r'^(if|else|for|while|do|switch|class|struct|namespace|public|private|protected)', stripped):
            continue
        if stripped.endswith(")") and re.search(r'\bvoid\b|\bint\b|\bfloat\b|\bbool\b', stripped):
            continue  # function declaration line
        # flag lines that look like statements without semicolons
        if len(stripped) > 3 and not stripped.endswith((")", ">", "]")):
            if re.search(r'[a-zA-Z0-9_\)]\s*$', stripped) and "=" in stripped:
                issues.append(f"Line {i+1} may be missing semicolon: {stripped[:50]}")

    return issues


def check_python(code: str) -> list[str]:
    issues = []
    if not code.strip():
        return ["Code is empty"]
    # Check for mismatched quotes (simple)
    sq = code.count("'") - code.count("\\'")
    dq = code.count('"') - code.count('\\"')
    if sq % 2 != 0:
        issues.append("Possibly unmatched single quotes")
    if dq % 2 != 0:
        issues.append("Possibly unmatched double quotes")
    # Indentation check (tabs vs spaces mix)
    tab_lines = sum(1 for l in code.split("\n") if l.startswith("\t"))
    space_lines = sum(1 for l in code.split("\n") if l.startswith("    "))
    if tab_lines > 0 and space_lines > 0:
        issues.append("Mixed tabs and spaces — will cause IndentationError")
    return issues


def validate_code_example(code: str, language: str = "cpp") -> list[str]:
    """Return list of issues. Empty = code looks OK."""
    lang = language.lower().replace("+", "p")
    if lang in ("cpp", "cplusplus", "c"):
        return check_cpp(code)
    elif lang == "python":
        return check_python(code)
    return []

# alias used by CodeAgent and import checks
validate_code = validate_code_example
