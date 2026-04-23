import os
from actions.filesystem import empty_recycle_bin, create_folder_at, delete_folder_at, goto_folder
from actions.explorer import navigate_to_system_folder, get_active_explorer_path
def get_context_path(handler):
    from core.system.windows import get_foreground_process_exe, get_foreground_window_title, get_active_explorer_path, get_known_folder_path
    
    # 1. Check Active IDE / Work App first (Coding takes priority)
    exe_name = get_foreground_process_exe()
    if exe_name:
        exe_basename = os.path.basename(exe_name).lower()
        context_apps = handler._settings.get('context_apps', ['code.exe', 'pycharm64.exe', 'phpstorm64.exe', 'antigravity.exe'])
        if exe_basename in [a.lower() for a in context_apps]:
            title = get_foreground_window_title()
            if title:
                import re
                path_match = re.search(r'[a-zA-Z]:\\[^:<>|"?\r\n]+', title)
                if path_match:
                    p = path_match.group(0).strip()
                    if os.path.isdir(p): return p
                    if os.path.exists(p): return os.path.dirname(p)
                
                candidates = []
                proj_match = re.search(r'\[([^\]]+)\]', title)
                if proj_match:
                    candidates.append(proj_match.group(1))
                # Fallback for VS Code / Cursor (e.g. "Project - Folder - file.py")
                for part in title.split(' - '):
                    part = part.strip()
                    if part and len(part) > 2:
                        candidates.append(part)
                
                if candidates:
                    from core.system.windows import get_known_folder_path
                    search_roots = []
                    for k in ['desktop', 'documents', 'downloads']:
                        p = get_known_folder_path(k)
                        if p: search_roots.append(p)
                    
                    from actions.filesystem import _find_folder_anywhere
                    for c in candidates:
                        # Skip if it's very clearly a file extension (prevent searching 'main.py')
                        if '.' in c and len(c.split('.')[-1]) <= 4:
                            continue
                        found = _find_folder_anywhere(search_roots, c, max_depth=3)
                        if found and found.is_dir():
                            return str(found)

    # 2. Check Active Explorer Window
    ex_path = get_active_explorer_path(any_open=False)
    if ex_path and os.path.isdir(ex_path):
        return ex_path
    # 3. Final Fallback to Desktop
    from core.system.windows import get_known_folder_path
    return get_known_folder_path('desktop') or os.path.join(os.path.expanduser('~'), 'Desktop')
