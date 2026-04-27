from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein
import re
WORDS_TO_NUM = {'ноль': '0', 'один': '1', 'одна': '1', 'одну': '1', 'одно': '1', 'два': '2', 'две': '2', 'три': '3', 'четыре': '4', 'пять': '5', 'шесть': '6', 'семь': '7', 'восемь': '8', 'девять': '9', 'десять': '10', 'одиннадцать': '11', 'двенадцать': '12', 'тринадцать': '13', 'четырнадцать': '14', 'пятнадцать': '15', 'шестнадцать': '16', 'семнадцать': '17', 'восемнадцать': '18', 'девятнадцать': '19', 'двадцать': '20', 'тридцать': '30', 'сорок': '40', 'пятьдесят': '50', 'шестьдесят': '60', 'семьдесят': '70', 'восемьдесят': '80', 'девяносто': '90', 'сто': '100', 'полминуты': '30', 'первую': '1', 'вторую': '2', 'третью': '3', 'четвертую': '4', 'пятую': '5', 'шестую': '6', 'седьмую': '7', 'восьмую': '8', 'девятую': '9', 'последнюю': '9', 'первый': '1', 'второй': '2', 'третий': '3', 'четвертый': '4', 'пятый': '5', 'шестой': '6', 'седьмой': '7', 'восьмой': '8', 'девятый': '9', 'последний': '9', 'первая': '1', 'вторая': '2', 'третья': '3', 'четвертая': '4', 'пятая': '5', 'шестая': '6', 'седьмая': '7', 'восьмая': '8', 'девятая': '9', 'последняя': '9', 'первое': '1', 'второе': '2', 'третье': '3'}
_STT_GLUE_MAP = {'вай фай': 'вайфай', 'ваи фай': 'вайфай', 'ва й фай': 'вайфай', 'блю туз': 'блютуз', 'блю тус': 'блютуз', 'блу туз': 'блютуз', 'блу тус': 'блютуз', 'ю туб': 'ютуб', 'дис корд': 'дискорд', 'клип чемп': 'клипчемп', 'клип чамп': 'клипчемп', 'фото шоп': 'фотошоп', 'скрин шот': 'скриншот', 'энтер': 'энтер', 'джаравис': 'джарвис', 'джарверс': 'джарвис', 'джервис': 'джарвис', 'дарвис': 'джарвис', 'дарвиз': 'джарвис', 'дервис': 'джарвис', 'джаравиз': 'джарвис', 'джарвиз': 'джарвис', 'джокумент': 'документ', 'ворддокумент': 'ворд документ', 'вордокумент': 'ворд документ', 'вортдокумент': 'ворд документ', 'проджектс': 'projects', 'проджетс': 'projects', 'проекст': 'projects', 'проектс': 'projects', 'даунлоадс': 'downloads', 'даунлодс': 'downloads', 'документс': 'documents'}
_STT_GLUE_SORTED = sorted(_STT_GLUE_MAP.keys(), key=len, reverse=True)
_RE_DASHES   = re.compile(r'[—–\-]')
_RE_PUNCT    = re.compile(r'[.,!?;:]+')
_RE_SPACES   = re.compile(r'\s+')
_RE_N_TAG    = re.compile(r'\{N\}')
_PS_SHORT = {
    'покажи слои': 'ps_layers_panel',
    'покажи слой': 'ps_layers_panel',
    'слои': 'ps_layers_panel',
    'слой': 'ps_layers_panel',
    'покажи кисти': 'ps_brushes_panel',
    'покажи цвета': 'ps_color_panel',
    'покажи панель слоев': 'ps_layers_panel',
    'покажи панель кистей': 'ps_brushes_panel',
    'покажи панель цветов': 'ps_color_panel',
    'кисть': 'ps_brush',
    'возьми кисть': 'ps_brush',
    'выбери кисть': 'ps_brush',
    'инструмент кисть': 'ps_brush',
    'ластик': 'ps_eraser',
    'выбери ластик': 'ps_eraser',
    'инструмент ластик': 'ps_eraser',
    'перемещение': 'ps_move',
    'инструмент перемещение': 'ps_move',
    'текст': 'ps_text',
    'инструмент текст': 'ps_text',
    'пипетка': 'ps_eyedropper',
    'инструмент пипетка': 'ps_eyedropper',
    'прямоугольник': 'ps_marquee',
    'выделение прямоугольником': 'ps_marquee',
    'выделение': 'ps_lasso',
    'лассо': 'ps_lasso',
    'рука': 'ps_hand',
    'масштаб': 'ps_zoom',
    'зум': 'ps_zoom',
    'увеличить': 'ps_zoom_in',
    'уменьшить': 'ps_zoom_out',
    'по размеру': 'ps_fit',
    'сто процентов': 'ps_100',
    'отмена': 'ps_undo',
    'повтори': 'ps_redo',
    'сохранить': 'ps_save',
    'сохранить как': 'ps_save_as',
    'новый слой': 'ps_new_layer',
    'дубликат слоя': 'ps_dup_layer',
    'трансформация': 'ps_transform',
    'заливка': 'ps_fill',
    'снять выделение': 'ps_deselect',
    'выделить все': 'ps_select_all',
}
_PS_SHORT.update({
    'создай слой': 'ps_new_layer',
    'создать слой': 'ps_new_layer',
    'создай новый слой': 'ps_new_layer',
    'создать новый слой': 'ps_new_layer',
    'пипетку': 'ps_eyedropper',
    'возьми пипетку': 'ps_eyedropper',
    'выбери пипетку': 'ps_eyedropper',
    'инструмент пипетка': 'ps_eyedropper',
    'возьми инструмент пипетка': 'ps_eyedropper',
    'выбери инструмент пипетка': 'ps_eyedropper',
})
_FIGMA_SHORT = {
    'фрейм': 'figma_frame',
    'рамка': 'figma_frame',
    'прямоугольник': 'figma_rect',
    'круг': 'figma_ellipse',
    'линия': 'figma_line',
    'стрелка': 'figma_arrow',
    'перо': 'figma_pen',
    'текст': 'figma_text',
    'рука': 'figma_hand',
    'масштаб': 'figma_zoom',
    'зум': 'figma_zoom',
    'увеличить': 'figma_zoom_in',
    'уменьшить': 'figma_zoom_out',
    'по размеру': 'figma_fit',
    'отмена': 'figma_undo',
    'повтори': 'figma_redo',
    'сохранить': 'figma_save',
    'дубликат': 'figma_duplicate',
    'группа': 'figma_group',
    'сгруппировать': 'figma_group',
    'разгруппировать': 'figma_ungroup',
    'автолейаут': 'figma_auto_layout',
    'компонент': 'figma_component',
    'экспорт': 'figma_export',
    'копировать': 'figma_copy',
    'вставить': 'figma_paste',
    'показать интерфейс': 'figma_toggle_ui',
    'показать ui': 'figma_toggle_ui',
}
def _normalize_stt(text: str) -> str:
    text = text.lower().strip()
    text = _RE_DASHES.sub(' ', text)
    text = _RE_PUNCT.sub('', text)
    text = _RE_SPACES.sub(' ', text).strip()
    for src in _STT_GLUE_SORTED:
        if src in text: text = text.replace(src, _STT_GLUE_MAP[src])
    text = text.replace('игррвой', 'игровой')
    text = text.replace('игрвой', 'игровой')
    text = text.replace('игрровой', 'игровой')
    text = text.replace('игрови', 'игровой')
    text = text.replace('игровй', 'игровой')
    return text
