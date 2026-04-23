import os

path = 'core/nlp/commands.py'
with open(path, 'rb') as f:
    content = f.read().decode('utf-8', 'ignore')

in_quote = False
quote_char = None
last_quote_pos = -1

for i, char in enumerate(content):
    if char == "'" and (i == 0 or content[i-1] != "\\"):
        if not in_quote:
            in_quote = True
            quote_char = "'"
            last_quote_pos = i
        elif quote_char == "'":
            in_quote = False
            quote_char = None
    elif char == '"' and (i == 0 or content[i-1] != "\\"):
        if not in_quote:
            in_quote = True
            quote_char = '"'
            last_quote_pos = i
        elif quote_char == '"':
            in_quote = False
            quote_char = None

if in_quote:
    # Find line and column
    lines = content[:last_quote_pos].splitlines()
    line_num = len(lines)
    col_num = last_quote_pos - sum(len(l) + 1 for l in lines[:-1]) if line_num > 1 else last_quote_pos
    
    print(f"Unterminated {quote_char} starting at line {line_num}, col {col_num} (pos {last_quote_pos})")
    start = max(0, last_quote_pos - 100)
    end = min(len(content), last_quote_pos + 100)
    print(f"Context: {repr(content[start:end])}")
else:
    print("No unterminated quotes found in the whole file.")
