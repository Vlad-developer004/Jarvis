import pytest

from features.gaming import GameInfo
from features.gaming.utils import fuzzy_find_game

GAMES = [
    GameInfo(name='Nuclear Option', launcher='', launch_uri='', install_dir=''),
    GameInfo(name='Euro Truck Simulator 2', launcher='', launch_uri='', install_dir=''),
]


@pytest.mark.parametrize('noise', ['о', 'а', 'ну', 'го', '  о ', '', '...'])
def test_short_noise_never_picks_a_game(noise):
    # regression: a stray "о" matched "Nuclear Option" (partial_ratio of a 1-letter query is 100) and launched it
    assert fuzzy_find_game(GAMES, noise) is None


@pytest.mark.parametrize('query,expected', [('нуклеар', 'Nuclear Option'), ('евро трак', 'Euro Truck Simulator 2'), ('ets', 'Euro Truck Simulator 2')])
def test_real_answers_still_match(query, expected):
    assert fuzzy_find_game(GAMES, query).name == expected