CANON_SIMPLE = {'джарвис': 'wake', 'бобик': 'wake', 'джервис': 'wake', 'дарвис': 'wake', 'джаравис': 'wake', 'джарвиз': 'wake', 'джарверс': 'wake',
               'стоп': 'media_pause', 'пауза': 'media_pause', 'продолжай': 'media_play', 'продолжить': 'media_play', 'хватит': 'media_pause', 'останови': 'media_pause',
               'продолжай в ютубе': 'media_play_youtube', 'продолжить в ютубе': 'media_play_youtube', 
               'продолжай в youtube': 'media_play_youtube', 'продолжить в youtube': 'media_play_youtube',
               'пауза в ютубе': 'media_pause_youtube', 'стоп в ютубе': 'media_pause_youtube',
               'продолжай в браузере': 'media_play_browser', 'продолжить в браузере': 'media_play_browser',
               'пауза в браузере': 'media_pause_browser', 'стоп в браузере': 'media_pause_browser',
               'стоп мышка': 'media_pause', 'полный экран': 'yt_full', 'видео на весь экран': 'yt_full', 'плеер на весь экран': 'yt_full', 'ютуб на весь экран': 'yt_full', 'youtube на весь экран': 'yt_full', 'на весь экран': 'max_win', 'вперед': 'yt_fwd', 'вперёд': 'yt_fwd', 'дальше': 'yt_fwd', 'назад': 'yt_bwd', 'закрой': 'context_close', 'следующее видео': 'yt_next', 'следующий ролик': 'yt_next', 'предыдущее видео': 'yt_prev', 'предыдущий ролик': 'yt_prev', 'громче': 'vol_up', 'погромче': 'vol_up', 'тише': 'vol_down', 'потише': 'vol_down', 'скриншот': 'screenshot', 'правее': 'mouse_right', 'право': 'mouse_right', 'вправо': 'mouse_right', 'левее': 'mouse_left', 'лево': 'mouse_left', 'влево': 'mouse_left', 'выше': 'mouse_up', 'наверх': 'mouse_up', 'вверх': 'mouse_up', 'ниже': 'mouse_down', 'вниз': 'mouse_down', 'быстрее': 'mouse_faster', 'быстрей': 'mouse_faster', 'ускорь': 'mouse_faster', 'медленнее': 'mouse_slower', 'медленее': 'mouse_slower', 'помедленнее': 'mouse_slower', 'нажимай': 'mouse_click', 'нажми': 'mouse_click', 'клик': 'mouse_click', 'двойной клик': 'mouse_dblclick', 'молодец': 'praise', 'ты молодец': 'praise', 'умница': 'praise', 'красавчик': 'praise', 'хорошая работа': 'praise', 'отличная работа': 'praise', 'перезагрузка': 'restart', 'перезагрузись': 'restart', 'скопируй': 'clip_copy', 'скопируй это': 'clip_copy', 'копируй': 'clip_copy', 'вставь': 'clip_paste', 'вставь это': 'clip_paste', 'вставить': 'clip_paste', 'ставь': 'clip_paste', 'вырежи': 'clip_cut', 'вырежи это': 'clip_cut', 'вырезать': 'clip_cut', 'отмени': 'undo', 'отмена': 'undo', 'назад действие': 'undo', 'повтори действие': 'redo', 'верни действие': 'redo', 'выдели всё': 'select_all', 'выдели все': 'select_all', 'буфер обмена': 'clip_history', 'открой буфер': 'clip_history', 'открой буфер обмена': 'clip_history', 'вставь последний элемент': 'clip_paste_last', 'вставь предпоследний элемент': 'clip_paste_prev', 'режим диктовки': 'dictation_on', 'начни диктовку': 'dictation_on', 'диктовка': 'dictation_on', 'печатай за мной': 'dictation_on', 'начинай печатать': 'dictation_on', 'очисти корзину': 'empty_trash', 'создай папку': 'create_folder', 'создай новую папку': 'create_folder', 'создать папку': 'create_folder', 'создать новую папку': 'create_folder', 'создай документ': 'create_word_doc', 'создай файл': 'create_word_doc', 'создать документ': 'create_word_doc', 'создать файл': 'create_word_doc', 'удали папку': 'delete_folder', 'запиши': 'note_save', 'запиши идею': 'note_save', 'сделай заметку': 'note_save', 'сохрани заметку': 'note_save', 'запомни': 'note_save', 'отмени напоминание': 'cancel_reminder', 'отменить напоминание': 'cancel_reminder', 'убери напоминание': 'cancel_reminder', 'отключи напоминание': 'cancel_reminder', 'распознай текст': 'ocr_screen', 'прочитай экран': 'ocr_screen', 'скопируй текст с экрана': 'ocr_screen', 'скопируй текст со скрина': 'ocr_last', 'текст со скриншота': 'ocr_last', 'прочитай скриншот': 'ocr_last', 'зайди в загрузки': 'explorer_goto', 'открой загрузки': 'explorer_goto', 'зайди в видео': 'explorer_goto', 'открой видео': 'explorer_goto', 'зайди в фото': 'explorer_goto', 'открой фото': 'explorer_goto', 'зайди в документы': 'explorer_goto', 'открой документы': 'explorer_goto', 'зайди в музыку': 'explorer_goto', 'открой музыку': 'explorer_goto', 'зайди в корзину': 'explorer_goto', 'открой корзину': 'explorer_goto', 'зайди на рабочий стол': 'explorer_goto', 'открой рабочий стол': 'explorer_goto', 'проводник': 'explorer_goto', 'открой проводник': 'explorer_goto', 'открой последний документ': 'recent_doc', 'открой последнюю таблицу': 'recent_sheet', 'открой последнюю презентацию': 'recent_pres', 'открой последний файл': 'recent_any', 'открой предпоследний документ': 'recent_doc_prev', 'открой предпоследнюю таблицу': 'recent_sheet_prev', 'открой предпоследнюю презентацию': 'recent_pres_prev', 'открой предпоследний файл': 'recent_any_prev', 'открой последнее видео': 'open_last_video', 'открой последний ролик': 'open_last_video', 'открой последнюю запись': 'open_last_video', 'покажи последнее видео': 'open_last_video', 'покажи последнюю запись': 'open_last_video', 'воспроизведи видео': 'open_last_video', 'запусти последнее видео': 'open_last_video', 'открой последнее видео в клипчамп': 'open_last_video', 'открой видео в клипчамп': 'open_last_video', 'открой последнее видео в плеере': 'open_last_video', 'открой последнее видео в медиаплеере': 'open_last_video', 'открой последнее видео в ютубе': 'yt_last_watched', 'покажи последнее видео в ютубе': 'yt_last_watched', 'открой последний ролик в ютубе': 'yt_last_watched', 'покажи последний ролик в ютубе': 'yt_last_watched', 'что я смотрел в ютубе': 'yt_last_watched', 'последнее просмотренное видео': 'yt_last_watched', 'открой историю ютуба': 'yt_last_watched', 'открой диспетчер задач': 'open_task_manager', 'запусти диспетчер задач': 'open_task_manager', 'покажи диспетчер задач': 'open_task_manager', 'диспетчер задач': 'open_task_manager', 'открой таск менеджер': 'open_task_manager', 'открой обс': 'open_obs', 'запусти обс': 'open_obs', 'открой obs': 'open_obs', 'запусти obs': 'open_obs', 
'открой браузер': 'open_browser', 'запусти браузер': 'open_browser',
'открой дискорд': 'open_discord', 'запусти дискорд': 'open_discord', 'открой discord': 'open_discord', 'запусти discord': 'open_discord',
'открой телеграм': 'open_telegram', 'запусти телеграм': 'open_telegram', 'открой телегу': 'open_telegram',
'открой фотошоп': 'open_photoshop', 'запусти фотошоп': 'open_photoshop',
'открой стим': 'open_steam', 'запусти стим': 'open_steam',
'открой код': 'open_vscode', 'запусти код': 'open_vscode', 'открой vscode': 'open_vscode',
'открой вайбер': 'open_viber', 'запусти вайбер': 'open_viber',
'открой вотсап': 'open_whatsapp', 'запусти вотсап': 'open_whatsapp',
'открой эксель': 'open_excel', 'запусти эксель': 'open_excel',
'открой ворд': 'open_word', 'запусти ворд': 'open_word',
'открой курсор': 'open_antigravity', 'запусти курсор': 'open_antigravity',
'найди документ': 'find_doc', 'найди таблицу': 'find_sheet', 'найди файл': 'find_file', 'покажи хад': 'show_hud', 'открой хад': 'show_hud', 'покажи интерфейс': 'show_hud',
'открой интерфейс': 'show_hud', 'открой джарвиса': 'show_hud', 'покажи джарвиса': 'show_hud',
'верни хад': 'show_hud', 'хад покажи': 'show_hud',
'помощь': 'show_help', 'покажи помощь': 'show_help', 'открой помощь': 'show_help',
'что ты умеешь': 'show_help', 'что ты можешь': 'show_help',
'расскажи о себе': 'show_help', 'расскажи что умеешь': 'show_help',
'покажи руководство': 'show_help', 'открой руководство': 'show_help',
'покажи возможности': 'show_help', 'что ты знаешь': 'show_help',
    'сверни все окна': 'min_all',
    'свернуть все окна': 'min_all',
    'сверни всё': 'min_all',
    'удали файл': 'delete_file',
    'удали документ': 'delete_file',
    'сотри файл': 'delete_file',
'перезапусти джарвиса': 'restart_jarvis', 'перезапустить джарвиса': 'restart_jarvis',
'перезагрузи джарвиса': 'restart_jarvis', 'перезапусти джарвис': 'restart_jarvis',
'перезапустить джарвис': 'restart_jarvis', 'перезагрузить джарвиса': 'restart_jarvis',
'го в ets': 'game_mode_on', 'го в etс': 'game_mode_on', 'го в ets2': 'game_mode_on',
'го в етс': 'game_mode_on', 'го в ets 2': 'game_mode_on',
'го в евро трак': 'game_mode_on', 'го в евротрак': 'game_mode_on',
'го в трак': 'game_mode_on', 'го в трак симулятор': 'game_mode_on',
'запусти евро трак': 'game_mode_on', 'запусти ets': 'game_mode_on',
'запусти ets2': 'game_mode_on', 'включи евро трак': 'game_mode_on',
'играть в ets': 'game_mode_on', 'играть в евро трак': 'game_mode_on',
'хочу в ets': 'game_mode_on', 'хочу в евро трак': 'game_mode_on',
'го в фс': 'game_mode_on', 'го в фс22': 'game_mode_on', 'го в фс25': 'game_mode_on',
'го в фарминг': 'game_mode_on', 'го в ферму': 'game_mode_on',
'го в farming': 'game_mode_on', 'го в fs22': 'game_mode_on', 'го в fs25': 'game_mode_on',
'запусти фарминг': 'game_mode_on', 'запусти фс': 'game_mode_on',
'включи фарминг': 'game_mode_on', 'играть в фарминг': 'game_mode_on',
'хочу в фарминг': 'game_mode_on', 'хочу в ферму': 'game_mode_on',
'го в хогвартс': 'game_mode_on', 'го в хог': 'game_mode_on',
'запусти хогвартс': 'game_mode_on', 'включи хогвартс': 'game_mode_on',
'играть в хогвартс': 'game_mode_on',
 'охраняй': 'guard_on', 'режим охраны': 'guard_on', 'включи охрану': 'guard_on', 'вольно': 'guard_off', 'отбой охраны': 'guard_off', 'выключи охрану': 'guard_off', 'игровой режим': 'game_mode_on', 'режим игры': 'game_mode_on', 'активируй игровой режим': 'game_mode_on', 'подготовь к игре': 'game_mode_on', 'выйди из игрового режима': 'game_mode_off', 'отключи игровой режим': 'game_mode_off', 'отмени игровой режим': 'game_mode_off', 'отмени режим': 'game_mode_off', 'выключи игровой режим': 'game_mode_off', 'выйди из игры': 'game_mode_off', 'отмени режим игры': 'game_mode_off', 'конец игры': 'game_mode_off', 'игра окончена': 'game_mode_off', 'верни обычный режим': 'game_mode_off', 'который час': 'time_now', 'сколько время': 'time_now', 'скажи время': 'time_now', 'время': 'time_now', 'текущее время': 'time_now', 'сколько сейчас времени': 'time_now', 'статус системы': 'system_status', 'состояние системы': 'system_status', 'как система': 'system_status', 'отчет о системе': 'system_status', 'системный статус': 'system_status', 'переключи звук на': 'audio_switch', 'звук на колонки': 'audio_switch', 'звук на наушники': 'audio_switch', 'включи режим экономии': 'economy_on', 'активируй режим экономии': 'economy_on', 'отключи режим экономии': 'economy_off', 'отмени режим экономии': 'economy_off', 'сделай уборку': 'system_cleanup', 'приберись': 'system_cleanup', 'уборка': 'system_cleanup', 'проверь интернет': 'internet_speed', 'скорость интернета': 'internet_speed', 'какая скорость интернета': 'internet_speed', 'тест интернета': 'internet_speed', 'убавь яркость': 'brightness_down', 'уменьши яркость': 'brightness_down', 'сделай потемнее': 'brightness_down', 'яркость на': 'brightness_set', 'сделай яркость на': 'brightness_set', 'установи яркость на': 'brightness_set', 'не слушай меня': 'listen_off', 'не слушай': 'listen_off', 'перестань слушать': 'listen_off',
'режим тишины': 'listen_off', 'включи режим тишины': 'listen_off', 'активируй режим тишины': 'listen_off',
'уйди в спячку': 'listen_off', 'иди в спячку': 'listen_off', 'иди спать': 'listen_off',
'джарвис молчи': 'listen_off', 'джарвис стой': 'listen_off', 'подожди меня': 'listen_off',
'не подслушивай': 'listen_off', 'не мешай': 'listen_off', 'не слушай нас': 'listen_off',
'я говорю не с тобой': 'listen_off', 'это не тебе': 'listen_off',
'стоп слушать': 'listen_off', 'выключи прослушивание': 'listen_off',
'жди': 'listen_off', 'подожди': 'listen_off', 'подождите': 'listen_off',
 'слушай меня': 'listen_on', 'начни слушать': 'listen_on', 'как ты': 'how_are_you', 'как дела': 'how_are_you', 'как самочувствие': 'how_are_you', 'слушай': 'listen_on', 'скачай': 'download_video', 'скачать': 'download_video', 'загрузи': 'download_video', 'сохрани': 'save_video', 'сохрани видео': 'save_video', 'запомни видео': 'save_video', 'джарвис скачай': 'download_video', 'джарвис скачай это видео': 'download_video', 'джарвис открой последнее видео на ютубе': 'yt_last_watched', 'открой последнее видео на ютубе': 'yt_last_watched', 'покажи последнее видео на ютубе': 'yt_last_watched', 'что я смотрел на ютубе': 'yt_last_watched', 'открой ютуб историю': 'yt_last_watched', 'покажи ютуб историю': 'yt_last_watched', 'открой сохраненное видео': 'open_saved', 'открой сохранённое видео': 'open_saved',
'открой первое сохранённое видео': 'open_saved', 'открой первое сохраненное видео': 'open_saved',
'открой второе сохранённое видео': 'open_saved', 'открой второе сохраненное видео': 'open_saved',
'открой третье сохранённое видео': 'open_saved', 'открой третье сохраненное видео': 'open_saved',
'открой четвёртое сохранённое видео': 'open_saved', 'открой четвертое сохраненное видео': 'open_saved',
'открой пятое сохранённое видео': 'open_saved', 'открой пятое сохраненное видео': 'open_saved',
'открой шестое сохранённое видео': 'open_saved', 'открой шестое сохраненное видео': 'open_saved',
'открой седьмое сохранённое видео': 'open_saved', 'открой седьмое сохраненное видео': 'open_saved',
'открой восьмое сохранённое видео': 'open_saved', 'открой восьмое сохраненное видео': 'open_saved',
'открой девятое сохранённое видео': 'open_saved', 'открой девятое сохраненное видео': 'open_saved',
'открой десятое сохранённое видео': 'open_saved', 'открой десятое сохраненное видео': 'open_saved',
'открой последнее сохранённое видео': 'open_saved', 'открой последнее сохраненное видео': 'open_saved',
'открой 1 сохранённое видео': 'open_saved', 'открой 1 сохраненное видео': 'open_saved',
'открой 2 сохранённое видео': 'open_saved', 'открой 2 сохраненное видео': 'open_saved',
'открой 3 сохранённое видео': 'open_saved', 'открой 3 сохраненное видео': 'open_saved',
'открой 4 сохранённое видео': 'open_saved', 'открой 4 сохраненное видео': 'open_saved',
'открой 5 сохранённое видео': 'open_saved', 'открой 5 сохраненное видео': 'open_saved',
'открой 6 сохранённое видео': 'open_saved', 'открой 6 сохраненное видео': 'open_saved',
'открой 7 сохранённое видео': 'open_saved', 'открой 7 сохраненное видео': 'open_saved',
'открой 8 сохранённое видео': 'open_saved', 'открой 8 сохраненное видео': 'open_saved',
'открой 9 сохранённое видео': 'open_saved', 'открой 9 сохраненное видео': 'open_saved',
    'открой ютуб': 'open_youtube', 'запусти ютуб': 'open_youtube', 'включи ютуб': 'open_youtube', 'открой youtube': 'open_youtube', 'запусти youtube': 'open_youtube', 'открой ютубчик': 'open_youtube',
    'джарвис открой ютуб': 'open_youtube', 'джарвис запусти ютуб': 'open_youtube', 'джарвис открой youtube': 'open_youtube',
    'покажи хад': 'show_hud', 'открой хад': 'show_hud', 'покажи худ': 'show_hud', 'открой худ': 'show_hud', 'открйо худ': 'show_hud', 'покажи интерфейс': 'show_hud', 'открой интерфейс': 'show_hud', 'разверни худ': 'show_hud', 'разверни хад': 'show_hud',
    'скрой худ': 'min_win', 'сверни худ': 'min_win', 'убери худ': 'min_win', 'закрой худ': 'min_win',
'открой настройки': 'open_settings', 'покажи настройки': 'open_settings', 'настройки системы': 'open_settings',
'установи город': 'set_weather_city', 'запомни город': 'set_weather_city', 'смени город': 'set_weather_city', 'мой город': 'set_weather_city',
'открой макросы': 'open_keybinds', 'открой клавиши': 'open_keybinds', 'настрой клавиши': 'open_keybinds', 'бинды': 'open_keybinds', 'настройка кнопок': 'open_keybinds',
    'открой расширения': 'open_extensions', 'покажи расширения': 'open_extensions', 'центр модулей': 'open_extensions',
    'мониторинг ресурсов': 'open_perf', 'открой мониторинг': 'open_perf', 'покажи нагрузку': 'open_perf', 'статус ресурсов': 'open_perf',
    'перезапусти джарвиса': 'restart_jarvis', 'перезагрузи джарвиса': 'restart_jarvis', 'перезапусти джарвис': 'restart_jarvis'
}
_INSULT = 'system_insult'


