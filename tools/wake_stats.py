"""Wake-word statistics from logs/jarvis.log ("[RECOGNITION] Jarvis heard: '...'" lines).

Shows how the ASR renders the wake word: exact hits, fuzzy hits accepted by the current
rule (core/engine/recognition.py WakeRegex: Levenshtein <= 1 for words up to 5 letters, <= 2 above),
and near misses the rule rejects (candidate missed activations).

Usage: python tools/wake_stats.py [path/to/jarvis.log]
"""
import re
import sys
from collections import Counter
from pathlib import Path

from rapidfuzz.distance import Levenshtein

BASES = ('джарвис', 'джарвіс')
HEARD = re.compile(r"Jarvis heard: '(.*)'\s*$")
NEAR = 3   # report rejected words closer than this to a base


def accepted(word: str) -> bool:
    limit = 1 if len(word) <= 5 else 2
    return any(Levenshtein.distance(word, b) <= limit for b in BASES)


def main(path: Path) -> None:
    exact, fuzzy, near, total = Counter(), Counter(), Counter(), 0
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        m = HEARD.search(line)
        if not m:
            continue
        total += 1
        for w in re.findall(r'\w+', m.group(1).lower()):
            if w in BASES:
                exact[w] += 1
            elif accepted(w):
                fuzzy[w] += 1
            elif min(Levenshtein.distance(w, b) for b in BASES) <= NEAR and len(w) >= 4:
                near[w] += 1
    print(f'utterances: {total}')
    print(f'exact wake word: {sum(exact.values())}')
    print(f'fuzzy accepted: {sum(fuzzy.values())}  {fuzzy.most_common(15)}')
    print(f'near misses (rejected, distance <= {NEAR}): {sum(near.values())}  {near.most_common(20)}')


if __name__ == '__main__':
    main(Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / 'logs' / 'jarvis.log'))
