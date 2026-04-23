import os

path = 'core/nlp/commands.py'
with open(path, 'rb') as f:
    lines = f.readlines()

giant_line = lines[341].decode('utf-8', 'ignore')

# Count quotes
sq = 0
dq = 0
for i, char in enumerate(giant_line):
    if char == "'" and (i == 0 or giant_line[i-1] != "\\"):
        sq += 1
    elif char == '"' and (i == 0 or giant_line[i-1] != "\\"):
        dq += 1

print(f"Single quotes: {sq}")
print(f"Double quotes: {dq}")

# Find where it breaks
# I'll try to scan for dict keys/values
import re
# Look for something like 'key': 'value or 'key': ['value
# and see if there's a missing closing quote.

# Actually, I'll just print the last 500 characters of that line
print("END OF LINE:")
print(repr(giant_line[-500:]))
