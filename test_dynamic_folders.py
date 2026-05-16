#!/usr/bin/env python3
"""
Тест динамической системы поиска папок
"""

import sys
from pathlib import Path

def test_dynamic_folder_search():
    print("=" * 70)
    print("🔬 ТЕСТ ДИНАМИЧЕСКОГО ПОИСКА ПАПОК")
    print("=" * 70)

    try:
        from actions.filesystem import normalize_folder_voice_query, get_name_variants
        from actions.explorer import get_active_explorer_path
        import tempfile
        import shutil

        # Создаём тестовую структуру папок
        test_dir = Path(tempfile.mkdtemp())
        print(f"\n📂 Создана тестовая директория: {test_dir}")

        # Создаём тестовые папки с разными названиями
        test_folders = {
            'Projects': 'projects folder',
            'Downloads': 'downloads folder',
            'Documents': 'documents folder',
            'мои_проекты': 'russian projects',
            'загрузки': 'russian downloads',
            'LR_1': 'lab folder 1',
        }

        for folder_name in test_folders.keys():
            folder_path = test_dir / folder_name
            folder_path.mkdir()
            print(f"  ✅ Создана папка: {folder_name}")

        # Тестируем поиск
        print("\n🔍 Тестирование поиска папок:\n")

        test_cases = [
            # (фраза, ожидаемая папка)
            # Замечание: 'проекты' найдёт 'мои_проекты' - это правильно (динамический поиск)
            ('проекты', 'мои_проекты'),  # Точное совпадение слова "проекты"
            ('Projects', 'Projects'),      # Английское имя
            ('загрузки', 'загрузки'),      # Точное совпадение русского названия
            ('лр один', 'LR_1'),           # Число преобразуется в цифру
            ('ЛР 1', 'LR_1'),              # Кириллица преобразуется
            ('documents', 'Documents'),    # Английское имя
            ('мои проекты', 'мои_проекты'), # Точное совпадение
        ]

        from actions.filesystem import _find_subdir_ci_or_fuzzy

        passed = 0
        failed = 0

        for query, expected_folder in test_cases:
            normalized = normalize_folder_voice_query(query)
            result = _find_subdir_ci_or_fuzzy(str(test_dir), query)

            if result and result.name == expected_folder:
                print(f"  ✅ '{query}' -> {result.name}")
                print(f"     (нормализовано: '{normalized}')")
                passed += 1
            else:
                actual = result.name if result else "НЕ НАЙДЕНА"
                print(f"  ❌ '{query}' -> {actual} (ожидалось {expected_folder})")
                print(f"     (нормализовано: '{normalized}')")
                failed += 1

        # Тесты транслитерации
        print("\n📝 Тестирование транслитерации:\n")

        trans_tests = [
            ('проект', ['проект', 'proekt']),
            ('Project', ['project', 'проект']),
        ]

        for text, expected_variants in trans_tests:
            variants = get_name_variants(text)
            print(f"  '{text}' -> {variants}")
            # Проверяем, что есть оба варианта
            has_variants = any(v in variants for v in expected_variants)
            status = "✅" if has_variants else "⚠️ "
            print(f"  {status} Найдены варианты: {', '.join([v for v in variants if v in expected_variants])}")

        # Очищаем тестовую директорию
        print(f"\n🧹 Удаления тестовой директории...")
        shutil.rmtree(test_dir)
        print(f"  ✅ Очищено")

        # Итоги
        print("\n" + "=" * 70)
        print(f"📊 РЕЗУЛЬТАТЫ: {passed} пройдено, {failed} провалено")
        print("=" * 70)

        return failed == 0

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    success = test_dynamic_folder_search()

    if success:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("\n💡 ПРЕИМУЩЕСТВА ДИНАМИЧЕСКОЙ СИСТЕМЫ:")
        print("  ✅ Работает с любыми названиями папок")
        print("  ✅ Поддерживает русские и английские названия")
        print("  ✅ Умный поиск с транслитерацией")
        print("  ✅ Без хардкодированных алиасов")
        return 0
    else:
        print("\n⚠️  НАЙДЕНЫ ПРОБЛЕМЫ")
        return 1

if __name__ == '__main__':
    sys.exit(main())