CANON_SIMPLE.update({'правее': 'mouse_right', 'левее': 'mouse_left', 'выше': 'mouse_up', 'ниже': 'mouse_down', 'быстрее': 'mouse_faster', 'медленнее': 'mouse_slower', 'ускорь': 'mouse_faster', 'замедли': 'mouse_slower', 'стоп': 'media_pause', 'хватит': 'media_pause', 'остановись': 'media_pause', 'замри': 'media_pause', 
    'ты дурак': _INSULT, 'ты дура': _INSULT, 'дурак': _INSULT,
    'автолейаут': 'figma_auto_layout', 'сгруппируй': 'figma_group', 'кисть': 'ps_brush', 'ластик': 'ps_eraser'
})

COMMAND_PATTERNS = [
    {'id': 'system_status', 'keywords': ['статус', 'система'], 'verbs': ['как'], 'patterns': ['как система', 'статус системы'], 'min_score': 75, 'description': 'Анализ текущей нагрузки на процессор, видеокарту и ОЗУ с выводом отчета', 'example': 'Джарвис, статус системы'},
    {'id': 'system_specs', 'keywords': ['характеристики', 'железо'], 'verbs': ['какое'], 'patterns': ['характеристики компьютера', 'какое железо'], 'min_score': 75, 'description': 'Технический обзор комплектующих: модель процессора, объем ОЗУ и видеокарта', 'example': 'Джарвис, характеристики компьютера'},
    {'id': 'shutdown_timer', 'keywords': ['выключи', 'через'], 'verbs': [], 'patterns': ['выключи через {N} минут', 'выключи пк через час'], 'min_score': 75, 'description': 'Планирование автоматического завершения работы через таймер обратного отсчета', 'example': 'Джарвис, выключи через полчаса'},
    {'id': 'cancel_timer', 'keywords': ['отмени', 'выключение'], 'verbs': [], 'patterns': ['отмени выключение', 'не выключай компьютер'], 'min_score': 75, 'description': 'Отмена активного запланированного выключения или перезагрузки', 'example': 'Джарвис, отмени выключение'},
    {'id': 'shutdown', 'keywords': ['компьютер'], 'verbs': ['выключи'], 'patterns': ['выключи компьютер', 'выключи пк'], 'min_score': 75, 'description': 'Безопасное завершение работы Windows и выключение питания ПК', 'example': 'Джарвис, выключи компьютер'},
    {'id': 'restart', 'keywords': ['систему'], 'verbs': ['перезагрузи'], 'patterns': ['перезагрузи компьютер', 'перезагрузи систему'], 'min_score': 75, 'description': 'Принудительная перезагрузка ОС для исправления программных ошибок', 'example': 'Джарвис, перезагрузи систему'},
    {'id': 'system_cleanup', 'keywords': ['уборку', 'мусор'], 'verbs': ['сделай', 'очисти'], 'patterns': ['сделай уборку', 'очисти компьютер от мусора'], 'min_score': 75, 'description': 'Очистка системного кэша и временных файлов для освобождения места на диске', 'example': 'Джарвис, сделай уборку'},
    {'id': 'empty_trash', 'keywords': ['корзину'], 'verbs': ['очисти'], 'patterns': ['очисти корзину', 'выброси мусор из корзины'], 'min_score': 75, 'description': 'Безвозвратное удаление всех объектов из корзины Windows', 'example': 'Джарвис, очисти корзину'},
    {'id': 'economy_on', 'keywords': ['экономию'], 'verbs': ['включи'], 'patterns': ['включи режим экономии', 'экономь батарею'], 'min_score': 75, 'description': 'Снижение энергопотребления за счет яркости экрана и частоты процессора', 'example': 'Джарвис, включи экономию'},
    {'id': 'wifi_toggle', 'keywords': ['вай', 'фай', 'вайфай'], 'verbs': ['включи', 'выключи', 'отключи'], 'patterns': ['выключи вай фай', 'выключи вайфай', 'отключи интернет'], 'min_score': 75, 'description': 'Программное управление состоянием Wi-Fi адаптера', 'example': 'Джарвис, выключи вай фай'},
    {'id': 'bluetooth_toggle', 'keywords': ['блютуз'], 'verbs': ['включи', 'выключи', 'отключи'], 'patterns': ['выключи блютуз', 'включи блютуз'], 'min_score': 75, 'description': 'Управление модулем Bluetooth для подключения устройств', 'example': 'Джарвис, включи блютуз'},
    {'id': 'internet_speed', 'keywords': ['скорость', 'интернета'], 'verbs': ['проверь'], 'patterns': ['проверь скорость интернета', 'какой интернет'], 'min_score': 75, 'description': 'Замер пропускной способности сети и пинга до сервера', 'example': 'Джарвис, проверь интернет'},
    {'id': 'vol_up', 'keywords': ['громче', 'звук'], 'verbs': ['сделай'], 'patterns': ['сделай погромче', 'добавь звука'], 'min_score': 75, 'description': 'Увеличение уровня громкости системных динамиков на 10%', 'example': 'Джарвис, сделай погромче'},
    {'id': 'vol_down', 'keywords': ['тише', 'звук'], 'verbs': ['сделай'], 'patterns': ['сделай потише', 'убавь звук'], 'min_score': 75, 'description': 'Снижение уровня громкости системных динамиков на 10%', 'example': 'Джарвис, сделай потише'},
    {'id': 'vol_mute', 'keywords': ['звук'], 'verbs': ['выключи'], 'patterns': ['выключи звук', 'тишина'], 'min_score': 75, 'description': 'Мгновенное отключение звука на всех активных устройствах', 'example': 'Джарвис, выключи звук'},
    {'id': 'vol_set', 'keywords': ['громкость'], 'verbs': ['поставь'], 'patterns': ['громкость на 50', 'звук на 20'], 'min_score': 75, 'description': 'Установка точного уровня громкости в процентах', 'example': 'Джарвис, громкость на 40'},
    {'id': 'audio_switch', 'keywords': ['колонки', 'наушники'], 'verbs': ['переключи'], 'patterns': ['звук на наушники', 'звук на колонки'], 'min_score': 75, 'description': 'Перенаправление звукового потока между колонками и наушниками', 'example': 'Джарвис, звук на наушники'},
    {'id': 'brightness_set', 'keywords': ['яркость'], 'verbs': ['поставь'], 'patterns': ['яркость на 70', 'сделай экран ярче'], 'min_score': 75, 'description': 'Настройка уровня подсветки монитора в процентном соотношении', 'example': 'Джарвис, яркость на 80'},
    {'id': 'create_folder', 'keywords': ['папку'], 'verbs': ['создай'], 'patterns': ['создай папку', 'сделай новую папку'], 'min_score': 75, 'description': 'Создание новой папки в текущем пути с именованием голосом', 'example': 'Джарвис, создай папку Проекты'},
    {'id': 'delete_file', 'keywords': ['файл'], 'verbs': ['удали'], 'patterns': ['удали файл', 'сотри этот файл'], 'min_score': 75, 'description': 'Перемещение выбранного файла из текущей папки в корзину', 'example': 'Джарвис, удали файл заметка'},
    {'id': 'explorer_go_up', 'keywords': ['папки', 'назад'], 'verbs': ['выйди', 'наверх'], 'patterns': ['выйди из папки', 'на уровень выше'], 'min_score': 75, 'description': 'Навигация в проводнике: возврат в родительскую директорию', 'example': 'Джарвис, выйди из папки'},
    {'id': 'create_word_doc', 'keywords': ['документ', 'ворд'], 'verbs': ['создай'], 'patterns': ['создай ворд', 'сделай новый документ'], 'min_score': 75, 'description': 'Создание и автоматическое открытие нового файла Word или Excel', 'example': 'Джарвис, создай документ ворд'},
    {'id': 'find_doc', 'keywords': ['документ'], 'verbs': ['найди'], 'patterns': ['найди документ', 'открой файл'], 'min_score': 75, 'description': 'Поиск файла по названию среди документов и его запуск', 'example': 'Джарвис, найди документ Отчет'},
    {'id': 'paste_file', 'keywords': ['файл'], 'verbs': ['вставь'], 'patterns': ['вставь файл', 'вставь последний файл'], 'min_score': 75, 'description': 'Вставка в текущую папку последнего скачанного или созданного файла', 'example': 'Джарвис, вставь файл'},
    {'id': 'min_all', 'keywords': ['окна'], 'verbs': ['сверни'], 'patterns': ['сверни все окна', 'покажи рабочий стол'], 'min_score': 75, 'description': 'Свертывание всех открытых приложений на панель задач', 'example': 'Джарвис, сверни всё'},
    {'id': 'close_win', 'keywords': ['окно'], 'verbs': ['закрой'], 'patterns': ['закрой окно', 'закрой это'], 'min_score': 75, 'description': 'Завершение работы активного окна (эквивалент Alt+F4)', 'example': 'Джарвис, закрой это'},
    {'id': 'win_snap_left', 'keywords': ['влево'], 'verbs': ['окно'], 'patterns': ['окно влево', 'прижми влево'], 'min_score': 75, 'description': 'Привязка активного окна к левой половине экрана', 'example': 'Джарвис, окно влево'},
    {'id': 'win_snap_right', 'keywords': ['вправо'], 'verbs': ['окно'], 'patterns': ['окно вправо', 'прижми вправо'], 'min_score': 75, 'description': 'Привязка активного окна к правой половине экрана', 'example': 'Джарвис, окно вправо'},
    {'id': 'ps_brush', 'keywords': ['кисть'], 'verbs': ['возьми'], 'patterns': ['возьми кисть', 'дай кисточку'], 'min_score': 75, 'description': 'Выбор основного инструмента рисования «Кисть» (B) в Photoshop', 'example': 'Джарвис, кисть'},
    {'id': 'ps_eraser', 'keywords': ['ластик'], 'verbs': ['возьми'], 'patterns': ['дай ластик', 'возьми стерку'], 'min_score': 75, 'description': 'Выбор инструмента «Ластик» (E) для стирания в Photoshop', 'example': 'Джарвис, ластик'},
    {'id': 'ps_save', 'keywords': ['проект'], 'verbs': ['сохрани'], 'patterns': ['сохрани проект', 'сохрани в фотошопе'], 'min_score': 75, 'description': 'Сохранение текущего состояния холста в файл .PSD (Ctrl+S)', 'example': 'Джарвис, сохрани проект'},
    {'id': 'figma_auto_layout', 'keywords': ['лейаут'], 'verbs': ['сделай'], 'patterns': ['сделай автолейаут', 'добавь лейаут'], 'min_score': 75, 'description': 'Применение функции Auto Layout к выделению в Figma (Shift+A)', 'example': 'Джарвис, автолейаут'},
    {'id': 'figma_group', 'keywords': ['сгруппируй'], 'verbs': [], 'patterns': ['сгруппируй', 'сделай группу'], 'min_score': 75, 'description': 'Объединение выделенных слоев в группу в Figma (Ctrl+G)', 'example': 'Джарвис, сгруппируй'},
    {'id': 'mouse_right', 'keywords': ['право'], 'verbs': ['веди'], 'patterns': ['мышка вправо', 'правее'], 'min_score': 75, 'description': 'Начало непрерывного движения курсора мыши вправо', 'example': 'Джарвис, мышка вправо'},
    {'id': 'media_pause', 'keywords': ['стоп', 'пауза'], 'verbs': ['останови', 'замри'], 'patterns': ['стоп', 'замри', 'хватит', 'поставь на паузу', 'останови видео'], 'min_score': 75, 'description': 'Мгновенная остановка движения курсора мыши или пауза медиа/видео', 'example': 'Джарвис, стоп'},
    {'id': 'media_play', 'keywords': ['продолжай', 'продолжить'], 'verbs': ['играй'], 'patterns': ['продолжай', 'продолжить видео', 'сними с паузы'], 'min_score': 75, 'description': 'Продолжение воспроизведения медиа/видео', 'example': 'Джарвис, продолжай'},
    {'id': 'mouse_faster', 'keywords': ['быстрее'], 'verbs': [], 'patterns': ['быстрее', 'ускорь мышку'], 'min_score': 75, 'description': 'Увеличение скорости движения курсора в 1.5 раза', 'example': 'Джарвис, быстрее'},
    {'id': 'weather', 'keywords': ['погода'], 'verbs': ['какая'], 'patterns': ['какая погода', 'температура на улице'], 'min_score': 75, 'description': 'Запрос текущего состояния погоды и прогноза температуры', 'example': 'Джарвис, какая погода?'},
    {'id': 'reminder', 'keywords': ['напомни'], 'verbs': [], 'patterns': ['напомни через {N} минут', 'напомни через {N} часа', 'напомни через час', 'сделай напоминание'], 'min_score': 75, 'description': 'Установка голосового напоминания с обратным отсчетом', 'example': 'Джарвис, напомни через 10 минут'},
    {'id': 'google_search', 'keywords': ['гугле'], 'verbs': ['найди'], 'patterns': ['найди в гугле', 'поиск в интернете'], 'min_score': 75, 'description': 'Автоматический поиск заданного запроса в поисковой системе Google', 'example': 'Джарвис, найди в гугле рецепт'},
    {'id': 'git_commit', 'keywords': ['коммит'], 'verbs': ['сделай'], 'patterns': ['сделай коммит', 'отправь изменения'], 'min_score': 75, 'description': 'Автоматизация Git: добавление всех файлов, коммит и пуш в облако', 'example': 'Джарвис, сделай коммит'},
    {'id': 'open_browser', 'keywords': ['браузер'], 'verbs': ['открой', 'запусти'], 'patterns': ['открой браузер', 'запусти браузер'], 'min_score': 75, 'description': 'Открытие веб-браузера', 'example': 'Джарвис, открой браузер'},
    {'id': 'open_discord', 'keywords': ['дискорд', 'discord'], 'verbs': ['открой', 'запусти'], 'patterns': ['открой дискорд', 'запусти дискорд'], 'min_score': 75, 'description': 'Открытие Discord', 'example': 'Джарвис, открой дискорд'},
    {'id': 'open_telegram', 'keywords': ['телеграм', 'телегу', 'telegram'], 'verbs': ['открой', 'запусти'], 'patterns': ['открой телеграм', 'запусти телегу'], 'min_score': 75, 'description': 'Открытие Telegram', 'example': 'Джарвис, открой телеграм'},
    {'id': 'open_photoshop', 'keywords': ['фотошоп', 'photoshop'], 'verbs': ['открой', 'запусти'], 'patterns': ['открой фотошоп', 'запусти фотошоп'], 'min_score': 75, 'description': 'Открытие Adobe Photoshop', 'example': 'Джарвис, открой фотошоп'},
    {'id': 'open_steam', 'keywords': ['стим', 'steam'], 'verbs': ['открой', 'запусти'], 'patterns': ['открой стим', 'запусти стим'], 'min_score': 75, 'description': 'Открытие Steam', 'example': 'Джарвис, открой стим'},
    {'id': 'play_yt', 'keywords': ['песню', 'видео', 'музыку', 'песня', 'трек', 'клип', 'ютубе', 'ютуб', 'youtube'], 'verbs': ['включи', 'поставь', 'найди'], 'patterns': ['включи песню', 'поставь видео', 'найди музыку', 'включи клип', 'включи на ютубе'], 'min_score': 70, 'description': 'Поиск и воспроизведение видео или музыки на YouTube', 'example': 'Джарвис, включи песню Linkin Park'},
    {'id': 'yt_channel', 'keywords': ['канал', 'канала'], 'verbs': ['открой', 'покажи', 'найди'], 'patterns': ['открой канал', 'покажи канал на ютубе', 'запусти канал'], 'min_score': 75, 'description': 'Открытие указанного YouTube канала', 'example': 'Джарвис, открой канал Wylsacom'},
    {'id': 'qa_search', 'keywords': ['скажи', 'ответь', 'расскажи', 'объясни'], 'verbs': ['скажи', 'ответь', 'расскажи', 'объясни'], 'patterns': ['скажи {N}', 'ответь {N}', 'расскажи {N}', 'объясни {N}'], 'min_score': 65, 'description': 'Запрос к искусственному интеллекту для получения ответа на любой вопрос', 'example': 'Джарвис, скажи кто такой Никола Тесла'},
    {'id': 'set_weather_city', 'keywords': ['город'], 'verbs': ['установи', 'запомни', 'смени'], 'patterns': ['установи город Москва', 'мой город Санкт-Петербург', 'смени город на Лондон'], 'min_score': 75, 'description': 'Установка города для прогноза погоды вручную', 'example': 'Джарвис, установи город Москва'},
]
_ALL_PATTERN_STRINGS = []
# Pre-compile clean patterns + word sets + lengths for each command at load time.
# This eliminates all _RE_N_TAG.sub() calls inside hot fuzzy loops.
for _cp in COMMAND_PATTERNS:
    _cp['_clean_patterns'] = []
    _cp['_pat_word_sets'] = []   # set of words in each clean pattern (for intersection filter)
    _cp['_pat_plens'] = []       # word-count of each clean pattern
    # Build a union of all unique words across all this command's keywords+verbs+patterns
    _kv_words: set = set(_cp.get('keywords', [])) | set(_cp.get('verbs', []))
    for _s in _cp['patterns']:
        _clean = _RE_N_TAG.sub('', _s).strip()
        if _clean:
            _ALL_PATTERN_STRINGS.append(_clean)
            _cp['_clean_patterns'].append(_clean)
            _ws = set(re.findall(r'\b\w+\b', _clean))
            _cp['_pat_word_sets'].append(_ws)
            _cp['_pat_plens'].append(len(_clean.split()))
            _kv_words |= _ws
    _cp['_all_words'] = _kv_words   # quick pre-filter: if text shares none of these, skip
