"""Ukrainian interface of the new UI: the command catalog, the currency names, the language topic and the catalog of window texts (web/i18n_uk.js)."""
import json
import os
import re

import pytest

from core import i18n
from ui_next.bridge import catalog as cat
from ui_next.bridge.commands_meta import META
from ui_next.bridge.commands_meta_uk import CATEGORIES_UK, META_UK

WEB = os.path.join(os.path.dirname(__file__), '..', 'ui_next', 'web')
RUSSIAN_ONLY = re.compile('[ыэъёЫЭЪЁ]')


@pytest.fixture
def uk():
    prev = i18n.get_language()
    i18n.set_language('uk')
    yield
    i18n.set_language(prev)


def test_every_command_has_a_ukrainian_name_and_description():
    assert set(META_UK) == set(META)
    for cid, (name, desc) in META_UK.items():
        assert name and desc, cid
        assert not RUSSIAN_ONLY.search(name + desc), cid           # a Russian letter that Ukrainian lacks: left untranslated
    assert {k for k, _, _ in cat.CATEGORIES} == set(CATEGORIES_UK)


def test_the_catalog_follows_the_interface_language(uk):
    built = cat.build_catalog()
    by_id = {i['id']: i for i in built['items']}
    assert by_id['timer_set']['name'] == META_UK['timer_set'][0] and by_id['weather']['desc'] == META_UK['weather'][1]
    assert [c['title'] for c in built['categories']][:2] == ['Помічник', 'Таймери та нотатки']
    i18n.set_language('ru')
    ru = cat.build_catalog()
    assert {i['id']: i for i in ru['items']}['timer_set']['name'] == META['timer_set'][0]
    assert ru['categories'][0]['title'] == 'Помощник'


def test_phrases_with_ukrainian_letters_come_first_and_russian_only_ones_last():
    """Judged by letters only: a phrase without any letter that tells the languages apart keeps its place in the middle."""
    assert cat._ukrainian_first(['открой браузер', 'гучність на [число]', 'выключи звук', 'вимкни звук']) == ['гучність на [число]', 'открой браузер', 'вимкни звук', 'выключи звук']


def test_currency_names_follow_the_language(uk):
    from actions import currency_pairs as cp
    from ui_next import bridge
    ru_names = {c['code']: c['name'] for c in cp.supported()}
    uk_names = {c['code']: c['name'] for c in cp.supported(True)}
    assert ru_names['UAH'] != uk_names['UAH'] and not RUSSIAN_ONLY.search(' '.join(uk_names.values()))
    res = bridge.run_command('currency', {'op': 'get'})
    assert res['list'][-1] == {'code': 'BTC', 'name': 'Біткоїн'} and {c['code']: c['name'] for c in res['list']}['UAH'] == uk_names['UAH']


def test_the_language_is_published_for_the_window(monkeypatch, uk):
    from ui_next.bridge.observer import Observer
    seen = []
    ob = Observer(lambda topic, payload, sticky=True: seen.append((topic, payload)))
    ob._slow_topics()
    assert ('lang', {'language': 'uk'}) in seen
    seen.clear()
    ob._slow_topics()
    assert not [s for s in seen if s[0] == 'lang']                  # only changes are sent
    i18n.set_language('ru')
    ob._slow_topics()
    assert ('lang', {'language': 'ru'}) in seen


def _catalog():
    src = open(os.path.join(WEB, 'i18n_uk.js'), encoding='utf-8').read()
    m = re.search(r'window\.I18N_UK = (\{.*?\});\s*window\.I18N_WORDS = (\{.*?\});', src, re.S)
    return json.loads(m.group(1)), json.loads(m.group(2))


def test_the_window_catalog_is_valid_and_has_no_russian_left_in_it():
    texts, words = _catalog()
    assert len(texts) > 1500 and len(words) > 20
    for k, v in {**texts, **words}.items():
        assert k.strip() and v.strip(), k
        if k != v:
            assert not RUSSIAN_ONLY.search(v), (k, v)            # translated text with a letter only Russian has
    assert texts['Настройки'] == 'Налаштування' and words['из'] == 'з'
    assert 'а-я0-9' not in texts and not [k for k in texts if '.test(' in k]      # fragments of code are never replaced


def test_the_language_switch_is_wired_into_the_page():
    html = open(os.path.join(WEB, 'app.html'), encoding='utf-8').read()
    assert html.index('shared.js') < html.index('i18n_uk.js') < html.index('i18n.js')
    shared = open(os.path.join(WEB, 'shared.js'), encoding='utf-8').read()
    assert "topic === 'lang'" in shared and "'lang'," in shared
