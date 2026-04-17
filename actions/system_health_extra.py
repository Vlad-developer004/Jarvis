from __future__ import annotations
def disk_health_voice() -> str:
    try:
        import psutil
    except Exception:
        return 'Модуль psutil недоступен.'
    parts: list[str] = []
    try:
        for part in psutil.disk_partitions(all=False):
            try:
                if 'cdrom' in (part.opts or '').lower():
                    continue
                u = psutil.disk_usage(part.mountpoint)
                free_gb = u.free / (1024**3)
                parts.append(f'{part.device} {part.mountpoint}: свободно {free_gb:.1f} ГБ, занято {u.percent:.0f} процентов')
            except Exception:
                continue
    except Exception as ex:
        return f'Не удалось прочитать диски: {ex}'
    if not parts:
        return 'Не удалось получить список разделов.'
    return ' '.join(parts[:8])
