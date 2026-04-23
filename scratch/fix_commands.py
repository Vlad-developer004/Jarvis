import os
path = 'core/nlp/commands.py'
with open(path, 'rb') as f:
    content = f.read().decode('utf-8', 'ignore')

old_line = "'тупой тыCOMMAND_PATTERNS = ["
new_line = "'тупой ты': _INSULT,\n})\nCOMMAND_PATTERNS = ["

if old_line in content:
    content = content.replace(old_line, new_line)
    with open(path, 'wb') as f:
        f.write(content.encode('utf-8'))
    print("Fixed successfully")
else:
    print("Target line not found")
