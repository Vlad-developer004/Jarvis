from core import i18n


def test_default_language_is_russian():
    assert i18n.get_language() == 'ru'


def test_set_language_switches_translations():
    i18n.set_language('ru')
    ru_text = i18n.tr('extensions.win_title')
    i18n.set_language('uk')
    uk_text = i18n.tr('extensions.win_title')
    assert ru_text != uk_text
    assert i18n.get_language() == 'uk'


def test_tr_falls_back_to_key_when_missing():
    assert i18n.tr('this.key.does.not.exist') == 'this.key.does.not.exist'


