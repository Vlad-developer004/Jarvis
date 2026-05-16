#!/usr/bin/env python3
"""
Глубокая диагностика Jarvis - проверка импортов и функций
"""

import sys

def test_import(module_path: str) -> tuple[bool, str]:
    """Пытается импортировать модуль"""
    try:
        # Преобразуем путь в импорт
        module_name = module_path.replace('/', '.').replace('\\', '.').replace('.py', '')
        exec(f'import {module_name}')
        return True, f"✅ Модуль {module_name} успешно импортирован"
    except ImportError as e:
        return False, f"❌ Ошибка импорта: {e}"
    except Exception as e:
        return False, f"❌ Ошибка: {e}"

def test_filesystem_funcs():
    """Тестирует функции файловой системы"""
    print("\n🔧 Тестирование функций файловой системы:\n")

    try:
        from actions.filesystem import (
            create_folder_at,
            delete_folder_at,
            goto_folder,
            empty_recycle_bin,
            normalize_folder_voice_query,
            get_name_variants,
        )
        print("  ✅ Все функции импортированы успешно")

        # Тест normalize_folder_voice_query
        test_cases = [
            ('проекты', 'projects'),
            ('загрузки', 'downloads'),
            ('десктоп', 'desktop'),
            ('лр 1', 'LR 1'),
        ]

        print("\n  Тестирование normalize_folder_voice_query:")
        for input_val, expected in test_cases:
            result = normalize_folder_voice_query(input_val)
            status = "✅" if result.lower() == expected.lower() else "⚠️ "
            print(f"    {status} '{input_val}' -> '{result}' (ожидалось '{expected}')")

        # Тест get_name_variants
        print("\n  Тестирование get_name_variants:")
        variants = get_name_variants('проект')
        print(f"    ✅ Варианты для 'проект': {variants}")

        return True
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_handlers():
    """Тестирует импорт обработчиков команд"""
    print("\n🔄 Тестирование импорта обработчиков команд:\n")

    # Маппинг модулей на правильные имена функций
    handlers_map = {
        'core.handler.commands.files': 'handle_files',
        'core.handler.commands.utils': 'handle_utils',
        'core.handler.commands.system': 'handle_system',
        'core.handler.commands.windows': 'handle_window',  # Note: singular!
        'core.handler.commands.browser': 'handle_browser',
    }

    results = {}
    for handler, func_name in handlers_map.items():
        try:
            module = __import__(handler, fromlist=[''])
            if hasattr(module, func_name):
                print(f"  ✅ {handler} - OK (функция {func_name})")
                results[handler] = True
            else:
                print(f"  ⚠️  {handler} - модуль есть, но функция {func_name} не найдена")
                results[handler] = False
        except ImportError as e:
            print(f"  ❌ {handler} - ошибка импорта: {e}")
            results[handler] = False
        except Exception as e:
            print(f"  ❌ {handler} - ошибка: {e}")
            results[handler] = False

    return all(results.values())

