"""The language model every solver scores against.

Everything here is built from ONE book (Pride and Prejudice) so that the
plaintexts we later encrypt (Sherlock Holmes for steering, Frankenstein for
the sealed held-out split) are never part of the statistics. That separation
is what makes a held-out score mean something.

    ngram_logp(n)   log10 P(letter n-gram), add-k smoothed, shape (26**n,)
    word_table()    sorted int64 hashes of the 3,000 most frequent words
    ENGLISH_ORDER   letters sorted by frequency in the training book
"""
from __future__ import annotations

import os
import re
from collections import Counter
from functools import lru_cache

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

TRAIN_BOOK = "pride_and_prejudice.txt"
STEER_BOOK = "sherlock_holmes.txt"
HELDOUT_BOOK = "frankenstein.txt"

MAX_HASH_LEN = 13  # 27**13 < 2**63, so a word of up to 13 letters hashes without overflow


def read_book(name: str) -> str:
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return f.read()


def clean(text: str) -> str:
    """Lowercase a-z and single spaces: the alphabet of an Aristocrat cipher."""
    text = text.lower().replace("’", "'").replace("'", "")
    text = re.sub(r"[^a-z]+", " ", text)
    return re.sub(r" +", " ", text).strip()


def to_ints(letters: str) -> np.ndarray:
    return np.frombuffer(letters.encode("ascii"), dtype=np.uint8).astype(np.int64) - 97


@lru_cache(maxsize=1)
def _train_letters() -> np.ndarray:
    return to_ints(clean(read_book(TRAIN_BOOK)).replace(" ", ""))


@lru_cache(maxsize=None)
def ngram_logp(n: int, k: float = 0.01) -> np.ndarray:
    """log10 probabilities of every letter n-gram, flattened to index sum(p[i]*26**(n-1-i))."""
    p = _train_letters()
    idx = np.zeros(len(p) - n + 1, dtype=np.int64)
    for i in range(n):
        idx = idx * 26 + p[i: len(p) - n + 1 + i]
    counts = np.bincount(idx, minlength=26 ** n).astype(np.float64)
    # add-k smoothing: unseen n-grams are rare, not impossible
    return np.log10((counts + k) / (counts.sum() + k * 26 ** n))


def word_hash(word: str) -> int:
    h = 0
    for ch in word:
        h = h * 27 + (ord(ch) - 96)  # letters 1..26 in base 27, so 'a' != 'aa'
    return h


@lru_cache(maxsize=1)
def word_counts() -> Counter:
    return Counter(clean(read_book(TRAIN_BOOK)).split())


@lru_cache(maxsize=None)
def word_table(top_k: int = 3000) -> np.ndarray:
    words = [w for w, _ in word_counts().most_common() if 2 <= len(w) <= MAX_HASH_LEN][:top_k]
    return np.array(sorted(word_hash(w) for w in words), dtype=np.int64)


@lru_cache(maxsize=1)
def english_order() -> np.ndarray:
    counts = np.bincount(_train_letters(), minlength=26)
    return np.argsort(-counts)


ENGLISH_LETTERS = "".join(chr(97 + i) for i in english_order())
