import sys
import os
from pathlib import Path

# Add project root to sys.path
root = r'c:\Users\tanja\OneDrive\Desktop\projects\Jarvis'
if root not in sys.path:
    sys.path.insert(0, root)

from core.system.windows import get_known_folder_path
from actions.filesystem import get_name_variants, calculate_match_score

print(f"Desktop Path: {get_known_folder_path('desktop')}")

# Test phonetic matching
query = "универ"
actual = "Універ"
variants_q = get_name_variants(query)
variants_a = get_name_variants(actual)

print(f"Query variants ({query}): {variants_q}")
print(f"Actual variants ({actual}): {variants_a}")

match = any(q == a for q in variants_q for a in variants_a)
print(f"Exact variant match: {match}")

score = calculate_match_score(query, actual)
print(f"Match score (rapidfuzz): {score}")
