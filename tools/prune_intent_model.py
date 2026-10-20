"""Shrinks the multilingual intent encoder (data/intent_model_onnx_quant) to the scripts Jarvis hears: Cyrillic (Russian/Ukrainian), Latin, digits and
punctuation. Unigram pieces made of any other script (CJK, Arabic, Thai, ...) can never match such text, so dropping them leaves the segmentation of
Russian/Ukrainian text identical. The rare Latin pieces (ids >= LATIN_TOP, i.e. low-frequency foreign words) go too, except the ones the intent phrases
and locale strings actually use, so every known phrase keeps its exact embedding (the centroid cache stays valid); only unseen long English words
are cut into shorter pieces. The embedding rows of the dropped ids go with the pieces. Cuts about 300 MB of RAM (tokenizer trie + embedding table).

    python tools/prune_intent_model.py [model_dir]

The original directory is kept as <model_dir>_full. Run once after prepare_model.py; running it again on a pruned directory does nothing."""
from __future__ import annotations

import json
import os
import shutil
import sys

import numpy as np
import onnx
from onnx import numpy_helper

EMB = 'm.embeddings.word_embeddings.weight_quantized'
LATIN_TOP = 30000      # Latin pieces below this id (the most frequent ones) are always kept


def _keep_char(c: str) -> bool:
    o = ord(c)
    return (c == '▁' or o < 0x250                      # ASCII, Latin-1, Latin Extended-A/B
            or 0x400 <= o <= 0x52F                          # Cyrillic + supplement (Ukrainian letters included)
            or 0x2000 <= o <= 0x2BFF)                       # punctuation, currency, arrows, maths, box drawing, shapes, dingbats


def _corpus() -> list[str]:
    """Every phrase the intent classifier is built from, plus the locale strings."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from core.nlp.intents import INTENTS
    out = [p for phrases in INTENTS.values() for p in phrases]

    def walk(o):
        if isinstance(o, str):
            out.append(o)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    data = os.path.join(os.path.dirname(__file__), '..', 'data')
    for rel in ('locales/ru.json', 'locales/uk.json', 'commands_vault.json'):
        walk(json.load(open(os.path.join(data, rel), encoding='utf-8')))
    return out


def _is_latin(piece: str) -> bool:
    return not any(0x400 <= ord(c) <= 0x52F for c in piece) and any(c.isalpha() for c in piece)


def prune(src: str) -> None:
    src = os.path.abspath(src)
    full = src + '_full'
    if os.path.exists(full):
        print('already pruned:', src)
        return
    tok = json.load(open(os.path.join(src, 'tokenizer.json'), encoding='utf-8'))
    vocab = tok['model']['vocab']
    special = {a['id'] for a in tok['added_tokens']} | set(range(4))
    from tokenizers import Tokenizer
    full_tok = Tokenizer.from_file(os.path.join(src, 'tokenizer.json'))
    full_tok.no_truncation()
    full_tok.no_padding()
    used = {i for e in full_tok.encode_batch(['query: ' + t for t in _corpus()]) for i in e.ids}
    keep = [i for i, (piece, _) in enumerate(vocab)
            if i in special or i in used or (all(_keep_char(c) for c in piece) and (i < LATIN_TOP or not _is_latin(piece)))]
    keep += [i for i in sorted(special) if i not in set(keep)]
    keep = sorted(set(keep))
    new_id = {old: n for n, old in enumerate(keep)}

    tok['model']['vocab'] = [vocab[i] for i in keep if i < len(vocab)]
    tok['model']['unk_id'] = new_id[tok['model']['unk_id']]
    for a in tok['added_tokens']:
        a['id'] = new_id[a['id']]
    pad = tok.get('padding')
    if pad and pad.get('pad_id') is not None:
        pad['pad_id'] = new_id[pad['pad_id']]
    pp = tok.get('post_processor') or {}
    for sp in (pp.get('special_tokens') or {}).values():
        sp['ids'] = [new_id[i] for i in sp['ids']]

    model = onnx.load(os.path.join(src, 'model_quantized.onnx'))
    for init in model.graph.initializer:
        if init.name == EMB:
            w = numpy_helper.to_array(init)
            rows = np.array([i for i in keep if i < w.shape[0]])
            init.CopyFrom(numpy_helper.from_array(np.ascontiguousarray(w[rows]), EMB))
            break
    else:
        raise SystemExit(f'{EMB} not found: not the expected model')

    shutil.copytree(src, full)
    json.dump(tok, open(os.path.join(src, 'tokenizer.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    onnx.save(model, os.path.join(src, 'model_quantized.onnx'))
    print(f'vocab {len(vocab)} -> {len(keep)}; original kept in {full}')


if __name__ == '__main__':
    prune(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'data', 'intent_model_onnx_quant'))
