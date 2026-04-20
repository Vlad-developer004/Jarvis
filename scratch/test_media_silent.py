import sys
import os

# Add project root to sys.path
sys.path.append(r'c:\Users\tanja\OneDrive\Desktop\projects\Jarvis')

from actions.system_parts.media import send_play_pause_to_video

print("Testing send_play_pause_to_video(prefer='browser')...")
try:
    res = send_play_pause_to_video(prefer='browser')
    print(f"Result: {res}")
except Exception as e:
    print(f"Error: {e}")

print("\nTesting send_play_pause_to_video(prefer='youtube')...")
try:
    res = send_play_pause_to_video(prefer='youtube')
    print(f"Result: {res}")
except Exception as e:
    print(f"Error: {e}")
