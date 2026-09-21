import os
import re
from actions.filesystem import empty_recycle_bin, create_folder_at, delete_folder_at, goto_folder
from actions.explorer import navigate_to_system_folder, get_active_explorer_path
from core.responses import spk
def get_context_path(handler):
    from core.system.windows import get_foreground_window_title, get_active_explorer_path, get_known_folder_path
    from actions.dev_projects import get_projects
    import win32gui
    import win32process
    import psutil

    title = get_foreground_window_title()
    if title:
        # 1. Direct path in window title (e.g. C:\path\to\file.py)
        path_match = re.search(r'[a-zA-Z]:\\[^:<>|"?\r\n]+', title)
        if path_match:
            p = path_match.group(0).strip()
            if os.path.isdir(p): return p
            if os.path.exists(p): return os.path.dirname(p)

        # 2. Match against configured dev projects database (by folder name or project name)
        try:
            from actions.dev_projects import _search_variants
            projects = get_projects()
            title_lower = title.lower()
            matched_proj_path = None
            for proj in projects:
                p_path = proj.get('path', '')
                if not p_path:
                    continue

                # Check actual folder name (e.g. "Jarvis" from path)
                folder_name = os.path.basename(p_path).lower()
                p_name = proj.get('name', '')

                matched = False
                if folder_name and folder_name in title_lower:
                    matched = True
                elif p_name:
                    variants = _search_variants(p_name)
                    if any(v.lower() in title_lower for v in variants if v):
                        matched = True

                if matched and os.path.isdir(p_path):
                    matched_proj_path = p_path
                    break

            if matched_proj_path:
                # Locate active file inside project to return the specific subdirectory
                file_candidate = None
                for part in title.split(' - '):
                    part = part.strip()
                    if '.' in part and not part.startswith('.'):
                        ext = part.split('.')[-1].lower()
                        programming_exts = handler._settings.get('programming_file_extensions', ['py', 'tsx', 'ts', 'js', 'html', 'css', 'json', 'md', 'txt'])
                        if ext in programming_exts:
                            file_candidate = part
                            break

                if file_candidate:
                    from pathlib import Path
                    for p in Path(matched_proj_path).rglob(file_candidate):
                        if any(part.startswith('.') or part in ('node_modules', 'venv', '.venv', '__pycache__', 'dist', 'build') for part in p.parts):
                            continue
                        if p.is_file():
                            return str(p.parent)

                return matched_proj_path
        except Exception:
            pass

    # 3. Check Active IDE / Work App process context
    hwnd = win32gui.GetForegroundWindow()
    exe_basename = ""
    cmdline_str = ""
    if hwnd:
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid:
                p = psutil.Process(pid)
                exe_path = p.exe()
                if exe_path:
                    exe_basename = os.path.basename(exe_path).lower()
                cmdline = p.cmdline()
                cmdline_str = ' '.join(cmdline).lower()
        except Exception:
            pass

    if exe_basename:
        context_apps = handler._settings.get('context_apps', ['code.exe', 'pycharm64.exe', 'phpstorm64.exe', 'antigravity.exe'])
        context_apps_lower = [a.lower() for a in context_apps]

        is_context_app = False
        exe_stem = os.path.splitext(exe_basename)[0]
        for app in context_apps_lower:
            app_stem = os.path.splitext(app)[0]
            # Match if active name or stem is a substring of the configured app name (or vice versa)
            if (app_stem in exe_basename) or (exe_stem in app_stem):
                is_context_app = True
                break

        # If running in development mode via Python, inspect command line args
        if not is_context_app and exe_basename in ('python.exe', 'pythonw.exe') and cmdline_str:
            for app in context_apps_lower:
                app_stem = os.path.splitext(app)[0]
                if app_stem in cmdline_str:
                    is_context_app = True
                    break

        if is_context_app:
            if title:
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

    # 4. Check Active Explorer Window
    ex_path = get_active_explorer_path(any_open=False)
    if ex_path and os.path.isdir(ex_path):
        return ex_path
    # 5. Final Fallback to Desktop
    return get_known_folder_path('desktop') or os.path.join(os.path.expanduser('~'), 'Desktop')

def _empty_trash(handler, cmd, text_lower):
    if empty_recycle_bin()[0]: handler.play_response()

def _create_folder(handler, cmd, text_lower):
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
        handler.speak(spk('files.cancelled'))
        return
    if not os.path.exists(base_path):
        try: os.makedirs(base_path, exist_ok=True)
        except Exception as e:
            handler.speak(spk("files.access_error_e", e=e))
            return
    ok, res = create_folder_at(base_path, name)
    if ok:
        handler.play_response('created')
    else:
        handler.speak(res)

def _delete_folder(handler, cmd, text_lower):
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
        handler.speak(spk('files.cancelled'))
        return

    ok, res_msg = delete_folder_at(base_path, name)
    if ok: handler.play_response('deleted')
    else: handler.speak(res_msg)

