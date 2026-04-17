from __future__ import annotations
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
_INVALID_WIN_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1F]')
def _safe_filename(stem: str) -> str:
    stem = (stem or "").strip()
    stem = _INVALID_WIN_NAME.sub(" ", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" .")
    return stem
def sanitize_document_stem(stem: str) -> str:
    return _safe_filename(stem)
def create_word_document(target_path: str) -> tuple[bool, str]:
    try:
        p = Path(target_path)
        if p.suffix.lower() != ".docx":
            p = p.with_suffix(".docx")
        p.parent.mkdir(parents=True, exist_ok=True)
        safe = _safe_filename(p.stem)
        if not safe:
            return (False, "Некорректное имя документа")
        p = p.with_name(safe + ".docx")
        if p.exists():
            return (False, f"Файл уже существует: {p.name}")
        import win32com.client
        word = None
        doc = None
        try:
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            doc = word.Documents.Add()
            doc.SaveAs(str(p), FileFormat=16)
            doc.Close(False)
            doc = None
            word.Quit()
            word = None
        finally:
            try:
                if doc is not None:
                    doc.Close(False)
            except Exception:
                pass
            try:
                if word is not None:
                    word.Quit()
            except Exception:
                pass
        return (True, str(p))
    except Exception as e:
        return (False, str(e))
def create_excel_workbook(target_path: str) -> tuple[bool, str]:
    try:
        p = Path(target_path)
        if p.suffix.lower() != ".xlsx":
            p = p.with_suffix(".xlsx")
        p.parent.mkdir(parents=True, exist_ok=True)
        safe = _safe_filename(p.stem)
        if not safe:
            return (False, "Некорректное имя")
        p = p.with_name(safe + ".xlsx")
        if p.exists():
            return (False, f"Файл уже существует: {p.name}")
        import win32com.client
        xl = None
        wb = None
        try:
            xl = win32com.client.Dispatch("Excel.Application")
            xl.Visible = False
            xl.DisplayAlerts = False
            wb = xl.Workbooks.Add()
            wb.SaveAs(str(p), FileFormat=51)
            wb.Close(False)
            wb = None
            xl.Quit()
            xl = None
        finally:
            try:
                if wb is not None:
                    wb.Close(False)
            except Exception:
                pass
            try:
                if xl is not None:
                    xl.Quit()
            except Exception:
                pass
        return (True, str(p))
    except Exception as e:
        return (False, str(e))
def create_powerpoint_presentation(target_path: str) -> tuple[bool, str]:
    try:
        p = Path(target_path)
        if p.suffix.lower() != ".pptx":
            p = p.with_suffix(".pptx")
        p.parent.mkdir(parents=True, exist_ok=True)
        safe = _safe_filename(p.stem)
        if not safe:
            return (False, "Некорректное имя")
        p = p.with_name(safe + ".pptx")
        if p.exists():
            return (False, f"Файл уже существует: {p.name}")
        import win32com.client
        PP_FORMAT_OPENXML = 24
        app = None
        prs = None
        try:
            app = win32com.client.Dispatch("PowerPoint.Application")
            app.Visible = False
            prs = app.Presentations.Add(WithWindow=False)
            prs.SaveAs(str(p), PP_FORMAT_OPENXML)
            prs.Close()
            prs = None
            app.Quit()
            app = None
        finally:
            try:
                if prs is not None:
                    prs.Close()
            except Exception:
                pass
            try:
                if app is not None:
                    app.Quit()
            except Exception:
                pass
        return (True, str(p))
    except Exception as e:
        return (False, str(e))
