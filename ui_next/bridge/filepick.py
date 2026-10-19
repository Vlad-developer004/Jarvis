"""Native Win32 open-file dialog for the bridge (independent of Tk, safe to call from any thread)."""
from __future__ import annotations

from pathlib import Path

NUL = chr(0)


def filters(*pairs: tuple[str, str]) -> str:
    """Win32 filter string from (name, pattern) pairs: "name<NUL>pattern<NUL>...". Always starts with "all files"."""
    out = [('Все файлы', '*.*'), *pairs]
    return ''.join(f'{n}{NUL}{p}{NUL}' for n, p in out)


ALL = filters()
MAIL = filters(('Изображения', '*.png;*.jpg;*.jpeg;*.gif;*.webp'), ('Документы', '*.pdf;*.doc;*.docx;*.xls;*.xlsx;*.txt'))
ICS = filters(('Календари iCalendar', '*.ics'))
GGUF = ''.join(f'{n}{NUL}{p}{NUL}' for n, p in (('Модель GGUF', '*.gguf'), ('Все файлы', '*.*')))


def pick_files(title: str, filter_string: str = ALL, multi: bool = False) -> list[str]:
    """Paths chosen in the dialog; empty when cancelled."""
    import win32con
    import win32gui
    flags = win32con.OFN_EXPLORER | win32con.OFN_FILEMUSTEXIST | win32con.OFN_PATHMUSTEXIST | win32con.OFN_NOCHANGEDIR
    if multi:
        flags |= win32con.OFN_ALLOWMULTISELECT
    try:
        fname, _, _ = win32gui.GetOpenFileNameW(hwndOwner=win32gui.GetForegroundWindow(), Flags=flags, Title=title, MaxFile=32768, Filter=filter_string)
    except Exception:                                                  # cancelled
        return []
    parts = [p for p in str(fname).split(NUL) if p]
    if len(parts) <= 1:
        return parts
    return [str(Path(parts[0]) / n) for n in parts[1:]]


def pick_folder(title: str) -> str:
    """The folder chosen in the native dialog; '' when cancelled."""
    try:
        import win32gui
        from win32com.shell import shell, shellcon
        pidl, _, _ = shell.SHBrowseForFolder(win32gui.GetForegroundWindow(), None, title, shellcon.BIF_RETURNONLYFSDIRS | 0x40, None, None)
        return str(shell.SHGetPathFromIDList(pidl) or '') if pidl else ''
    except Exception:                                                  # cancelled or no pywin32
        return ''


def save_file(title: str, default_name: str, filter_string: str = '') -> str:
    """The path chosen in the native "save as" dialog (a .json extension is added when missing); '' when cancelled."""
    try:
        import win32con
        import win32gui
        flt = filter_string or ''.join(f'{n}{NUL}{p}{NUL}' for n, p in (('Файлы JSON', '*.json'), ('Все файлы', '*.*')))
        flags = win32con.OFN_EXPLORER | win32con.OFN_OVERWRITEPROMPT | win32con.OFN_PATHMUSTEXIST | win32con.OFN_NOCHANGEDIR
        fname, _, _ = win32gui.GetSaveFileNameW(hwndOwner=win32gui.GetForegroundWindow(), Flags=flags, Title=title, File=default_name, DefExt='json', MaxFile=4096, Filter=flt)
        return str(fname or '')
    except Exception:                                                  # cancelled or no pywin32
        return ''
