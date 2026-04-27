from __future__ import annotations
import re
def parse_create_file_intent(text_lower: str) -> dict:
    t = (text_lower or "").strip().lower()
    t = re.sub(r"^\s*в проекте\s+", "", t)
    folder_hint: str | None = None
    name_hint: str | None = None
    for pat in (
        r"\bв папк(?:е|у)\s+(.+)$",
        r"\bв каталоге\s+(.+)$",
        r"\bпапк[еу]\s+(.+)$",
    ):
        m = re.search(pat, t, re.I)
        if m:
            folder_hint = m.group(1).strip().strip(".,")
            t = t[: m.start()].strip()
            break
    for pat in (
        r"\b(?:именем|названием|название|имя)\s+(.+)$",
        r"\bфайл\s+([a-zа-яёії0-9_.\- ]+)$",
        r"\b(?:создай|сделай|создать)\s+(?:файл|новый файл|пустой файл)\s+([a-zа-яёії0-9_.\- ]{1,80})$",
    ):
        m = re.search(pat, t, re.I)
        if m:
            cand = m.group(1).strip().strip(".,")
            # Don't confuse extension keywords with filenames
            _EXT_WORDS = {'python', 'пайтон', 'питон', 'typescript', 'javascript', 'markdown', 'html', 'css', 'json', 'vue', 'react', 'scss', 'word', 'ворд', 'excel', 'эксель'}
            if cand and len(cand) < 120 and cand.lower() not in _EXT_WORDS:
                name_hint = cand
                t = t[: m.start()].strip()
            break
    kind = _detect_kind(t)
    return {"kind": kind, "folder_hint": folder_hint, "name_hint": name_hint, "remainder": t}
def _detect_kind(t: str) -> str | None:
    if not t:
        return None
    if re.search(
        r"(powerpoint|pptx|\bppt\b|презентац|пауэрпоинт|павэрпоинт|повер\s*поинт)",
        t,
        re.I,
    ):
        return "pptx"
    if re.search(
        r"\b(excel|xlsx|эксель|эксел|экселя|таблиц\w*|электронн\w*\s+таблиц)\b",
        t,
        re.I,
    ):
        return "xlsx"
    if re.search(r"\btsx\b", t, re.I):
        return "tsx"
    if re.search(r"\bjsx\b", t, re.I):
        return "jsx"
    if re.search(r"\btypescript\b|\bтайпскрипт\b", t, re.I):
        return "ts"
    if re.search(r"\bjavascript\b|\bджаваскрипт\b|\bжс\b", t, re.I):
        return "js"
    if re.search(r"\breact\b|\bреакт\b", t, re.I) and not re.search(r"\btsx\b", t, re.I):
        return "tsx"
    if re.search(r"\bjson\b", t, re.I):
        return "json"
    if re.search(r"\bgraphql\b|\bgql\b", t, re.I):
        return "graphql"
    if re.search(r"\bvue\b|\bвью\b", t, re.I):
        return "vue"
    if re.search(r"\bsvelte\b", t, re.I):
        return "svelte"
    if re.search(r"\bscss\b", t, re.I):
        return "scss"
    if re.search(r"\bsass\b", t, re.I):
        return "sass"
    if re.search(r"\bcss\b", t, re.I):
        return "css"
    if re.search(r"\bhtml\b|\bхтмл\b|\bаштиэмэль\b", t, re.I):
        return "html"
    if re.search(r"\bphp\b|\bпхп\b", t, re.I):
        return "php"
    if re.search(r"\bgo\b|\bголанг\b", t, re.I):
        return "go"
    if re.search(r"\brust\b|\bраст\b", t, re.I):
        return "rs"
    if re.search(r"\byaml\b|\bямал\b", t, re.I):
        return "yaml"
    if re.search(r"\btoml\b", t, re.I):
        return "toml"
    if re.search(r"\bsql\b", t, re.I):
        return "sql"
    if re.search(r"\bxml\b", t, re.I):
        return "xml"
    if re.search(r"\bsvg\b", t, re.I):
        return "svg"
    if re.search(r"\b(mjs|cjs|mts|cts)\b", t, re.I):
        m = re.search(r"\b(mjs|cjs|mts|cts)\b", t, re.I)
        return m.group(1).lower() if m else "js"
    if re.search(r"\bpython\b|\bпайтон\b|\bпитон\b", t, re.I):
        return "py"
    if re.search(r"\b(markdown|маркдаун)\b", t, re.I) or re.search(r"\.md\b", t, re.I):
        return "md"
    if re.search(
        r"\b(текстовый файл|файл txt|простой текст|блокнот|\.txt\b|^txt\s)",
        t,
        re.I,
    ):
        return "txt"
    if re.search(r"\b(ворд|word|документ ворд|word\s+документ)\b", t, re.I):
        return "docx"
    if re.search(r"\bдокумент\b", t, re.I) and not re.search(
        r"\b(пайтон|питон|python|таблиц|презентац|react|json|html|css|typescript|javascript)\b",
        t,
        re.I,
    ):
        return "docx"
    if re.search(r"\b(новый файл|создай файл|пустой файл)\b", t, re.I):
        return None
    return None

def dominant_ext_in_folder(folder_path: str) -> str | None:
    """Count file extensions in folder and return the most common one (among code/doc types)."""
    from pathlib import Path
    from collections import Counter
    _CANDIDATE_EXTS = {
        'py', 'ts', 'tsx', 'js', 'jsx', 'vue', 'svelte', 'php', 'go', 'rs',
        'html', 'css', 'scss', 'json', 'md', 'txt', 'docx', 'xlsx', 'pptx',
        'java', 'cs', 'cpp', 'rb', 'swift', 'kt'
    }
    try:
        p = Path(folder_path)
        if not p.is_dir():
            return None
        counts = Counter(
            f.suffix.lower().lstrip('.')
            for f in p.iterdir()
            if f.is_file() and f.suffix.lower().lstrip('.') in _CANDIDATE_EXTS
        )
        if not counts:
            return None
        top_ext, top_count = counts.most_common(1)[0]
        # Only suggest if there are at least 2 files of this type
        if top_count >= 2:
            return top_ext
        return None
    except Exception:
        return None
