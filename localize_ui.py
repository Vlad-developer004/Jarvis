#!/usr/bin/env python3
"""
Automated UI localization helper.
Finds hardcoded Russian strings in ui/ folder and helps localize them.
"""
import os
import re
import json
from pathlib import Path
from collections import defaultdict

SKIP_PATTERNS = [
    r'#.*[А-Яа-я]',  # Comments
    r"'''.*'''",      # Docstrings
    r'""".*"""',      # Docstrings
    r'\*\*.*\*\*',    # Formatting
    r'\.format\(',    # Format placeholders
]

def extract_russian_strings(file_path: str) -> list[tuple[str, int, str]]:
    """Extract Russian strings from Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except:
        return []

    results = []
    for i, line in enumerate(lines, 1):
        # Skip comments and docstrings
        if line.strip().startswith('#'):
            continue

        # Find all quoted strings with Russian text
        matches = re.finditer(r"['\"]([А-Яа-яЁё\s\-\(\)\«\»\.\,\!\?\:\;\/]+)['\"]", line)
        for match in matches:
            text = match.group(1)
            if len(text) > 2 and not any(re.match(p, text) for p in SKIP_PATTERNS):
                results.append((text, i, file_path))

    return results

def find_all_russian_strings() -> dict[str, list]:
    """Find all Russian strings in ui/ folder."""
    ui_dir = Path('ui')
    strings_by_file = defaultdict(list)

    for py_file in ui_dir.rglob('*.py'):
        strings = extract_russian_strings(str(py_file))
        if strings:
            rel_path = str(py_file.relative_to(ui_dir))
            strings_by_file[rel_path] = strings

    return strings_by_file

def generate_localization_key(text: str, context: str = '') -> str:
    """Generate a localization key from Russian text."""
    # Remove special characters and convert to lowercase
    key = text.lower().strip()
    key = re.sub(r'[^а-яё0-9_\s]', '', key)  # Remove non-cyrillic except space/underscore
    key = re.sub(r'\s+', '_', key)[:30]  # Replace spaces with underscore, limit length
    return f"ui.{context}.{key}" if context else f"ui.{key}"

if __name__ == '__main__':
    strings = find_all_russian_strings()

    print(f"Found Russian strings in {len(strings)} files:\n")

    for file_path, string_list in sorted(strings.items()):
        print(f"\n{file_path} ({len(string_list)} strings):")
        for text, line, _ in string_list[:5]:  # Show first 5
            key = generate_localization_key(text, file_path.split('/')[0])
            print(f"  Line {line}: '{text}' -> {key}")

        if len(string_list) > 5:
            print(f"  ... and {len(string_list) - 5} more")

    # Summary
    total = sum(len(v) for v in strings.values())
    print(f"\n\nTotal: {total} Russian strings found in {len(strings)} files")
    print("\nRecommendation: Use automated replacement with i18n.tr() for all strings.")
