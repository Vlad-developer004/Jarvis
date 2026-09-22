"""LLM narration for Planetbase events — game-specific prompts on top of the
shared has_llm_configured()/ask_llm_narration() plumbing in
features/gaming_common/llm_narration.py (also used by features/ets2/llm.py),
scaled down to Planetbase's much smaller telemetry surface (no cargo/route/
wear detail to narrate)."""
_SYS_RU = (
    "Ты — бортовой ИИ J.A.R.V.I.S., управляющий колонией в Planetbase. Сухой, чуть ироничный командный компьютер.\n"
    "Формат: без Markdown; без вводных слов (Конечно/Отлично/Понял/Принято); 2-4 коротких предложения; только русский.\n"
    "Комментируй событие по существу: что случилось, чем это грозит или чем радует, что делать дальше (если уместно)."
)

_SYS_UK = (
    "Ти — бортовий ШІ J.A.R.V.I.S., що керує колонією в Planetbase. Сухий, трохи іронічний командний комп'ютер.\n"
    "Формат: без Markdown; без вступних слів (Звичайно/Чудово/Зрозумів/Добре); 2-4 коротких речення; тільки українська.\n"
    "Коментуй подію по суті: що сталося, чим це загрожує або чим тішить, що робити далі (якщо доречно)."
)


def _sys_prompt() -> str:
    try:
        from core.i18n import get_speech_language
        return _SYS_UK if get_speech_language() == 'uk' else _SYS_RU
    except Exception:
        return _SYS_RU


def has_llm_configured() -> bool:
    """True if an API key exists and Planetbase AI narration isn't disabled."""
    from features.gaming_common.llm_narration import has_llm_configured as _shared
    return _shared('planetbase_llm_enabled')


_DISASTER_LABELS = {
    'sandstorm':   ('песчаная буря', 'піщана буря'),
    'solar_flare': ('солнечная вспышка', 'сонячний спалах'),
    'blizzard':    ('метель', 'заметіль'),
    'generic':     ('стихийное бедствие', 'стихійне лихо'),
}


def build_disaster_prompt(data: dict, kind: str) -> str:
    try:
        from core.i18n import get_speech_language
        uk = get_speech_language() == 'uk'
    except Exception:
        uk = False

    label = _DISASTER_LABELS.get(kind, _DISASTER_LABELS['generic'])[1 if uk else 0]
    colonists = data.get('colonists', 0)
    power_pct = data.get('power_pct', 0)
    water_pct = data.get('water_pct', 0)

    if uk:
        lines = [
            f"Подія: почалася {label}.",
            f"Колонія: {colonists} колоністів, енергія {power_pct}%, вода {water_pct}%.",
            "Дай коротке попередження про цю подію та практичну пораду, що робити.",
        ]
    else:
        lines = [
            f"Событие: началась {label}.",
            f"Колония: {colonists} колонистов, энергия {power_pct}%, вода {water_pct}%.",
            "Дай короткое предупреждение об этом событии и практичный совет, что делать.",
        ]
    return "\n".join(lines)


def build_milestone_prompt(data: dict, milestone: int) -> str:
    try:
        from core.i18n import get_speech_language
        uk = get_speech_language() == 'uk'
    except Exception:
        uk = False

    modules = data.get('module_count', 0)
    if uk:
        lines = [
            f"Подія: населення колонії досягло {milestone} колоністів.",
            f"Побудовано модулів: {modules}.",
            "Коротко привітай з цією віхою в характерному стилі, без пафосу.",
        ]
    else:
        lines = [
            f"Событие: население колонии достигло {milestone} колонистов.",
            f"Построено модулей: {modules}.",
            "Коротко поздравь с этой вехой в характерном стиле, без пафоса.",
        ]
    return "\n".join(lines)


def ask_pb(prompt: str, timeout: int = 12) -> str:
    """Call the configured LLM with Planetbase context. Returns '' on any failure."""
    from features.gaming_common.llm_narration import ask_llm_narration
    return ask_llm_narration(_sys_prompt(), prompt, max_tokens=250, timeout=timeout)
