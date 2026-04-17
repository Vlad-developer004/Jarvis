import os
import asyncio
import pyperclip
from pathlib import Path
from PIL import Image
import io
async def _ocr_from_image(img: Image.Image, lang: str='ru') -> str:
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.globalization import Language
    from winsdk.windows.graphics.imaging import SoftwareBitmap, BitmapPixelFormat, BitmapAlphaMode
    from winsdk.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
    from winsdk.windows.graphics.imaging import BitmapDecoder
    img_rgb = img.convert('RGBA')
    buf = io.BytesIO()
    img_rgb.save(buf, format='PNG')
    buf.seek(0)
    png_bytes = buf.read()
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(png_bytes)
    await writer.store_async()
    await writer.flush_async()
    stream.seek(0)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    try:
        language = Language(lang)
        engine = OcrEngine.try_create_from_language(language)
    except Exception:
        engine = OcrEngine.try_create_from_user_profile_languages()
    if not engine:
        engine = OcrEngine.try_create_from_user_profile_languages()
    if not engine:
        return ''
    result = await engine.recognize_async(bitmap)
    return result.text if result else ''
def ocr_from_screenshot() -> tuple[bool, str]:
    try:
        import pyautogui
        img = pyautogui.screenshot()
        text = asyncio.run(_ocr_from_image(img, 'ru'))
        if not text or not text.strip():
            text_en = asyncio.run(_ocr_from_image(img, 'en'))
            if text_en and text_en.strip():
                text = text_en
        if text and text.strip():
            pyperclip.copy(text.strip())
            preview = text.strip()[:80].replace('\n', ' ')
            return (True, f'Распознано и скопировано: {preview}...')
        else:
            return (False, 'Текст не найден')
    except Exception as e:
        return (False, str(e))
def ocr_from_last_screenshot() -> tuple[bool, str]:
    try:
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\User Shell Folders')
            pics_raw, _ = winreg.QueryValueEx(key, 'My Pictures')
            winreg.CloseKey(key)
            pics = os.path.expandvars(pics_raw)
        except Exception:
            pics = os.path.join(os.path.expanduser('~'), 'Pictures')
        screenshots_dir = Path(pics) / 'Screenshots'
        if not screenshots_dir.is_dir():
            return (False, 'Папка скриншотов не найдена')
        files = sorted([f for f in screenshots_dir.iterdir() if f.suffix.lower() in {'.png', '.jpg', '.jpeg', '.bmp'}], key=lambda f: f.stat().st_mtime, reverse=True)
        if not files:
            return (False, 'Нет скриншотов')
        img = Image.open(files[0])
        text = asyncio.run(_ocr_from_image(img, 'ru'))
        if not text or not text.strip():
            text_en = asyncio.run(_ocr_from_image(img, 'en'))
            if text_en and text_en.strip():
                text = text_en
        if text and text.strip():
            pyperclip.copy(text.strip())
            preview = text.strip()[:80].replace('\n', ' ')
            return (True, f'Из {files[0].name}: {preview}...')
        else:
            return (False, 'Текст не найден на скриншоте')
    except Exception as e:
        return (False, str(e))