_CANON_SIMPLE_KEYS = sorted(CANON_SIMPLE.keys(), key=len, reverse=True)
_CANON_SUBSTR_KEYS = [k for k in _CANON_SIMPLE_KEYS if len(k) >= 4]
_SPLIT_PATTERN = re.compile('\\s+(?:и|а потом|потом|затем|после чего|после)\\s+')
_ORDINALS_MAP = {'первый': '1', 'второй': '2', 'третий': '3', 'первая': '1', 'вторая': '2', 'третья': '3', 'первую': '1', 'вторую': '2', 'третью': '3', 'первое': '1', 'втовое': '2', 'третье': '3', 'первого': '1', 'второго': '2', 'третьего': '3', 'первом': '1', 'втором': '2', 'третьем': '3'}
_TENS_VAL = {'двадцать': 20, 'тридцать': 30, 'сорок': 40, 'пятьдесят': 50, 'шестьдесят': 60, 'семьдесят': 70, 'восемьдесят': 80, 'девяносто': 90}
_UNITS_VAL = {'один': 1, 'одна': 1, 'одну': 1, 'одно': 1, 'два': 2, 'две': 2, 'три': 3, 'четыре': 4, 'пять': 5, 'шесть': 6, 'семь': 7, 'восемь': 8, 'девять': 9}

