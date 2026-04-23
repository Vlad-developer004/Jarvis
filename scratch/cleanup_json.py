import json
from pathlib import Path

path = Path(r'c:\Users\tanja\OneDrive\Desktop\projects\Jarvis\data\game_profiles\euro_truck_simulator_2.json')
data = json.loads(path.read_text(encoding='utf-8'))

# Update bindings
if 'bindings' in data:
    b = data['bindings']
    if b.get('action') == 'MACRO': b['action'] = 'enter'
    if b.get('refuel') == 'MACRO': b['refuel'] = 'r'
    
    # Replace any remaining MACRO in bindings with empty string
    for k, v in b.items():
        if v == 'MACRO': b[k] = ''

# Recursive replace in spells
def clean_macro(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if v == 'MACRO':
                obj[k] = ''
            else:
                clean_macro(v)
    elif isinstance(obj, list):
        for item in obj:
            clean_macro(item)

clean_macro(data.get('spells', []))

path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
print("Cleanup complete.")
