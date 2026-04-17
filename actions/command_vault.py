import os
import json
import time
import pyautogui
import pyperclip
COMMANDS_FILE = 'data/commands_vault.json'
def _ensure_data_dir():
    os.makedirs(os.path.dirname(COMMANDS_FILE), exist_ok=True)
    if not os.path.exists(COMMANDS_FILE):
        with open(COMMANDS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
def _load_commands():
    _ensure_data_dir()
    try:
        with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}
def _save_commands(data):
    _ensure_data_dir()
    with open(COMMANDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
def save_command(command_name):
    pyperclip.copy('')
    time.sleep(0.1)
    pyautogui.keyDown('ctrl')
    pyautogui.press('insert')
    pyautogui.keyUp('ctrl')
    time.sleep(0.3)
    text = pyperclip.paste().strip()
    if not text:
        return False
    commands = _load_commands()
    clean_name = command_name.replace('команду', '').strip()
    if not clean_name:
        clean_name = 'default_cmd'
    commands[clean_name] = text
    _save_commands(commands)
    return True
def get_command(command_name):
    commands = _load_commands()
    clean_name = command_name.replace('команду', '').strip()
    if not clean_name:
        clean_name = 'default_cmd'
    if clean_name in commands:
        text = commands[clean_name]
        pyperclip.copy(text)
        time.sleep(0.2)
        pyautogui.keyDown('shift')
        pyautogui.press('insert')
        pyautogui.keyUp('shift')
        return True
    return False
def delete_command(command_name):
    commands = _load_commands()
    clean_name = command_name.replace('команду', '').strip()
    if clean_name in commands:
        del commands[clean_name]
        _save_commands(commands)
        return True
    return False
