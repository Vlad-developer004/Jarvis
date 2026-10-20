"""Follow-up phrases ("а завтра?", "ещё пять минут", "ещё") resolve against the previous command only, and only while it is fresh."""
import pytest

from core.nlp import followup


@pytest.fixture(autouse=True)
def _clean():
    followup.forget()
    yield
    followup.forget()


def test_nothing_before_any_command():
    assert followup.resolve('а завтра') is None


@pytest.mark.parametrize('said,want', [('а завтра?', 'погода завтра'), ('и послезавтра', 'погода послезавтра'), ('а вечером', 'погода вечером'),
                                       ('а в Киеве?', 'погода в киеве'), ('а на завтра', 'погода завтра')])
def test_weather_follow_ups(said, want):
    followup.remember('weather', 'какая погода')
    assert followup.resolve(said) == ('weather', want)


def test_a_follow_up_only_means_something_after_its_command():
    followup.remember('vol_up', 'громче')
    assert followup.resolve('а завтра') is None and followup.resolve('а в киеве') is None


def test_timer_more_needs_a_duration():
    followup.remember('timer_set', 'поставь таймер на десять минут')
    assert followup.resolve('ещё пять минут') == ('timer_add', 'добавь пять минут')
    assert followup.resolve('ещё чего') is None


@pytest.mark.parametrize('said', ['ещё', 'еще раз', 'ещё немного', 'и ещё'])
def test_again_repeats_volume_and_brightness_only(said):
    followup.remember('vol_up', 'громче')
    assert followup.resolve(said) == ('vol_up', 'громче')
    followup.remember('weather', 'погода')
    assert followup.resolve(said) is None


def test_stale_previous_command_is_ignored():
    followup.remember('weather', 'погода')
    assert followup.resolve('а завтра', now=__import__('time').time() + followup.TTL + 5) is None


def test_long_or_unrelated_phrases_are_left_alone():
    followup.remember('weather', 'погода')
    assert followup.resolve('а завтра мне надо купить хлеб и молоко и ещё что-нибудь') is None
    assert followup.resolve('открой браузер') is None
