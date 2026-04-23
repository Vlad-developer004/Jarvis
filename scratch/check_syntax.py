import os
import traceback

path = 'core/nlp/commands.py'
with open(path, 'rb') as f:
    content = f.read().decode('utf-8', 'ignore')

try:
    compile(content, path, 'exec')
    print("Compiled successfully!")
except SyntaxError as e:
    print(f"SyntaxError: {e}")
    print(f"At line {e.lineno}, offset {e.offset}")
    if e.text:
        print(f"Line content: {repr(e.text)}")
except Exception as e:
    print(f"Error: {e}")