# -----------------------------------------------------------------------
# ADAPTIVE CONVERSATIONAL FILTER
# Built automatically from COMMAND_PATTERNS — no hardcoded lists.
# Any new command added to COMMAND_PATTERNS automatically expands this set.
# -----------------------------------------------------------------------
_COMMAND_VERBS: set = set()
for _cp in COMMAND_PATTERNS:
    _COMMAND_VERBS.update(_cp.get('verbs', []))
# Add common standalone imperative forms not always present in pattern verbs
_COMMAND_VERBS.update({
    'напомни', 'запомни', 'расскажи', 'объясни', 'стоп', 'хватит',
    'откройте', 'закройте', 'сверните', 'включите', 'выключите',
    # Infinitives commonly used as commands in Russian
    'открыть', 'закрыть', 'создать', 'сделать', 'найти', 'включить', 'выключить',
    'запустить', 'удалить', 'сохранить', 'отправить', 'скачать', 'загрузить',
    'подключить', 'отключить', 'перезагрузить', 'выключиться',
})
_COMMAND_VERBS.discard('')  # safety

# Russian question-starter words (interrogative pronouns/adverbs)
_QUESTION_STARTERS = frozenset({
    'что', 'чего', 'зачем', 'почему', 'как', 'каким', 'какой', 'какая', 'какое', 'какие',
    'когда', 'где', 'кто', 'кому', 'кого', 'чем', 'чему', 'сколько'
})

