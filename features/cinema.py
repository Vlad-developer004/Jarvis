import re
import time
import webbrowser
import urllib.parse
from core.system import force_foreground
BRAVE_PATH = 'C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe'
DOMAIN = ''
def _get_headless_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    opts = Options()
    opts.binary_location = BRAVE_PATH
    opts.add_argument('--headless=new')
    opts.add_argument('--window-size=1920,1080')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    opts.add_experimental_option('excludeSwitches', ['enable-automation'])
    opts.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(service=Service(), options=opts)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver
def _find_best_link(driver, title: str) -> str | None:
    from selenium.webdriver.common.by import By
    title_lower = title.lower()
    links = driver.find_elements(By.CSS_SELECTOR, 'article.shortStory .hTitle a, div.b-content__inline_item-link a, .zagolovki a')
    best = None
    for link in links:
        text = link.text.lower().strip()
        if title_lower in text:
            main_title = text.split('/')[0].split('(')[0].split('[')[0].strip()
            if main_title == title_lower:
                return link.get_attribute('href')
            after = text[text.index(title_lower) + len(title_lower):].replace(' ', '').replace('(', '').strip()
            if not re.match('^\\d', after):
                return link.get_attribute('href')
            if not best:
                best = link.get_attribute('href')
    if best:
        return best
    if links:
        return links[0].get_attribute('href')
    return None
def _search_movie_url(title: str) -> str | None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    driver = _get_headless_driver()
    try:
        search_url = f'https://{DOMAIN}/index.php?do=search&subaction=search&story={urllib.parse.quote(title)}'
        driver.get(search_url)
        try:
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'article.shortStory, div.b-content__inline_item, .zagolovki')))
        except Exception:
            if 'не дал никаких результатов' in driver.page_source:
                return None
            return None
        movie_url = _find_best_link(driver, title)
        if movie_url:
            return movie_url
        return None
    except Exception as e:
        return None
    finally:
        driver.quit()
def parse_cinema_request(text: str) -> dict:
    from core.nlp import normalize_numbers
    text_lower = text.lower()
    for prefix in ['включи фильм ', 'смотреть фильм ', 'найди фильм ', 'поставь фильм ', 'покажи фильм ']:
        if prefix in text_lower:
            title = text[text_lower.index(prefix) + len(prefix):].strip()
            title = normalize_numbers(title)
            return {'type': 'movie', 'title': title}
    season, episode = (1, 1)
    for prefix in ['включи сериал ', 'смотреть сериал ', 'найди сериал ', 'поставь сериал ', 'покажи сериал ']:
        if prefix in text_lower:
            rest = text[text_lower.index(prefix) + len(prefix):].strip()
            rest = normalize_numbers(rest)
            m = re.search('сезон\\s*(\\d+)', rest, re.IGNORECASE)
            if m:
                season = int(m.group(1))
            m2 = re.search('(?:серия|серию|эпизод)\\s*(\\d+)', rest, re.IGNORECASE)
            if m2:
                episode = int(m2.group(1))
            title = re.sub('\\s*сезон\\s*\\d+.*', '', rest, flags=re.IGNORECASE).strip()
            title = re.sub('\\s*сери[яю]\\s*\\d+.*', '', title, flags=re.IGNORECASE).strip()
            return {'type': 'series', 'title': title, 'season': season, 'episode': episode}
    text_norm = normalize_numbers(text)
    return {'type': 'unknown', 'title': text_norm}
def watch_media(title: str, is_series: bool=False, season: int=1, episode: int=1):
    import pyautogui
    import ctypes
    import pygetwindow as gw
    media_type = 'сериал' if is_series else 'фильм'
    movie_url = _search_movie_url(title)
    if not movie_url:
        fallback_query = urllib.parse.quote(f'смотреть {media_type} {title} онлайн')
        fallback_url = f'https://www.google.com/search?q={fallback_query}'
        webbrowser.open(fallback_url)
        return (True, fallback_url)
    webbrowser.open(movie_url)
    for _ in range(50):
        time.sleep(0.1)
        wins = [w for w in gw.getAllWindows() if w.visible and 'brave' in w.title.lower()]
        if wins:
            try:
                wins[0].maximize()
                force_foreground(wins[0]._hWnd)
            except:
                pass
            break
    time.sleep(3.0)
    screen_w, screen_h = pyautogui.size()
    pyautogui.click(10, screen_h // 2)
    time.sleep(0.5)
    pyautogui.press('space')
    time.sleep(0.5)
    for _ in range(12):
        pyautogui.press('down')
        time.sleep(0.1)
    time.sleep(1.0)
    center_x = screen_w // 2
    center_y = screen_h // 2 + 40
    pyautogui.moveTo(center_x, center_y)
    pyautogui.click(center_x, center_y)
    time.sleep(1.0)
    pyautogui.click(10, screen_h // 2)
    time.sleep(0.5)
    pyautogui.moveTo(center_x, center_y)
    pyautogui.doubleClick(center_x, center_y)
    time.sleep(0.5)
    pyautogui.press('f')
    return (True, movie_url)
