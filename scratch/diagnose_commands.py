import os
import ast
import pprint

path = 'core/nlp/commands.py'
with open(path, 'rb') as f:
    content = f.read().decode('utf-8', 'ignore')

# We know the file is broken. Let's try to extract the COMMAND_PATTERNS assignment.
# It seems it's one giant line.

lines = content.splitlines()
new_lines = []
for i, line in enumerate(lines):
    if 'COMMAND_PATTERNS = [' in line:
        # If it's a giant line, it might contain the whole list.
        # But wait, if it's a SyntaxError, ast.parse will fail.
        new_lines.append(line)
    else:
        new_lines.append(line)

# Let's try to find where the unterminated string is.
# I'll use a more advanced check.
def find_unterminated_string(content):
    import tokenize
    from io import BytesIO
    try:
        tokens = tokenize.tokenize(BytesIO(content.encode('utf-8')).readline)
        for token in tokens:
            pass
    except tokenize.TokenError as e:
        print(f"TokenError: {e}")

find_unterminated_string(content)
