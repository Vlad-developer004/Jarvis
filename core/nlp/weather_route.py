"""What kind of weather question a phrase is: rain in the next hours, what to wear, a week or weekend overview, air quality.

Phrases with "погода" already reach the weather command through its keyword; `route` is for the ones that never say it
("возьму зонт?", "что надеть?", "какой воздух"). `parse` is used by the command itself to pick the answer and to leave only the
place name behind."""
from __future__ import annotations

import re
from typing import NamedTuple

_SKY = r'(?:дождь|дожд\w+|снег\w*|осадк\w+|дощ\w*|сніг\w*|опад\w+)'
_AIR = re.compile(r'качеств\w+\s+воздух\w*|чистот\w+\s+воздух\w*|загрязнени\w+\s+воздух\w*|что\s+с\s+воздухом|какой\s+(?:сейчас\s+)?воздух|пыльц\w*|аллерг\w+'
                  r'|якіст\w+\s+повітр\w*|стан\s+повітр\w*|яке\s+повітря|пилок|пилку|\baqi\b')
_WEAR = re.compile(r'что\s+(?:мне\s+)?(?:надеть|одеть|надену|одевать)|как\s+(?:мне\s+)?(?:одеться|одеваться|оде\w+ся)|во\s+что\s+(?:мне\s+)?одеться'
                   r'|що\s+(?:мені\s+)?(?:вдягнути|одягнути|вдягнуся)|як\s+(?:мені\s+)?(?:одягнутися|вдягнутися|одягатися)|одежд\w+\s+на\s+(?:сегодня|сьогодні|улиц\w+|вулиц\w+)')
_RAIN = re.compile(rf'(?:будет|буде)\s+ли\s+(?:сегодня\s+|сейчас\s+|вечером\s+|утром\s+|днём\s+|днем\s+)?{_SKY}|чи\s+буде\s+(?:сьогодні\s+|ввечері\s+)?{_SKY}'
                   rf'|(?:нужен|нужно|нужна)\s+ли\s+(?:мне\s+)?(?:сегодня\s+)?(?:зонт\w*|зонтик\w*)|(?:брать|взять|возьму|захватить|прихватить)\s+(?:ли\s+)?(?:с\s+собой\s+)?(?:мне\s+)?(?:зонт\w*|зонтик\w*)'
                   rf'|(?:потрібен|потрібна|треба|брати|взяти|візьму)\s+(?:мені\s+)?(?:парасол\w*|парасоль\w*)'
                   rf'|(?:когда|во\s+сколько|коли|о\s+котрій)\s+(?:\w+\s+)?(?:закончится|кончится|перестанет|начн[её]тся|пойд[её]т|закінчиться|скінчиться|перестане|почнеться|піде)\s+{_SKY}'
                   rf'|{_SKY}\s+(?:будет|пойд[её]т|буде|піде)(?:\s+(?:сегодня|сьогодні))?')
_WEEKEND = re.compile(r'(?:погод\w*|прогноз\w*|погоду)\s+(?:на\s+)?(?:эти\s+|ці\s+)?(?:выходн\w+|вихідн\w+)')
_WEEK = re.compile(r'(?:погод\w*|прогноз\w*)\s+(?:на\s+)?(?:эту\s+|цю\s+)?(?:недел\w+|тиждень|тижня)')
# order matters: the first kind that matches wins
_KINDS = (('air', _AIR), ('wear', _WEAR), ('rain', _RAIN), ('weekend', _WEEKEND), ('week', _WEEK))


class WeatherQuery(NamedTuple):
    kind: str | None        # air / wear / rain / weekend / week, or None for plain "weather now / tomorrow / in a city"
    rest: str               # the phrase with the matched words cut out, what is left may name a place


def parse(text: str) -> WeatherQuery:
    t = re.sub(r'\s+', ' ', text.lower().replace('?', ' ').replace('!', ' ').replace(',', ' ')).strip()
    for kind, rx in _KINDS:
        m = rx.search(t)
        if m:
            return WeatherQuery(kind, f'{t[:m.start()]} {t[m.end():]}'.strip())
    return WeatherQuery(None, t)


def route(text: str) -> tuple[str, str] | None:
    """('weather', phrase) for a question the weather command answers although the phrase has no "погод" in it."""
    t = text.lower()
    if 'погод' in t:
        return None
    return ('weather', t) if parse(t).kind else None
