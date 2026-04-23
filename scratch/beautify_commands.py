import os
import ast
import pprint
import re
import traceback

path = 'core/nlp/commands.py'
with open(path, 'rb') as f:
    content = f.read().decode('utf-8', 'ignore')

# We'll try to find the start and end of COMMAND_PATTERNS
try:
    # Use a simpler way: find the start and try to find the end by matching brackets
    start_marker = 'COMMAND_PATTERNS = ['
    start_idx = content.find(start_marker)
    if start_idx == -1:
        print("Could not find start of COMMAND_PATTERNS")
        exit(1)
    
    # Extract the list part
    list_start = start_idx + len(start_marker) - 1
    bracket_count = 0
    end_idx = -1
    for i in range(list_start, len(content)):
        if content[i] == '[':
            bracket_count += 1
        elif content[i] == ']':
            bracket_count -= 1
            if bracket_count == 0:
                end_idx = i + 1
                break
    
    if end_idx == -1:
        # If it's not closed, let's find the last '}' and add ']'
        last_brace = content.rfind('}')
        if last_brace != -1:
            print("Found last brace, adding closing bracket")
            list_str = content[list_start:last_brace+1] + ']'
        else:
            print("Could not find any brace")
            exit(1)
    else:
        list_str = content[list_start:end_idx]

    # Try to parse and beautify the list
    try:
        patterns_list = ast.literal_eval(list_str)
        formatted_list = pprint.pformat(patterns_list, indent=4, width=120, sort_dicts=False)
        
        # Reconstruct the file
        before = content[:start_idx]
        after = content[end_idx:] if end_idx != -1 else ""
        # Find next valid code in 'after' (e.g. skip the rest of the giant line if it was corrupted)
        # Usually after COMMAND_PATTERNS comes _NEGATIVE_KEYWORDS or functions.
        # But wait, if it was a giant line, the corrupt part might be AFTER the list.
        
        # Let's find the next function or variable
        next_code = re.search(r'\n\w+\s*=', content[start_idx+len(list_str):])
        if next_code:
            after = content[start_idx+len(list_str) + next_code.start():]
        else:
            # Maybe it's _ALL_PATTERN_STRINGS
            next_code = content.find('_ALL_PATTERN_STRINGS = []')
            if next_code != -1:
                after = content[next_code:]

        new_content = before + "COMMAND_PATTERNS = " + formatted_list + "\n\n" + after
        
        with open(path, 'wb') as f:
            f.write(new_content.encode('utf-8'))
        print("Beautified successfully!")
    except Exception as e:
        print(f"Error parsing list: {e}")
        # If literal_eval fails, it's likely because of the unterminated string.
        # Let's try to fix the unterminated string in the raw string.
        print("Trying to fix unterminated string manually...")
        # Search for any ' followed by space or comma or bracket but NO closing '
        # This is hard.
        exit(1)

except Exception as e:
    print(f"General error: {e}")
    traceback.print_exc()
