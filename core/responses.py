"""
Centralized spoken (TTS) response strings.

Usage:
    from core.responses import spk
    self.speak(spk('weather.fetching', city=city_name))

This project has three separate places user-facing text can live, picked by
precedent rather than a written rule until now — worth stating explicitly
so the next addition doesn't have to guess by scanning neighboring code:

  - data/locales/{ru,uk}.json + core.i18n.tr(key)  → on-screen UI text
    (dialog/button/label text — anything rendered in a Tkinter widget,
    never spoken).
  - core/responses.py (this file) + spk(key, **fmt) → spoken text that's
    reusable across call sites and/or needs {placeholder} formatting.
    Prefer this for any new handler.speak(...) call.
  - A raw string literal inline in a handler function → only when the text
    is single-call-site AND either static or already fully assembled from
    already-language-resolved data by the time it's built (e.g. an external
    API response spliced into a sentence, as in actions/weather.py's own
    RU/UK branching). If it'll ever be reused or is plain static phrasing,
    it belongs in one of the two mechanisms above instead.
"""
from __future__ import annotations

_STRINGS: dict[str, dict[str, str]] = {
    # --- dispatch ---
    'module.ai_disabled':        {'ru': 'Модуль ИИ отключен в текущем профиле.', 'uk': 'Модуль ШІ вимкнено в поточному профілі.'},
    'module.cinema_disabled':    {'ru': 'Кино модуль отключен в текущем профиле.', 'uk': 'Кіно модуль вимкнено в поточному профілі.'},
    'module.games_disabled':     {'ru': 'Игровой модуль отключен в текущем профиле.', 'uk': 'Ігровий модуль вимкнено в поточному профілі.'},
    'module.ps_disabled':        {'ru': 'Модуль Photoshop отключен в текущем профиле.', 'uk': 'Модуль Photoshop вимкнено в поточному профілі.'},
    'module.figma_disabled':     {'ru': 'Модуль Figma отключен в текущем профиле.', 'uk': 'Модуль Figma вимкнено в поточному профілі.'},
    'module.net_disabled':       {'ru': 'Модуль «Сеть и система» выключен. Включите расширение в центре модулей.', 'uk': 'Модуль «Мережа і система» вимкнено. Увімкніть розширення в центрі модулів.'},
    'module.integrations_disabled': {'ru': 'Модуль «Интеграции» выключен. Включите расширение в центре модулей.', 'uk': 'Модуль «Інтеграції» вимкнено. Увімкніть розширення в центрі модулів.'},
    'module.mail_disabled':      {'ru': 'Модуль «Почта» выключен. Включите расширение в центре модулей.', 'uk': 'Модуль «Пошта» вимкнено. Увімкніть розширення в центрі модулів.'},
    'open.error':                {'ru': 'Не удалось открыть: {res}', 'uk': 'Не вдалося відкрити: {res}'},
    'open.help_error':           {'ru': 'Не удалось открыть руководство.', 'uk': 'Не вдалося відкрити посібник.'},
    'hud.not_running':           {'ru': 'Интерфейс не запущен.', 'uk': 'Інтерфейс не запущено.'},
    'hud.error':                 {'ru': 'Ошибка при управлении интерфейсом.', 'uk': 'Помилка при керуванні інтерфейсом.'},
    'help.intro':                {'ru': 'Я голосовой ассистент Джарвис. Я умею управлять системой, открывать приложения и игры, искать информацию, переводить текст, диктовать заметки и письма, а также помогать в играх. Подробный список команд открыт на экране.', 'uk': 'Я голосовий асистент Джарвіс. Я вмію керувати системою, відкривати застосунки та ігри, шукати інформацію, перекладати текст, диктувати нотатки та листи, а також допомагати в іграх. Детальний список команд відкрито на екрані.'},
    # --- info / weather ---
    'weather.fetching':          {'ru': 'Получаю информацию о погоде для {city}...', 'uk': 'Отримую інформацію про погоду для {city}...'},
    'nasa.fetching':              {'ru': 'Запрашиваю картинку дня у NASA...', 'uk': 'Запитую картинку дня у NASA...'},
    'yt_picker.prompt':           {'ru': 'Нашлось несколько похожих результатов. Кликните нужный, или скажите «первое», «второе» и так далее.', 'uk': 'Знайшлося декілька схожих результатів. Клікніть потрібний, або скажіть «перше», «друге» і так далі.'},
    'yt_picker.picked':           {'ru': 'Включаю вариант {n}.', 'uk': 'Вмикаю варіант {n}.'},
    'nasa.ready':                 {'ru': 'Картинка дня от NASA готова, описание на английском — смотрите в окне.', 'uk': 'Картинка дня від NASA готова, опис англійською — дивіться у вікні.'},
    'nasa.ready_video':           {'ru': 'Сегодня у NASA видео дня вместо фото. Показываю превью без звука в окне.', 'uk': 'Сьогодні у NASA відео дня замість фото. Показую прев\'ю без звуку у вікні.'},
    'song.listening':             {'ru': 'Слушаю...', 'uk': 'Слухаю...'},
    'song.result':                {'ru': 'Это «{title}», исполнитель {artist}.', 'uk': 'Це «{title}», виконавець {artist}.'},
    'song.result_notitle':        {'ru': 'Это «{title}».', 'uk': 'Це «{title}».'},
    'song.no_match':              {'ru': 'Не удалось распознать песню. Попробуйте сделать звук погромче.', 'uk': 'Не вдалося розпізнати пісню. Спробуйте зробити звук гучніше.'},
    'song.no_key':                {'ru': 'Не удалось распознать песню — Shazam недоступен, а резервный ключ AudD не настроен.', 'uk': 'Не вдалося розпізнати пісню — Shazam недоступний, а резервний ключ AudD не налаштовано.'},
    'song.error':                 {'ru': 'Не удалось распознать песню из-за ошибки.', 'uk': 'Не вдалося розпізнати пісню через помилку.'},
    'weather.city_saved':        {'ru': 'Хорошо, {address}. Теперь я буду показывать погоду для города {city}.', 'uk': 'Добре, {address}. Тепер буду показувати погоду для міста {city}.'},
    'weather.city_save_error':   {'ru': 'Не удалось сохранить настройки города.', 'uk': 'Не вдалося зберегти налаштування міста.'},
    'weather.ask_city':          {'ru': 'Какой город мне запомнить?', 'uk': 'Яке місто мені запам\'ятати?'},
    'search.ask_query':          {'ru': 'Что именно мне найти, {address}?', 'uk': 'Що саме знайти, {address}?'},
    'translate.translating':     {'ru': 'Перевожу на {lang}', 'uk': 'Перекладаю на {lang}'},
    'translate.error':           {'ru': 'Проблема с переводом: {msg}', 'uk': 'Проблема з перекладом: {msg}'},
    'translate.result':          {'ru': 'Это переводится как: {text}', 'uk': 'Це перекладається як: {text}'},
    'translate.fetch_error':     {'ru': 'Не удалось получить перевод.', 'uk': 'Не вдалося отримати переклад.'},
    'translate.generic_error':   {'ru': 'Произошла ошибка при переводе.', 'uk': 'Сталася помилка при перекладі.'},
    'translate.ask_text':        {'ru': 'Я не понял, что именно нужно перевести.', 'uk': 'Я не зрозумів, що саме потрібно перекласти.'},
    'ip.fetching':               {'ru': 'Получаю ваш IP адрес, {address}...', 'uk': 'Отримую вашу IP адресу, {address}...'},
    'specs.error':               {'ru': 'Не удалось собрать полные характеристики системы.', 'uk': 'Не вдалося зібрати характеристики системи.'},
    # --- system ---
    'system.cleanup_start':      {'ru': 'Начинаю уборку, {address}. Чищу временные файлы, кэши браузеров, мусор Windows. Доложу по завершении.', 'uk': 'Починаю прибирання, {address}. Чищу тимчасові файли, кеші браузерів, сміття Windows. Доповім після завершення.'},
    'system.cleanup_deep_scan':  {'ru': 'Начинаю глубокую уборку, {address}. Чищу временные файлы и кэши, затем поищу папки от удалённых программ — это займёт немного времени.', 'uk': 'Починаю глибоке прибирання, {address}. Чищу тимчасові файли й кеші, потім пошукаю папки від видалених програм — це займе трохи часу.'},
    'system.cleanup_deep_done':  {'ru': 'Готово, {address}. Освобождено {freed_mb} {mb_word}. Ошибок: {errors}.', 'uk': 'Готово, {address}. Звільнено {freed_mb} мегабайт. Помилок: {errors}.'},
    'net.speed_start':           {'ru': 'Запускаю проверку скорости... Один момент.', 'uk': 'Запускаю перевірку швидкості... Одну мить.'},
    'net.speed_timeout':         {'ru': 'Сервер не отвечает. Проверьте соединение или попробуйте позже.', 'uk': 'Сервер не відповідає. Перевірте з\'єднання або спробуйте пізніше.'},
    'guard.activating':          {'ru': 'Активирую режим охраны. Пожалуйста, смотрите в камеру.', 'uk': 'Активую режим охорони. Подивіться в камеру.'},
    'guard.on':                  {'ru': 'Режим охраны включен. Я слежу за порядком, {address}.', 'uk': 'Режим охорони увімкнено. Я стежу за порядком, {address}.'},
    'guard.on_error':            {'ru': 'Не удалось включить охрану: {res}', 'uk': 'Не вдалося увімкнути охорону: {res}'},
    'guard.off':                 {'ru': 'Система охраны отключена. Вольно, {address}.', 'uk': 'Систему охорони вимкнено. Вільно, {address}.'},
    'guard.not_active':          {'ru': 'Охрана не была активна.', 'uk': 'Охорона не була активна.'},
    'shutdown.timer':            {'ru': 'Хорошо, компьютер выключится через {delay}.', 'uk': 'Добре, комп\'ютер вимкнеться через {delay}.'},
    'shutdown.timer_error':      {'ru': 'Не удалось распознать время выключения.', 'uk': 'Не вдалося розпізнати час вимкнення.'},
    'shutdown.now':              {'ru': 'Завершаю работу. До встречи, {address}.', 'uk': 'Завершую роботу. До зустрічі, {address}.'},
    'restart.now':               {'ru': 'Перезапускаю, {address}. Буду снова в строю через минуту.', 'uk': 'Перезапускаю, {address}. Буду знову готовий за хвилину.'},
    'listen.off':                {'ru': 'Режим тишины: команды не выполняю. Скажите «слушай меня» чтобы продолжить.', 'uk': 'Режим тиші: команди не виконую. Скажіть «слухай мене» щоб продовжити.'},
    'listen.on':                 {'ru': 'Я снова слушаю вас, {address}.', 'uk': 'Я знову вас слухаю, {address}.'},
    'economy.on':                {'ru': 'Режим экономии энергии активирован.', 'uk': 'Режим економії енергії активовано.'},
    'economy.off':               {'ru': 'Режим максимальной производительности восстановлен.', 'uk': 'Режим максимальної продуктивності відновлено.'},
    'shutdown.cancel':           {'ru': 'Таймер выключения отменен.', 'uk': 'Таймер вимкнення скасовано.'},
    'work.open_one':             {'ru': 'Открываю проект {name}, {address}. Продуктивной работы.', 'uk': 'Відкриваю проект {name}, {address}. Продуктивної роботи.'},
    'work.ask_which':            {'ru': 'Над каким проектом работаем, {address}?', 'uk': 'Над яким проектом працюємо, {address}?'},
    'work.open_selected':        {'ru': 'Открываю {name}. За работу, {address}.', 'uk': 'Відкриваю {name}. До роботи, {address}.'},
    'work.not_found':            {'ru': 'Проект не найден. Скажите точнее, {address}.', 'uk': 'Проект не знайдено. Скажіть точніше, {address}.'},
    'work.no_projects':          {'ru': '{Address}, список проектов пуст. Добавьте проект в настройках разработки.', 'uk': '{Address}, список проектів порожній. Додайте проект у налаштуваннях.'},
    'work.error':                {'ru': 'Не удалось открыть проект.', 'uk': 'Не вдалося відкрити проект.'},
    'timer.done_title':          {'ru': 'ВРЕМЯ  ВЫШЛО', 'uk': 'ЧАС  ВИЙШОВ'},
    'timer.done_ready':          {'ru': 'ГОТОВО', 'uk': 'ГОТОВО'},
    'timer.hint_close':          {'ru': '«закрой»  /  «ок»', 'uk': '«закрий»  /  «ок»'},
    'timer.btn_close':           {'ru': 'ЗАКРЫТЬ   ✕', 'uk': 'ЗАКРИТИ   ✕'},
    'reminder.error':            {'ru': 'Не удалось распознать время напоминания.', 'uk': 'Не вдалося розпізнати час нагадування.'},
    'reminder.set':              {'ru': 'Хорошо, напомню через {delay}.', 'uk': 'Добре, нагадаю через {delay}.'},
    # --- files ---
    'files.cancelled':           {'ru': 'Отменено.', 'uk': 'Скасовано.'},
    'files.access_error':        {'ru': 'Ошибка доступа к пути: {e}', 'uk': 'Помилка доступу до шляху: {e}'},
    'files.not_found':           {'ru': 'Файл не найден в текущей папке.', 'uk': 'Файл не знайдено в поточній папці.'},
    'files.delete_error':        {'ru': 'Ошибка удаления: {e}', 'uk': 'Помилка видалення: {e}'},
    'files.ask_folder':          {'ru': 'Скажите название папки.', 'uk': 'Скажіть назву папки.'},
    'files.ask_goto':            {'ru': 'Скажите, куда зайти: например «зайди в папку Проекты»', 'uk': 'Скажіть, куди перейти: наприклад «відкрий папку Проекти»'},
    'files.bad_name':            {'ru': 'Некорректное имя.', 'uk': 'Некоректна назва.'},
    'files.create_error':        {'ru': 'Ошибка доступа: {e}', 'uk': 'Помилка доступу: {e}'},
    'files.ask_filename':        {'ru': 'Укажите название файла.', 'uk': 'Вкажіть назву файлу.'},
    'files.searching':           {'ru': 'Ищу {query}...', 'uk': 'Шукаю {query}...'},
    # --- video ---
    'video.ask_monitor':         {'ru': 'У вас несколько мониторов. На каком записывать?', 'uk': 'У вас кілька моніторів. На якому записувати?'},
    'video.no_saved':            {'ru': 'Сохранённое видео не найдено.', 'uk': 'Збережене відео не знайдено.'},
    'video.download_error':      {'ru': 'Ошибка скачивания: {res}', 'uk': 'Помилка завантаження: {res}'},
    'video.ocr_error':           {'ru': 'Ошибка распознавания: {res}', 'uk': 'Помилка розпізнавання: {res}'},
    # --- game ---
    'game.confirm':              {'ru': 'Смею предположить, вы хотите сыграть в {game}? Запускаем?', 'uk': 'Схоже, ви хочете зіграти в {game}? Запускаємо?'},
    # --- creative ---
    'ps.not_active':             {'ru': 'Окно Photoshop не активно. Откройте Photoshop и повторите.', 'uk': 'Вікно Photoshop не активне. Відкрийте Photoshop і повторіть.'},
    'ps.unknown_cmd':            {'ru': 'Команда Photoshop не распознана.', 'uk': 'Команду Photoshop не розпізнано.'},
    'ps.send_error':             {'ru': 'Не получилось отправить команду в Photoshop.', 'uk': 'Не вдалося надіслати команду в Photoshop.'},
    'figma.not_active':          {'ru': '{Address}, активируйте окно Figma.', 'uk': '{Address}, активуйте вікно Figma.'},
    'figma.unknown_cmd':         {'ru': 'Команда Figma не распознана.', 'uk': 'Команду Figma не розпізнано.'},
    'figma.send_error':          {'ru': 'Не получилось отправить команду в Figma.', 'uk': 'Не вдалося надіслати команду в Figma.'},
    'cmd.not_supported':         {'ru': 'Команда не поддерживается.', 'uk': 'Команда не підтримується.'},
    # --- cinema ---
    'cinema.ask':                {'ru': 'Какой фильм или сериал вы хотите посмотреть, {address}?', 'uk': 'Який фільм або серіал ви хочете подивитися, {address}?'},
    'cinema.searching':          {'ru': 'Ищу {type} {title}...', 'uk': 'Шукаю {type} {title}...'},
    'cinema.not_found':          {'ru': 'Извините, {address}, я не смог найти {type} {title}.', 'uk': 'Вибачте, {address}, я не зміг знайти {type} {title}.'},
    # --- ai ---
    'ai.no_answer':              {'ru': 'К сожалению, я не смог найти ответ на этот вопрос.', 'uk': 'На жаль, я не зміг знайти відповідь на це питання.'},
    'ai.error':                  {'ru': '{Address}, возникла ошибка при получении ответа от нейросети.', 'uk': '{Address}, виникла помилка при отриманні відповіді від нейромережі.'},
    # --- integrations ---
    'net.ask_profile':           {'ru': 'Скажите, например: переключи сеть на дом, на офис, на игры.', 'uk': 'Скажіть, наприклад: переключи мережу на дім, на офіс, на ігри.'},
    'mail.opening':              {'ru': 'Открываю окно для нового письма.', 'uk': 'Відкриваю вікно для нового листа.'},
    'mail.not_loaded':           {'ru': 'Интерфейс ещё не загружен.', 'uk': 'Інтерфейс ще не завантажено.'},
    'mail.error':                {'ru': 'Не удалось открыть окно. Попробуйте кнопку «Почта» в интерфейсе.', 'uk': 'Не вдалося відкрити вікно. Спробуйте кнопку «Пошта» в інтерфейсі.'},
    # --- notes ---
    'notes.ask':                 {'ru': '{Address}, что именно мне записать?', 'uk': '{Address}, що саме мені записати?'},
    'notes.save_error':          {'ru': 'Не удалось сохранить заметку.', 'uk': 'Не вдалося зберегти нотатку.'},
    'reminder.notify':           {'ru': '{Address}, вы просили напомнить: {msg}', 'uk': '{Address}, ви просили нагадати: {msg}'},
    # --- media ---
    'media.ask_channel':         {'ru': 'Какой канал открыть, {address}?', 'uk': 'Який канал відкрити, {address}?'},
    'media.ask_what_to_play':    {'ru': 'Что включить, {address}?', 'uk': 'Що включити, {address}?'},
    'media.no_audio_device':     {'ru': 'Не удалось найти устройство вывода.', 'uk': 'Не вдалося знайти пристрій виводу.'},
    # --- windows ---
    'win.min_all_error':         {'ru': 'Не удалось свернуть все окна: {msg}', 'uk': 'Не вдалося згорнути всі вікна: {msg}'},
    'win.move_error':            {'ru': 'Не удалось переместить окно.', 'uk': 'Не вдалося перемістити вікно.'},
    # --- mouse ---
    'mouse.faster':              {'ru': 'Ускоряю. Множитель: {mult}', 'uk': 'Прискорюю. Множник: {mult}'},
    'mouse.slower':              {'ru': 'Замедляю. Множитель: {mult}', 'uk': 'Сповільнюю. Множник: {mult}'},
    # --- utils ---
    'bt.devices':                {'ru': 'Доступные устройства: {names}', 'uk': 'Доступні пристрої: {names}'},
    'bt.none':                   {'ru': 'Bluetooth устройств не найдено.', 'uk': 'Bluetooth пристроїв не знайдено.'},
    'bt.paired':                 {'ru': 'Спаренные устройства: {names}', 'uk': 'Спарені пристрої: {names}'},
    'bt.none_paired':            {'ru': 'Устройств не найдено.', 'uk': 'Пристроїв не знайдено.'},
    'git.no_repo':               {'ru': 'Репозиторий не найден. Откройте папку проекта.', 'uk': 'Репозиторій не знайдено. Відкрийте папку проекту.'},
    'git.nothing':               {'ru': 'Нет изменений для коммита.', 'uk': 'Немає змін для коміту.'},
    'git.cancelled':             {'ru': 'Коммит отменён.', 'uk': 'Коміт скасовано.'},
    'git.no_files':              {'ru': 'Вы не выбрали ни одного файла.', 'uk': 'Ви не вибрали жодного файлу.'},
    'reminder.ask_time':         {'ru': 'Я не понял, через какое время нужно напомнить.', 'uk': 'Я не зрозумів, через який час потрібно нагадати.'},
    # --- system (dynamic) ---
    'shutdown.timer_ok':         {'ru': 'Хорошо, компьютер выключится через {delay}.', 'uk': 'Добре, комп\'ютер вимкнеться через {delay}.'},
    'reminder.set_ok':           {'ru': 'Хорошо, напомню через {delay}.', 'uk': 'Добре, нагадаю через {delay}.'},
    'restart.jarvis_now':        {'ru': 'Перезапускаю, {address}. Буду снова в строю через несколько секунд.', 'uk': 'Перезапускаю, {address}. Буду готовий за кілька секунд.'},
    'listen.off_v2':             {'ru': 'Режим тишины: команды не выполняю. Скажите «слушай меня», чтобы вернуться.', 'uk': 'Режим тиші: команди не виконую. Скажіть «слухай мене», щоб повернутись.'},
    # --- files (dynamic) ---
    'files.access_error_e':      {'ru': 'Ошибка доступа к пути: {e}', 'uk': 'Помилка доступу до шляху: {e}'},
    'files.create_error_e':      {'ru': 'Ошибка доступа: {e}', 'uk': 'Помилка доступу: {e}'},
    'files.delete_error_e':      {'ru': 'Ошибка удаления: {e}', 'uk': 'Помилка видалення: {e}'},
    'files.ask_goto_v2':         {'ru': 'Скажите, куда зайти: например «зайди в папку проекты» или «зайди в загрузки».', 'uk': 'Скажіть, куди перейти: наприклад «відкрий папку проекти» або «відкрий завантаження».'},
    # --- info (dynamic) ---
    'translate.translating_v2':  {'ru': 'Перевожу на {lang}', 'uk': 'Перекладаю на {lang}'},
    'translate.problem':         {'ru': 'Проблема с переводом: {msg}', 'uk': 'Проблема з перекладом: {msg}'},
    'translate.result_v2':       {'ru': 'Это переводится как: {text}', 'uk': 'Це перекладається як: {text}'},
    # --- video ---
    'video.no_saved_v2':         {'ru': 'Сохранённое видео не найдено', 'uk': 'Збережене відео не знайдено'},
    'video.download_error_v2':   {'ru': 'Ошибка скачивания: {res}', 'uk': 'Помилка завантаження: {res}'},
    'video.ocr_error_v2':        {'ru': 'Ошибка распознавания: {res}', 'uk': 'Помилка розпізнавання: {res}'},
    'video.ask_monitor_v2':      {'ru': 'У вас несколько мониторов. На каком записывать?', 'uk': 'У вас кілька моніторів. На якому записувати?'},
    # --- mouse ---
    'mouse.faster_v2':           {'ru': 'Ускоряю. Множитель: {mult}', 'uk': 'Прискорюю. Множник: {mult}'},
    'mouse.slower_v2':           {'ru': 'Замедляю. Множитель: {mult}', 'uk': 'Сповільнюю. Множник: {mult}'},
    # --- utils dynamic ---
    'bt.devices_v2':             {'ru': 'Доступные устройства: {names}', 'uk': 'Доступні пристрої: {names}'},
    'bt.paired_v2':              {'ru': 'Спаренные устройства: {names}', 'uk': 'Спарені пристрої: {names}'},
    'reminder.notify_v2':        {'ru': '{Address}, вы просили напомнить: {msg}', 'uk': '{Address}, ви просили нагадати: {msg}'},
    'reminder.set_v2':           {'ru': 'Хорошо, напомню через {delay}', 'uk': 'Добре, нагадаю через {delay}'},
    # --- creative ---
    'ps.not_active_v2':          {'ru': 'Окно Photoshop не активно. Откройте Photoshop и сделайте его активным.', 'uk': 'Вікно Photoshop не активне. Відкрийте Photoshop і зробіть його активним.'},
    'ps.send_error_v2':          {'ru': 'Не получилось отправить команду в Photoshop. Проверьте, что Photoshop не запущен от администратора.', 'uk': 'Не вдалося надіслати команду в Photoshop. Перевірте, що Photoshop не запущено від адміністратора.'},
    'figma.send_error_v2':       {'ru': 'Не получилось отправить команду в Figma. Проверьте, что приложение не запущено от администратора.', 'uk': 'Не вдалося надіслати команду в Figma. Перевірте, що додаток не запущено від адміністратора.'},
    # --- integrations ---
    'net.ask_profile_v2':        {'ru': 'Скажите, например: переключи сеть на дом, на офис или на публичную сеть.', 'uk': 'Скажіть, наприклад: переключи мережу на дім, на офіс або на публічну мережу.'},
    'mail.error_v2':             {'ru': 'Не удалось открыть окно. Попробуйте кнопку «Почта» в интерфейсе.', 'uk': 'Не вдалося відкрити вікно. Спробуйте кнопку «Пошта» в інтерфейсі.'},
}


