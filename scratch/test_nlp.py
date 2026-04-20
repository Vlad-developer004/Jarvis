import sys
import os

# Add project root to sys.path
sys.path.append(r'c:\Users\tanja\OneDrive\Desktop\projects\Jarvis')

from core.nlp.commands import match_command

test_cases = [
    ("джарвис стоп в браузере", "media_pause_browser"),
    ("выключи джарвис", "jarvis_exit"),
    ("три", ""),
    ("два", ""),
    ("один", ""),
    ("открой третье сохранённое видео", "open_saved"),
    ("джарвис останови видео", "stop_video"),
]

print("--- Testing Command Matching ---")
failed = False
for text, expected in test_cases:
    cmd = match_command(text)
    status = "✅" if cmd == expected else "❌"
    print(f"{status} Text: '{text:30}' -> Result: '{cmd:20}' (Expected: '{expected}')")
    if cmd != expected:
        failed = True

if not failed:
    print("\nALL TESTS PASSED! Numbers are no longer greedy.")
else:
    print("\nSOME TESTS FAILED.")
