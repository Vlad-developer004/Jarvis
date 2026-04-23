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
    print(f"Unterminated {quote_char} starting at position {last_quote_pos}")
    print(f"Context before: {repr(content[last_quote_pos-50:last_quote_pos])}")
    print(f"Context after: {repr(content[last_quote_pos:last_quote_pos+50])}")
else:
    print("No unterminated quotes.")
