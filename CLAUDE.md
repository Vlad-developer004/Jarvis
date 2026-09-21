# Jarvis — offline RU/UA голосовой ассистент

Local offline Win-voice assistant. Pipeline: ASR (sherpa-onnx/Vosk) -> Intent (keyword/semantic) -> Dispatch -> Action (CustomTkinter HUD, Silero TTS). Cloud: нет (опционально Groq — только для чата).

## Binding rules (flag tradeoff + confirm before changing)

1. **Startup order is crash-sensitive.** `CUDA_VISIBLE_DEVICES=''` и стабы `pynvml`/`pyarrow` — в самом верху `main.py`, до импорта torch/nltk/pandas. Нарушение порядка = 0xC0000005 crash при старте.
2. **No speculative refactoring.** Не менять рабочий код ради стиля/чистоты — нет автотестов, высокий риск сломать нативную Win32/DLL-логику (порядок preload, COM-инициализация). Сохранять Win32 API, реестр и Windows-специфичные пути как есть.
3. **Thread safety в `core/system/state.py`.** Глобальные флаги (`pytorch_loaded`, `jarvis_active`, `game_mode`) читаются/пишутся из нескольких потоков (background init, HUD, audio loop) — при правках сохранять существующие блокировки, не убирать их «для упрощения».
4. **UI-обновления только в UI-потоке** (`ui/hud.py`, CustomTkinter). Не дёргать HUD напрямую из audio/background потоков — только через существующий механизм передачи сообщений.

## Codebase exploration: no naive grep/full-file reads

Проект в `codebase-memory` MCP (`C-Users-tanja-OneDrive-Desktop-projects-Jarvis`). Использовать граф вместо grep/чтения файлов целиком:
- `get_architecture` — структура/пакеты/хотспоты
- `search_graph` / `search_code` / `query_graph` — где определено/используется
- `get_code_snippet` — блок по номерам строк, не весь файл (полный `Read` файла >200 строк — только если граф не справился)
- `trace_path` — цепочка вызовов/зависимостей
- `detect_changes` — blast radius диффа перед/после правки
- `manage_adr` (get) — архитектурные решения

grep — только когда граф не может ответить (строка внутри non-code asset, один уже открытый файл). Никогда — для брутфорса «где используется X» по всему дереву.

**Индекс:** после структурных/архитектурных изменений — `index_repository` (full/fast/moderate).

## Commit workflow

Без автономных коммитов. Показать диф → дождаться одобрения → закоммитить → предложить `/clear`.

## File size

~500 строк — оценить на декомпозицию. >600 — стоп, предложить план разбиения, без самостоятельного рефакторинга.

## Definition of Done

Обновить `README.md`/`docs/*.md`, если меняется поведение. Early-accept: остановиться, как только изменение работает и проходит ручную проверку — автотестов нет, верификация запуском приложения.

## Communication style

RU в чате без эмодзи, EN в коде/комментариях/докстрингах/коммитах. Кратко, без AI-slop (delve, robust, seamless, leverage...). Секреты в чат не печатать — только подтверждать наличие в `.env`, `secrets.env` или `%APPDATA%\Jarvis\secrets.env`.

## Commands & Env

- Run: `python main.py` | Deps: `pip install -r requirements.txt` (+ опционально `requirements-*.txt`)
- Build: `build.bat` (PyInstaller через `jarvis.spec`; копирует assets/models/profiles, strips envs)
- Tests: автотестов нет, проверка вручную запуском приложения

## Project shape

### Startup sequence (`main.py`)
*Порядок критичен — предотвращает 0xC0000005 и DLL-конфликты.*
1. Верх файла: `CUDA_VISIBLE_DEVICES=''`, стабы `pynvml`/`pyarrow` (до torch/nltk/pandas).
2. `core.system.bootstrap.bootstrap()` — DPI, dir fix, логи, mutex.
3. `_background_init()` (thread): preload PyTorch DLL -> TTS warmup -> async semantic models -> PyAudio stream -> `CommandHandler`+`JarvisEngine` -> mic profile -> опциональные фичи.
4. UI: `_run_hud` (thread), ждёт `_engine_ready`.
5. Main thread: блокируется на `_engine_ready` -> `engine.run()` (audio loop).

### Pipeline & core modules
- **Audio/VAD**: `core/engine/jarvis.py` (RMS/Silero VAD, pre-buffer, dynamic EMA noise floor, speech thread). Game mode = более жёсткие VAD-пороги.
- **ASR/TTS**: `core/speech/asr.py` (Vosk/sherpa-onnx) | `core/speech/tts.py` (Silero `v5_5_ru`/`v4_ua`, кэш в `%TEMP%`, thread-safe `inference_lock`, тяжёлая нормализация текста).
- **NLP/Intents**:
  - `core/nlp/commands.py` — typo/glue fixes, word->digit, `CANON_SIMPLE` keywords -> fuzzy fallback (`rapidfuzz`).
  - `core/nlp/{intents,semantic}.py` — sentence-transformers/ONNX embeddings, кэш `data/semantic_cache.npz`.
- **Handler/Actions**:
  - `core/handler/dispatch.py` — routing интента в `core/handler/commands/*.py` (по флагам).
  - `core/handler/base.py` — interactive state machine, RU/UA phrase cache, night/silent mode.
  - `actions/*.py` — исполнение системных/прикладных действий.

### Config, State & UI
- `config_pack/config.py` — пороги, пути. Приоритет `%LOCALAPPDATA%\Jarvis` / `%APPDATA%\Jarvis`, fallback `./data`.
- `core/system/state.py` — глобальный singleton флагов (`pytorch_loaded`, `jarvis_active`, `game_mode` и т.д.). **Thread safety критична.**
- `core/i18n.py` — локали `data/locales/{ru,uk}.json`, `tr(key)`.
- `ui/`: `hud.py` (overlay LOADING/IDLE/LISTENING/SPEAKING), `dialogs/` (settings). UI-обновления только в UI-потоке.

### Game Integration
- Профили: `data/game_profiles/*.json` (ETS2, Hogwarts и др.).
- Телеметрия: `actions/ets2_telemetry.py` (UDP), `ets2_telemetry_installer.py`.
- Core: `features/gaming/`, `core/system_parts/game_mode.py`.
