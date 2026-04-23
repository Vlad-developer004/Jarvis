import os
import re

def check_file(path):
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        # Very simple check for unclosed single quotes on a single line
        # This doesn't handle multi-line strings, but Jarvis usually doesn't use them here.
        # It also doesn't handle escaped quotes, but we'll see.
        quotes = line.count("'")
        if quotes % 2 != 0:
            print(f"Line {i+1} has odd number of quotes ({quotes}): {line.strip()}")

check_file('core/nlp/commands.py')