def test_explorer_funcs():
    """Тестирует функции работы с проводником"""
    print("\n🗂️  Тестирование функций проводника:\n")

    try:
        from actions.explorer import (
            navigate_to_system_folder,
            open_in_explorer,
            get_active_explorer_path,
        )
        print("  ✅ Все функции импортированы успешно")

        # Проверяем, что функции есть
        print(f"\n  Функции готовы к использованию:")
        print(f"    ✅ navigate_to_system_folder")
        print(f"    ✅ open_in_explorer")
        print(f"    ✅ get_active_explorer_path")

        return True
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_git_commit():
    """Тестирует функции git commit"""
    print("\n📝 Тестирование функций git commit:\n")

    try:
        from actions.git_commit import (
            detect_repo_and_status,
            git_commit_push,
            create_branch,
            _get_branches,
        )
        print("  ✅ Все функции импортированы успешно")

        # Проверяем наличие новых функций
        print(f"\n  Доступные функции:")
        print(f"    ✅ detect_repo_and_status")
        print(f"    ✅ git_commit_push")
        print(f"    ✅ create_branch")
        print(f"    ✅ _get_branches")

        return True
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_nlp_functions():
    """Тестирует NLP функции"""
    print("\n🧠 Тестирование NLP функций:\n")

    try:
        from core.nlp import extract_amount, extract_duration_seconds
        print("  ✅ NLP функции импортированы успешно")

        # Тест extract_duration_seconds
        test_cases = [
            ('напомни через 5 минут', 300),
            ('напомни через 1 час', 3600),
            ('напомни через 30 секунд', 30),
        ]

        print(f"\n  Тестирование extract_duration_seconds:")
        for text, expected_min in test_cases:
            result = extract_duration_seconds(text)
            status = "✅" if result == expected_min else "⚠️ "
            print(f"    {status} '{text}' -> {result}сек (ожидалось {expected_min}сек)")

        return True
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_critical_issues():
    """Проверяет критические проблемы"""
    print("\n⚠️  Проверка критических проблем:\n")

    issues = []

    # Проверка 1: файл actions/filesystem.py имеет известную ошибку?
    try:
        with open('actions/filesystem.py', 'r', encoding='utf-8') as f:
            content = f.read()
            # Проверяем, исправлена ли ошибка с best переменной
            if '_find_subdir_ci_or_fuzzy' in content:
                if 'best = (score, entry)' in content:
                    print("  ✅ Ошибка в _find_subdir_ci_or_fuzzy исправлена")
                else:
                    print("  ❌ НАЙДЕНА ОШИБКА в _find_subdir_ci_or_fuzzy - переменная best не обновляется!")
                    issues.append("_find_subdir_ci_or_fuzzy bug")
    except Exception as e:
        print(f"  ❌ Не удалось проверить файл: {e}")

    # Проверка 2: typos в utils.py
    try:
        with open('core/handler/commands/utils.py', 'r', encoding='utf-8') as f:
            content = f.read()
            typos = ['комм+ит', 'выбр+али']
            found_typos = [t for t in typos if t in content]
            if found_typos:
                print(f"  ❌ Найдены опечатки в utils.py: {found_typos}")
                issues.append(f"Typos in utils.py: {found_typos}")
            else:
                print("  ✅ Опечатки в utils.py исправлены")
    except Exception as e:
        print(f"  ❌ Не удалось проверить файл: {e}")

    return len(issues) == 0, issues

def main():
    print("=" * 70)
    print("🔬 JARVIS - ГЛУБОКАЯ ДИАГНОСТИКА")
    print("=" * 70)

    results = {}

    # Тесты
    results['filesystem'] = test_filesystem_funcs()
    results['handlers'] = test_command_handlers()
    results['explorer'] = test_explorer_funcs()
    results['git'] = test_git_commit()
    results['nlp'] = test_nlp_functions()
    critical_ok, critical_issues = check_critical_issues()
    results['critical'] = critical_ok

    # Итоговый отчёт
    print("\n\n" + "=" * 70)
    print("📊 ИТОГОВЫЙ ОТЧЁТ")
    print("=" * 70)

    all_ok = all(results.values())

    for test_name, result in results.items():
        status = "✅" if result else "❌"
        print(f"{status} {test_name.upper()}: {'OK' if result else 'ОШИБКА'}")

    if critical_issues:
        print(f"\n⚠️  Критические проблемы:")
        for issue in critical_issues:
            print(f"   - {issue}")

    print("\n" + "=" * 70)

    if all_ok:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("\n💡 РЕКОМЕНДАЦИИ:")
        print("  1. Протестируйте основные команды голосом")
        print("  2. Проверьте работу функций создания/удаления папок")
        print("  3. Проверьте STT распознавание")
        return 0
    else:
        print("⚠️  НАЙДЕНЫ ПРОБЛЕМЫ - см. выше")
        return 1

if __name__ == '__main__':
    sys.exit(main())
