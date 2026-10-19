import pytest

from core.nlp import format_remaining_russian
from features.gaming import scanner


@pytest.mark.parametrize('sec,expected', [
    (291, 'четыре минуты пятьдесят одна секунда'),
    (300, 'пять минут'),
    (61, 'одна минута одна секунда'),
    (45, 'сорок пять секунд'),
    (0, 'ноль секунд'),
    (3600 + 5 * 60 + 30, 'один час пять минут'),     # seconds are dropped from an hour up
])
def test_format_remaining_russian(sec, expected):
    assert format_remaining_russian(sec) == expected


def test_read_game_config(tmp_path):
    (tmp_path / 'MicrosoftGame.config').write_text(
        '<Game><ShellVisuals DefaultDisplayName="Cool Game"/><ExecutableList><Executable Id="App" Name="a.exe"/></ExecutableList></Game>', encoding='utf-8')
    assert scanner._read_game_config(str(tmp_path)) == ('Cool Game', 'App')


def test_read_game_config_rejects_non_games(tmp_path):
    assert scanner._read_game_config(str(tmp_path)) is None            # no config file: a system package such as Paint
    assert scanner._read_game_config('') is None
    (tmp_path / 'MicrosoftGame.config').write_text('not xml', encoding='utf-8')
    assert scanner._read_game_config(str(tmp_path)) is None


def test_xbox_games_come_only_from_packages_with_a_game_config(tmp_path, monkeypatch):
    import json
    import subprocess
    import types
    game = tmp_path / 'game'
    game.mkdir()
    (game / 'MicrosoftGame.config').write_text('<Game><ShellVisuals DefaultDisplayName="ms-resource:Name"/></Game>', encoding='utf-8')
    plain = tmp_path / 'paint'
    plain.mkdir()
    payload = json.dumps([{'Name': 'Maker.Forza', 'PackageFamilyName': 'Maker.Forza_abc', 'InstallLocation': str(game)},
                          {'Name': 'Microsoft.Paint', 'PackageFamilyName': 'Microsoft.Paint_x', 'InstallLocation': str(plain)}])
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: types.SimpleNamespace(returncode=0, stdout=payload))
    games = scanner.get_xbox_games()
    assert [(g.name, g.launch_uri) for g in games] == [('Maker.Forza', 'shell:AppsFolder\Maker.Forza_abc!Game')]
