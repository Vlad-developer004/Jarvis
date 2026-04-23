import os
path = 'core/nlp/commands.py'
with open(path, 'rb') as f:
    content = f.read().decode('utf-8', 'ignore')

# The log showed: 'ты тупой': _INSULT, 'тупой тыCOMMAND_PATTERNS = [
# It seems there's a missing quote and colon.

import re
# Look for 'тупой ты' followed by COMMAND_PATTERNS or just the end of line
# because it's an unterminated string.
new_content = re.sub(r"'тупой тыCOMMAND_PATTERNS = \[", "'тупой ты': _INSULT,\n})\nCOMMAND_PATTERNS = [", content)

if new_content != content:
    with open(path, 'wb') as f:
        f.write(new_content.encode('utf-8'))
    print("Fixed successfully with regex")
else:
    # Try another way if exact match failed
    print("Regex match failed, trying fallback")
    # Maybe it's 'тупой ты' followed by more stuff
    if "'тупой тыCOMMAND_PATTERNS" in content:
        content = content.replace("'тупой тыCOMMAND_PATTERNS", "'тупой ты': _INSULT,\n})\nCOMMAND_PATTERNS")
        with open(path, 'wb') as f:
            f.write(content.encode('utf-8'))
        print("Fixed with fallback replace")
    else:
        print("Could not find the broken line")
