import os

path = 'core/nlp/commands.py'
with open(path, 'rb') as f:
    lines = f.readlines()

giant_line = lines[341].decode('utf-8', 'ignore')

# Scan for unbalanced quotes in dicts
in_quote = False
quote_char = None
last_quote_pos = -1

for i, char in enumerate(giant_line):
    if char == "'" and (i == 0 or giant_line[i-1] != "\\"):
        if not in_quote:
            in_quote = True
            quote_char = "'"
            last_quote_pos = i
        elif quote_char == "'":
            in_quote = False
            quote_char = None
    elif char == '"' and (i == 0 or giant_line[i-1] != "\\"):
        if not in_quote:
            in_quote = True
            quote_char = '"'
            last_quote_pos = i
        elif quote_char == '"':
            in_quote = False
            quote_char = None

if in_quote:
    print(f"Unterminated quote starting at position {last_quote_pos}")
    start = max(0, last_quote_pos - 50)
    end = min(len(giant_line), last_quote_pos + 50)
    print(f"Context: {giant_line[start:end]}")
else:
    print("No unterminated quote found in single-pass (maybe it's more complex)")
