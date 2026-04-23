import os
import re

path = 'core/nlp/commands.py'
with open(path, 'rb') as f:
    content = f.read().decode('utf-8', 'ignore')

# Fix missing quotes for min_score
# It should be 'min_score'
new_content = re.sub(r"(?<!')min_score'", "'min_score'", content)

if new_content != content:
    with open(path, 'wb') as f:
        f.write(new_content.encode('utf-8'))
    print("Fixed missing quotes for min_score")
else:
    print("No missing quotes for min_score found")