# Russian 2nd-person present-tense verb endings ("ты пишешь", "ты делаешь" etc.)
_RE_2ND_PERSON_VERB = re.compile(r'\b\w+(ешь|ёшь|ишь|аешь|яешь|уешь|оешь)\b')

# Russian 1st-person present-tense verb endings short form ("я делаю", "я хочу")
_RE_1ST_PERSON_VERB = re.compile(r'^\bя\b\s+\w+(ю|аю|яю|ею|иваю|ываю|уваю)\s*$')

def _is_conversational(text: str) -> bool:
    """
    Detects if the phrase is a conversational utterance rather than a command.
    Uses Russian grammar rules + the dynamically-built _COMMAND_VERBS set.

    Rules (all without any hardcoded phrase lists):
    1. Phrase starts with a question word AND contains no known command verb.
    2. Phrase contains "ты" + a 2nd-person present-tense verb AND no command verb.
    3. Short phrase "я + [1st-person verb]" AND no command verb.

    NOTE: Exact matches in CANON_SIMPLE already bypass this function entirely
    (they return before this is called). So "что ты умеешь" still works as show_help.
    """
    t = text.lower().strip()
    words = t.split()
    if len(words) < 2:
        return False

    has_cmd_verb = any(w in _COMMAND_VERBS for w in words)
    if has_cmd_verb:
        return False  # Has a real command verb — let it through

    # Rule 1: starts with question word, no command verb
    if words[0] in _QUESTION_STARTERS:
        return True

    # Rule 2: contains "ты" + 2nd-person present-tense verb
    if 'ты' in words and _RE_2ND_PERSON_VERB.search(t):
        return True

    # Rule 3: short "я + [1st-person verb]" phrase
    if words[0] == 'я' and len(words) <= 4 and _RE_1ST_PERSON_VERB.match(t):
        return True

    return False


_NOISE_WORDS = {
    'открой', 'закрой', 'удали', 'создай', 'сделай', 'покажи', 'найди', 'найти', 'запусти', 'включи', 'выключи',
    'переключи', 'смени', 'поменяй', 'установи', 'поставь', 'сверни', 'разверни', 'выполни',
    'что', 'как', 'почему', 'зачем', 'где', 'когда', 'кто', 'какой', 'какая', 'какое', 'какие',
    'сколько', 'один', 'два', 'три', 'четыре', 'пять', 'первый', 'второй', 'третий', 'это', 'тут', 'здесь', 'сейчас'
}
_WAKE_WORDS_STRICT = {'джарвис', 'джарвиса', 'джарвису', 'джарвисе', 'жарвис', 'жарвиса', 'жарвису', 'шарвис', 'шарвиса', 'жорвис', 'джорвис', 'жарвист', 'жаркс', 'джаркс', 'жарост', 'жарност', 'жарс', 'жорс', 'джорс', 'жорпс', 'джорпс', 'джервис', 'джарвиз', 'джарвест', 'джаравис', 'джарверс', 'джаверс', 'бобик'}
_FILLERS_STRICT = {'пожалуйста', 'плиз', 'ну', 'давай', 'хочу', 'мне', 'эту', 'тут', 'здесь', 'плиз', 'сэр', 'слушай'}