def handle_files(handler, cmd, text_lower):
    if cmd == 'empty_trash':
        if empty_recycle_bin()[0]: handler.play_response()
    elif cmd == 'create_folder':
        from core.handler.dispatch import parse_folder_name
        from ui.dialogs.name_dlg import ask_text
        name = parse_folder_name(text_lower, 'create').strip()
        base_path = get_context_path(handler)
        if not name:
            res = ask_text(
                title='ПАПКА — J.A.R.V.I.S.',
                header='⬡  СОЗДАТЬ ПАПКУ',
                ok_text='СОЗДАТЬ',
                cancel_text='ОТМЕНА',
                placeholder='Новая папка',
                hint_voice='Голосом: «создай» / «отмена»  ·  Enter / Esc',
                initial_path=base_path,
            )
            if isinstance(res, tuple):
                base_path, name = res
            else:
                name = res
        if not name:
            handler.speak('Отменено.')
            return
        if not os.path.exists(base_path):
            try: os.makedirs(base_path, exist_ok=True)
            except Exception as e:
                handler.speak(f"Ошибка доступа к пути: {e}")
                return
        ok, res = create_folder_at(base_path, name)
        if ok:
            handler.play_response('created')
        else:
            handler.speak(res)
    elif cmd == 'delete_folder':
        from core.handler.dispatch import parse_folder_name
        from ui.dialogs.name_dlg import ask_text
        name = parse_folder_name(text_lower, 'delete').strip()
        base_path = get_context_path(handler)
        if not name:
            res = ask_text(
                title='УДАЛЕНИЕ — J.A.R.V.I.S.',
                header='⬡  УДАЛИТЬ ПАПКУ',
                ok_text='УДАЛИТЬ',
                cancel_text='ОТМЕНА',
                placeholder='Название папки',
                hint_voice='Голосом: «удали» / «отмена»  ·  Enter / Esc',
                initial_path=base_path,
            )
            name = res[1] if isinstance(res, tuple) else res
        
        if not name:
            handler.speak('Отменено.')
            return
            
        ok, res_msg = delete_folder_at(base_path, name)
        if ok: handler.play_response('deleted')
        else: handler.speak(res_msg)
    elif cmd == 'delete_file':
        import re
        from ui.dialogs.name_dlg import ask_text
        from pathlib import Path
        from actions.filesystem import normalize_folder_voice_query, get_name_variants, calculate_match_score
        
        base_path = get_context_path(handler)
        
        query = re.sub(r'^(удали(ть)?|сотри(ть)?)\s+(файл|документ)\s*', '', text_lower).strip()
        if not query or query == text_lower:
            query = re.sub(r'^(удали(ть)?|сотри(ть)?)\s*', '', text_lower).strip()
        
        query = normalize_folder_voice_query(query)
            
        res = ask_text(
            title='УДАЛЕНИЕ — J.A.R.V.I.S.',
            header='⬡  УДАЛИТЬ ФАЙЛ',
            ok_text='УДАЛИТЬ',
            cancel_text='ОТМЕНА',
            placeholder='Имя файла (без расширения)',
            hint_voice='Голосом: «удали» / «отмена»  ·  Enter / Esc',
            initial_path=base_path,
            initial_value=query,
        )
        name = res[1] if isinstance(res, tuple) else res
        
        if not name:
            handler.speak('Отменено.')
            return
            
        base = Path(base_path)
        target = None
        if base.exists():
            # Exact match
            for f in base.iterdir():
                if f.is_file() and (f.name.lower() == name.lower() or f.stem.lower() == name.lower()):
                    target = f
                    break
            # Fuzzy match
            if not target:
                query_norm = normalize_folder_voice_query(name)
                query_vars = get_name_variants(query_norm)
                best_score, best_f = 0, None
                for f in base.iterdir():
                    if f.is_file():
                        ev = get_name_variants(f.stem)
                        ev.extend(get_name_variants(f.name))
                        if any(q == e for q in query_vars for e in ev):
                            target = f
                            break
                        for q in query_vars:
                            for e in ev:
                                s = calculate_match_score(q, e)
                                if s > best_score:
                                    best_score, best_f = s, f
                if not target and best_score >= 80:
                    target = best_f

        if not target:
            handler.speak('Файл не найден в текущей папке.')
            return
            
        try:
            target.unlink()
            handler.play_response('deleted')
        except Exception as e:
            handler.speak(f"Ошибка удаления: {e}")
            
    elif cmd == 'cd_folder':
        from core.handler.dispatch import parse_cd_name
        name = parse_cd_name(text_lower).strip()
        if not name:
            handler.speak('Скажите название папки.')
            return
        ok, res = goto_folder(get_context_path(handler), name)
        if ok:
            handler.play_response()
        else:
            handler.speak(res)
    elif cmd == 'explorer_goto':
        folder = text_lower.replace('зайди', '').replace('открой', '').replace('в', '').strip()
        if not folder:
            handler.speak('Скажите, куда зайти: например «зайди в папку проекты» или «зайди в загрузки».')
            return
        ok, res = navigate_to_system_folder(folder)
        if ok:
            handler.play_response()
        else:
            handler.speak(res)
    elif cmd == 'explorer_go_up':
        ok, res = navigate_to_system_folder('..')
        if ok: handler.play_response()
        else: handler.speak(res)
    elif cmd == 'create_word_doc':
        from pathlib import Path
        from actions.filesystem import resolve_folder_for_hint
        from actions.office_documents import CREATE_BY_KIND, open_file, sanitize_document_stem, create_plain_text_file
        _KNOWN_EXT = tuple(sorted(CREATE_BY_KIND.keys(), key=len, reverse=True))
        from core.handler.parse_create_file import parse_create_file_intent
        from ui.dialogs.name_dlg import ask_text
        intent = parse_create_file_intent(text_lower)
        ctx = get_context_path(handler)
        base_path, folder_warn = resolve_folder_for_hint(intent.get('folder_hint'), ctx)
        if folder_warn:
            handler.speak(folder_warn)
        kind = intent.get('kind')
        if not kind:
            from pathlib import Path as _Path
            bp = _Path(ctx).resolve()
            # Coding context check
            if (
                (bp / 'pyproject.toml').is_file()
                or (bp / 'setup.py').is_file()
                or (bp / 'package.json').is_file()
                or (bp / 'Cargo.toml').is_file()
                or any(bp.glob('*.py'))
            ):
                kind = 'py'
            else:
                # Office document context check
                if any(bp.glob('*.docx')) or any(bp.glob('*.xlsx')) or any(bp.glob('*.pptx')):
                    kind = 'docx' # Standard default for office-heavy folders
                else:
                    kind = None # Let the unified dialog handle it
        name = (intent.get('name_hint') or '').strip()
        if name:
            low = name.lower()
            for ext in _KNOWN_EXT:
                suf = f'.{ext}'
                if low.endswith(suf):
                    name = name[: -len(suf)].strip()
                    if ext in CREATE_BY_KIND:
                        kind = ext
                    break
        if not name or not kind:
            titles = {
                'docx': ('WORD — J.A.R.V.I.S.', '⬡  ИМЯ ДОКУМЕНТА (.docx)'),
                'xlsx': ('EXCEL — J.A.R.V.I.S.', '⬡  ИМЯ ТАБЛИЦЫ (.xlsx)'),
                'pptx': ('POWERPOINT — J.A.R.V.I.S.', '⬡  ИМЯ ПРЕЗЕНТАЦИИ (.pptx)'),
                'txt': ('ТЕКСТ — J.A.R.V.I.S.', '⬡  ИМЯ ФАЙЛА (.txt)'),
                'py': ('PYTHON — J.A.R.V.I.S.', '⬡  ИМЯ МОДУЛЯ (.py)'),
                'md': ('MARKDOWN — J.A.R.V.I.S.', '⬡  ИМЯ ФАЙЛА (.md)'),
            }
            tit, hdr = titles.get(
                kind or 'docx',
                ('ФАЙЛ — J.A.R.V.I.S.', f'⬡  ИМЯ ФАЙЛА (.{kind or "docx"})'),
            )
            try:
                res_vals = ask_text(
                    title=tit,
                    header=hdr,
                    ok_text='СОЗДАТЬ',
                    cancel_text='ОТМЕНА',
                    placeholder='',
                    initial_path=str(base_path),
                    show_extension_field=True,
                    default_extension=kind,
                )
                if isinstance(res_vals, tuple) and len(res_vals) == 3:
                    base_path_str, name, ext_pick = res_vals
                    base_path = Path(base_path_str)
                    ext_pick = (ext_pick or '').strip().lower().lstrip('.')
                    if ext_pick:
                        kind = ext_pick
                elif isinstance(res_vals, tuple):
                    base_path_str, name = res_vals[0], res_vals[1]
                    base_path = Path(base_path_str)
                else:
                    name = res_vals
            except Exception:
                name = None
        if not name:
            handler.speak('Отменено.')
            return
        suf = f'.{kind}'.lower()
        if name.lower().endswith(suf):
            name = name[: -len(suf)].strip()
        stem = sanitize_document_stem(name)
        if not stem:
            handler.speak('Некорректное имя.')
            return
        if not base_path.exists():
            try: base_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                handler.speak(f"Ошибка доступа: {e}")
                return
        target = str(base_path / f'{stem}.{kind}')
        
        # Use specific creator if available, otherwise default to plain empty file
        creator = CREATE_BY_KIND.get(kind, create_plain_text_file)
        ok, res = creator(target)
        if not ok:
            handler.speak(res)
            return
        o_ok, o_msg = open_file(res)
        if not o_ok:
            handler.speak(o_msg)
        handler.play_response('created')
    elif cmd.startswith('recent_'):
        from actions.recent import open_recent_file
        types_map = {
            'recent_doc': ('document', 0),
            'recent_doc_prev': ('document', 1),
            'recent_sheet': ('spreadsheet', 0),
            'recent_sheet_prev': ('spreadsheet', 1),
            'recent_pres': ('presentation', 0),
            'recent_pres_prev': ('presentation', 1),
            'recent_any': ('any', 0),
            'recent_any_prev': ('any', 1),
        }
        r_type, offset = types_map.get(cmd, ('any', 0))
        ok, res = open_recent_file(r_type, offset)
        if ok:
            handler.speak(res)
            handler.play_response()
        else:
            handler.speak(res)
    elif cmd in ('find_doc', 'find_sheet', 'find_file'):
        from actions.recent import search_and_open_file
        type_map = {'find_doc': 'document', 'find_sheet': 'spreadsheet', 'find_file': 'any'}
        file_type = type_map[cmd]
        query = text_lower
        for kw in ('найди документ', 'найди таблицу', 'найди файл', 'открой документ',
                   'открой таблицу', 'открой файл', 'найди', 'открой'):
            if query.startswith(kw):
                query = query[len(kw):].strip()
                break
        if not query:
            handler.speak("Укажите название файла.")
            return
        handler.speak(f"Ищу {query}...")
        import threading
        def _search():
            # For searching/opening, we don't restrict to subfolders
            ok, res = search_and_open_file(query, file_type)
            handler.speak(res)
            if ok: handler.play_response()
        threading.Thread(target=_search, daemon=True).start()
