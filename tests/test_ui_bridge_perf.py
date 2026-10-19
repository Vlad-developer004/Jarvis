"""ui_next/bridge/perf.py: the collector behind the System screen runs only while the screen watches, and parses the hardware answers."""
import time

import pytest

from ui_next import bridge
from ui_next.bridge import perf


@pytest.fixture
def fresh(monkeypatch):
    sent = []
    monkeypatch.setattr(perf, '_publish', lambda topic, payload, sticky=True: sent.append((topic, payload, sticky)))
    monkeypatch.setattr(perf, '_running', False)
    monkeypatch.setattr(perf, '_last', None)
    monkeypatch.setattr(perf, '_watch_at', 0.0)
    monkeypatch.setattr(perf, '_static', {'cpu': {'name': 'X'}})          # not empty: no PowerShell is started
    monkeypatch.setattr(perf, '_run_once', lambda flag, fn: None)
    monkeypatch.setattr(perf, '_prev', {})
    for q in perf._hist.values():
        q.clear()
    return sent


def test_one_sample_has_every_section_and_a_bounded_history(fresh):
    for _ in range(perf._HIST + 5):
        snap = perf._tick()
    assert set(snap) >= {'ts', 'uptime', 'ping', 'cpu', 'ram', 'disk', 'net', 'gpu', 'hist'}
    assert snap['cpu']['name'] == 'X' and 0 <= snap['ram']['pct'] <= 100 and snap['ram']['total'] > 0
    assert set(snap['hist']) == set(perf._SERIES) and all(len(v) == perf._HIST for v in snap['hist'].values())


def test_watching_starts_the_collector_and_it_stops_by_itself(fresh, monkeypatch):
    monkeypatch.setattr(perf, '_WATCH_TTL', 0.4)
    r = bridge.run_command('perf', {'op': 'watch'})
    assert r['ok'] and r['snapshot'] is None
    end = time.time() + 2
    while time.time() < end and not fresh:
        time.sleep(0.02)
    assert fresh and fresh[0][0] == 'perf' and fresh[0][2] is False       # samples are not replayed to a window that connects later
    end = time.time() + 4
    while time.time() < end and perf._running:
        time.sleep(0.05)
    assert not perf._running
    n = len(fresh)
    time.sleep(0.3)
    assert len(fresh) == n                                                # idle once the watch ended
    assert bridge.run_command('perf', {'op': 'watch'})['snapshot'] is not None


def test_unknown_op_is_refused(fresh):
    assert bridge.run_command('perf', {'op': 'x'})['error'] == 'bad_op'


def test_static_hardware_is_parsed():
    raw = {'cpu': {'Name': ' Core i5 ', 'NumberOfCores': 4, 'NumberOfLogicalProcessors': 8, 'MaxClockSpeed': 2496, 'L2CacheSize': 5120, 'L3CacheSize': 8192, 'VirtualizationFirmwareEnabled': False},
           'gpu': [{'Name': 'Intel(R) Iris(R) Xe Graphics', 'DriverVersion': '32.0', 'AdapterRAM': 2147479552}, {'Name': 'NVIDIA GeForce RTX 3060', 'DriverVersion': '555', 'AdapterRAM': -1}],
           'ram': {'Capacity': 1, 'Speed': 3200, 'ConfiguredClockSpeed': 0, 'FormFactor': 12, 'SMBIOSMemoryType': 26}, 'slots': 2, 'disk': 'SSD',
           'nic': {'InterfaceDescription': 'Wi-Fi 6', 'LinkSpeed': '144 Mbps'}, 'profile': 'Home'}
    st = perf.parse_static(raw)
    assert st['cpu']['name'] == 'Core i5' and st['cpu']['threads'] == 8 and st['cpu']['virt'] is False
    assert st['gpu']['name'].startswith('NVIDIA') and st['gpu']['discrete']                # a discrete card wins over the integrated one
    assert st['ram'] == {'speed': 3200, 'sticks': 1, 'slots': 2, 'form': 'SODIMM', 'kind': 'DDR4'}
    assert st['disk']['kind'] == 'SSD' and st['net']['link'] == '144 Mbps' and perf.parse_static({})['cpu']['name'] == ''


def test_nvidia_smi_line_is_parsed():
    g = perf.parse_nvidia_smi('37, 61, 1815, 128.40, 2048, 12288\n')
    assert g == {'util': 37.0, 'temp': 61.0, 'clock': 1815.0, 'power': 128.4, 'mem_used': 2048 * 1048576, 'mem_total': 12288 * 1048576}
    assert perf.parse_nvidia_smi('garbage') == {} and perf.parse_nvidia_smi('') == {}


def test_slow_counters_become_numbers(monkeypatch):
    monkeypatch.setattr(perf, '_slow', {})
    monkeypatch.setattr(perf, '_nvidia', lambda: {})
    monkeypatch.setattr(perf, '_ps_json', lambda script, timeout: {'disk': {'PercentDiskTime': 150, 'AvgDisksecPerTransfer': 0.0042}, 'gpu3d': 250, 'gpudedicated': 100, 'gpushared': 50, 'temp': 3232})
    perf._load_slow()
    assert perf._slow['active'] == 100.0 and perf._slow['latency_ms'] == pytest.approx(4.2)
    assert perf._slow['cpu_temp'] == pytest.approx(50.0, abs=0.1) and perf._slow['gpu'] == {'util': 100.0, 'mem_used': 150.0}