# Grammatical pattern: "что ты [verb 2nd person present]" or "ты [verb -ешь/-ишь/-ёшь]"
# These are conversational questions about what Jarvis is CURRENTLY doing — never a command.
# Русская грамматика: глагол 2 лица наст. времени оканчивается на -ешь, -ёшь, -ишь.
_RE_CONVO_QUESTION = re.compile(
    r'^(что|чего|зачем|почему|как)?\s*ты\s+\w*(ешь|ёшь|ишь|аешь|яешь|уешь|оешь)\s*$'
)
# "я [verb -ю/-аю/-яю/-ею]" — user talks about themselves, never a command.
_RE_SELF_STATEMENT = re.compile(
    r'^я\s+\w+(ю|аю|яю|ею|иваю|ываю|уваю)\s*$'
)

_NOISE_SINGLE_VERBS = frozenset({
    'открой', 'запусти', 'удали', 'закрой', 'создай', 'сделай',
    'покажи', 'найди', 'найти', 'установи', 'поставь'
})

def _is_noise_phrase(text: str) -> bool:
    t = text.lower().strip()
    if not t: return True
    if t in _WAKE_WORDS_STRICT: return True
    if t in _FILLERS_STRICT: return True
    if t in _NOISE_SINGLE_VERBS: return True          # O(1) frozenset lookup
    if _RE_CONVO_QUESTION.match(t): return True
    if _RE_SELF_STATEMENT.match(t): return True
    return False

def normalize_numbers(text: str) -> str:
    words = text.split()
    result = []
    i = 0
    while i < len(words):
        w = words[i]
        if w in _TENS_VAL and i + 1 < len(words) and (words[i + 1] in _UNITS_VAL):
            result.append(str(_TENS_VAL[w] + _UNITS_VAL[words[i + 1]]))
            i += 2
        elif w in WORDS_TO_NUM:
            result.append(WORDS_TO_NUM[w])
            i += 1
        else:
            result.append(w); i += 1
    return ' '.join(result)

_NEGATIVE_KEYWORDS = {
    'вкладку': {'close_win', 'close_all_win', 'close_other_win', 'min_win', 'max_win', 'min_all', 'min_other_win', 'unmin_win', 'win_snap_left', 'win_snap_right', 'win_snap_top_left', 'win_snap_top_right', 'win_snap_bottom_left', 'win_snap_bottom_right'},
    'вкладки': {'close_win', 'close_all_win', 'close_other_win', 'min_win', 'max_win', 'min_all', 'min_other_win', 'unmin_win'},
    'вкладка': {'close_win', 'close_all_win', 'close_other_win', 'min_win', 'max_win'},
    'окно': {'close_tab', 'close_tab_n', 'close_all_tabs', 'browser_tab'},
    'окна': {'close_tab', 'close_tab_n', 'close_all_tabs', 'browser_tab'}
}

_CREATE_FILE_COMPLETION_MARKERS = (
    'папке', 'папку', 'папка', 'каталог', 'проект', 'имен', 'назван', 'новый', 'новая', 'новое', 'пустой',
    'ворд', 'word', 'excel', 'эксель', 'эксел', 'таблиц', 'презентац', 'powerpoint', 'ppt',
    'python', 'пайтон', 'питон', 'текстов', 'markdown', 'маркдаун',
    'javascript', 'typescript', 'jsx', 'tsx', 'react', 'html', 'json',
    'vue', 'svelte', 'css', 'scss', 'sass', 'js', 'ts', 'php', 'node',
    'документ', 'модул', 'скрипт', 'класс', 'интерфейс', 'компонент',
)

def _create_file_phrase_complete_enough(text_lower: str) -> bool:
    t = (text_lower or '').strip()
    if not t:
        return False
    if any(m in t for m in _CREATE_FILE_COMPLETION_MARKERS):
        return True
    if re.search(r'\.(py|ts|js|tsx|jsx|md|txt|json|html|css|sql|rs|go|java|cs|kt)\b', t):
        return True
    if re.match(r'^(джарвис|джервис|жарвис)\s+(создай|сделай|создать|сделать)\s+файл\s*$', t):
        return False
    return True

def _is_blocked_by_negative_kw(text_words: set, candidate_id: str) -> bool:
    for neg_word, blocked_ids in _NEGATIVE_KEYWORDS.items():
        if neg_word in text_words and candidate_id in blocked_ids: return True
    return False
def _keyword_verb_startswith_match(text: str, text_lower: str, text_words: set) -> str:
    """Combined keyword/verb + startswith pass — single loop over COMMAND_PATTERNS."""
    for pat in COMMAND_PATTERNS:
        pat_id = pat['id']
        bw = pat.get('block_words')
        if bw and any(b in w for b in bw for w in text_words): continue
        if _is_blocked_by_negative_kw(text_words, pat_id): continue
        rw = pat.get('require_words')
        if rw and not any(r in text_words for r in rw): continue

        # --- startswith check (fast, no fuzzy) ---
        for cp in pat.get('_clean_patterns', []):
            if text.startswith(cp):
                if pat_id == 'create_word_doc' and not _create_file_phrase_complete_enough(text_lower):
                    break
                return pat_id

        # --- keyword/verb check ---
        k_found = [kw for kw in pat.get('keywords', []) if kw in text_words]
        v_found = [v for v in pat.get('verbs', []) if v in text_words]
        e_found = []
        for e in pat.get('extras', []):
            if ' ' in e:
                if e in text_lower: e_found.append(e)
            elif e in text_words: e_found.append(e)
        if (k_found and v_found) or (k_found and e_found) or (v_found and e_found):
            matched_words = set(k_found) | set(v_found)
            for e in e_found: matched_words.update(e.split())
            if len(matched_words) >= 2:
                if pat_id == 'create_word_doc' and not _create_file_phrase_complete_enough(text_lower):
                    continue
                return pat_id
    return ''

def _keyword_verb_match(text: str) -> str:
    """Legacy entry-point kept for external callers."""
    if _is_noise_phrase(text): return ''
    text_lower = text.lower()
    text_words = set(re.findall(r'\b\w+\b', text_lower))
    return _keyword_verb_startswith_match(text, text_lower, text_words)
def _pattern_fuzzy_match(text: str, text_words_set: set | None = None) -> tuple[str, int]:
    """
    Fuzzy match against COMMAND_PATTERNS.
    Optimizations:
    - Uses pre-compiled _clean_patterns (no _RE_N_TAG.sub at runtime)
    - Uses pre-built _all_words per command for O(1) intersection pre-filter
    - Pre-built _pat_plens avoids len(split()) per iteration
    - Early exit when score >= 95 (near-perfect match)
    - Accepts text_words_set to avoid recomputing it if already available
    """
    best_id, best_score, best_len = '', 0, 0
    if text_words_set is None:
        text_words_set = set(re.findall(r'\b\w+\b', text.lower()))
    text_words = len(text.split())
    text_lower = text.lower()
    for pat in COMMAND_PATTERNS:
        pat_id = pat['id']
        # Word-intersection pre-filter: if text shares NO word with this command's
        # entire vocabulary (keywords + verbs + pattern words), fuzzy cannot match.
        if not (text_words_set & pat['_all_words']): continue
        bw = pat.get('block_words')
        if bw and any(b in w for b in bw for w in text_words_set): continue
        if _is_blocked_by_negative_kw(text_words_set, pat_id): continue
        rw = pat.get('require_words')
        if rw and not any(r in text_words_set for r in rw): continue
        for cp, pws, plen in zip(pat['_clean_patterns'], pat['_pat_word_sets'], pat['_pat_plens']):
            # Skip if no word overlap between text and this specific pattern
            if not (text_words_set & pws): continue
            score = fuzz.token_set_ratio(text_lower, cp)
            if text_words < plen: score *= (text_words / plen) ** 0.5
            elif plen < text_words: score *= max(plen / text_words, 0.6)
            if score >= pat['min_score']:
                if score > best_score or (score == best_score and plen > best_len):
                    best_score, best_len, best_id = score, plen, pat_id
                    if best_score >= 95:
                        break  # near-perfect, no need to check remaining patterns
        if best_score >= 95:
            break
    if best_id == 'create_word_doc' and not _create_file_phrase_complete_enough(text_lower):
        return ('', 0)
    return (best_id, best_score)
_match_cache: dict[str, str] = {}
_ext_manager_cache = None

def _get_ext_manager():
    global _ext_manager_cache
    if _ext_manager_cache is None:
        try:
            from core.extensions import ExtensionManager
            _ext_manager_cache = ExtensionManager()
        except Exception:
            pass
    return _ext_manager_cache
