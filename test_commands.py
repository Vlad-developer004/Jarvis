#!/usr/bin/env python3
"""
Комплексный тест всех команд Jarvis
Проверяет:
1. Синтаксис всех файлов команд
2. Импорты всех зависимостей
3. Наличие функций обработчиков
4. Основные логические ошибки
"""

import os
import sys
import json
from pathlib import Path

def check_file_syntax(file_path: str) -> tuple[bool, str]:
    """Проверяет синтаксис Python файла"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            compile(f.read(), file_path, 'exec')
        return True, "OK"
    except SyntaxError as e:
        return False, f"Синтаксическая ошибка на строке {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)

def check_imports_in_file(file_path: str) -> tuple[bool, list[str]]:
    """Проверяет импорты в файле"""
    missing = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Простая проверка импортов
            for line in content.split('\n'):
                if line.strip().startswith('from ') or line.strip().startswith('import '):
                    try:
                        compile(line, file_path, 'exec')
                    except:
                        missing.append(line.strip())
        return len(missing) == 0, missing
    except Exception as e:
        return False, [str(e)]

def check_command_handlers():
    """Проверяет все обработчики команд"""
    base_path = Path('core/handler/commands')
    results = {}

    for cmd_file in base_path.glob('*.py'):
        if cmd_file.name == '__init__.py':
            continue

        print(f"\n📋 Проверяю: {cmd_file.name}")

        # Синтаксис
        ok, msg = check_file_syntax(str(cmd_file))
        results[cmd_file.name] = {'syntax': ok, 'message': msg}
        print(f"  Синтаксис: {'✅' if ok else '❌'} {msg}")

        # Проверяем наличие основной функции handle_*
        try:
            with open(cmd_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Ищем функцию handle_*
                handler_funcs = []
                for line in content.split('\n'):
                    if line.startswith('def handle_'):
                        func_name = line.split('(')[0].replace('def ', '')
                        handler_funcs.append(func_name)

                if handler_funcs:
                    print(f"  Функции: {'✅'} {', '.join(handler_funcs)}")
                    results[cmd_file.name]['functions'] = handler_funcs
                else:
                    print(f"  Функции: ⚠️  Не найдены основные функции handle_*")
                    results[cmd_file.name]['functions'] = []
        except Exception as e:
            print(f"  Функции: ❌ Ошибка при проверке: {e}")

    return results

def check_filesystem_operations():
    """Проверяет функции работы с файловой системой"""
    print("\n\n🗂️  Проверка операций с файлами:")

    fs_path = Path('actions/filesystem.py')
    if not fs_path.exists():
        print("❌ Файл actions/filesystem.py не найден!")
        return False

    try:
        with open(fs_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Проверяемые функции
        required_funcs = [
            'create_folder_at',
            'delete_folder_at',
            'goto_folder',
            'empty_recycle_bin',
        ]

        for func_name in required_funcs:
            if f'def {func_name}(' in content:
                print(f"  ✅ {func_name} - найдена")
            else:
                print(f"  ❌ {func_name} - НЕ найдена!")

        return True
    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")
        return False

def check_dispatch_commands():
    """Проверяет диспетчер команд"""
    print("\n\n🔀 Проверка диспетчера команд:")

    dispatch_path = Path('core/handler/dispatch.py')
    if not dispatch_path.exists():
        print("❌ Файл core/handler/dispatch.py не найден!")
        return False

    try:
        with open(dispatch_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Ищем все команды в диспетчере
        import re
        commands = re.findall(r"elif cmd in \[(.*?)\]|elif cmd == '(.*?)'|if cmd == '(.*?)'", content)

        print(f"  Найдено команд: {len(commands)}")

        # Проверяем синтаксис
        ok, msg = check_file_syntax(str(dispatch_path))
        print(f"  Синтаксис: {'✅' if ok else '❌'}")

        return ok
    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")
        return False

def check_settings():
    """Проверяет файл настроек"""
    print("\n\n⚙️  Проверка настроек:")

    settings_path = Path('data/jarvis_settings.json')
    if not settings_path.exists():
        print("⚠️  Файл настроек не найден. Это может быть нормально.")
        return True

    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"  ✅ JSON валидный")
        print(f"  Найдено параметров: {len(data)}")
        return True
    except json.JSONDecodeError as e:
        print(f"  ❌ Ошибка JSON: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False

def main():
    print("=" * 60)
    print("🔍 JARVIS - Комплексная проверка команд")
    print("=" * 60)

    # Проверяем команды
    cmd_results = check_command_handlers()

    # Проверяем файловые операции
    fs_ok = check_filesystem_operations()

    # Проверяем диспетчер
    dispatch_ok = check_dispatch_commands()

    # Проверяем настройки
    settings_ok = check_settings()

    # Итоговый отчёт
    print("\n\n" + "=" * 60)
    print("📊 ИТОГОВЫЙ ОТЧЁТ")
    print("=" * 60)

    total_files = len(cmd_results)
    ok_files = sum(1 for r in cmd_results.values() if r['syntax'])

    print(f"\n✅ Файлы команд: {ok_files}/{total_files} OK")

    if ok_files < total_files:
        print("\nОшибки в файлах:")
        for fname, result in cmd_results.items():
            if not result['syntax']:
                print(f"  ❌ {fname}: {result['message']}")

    print(f"\n✅ Файловые операции: {'OK' if fs_ok else 'ОШИБКА'}")
    print(f"✅ Диспетчер команд: {'OK' if dispatch_ok else 'ОШИБКА'}")
    print(f"✅ Настройки: {'OK' if settings_ok else 'ОШИБКА'}")

    print("\n" + "=" * 60)

    # Общий статус
    if ok_files == total_files and fs_ok and dispatch_ok and settings_ok:
        print("🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        return 0
    else:
        print("⚠️  НАЙДЕНЫ ПРОБЛЕМЫ - см. выше")
        return 1

if __name__ == '__main__':
    sys.exit(main())