_response_bags: dict[str, tuple[frozenset, list[str], str | None]] = {}

def pick_response(key: str, options: list[str]) -> str:
    """Pick one of `options` without repeating an item until every other
    option has come up at least once — a 'shuffle bag'. Plain random.choice()
    on a short list (3-6 phrases) has a real chance of picking the same
    phrase 2-3 times in a row, which sounds broken/repetitive to a user even
    though it's "correctly" random.

    `key` must be a stable id for this specific list across calls (e.g.
    'social.praise') so the bag persists. If `options` changes between calls
    under the same key (e.g. the response language changed), the bag is
    rebuilt automatically.
    """
    if not options:
        return ''
    if len(options) == 1:
        return options[0]
    opt_set = frozenset(options)
    entry = _response_bags.get(key)
    if entry is None or entry[0] != opt_set or not entry[1]:
        bag = list(options)
        import random
        random.shuffle(bag)
        last = entry[2] if entry else None
        if last is not None and len(bag) > 1 and bag[-1] == last:
            bag[0], bag[-1] = bag[-1], bag[0]
        entry = (opt_set, bag, last)
    opt_set, bag, last = entry
    item = bag.pop()
    _response_bags[key] = (opt_set, bag, item)
    return item

def spk(key: str, **fmt) -> str:
    """Return spoken response in the current speech language (independent
    from the on-screen UI language — see core.i18n.get_speech_language),
    falling back to Russian."""
    from core.i18n import get_speech_language
    lang = get_speech_language()
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(lang) or entry.get('ru') or key
    if '{address' in text:
        from core.address import get_address
        addr = get_address(lang)
        fmt.setdefault('address', addr)
        fmt.setdefault('Address', addr.capitalize())
    return text.format(**fmt) if fmt else text