def match_command(text: str, threshold: int=75) -> str:
    text = _normalize_stt(text)
    if not text: return ''
    _cached = _match_cache.get(text)
    if _cached is not None: return _cached
    result = _match_command_inner(text, threshold)
    if len(_match_cache) > 512:
        _match_cache.clear()
    _match_cache[text] = result
    return result
def _match_command_inner(text: str, threshold: int) -> str:
    text_norm = normalize_numbers(text)

    # --- Exact CANON_SIMPLE lookup (O(1)) ---
    _game_kw = {'игр', 'геймод', 'game', 'играть', 'играй', 'запусти', 'включи', 'хочу'}
    for t in (text, text_norm):
        cmd0 = CANON_SIMPLE.get(t)
        if cmd0:
            if cmd0 == 'game_mode_on' and not any(kw in t for kw in _game_kw):
                return ''
            if cmd0 == 'reminder' and 'напомн' not in t and 'напомин' not in t:
                return ''
            return cmd0

    # --- Insult detection ---
    try:
        words = set(re.findall(r'\b\w+\b', text_norm))
        has_jarvis = bool(words & {'джарвис', 'джервис', 'жарвис'})
        directed = has_jarvis or (text_norm.startswith('ты ') and len(words) <= 4)
        if directed and any(k in text_norm for k in (
            'туп', 'дурак', 'дура', 'идиот', 'дебил', 'кретин', 'тормоз',
            'заткни', 'замолчи', 'молчи', 'завали', 'закройся',
            'отвали', 'проваливай', 'уйди', 'пошел', 'пошёл', 'нахер',
        )):
            return _INSULT
    except Exception:
        pass

    # --- App-context shortcuts (PS / Figma) — cached ExtensionManager ---
    try:
        from core.system import get_foreground_process_name
        ext = _get_ext_manager()
        if ext:
            proc = (get_foreground_process_name() or '').lower()
            if proc:
                if 'photoshop' in proc and ext.has_feature('photoshop_voice'):
                    cmd = _PS_SHORT.get(text_norm) or _PS_SHORT.get(text)
                    if cmd: return cmd
                if ext.has_feature('figma_voice') and any(k in proc for k in ('figma', 'chrome', 'brave', 'msedge')):
                    cmd = _FIGMA_SHORT.get(text_norm) or _FIGMA_SHORT.get(text)
                    if cmd: return cmd
    except Exception:
        pass

    # Compute once — reused across all sub-functions
    is_noise = _is_noise_phrase(text_norm)
    if is_noise:
        return ''

    text_lower = text_norm.lower()
    text_words_set = set(re.findall(r'\b\w+\b', text_lower))
    
    # Strip wake words and exact fillers to avoid length penalties and fix startswith
    _stripped_lower = text_lower
    _stripped_words_set = set(text_words_set)
    for w in _WAKE_WORDS_STRICT | _FILLERS_STRICT:
        if w in _stripped_words_set:
            _stripped_lower = re.sub(r'\b' + w + r'\b', '', _stripped_lower).strip()
            _stripped_words_set.discard(w)

    if not _stripped_lower:
        return ''

    # --- Keyword/verb + startswith — single pass over COMMAND_PATTERNS ---
    kv_result = _keyword_verb_startswith_match(_stripped_lower, _stripped_lower, _stripped_words_set)
    if kv_result: return kv_result

    # --- Fuzzy pattern match against COMMAND_PATTERNS ---
    # Pass text_words_set to avoid recomputing it inside
    pat_id, _ = _pattern_fuzzy_match(_stripped_lower, _stripped_words_set)
    if pat_id: return pat_id

    # --- Conversational gate (before expensive fallbacks) ---
    if _is_conversational(text_norm):
        return ''

    # --- CANON_SIMPLE substring scan ---
    for key in _CANON_SUBSTR_KEYS:
        if key in _stripped_lower and re.search(r'\b' + re.escape(key) + r'\b', _stripped_lower):
            return CANON_SIMPLE[key]

    # --- Levenshtein fallback (typo correction, tight threshold) ---
    best_lev_match, best_lev_dist = None, float('inf')
    for key in _CANON_SIMPLE_KEYS:
        max_len = max(len(key), len(_stripped_lower))
        if max_len == 0: continue
        dist = Levenshtein.distance(_stripped_lower, key)
        if dist / max_len <= 0.2 and dist < best_lev_dist:
            best_lev_dist, best_lev_match = dist, key
    if best_lev_match: return CANON_SIMPLE[best_lev_match]

    # --- Final fuzzy token_set_ratio on CANON_SIMPLE ---
    best_match, best_score, best_len = None, 0, 0
    tlen = len(_stripped_lower.split())
    for key in _CANON_SIMPLE_KEYS:
        score = fuzz.token_set_ratio(_stripped_lower, key)
        if score >= threshold:
            klen = len(key.split())
            if tlen == 1 and klen > 1:
                if score < 100: continue
                if _stripped_lower in _NOISE_WORDS or _stripped_lower.isdigit(): continue
                if klen > 2: continue
            if score > best_score or (score == best_score and klen > best_len):
                best_score, best_len, best_match = score, klen, key
    if best_match:
        return CANON_SIMPLE[best_match]
    return ''
def extract_all_commands(text: str) -> list[tuple[str, str]]:
    text = _normalize_stt(text)
    if not text: return []
    if 'кроме ' in text:
        idx = text.find('кроме ')
        text = text[:idx] + text[idx:].replace(' и ', ' да ')
    segments = _SPLIT_PATTERN.split(text)
    results = []
    for seg in segments:
        seg = seg.strip()
        if not seg: continue
        cmd = match_command(seg)
        if cmd: results.append((cmd, seg))
    if not results:
        cmd = match_command(text)
        if cmd: results.append((cmd, text))
        return results
    if len(results) == 1 and len(segments) > 1:
        full_cmd = match_command(text)
        if full_cmd == results[0][0]: return [(full_cmd, text)]
    return results
def extract_amount(text: str) -> int:
    text_norm = normalize_numbers(text.lower())
    nums = re.findall('\\d+', text_norm)
    return sum((int(n) for n in nums)) if nums else 5
def extract_duration_seconds(text: str) -> int:
    text_norm = normalize_numbers(text.lower())
    if re.search(r'\bполчаса\b', text_norm): return 1800
    if re.search(r'\bполминуты\b', text_norm): return 30
    total, found = 0, False
    for unit, mult in [('час', 3600), ('минут', 60), ('секунд', 1)]:
        m = re.search(f'(\\d+)\\s*{unit}', text_norm)
        if m: total += int(m.group(1)) * mult; found = True
    if not re.search(r'\d+\s*час', text_norm) and re.search(r'\bчас(?:а|ов)?\b', text_norm):
        total += 3600; found = True
    if not re.search(r'\d+\s*минут', text_norm) and re.search(r'\bминут(?:у|ы|е)?\b', text_norm):
        total += 60; found = True
    if not re.search(r'\d+\s*секунд', text_norm) and re.search(r'\bсекунд(?:у|ы|е)?\b', text_norm):
        total += 1; found = True
    if found: return total
    return extract_amount(text)
def build_grammar_words() -> list[str]:
    words = set()
    for key in CANON_SIMPLE:
        for w in key.split(): words.add(w)
    for pat in COMMAND_PATTERNS:
        for cat in ['keywords', 'verbs', 'extras']:
            for item in pat.get(cat, []):
                for w in item.split(): words.add(w)
        for p in pat.get('patterns', []):
            for w in _RE_N_TAG.sub('',p).strip().split(): words.add(w)
    for w in WORDS_TO_NUM: words.add(w)
    words.update(['джарвис', 'бобик', 'и', 'а', 'потом', 'затем', 'после', 'на', 'в', 'с', 'к', 'у', 'о', 'по', 'из', 'за', 'от', 'до', 'это', 'то', 'мне', 'мой', 'мои', 'эту', 'тут', 'здесь', 'да', 'нет', 'не', 'ага', 'давай', 'отмена', 'час', 'часа', 'часов', 'минут', 'минуту', 'минуты', 'секунд', 'секунду', 'секунды', 'окно', 'окна', 'монитор', 'экран', 'вкладку', 'вкладка', 'компьютер', 'папку', 'папка', 'папке', 'видео', 'песню', 'песня', 'фильм', 'сериал', 'русский', 'английский', 'украинский', 'немецкий', 'французский', 'испанский', 'китайский', 'японский', 'корейский', 'итальянский'])
    words.discard('')
    return sorted(words)