def create_plain_text_file(target_path: str, *, content: str = "") -> tuple[bool, str]:
    try:
        p = Path(target_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        safe = _safe_filename(p.stem)
        if not safe:
            return (False, "Некорректное имя")
        suf = p.suffix.lower() or ".txt"
        p = p.with_name(safe + suf)
        if p.exists():
            return (False, f"Файл уже существует: {p.name}")
        p.write_text(content or "", encoding="utf-8", newline="\n")
        return (True, str(p))
    except Exception as e:
        return (False, str(e))
def create_python_file(target_path: str) -> tuple[bool, str]:
    body = "# -*- coding: utf-8 -*-\n\n"
    p = Path(target_path)
    if p.suffix.lower() != ".py":
        p = p.with_suffix(".py")
    return create_plain_text_file(str(p), content=body)
def _create_txt(path: str) -> tuple[bool, str]:
    return create_plain_text_file(path, content="")
def _create_md(path: str) -> tuple[bool, str]:
    return create_plain_text_file(path, content="")
def _create_plain_empty(path: str) -> tuple[bool, str]:
    return create_plain_text_file(path, content="")
_PLAIN_WEB_EXTS: tuple[str, ...] = (
    "js",
    "jsx",
    "mjs",
    "cjs",
    "ts",
    "tsx",
    "mts",
    "cts",
    "html",
    "htm",
    "css",
    "scss",
    "sass",
    "less",
    "json",
    "vue",
    "svelte",
    "php",
    "rb",
    "go",
    "rs",
    "java",
    "kt",
    "swift",
    "c",
    "h",
    "cpp",
    "hpp",
    "cs",
    "sql",
    "graphql",
    "gql",
    "yaml",
    "yml",
    "toml",
    "ini",
    "env",
    "sh",
    "ps1",
    "xml",
    "svg",
)
_IDE_OPEN_EXTS: frozenset[str] = frozenset(_PLAIN_WEB_EXTS) | frozenset(("py", "md"))
_OFFICE_EXTS: frozenset[str] = frozenset(("docx", "xlsx", "pptx"))
CREATE_BY_KIND: dict[str, callable] = {
    "docx": create_word_document,
    "xlsx": create_excel_workbook,
    "pptx": create_powerpoint_presentation,
    "txt": _create_txt,
    "md": _create_md,
    "py": create_python_file,
}
for _ext in _PLAIN_WEB_EXTS:
    CREATE_BY_KIND[_ext] = _create_plain_empty
LIST_CREATE_KINDS_UI: tuple[tuple[str, str], ...] = (
    ("docx", "Word  .docx"),
    ("xlsx", "Excel  .xlsx"),
    ("pptx", "PowerPoint  .pptx"),
    ("py", "Python  .py"),
    ("ts", "TypeScript  .ts"),
    ("tsx", "TSX / React  .tsx"),
    ("js", "JavaScript  .js"),
    ("jsx", "JSX  .jsx"),
    ("mjs", "ES module  .mjs"),
    ("cjs", "CommonJS  .cjs"),
    ("html", "HTML  .html"),
    ("htm", "HTML  .htm"),
    ("css", "CSS  .css"),
    ("scss", "SCSS  .scss"),
    ("sass", "Sass  .sass"),
    ("less", "Less  .less"),
    ("json", "JSON  .json"),
    ("vue", "Vue  .vue"),
    ("svelte", "Svelte  .svelte"),
    ("php", "PHP  .php"),
    ("go", "Go  .go"),
    ("rs", "Rust  .rs"),
    ("java", "Java  .java"),
    ("cs", "C#  .cs"),
    ("sql", "SQL  .sql"),
    ("graphql", "GraphQL  .graphql"),
    ("yaml", "YAML  .yaml"),
    ("yml", "YAML  .yml"),
    ("toml", "TOML  .toml"),
    ("xml", "XML  .xml"),
    ("svg", "SVG  .svg"),
    ("sh", "Shell  .sh"),
    ("ps1", "PowerShell  .ps1"),
    ("ini", "INI  .ini"),
    ("env", "env  .env"),
    ("rb", "Ruby  .rb"),
    ("kt", "Kotlin  .kt"),
    ("swift", "Swift  .swift"),
    ("c", "C  .c"),
    ("cpp", "C++  .cpp"),
    ("h", "C header  .h"),
    ("hpp", "C++ header  .hpp"),
    ("mts", "TS module  .mts"),
    ("cts", "TS CJS types  .cts"),
    ("gql", "GraphQL  .gql"),
    ("txt", "Текст  .txt"),
    ("md", "Markdown  .md"),
)
def _popen_quiet(args: list[str]) -> bool:
    try:
        cf = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.Popen(args, close_fds=True, creationflags=cf)
        return True
    except Exception:
        return False
def _ide_cli_order() -> list[str]:
    out: list[str] = []
    try:
        import psutil
        names = {p.name().lower() for p in psutil.process_iter(["name"])}
        if "cursor.exe" in names:
            out.append("cursor")
        if "code.exe" in names or "code - insiders.exe" in names:
            out.append("code")
    except Exception:
        pass
    for c in ("cursor", "code"):
        if c not in out:
            out.append(c)
    return out
def _compose_ide_argv(ide_exe: str, file_path: str) -> list[str] | None:
    fp = os.path.normpath(os.path.abspath(file_path))
    base = os.path.basename(ide_exe).lower()
    low = ide_exe.lower()
    if base in ("python.exe", "pythonw.exe"):
        return None
    if base == "devenv.exe":
        return [ide_exe, "/Edit", fp]
    if base in (
        "code.exe",
        "code - insiders.exe",
        "code - oss.exe",
        "cursor.exe",
        "antigravity.exe",
        "pycharm64.exe",
        "pycharm32.exe",
        "idea64.exe",
        "webstorm64.exe",
        "phpstorm64.exe",
        "rider64.exe",
        "clion64.exe",
        "goland64.exe",
        "rubymine64.exe",
        "rustrover64.exe",
        "dataspell64.exe",
        "studio64.exe",
        "sublime_text.exe",
        "notepad++.exe",
    ):
        return [ide_exe, fp]
    if "jetbrains" in low:
        return [ide_exe, fp]
    if r"\microsoft vs code\code.exe" in low or r"\programs\microsoft vs code\code.exe" in low:
        return [ide_exe, fp]
    if r"\programs\cursor" in low and base.endswith(".exe"):
        return [ide_exe, fp]
    return None
def open_file(path: str) -> tuple[bool, str]:
    p = os.path.normpath(os.path.abspath(str(path)))
    ext = Path(p).suffix.lower().lstrip(".")
    if ext in _OFFICE_EXTS:
        try:
            os.startfile(p)
            return (True, p)
        except Exception as e:
            return (False, str(e))
    if ext not in _IDE_OPEN_EXTS:
        try:
            os.startfile(p)
            return (True, p)
        except Exception as e:
            return (False, str(e))
    try:
        from core.system import get_foreground_process_exe
        iexe = get_foreground_process_exe()
    except Exception:
        iexe = None
    if iexe:
        argv = _compose_ide_argv(iexe, p)
        if argv and _popen_quiet(argv):
            return (True, p)
    for cli in _ide_cli_order():
        w = shutil.which(cli)
        if w and _popen_quiet([w, p]):
            return (True, p)
    try:
        os.startfile(p)
        return (True, p)
    except Exception as e:
        return (False, str(e))