def _delete_file(handler, cmd, text_lower):
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
        handler.speak(spk('files.cancelled'))
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
        handler.speak(spk('files.not_found'))
        return

    try:
        target.unlink()
        handler.play_response('deleted')
    except Exception as e:
        handler.speak(spk("files.delete_error_e", e=e))

def _cd_folder(handler, cmd, text_lower):
    from core.handler.dispatch import parse_cd_name
    name = parse_cd_name(text_lower).strip()
    if not name:
        handler.speak(spk('files.ask_folder'))
        handler._set_interactive('cd_folder_ask', {'ctx': str(get_context_path(handler))}, timeout=20.0)
        return
    ok, res = goto_folder(get_context_path(handler), name)
    if ok:
        handler.play_response()
    else:
        handler.speak(res)

def _explorer_goto(handler, cmd, text_lower):
    # If user just said "open explorer/провідник" with no folder — open root
    if re.search(r'\bпровод?ни[кгків]+\b|\bпровідни[кгків]+\b', text_lower):
        folder = ''
    else:
        folder = text_lower
        for w in ('зайди', 'перейди', 'відкрий', 'открой', 'папку', 'папки',
                  'директорию', 'директорії', 'до', 'в', 'у'):
            folder = re.sub(r'\b' + w + r'\b', '', folder)
        folder = folder.strip()
    if not folder:
        import subprocess
        subprocess.Popen(['explorer'])
        handler.play_response()
        return
    ok, res = navigate_to_system_folder(folder)
    if ok:
        handler.play_response()
    else:
        handler.speak(res)

def _explorer_go_up(handler, cmd, text_lower):
    ok, res = navigate_to_system_folder('..')
    if ok: handler.play_response()
    else: handler.speak(res)

def _create_word_doc(handler, cmd, text_lower):
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
        # Use dominant extension in the current folder as smart default
        from core.handler.parse_create_file import dominant_ext_in_folder
        kind = dominant_ext_in_folder(str(bp))
        if not kind:
            # Fallback: check for office documents
            if any(bp.glob('*.docx')) or any(bp.glob('*.xlsx')) or any(bp.glob('*.pptx')):
                kind = 'docx'
            else:
                kind = 'txt'  # Safe universal default
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
    # Always show the dialog — pre-fill with what we know, user confirms
    kind = kind or 'txt'
    titles = {
        'docx': ('WORD — J.A.R.V.I.S.', '⬡  ИМЯ ДОКУМЕНТА (.docx)'),
        'xlsx': ('EXCEL — J.A.R.V.I.S.', '⬡  ИМЯ ТАБЛИЦЫ (.xlsx)'),
        'pptx': ('POWERPOINT — J.A.R.V.I.S.', '⬡  ИМЯ ПРЕЗЕНТАЦИИ (.pptx)'),
        'txt': ('ТЕКСТ — J.A.R.V.I.S.', '⬡  ИМЯ ФАЙЛА (.txt)'),
        'py': ('PYTHON — J.A.R.V.I.S.', '⬡  ИМЯ МОДУЛЯ (.py)'),
        'md': ('MARKDOWN — J.A.R.V.I.S.', '⬡  ИМЯ ФАЙЛА (.md)'),
    }
    tit, hdr = titles.get(
        kind,
        ('ФАЙЛ — J.A.R.V.I.S.', f'⬡  ИМЯ ФАЙЛА (.{kind})'),
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
            initial_value=name or '',
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
        handler.speak(spk('files.cancelled'))
        return
    suf = f'.{kind}'.lower()
    if name.lower().endswith(suf):
        name = name[: -len(suf)].strip()
    stem = sanitize_document_stem(name)
    if not stem:
        handler.speak(spk('files.bad_name'))
        return
    if not base_path.exists():
        try: base_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            handler.speak(spk("files.create_error_e", e=e))
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

def _recent_file(handler, cmd, text_lower):
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

def _find_file(handler, cmd, text_lower):
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
        handler.speak(spk("files.ask_filename"))
        handler._set_interactive('find_file_ask', {'file_type': file_type}, timeout=20.0)
        return
    handler.speak(spk("files.searching", query=query))
    import threading
    def _search():
        # For searching/opening, we don't restrict to subfolders
        ok, res = search_and_open_file(query, file_type)
        handler.speak(res)
        if ok: handler.play_response()
    threading.Thread(target=_search, daemon=True).start()

_FILES_EXACT = {
    'empty_trash': _empty_trash,
    'create_folder': _create_folder,
    'delete_folder': _delete_folder,
    'delete_file': _delete_file,
    'cd_folder': _cd_folder,
    'explorer_goto': _explorer_goto,
    'explorer_go_up': _explorer_go_up,
    'create_word_doc': _create_word_doc,
    'find_doc': _find_file,
    'find_sheet': _find_file,
    'find_file': _find_file,
}

def handle_files(handler, cmd, text_lower):
    action = _FILES_EXACT.get(cmd)
    if action is None and cmd.startswith('recent_'):
        action = _recent_file
    if action:
        action(handler, cmd, text_lower)
