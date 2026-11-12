"""Cipher instances and the four splits every lab shares.

An instance is a window of real English prose encrypted with a random
monoalphabetic substitution key. Word spaces are kept (an "Aristocrat"
cipher), unless the family is "patristocrat" (spaces removed, much harder).

    split      book            n    used for
    fit        Sherlock (A)    16   labelling edits to train Budget RSI's readout
    steering   Sherlock (B)    48   every keep/discard decision during search
    heldout    Frankenstein    96   the final report only; sealed during search
    probe      Sherlock (C)    24   diagnostic probes (SO-RSI); never scored

Sherlock is cut into three disjoint regions so fit, steering and probe never
share a sentence. Everything is a pure function of (split, seed): every
process that rebuilds a split gets byte-identical instances.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Tuple

import numpy as np

from .corpus import HELDOUT_BOOK, MAX_HASH_LEN, STEER_BOOK, clean, read_book, to_ints

LENGTHS = (40, 60, 80, 110, 150, 220, 320)  # characters, spaces included


@dataclass
class Instance:
    uid: str
    split: str
    family: str
    plaintext: str           # a-z and spaces
    ciphertext: str          # same layout, letters substituted
    cipher: np.ndarray       # cipher letters only, ints 0..25
    plain: np.ndarray        # true plaintext letters only, ints 0..25
    true_key: np.ndarray     # cipher letter -> plain letter (what a solver must find)
    word_starts: np.ndarray  # index of each word's first letter in `cipher`
    word_lens: np.ndarray
    word_pow: np.ndarray     # per-letter weight 27**(letters left in word), for hashing
    word_ok: np.ndarray      # words short enough to hash (<= 13 letters)
    extra: Dict = field(default_factory=dict)

    @property
    def length(self) -> int:
        return len(self.plaintext)

    @property
    def bucket(self) -> str:
        return "short" if self.length <= 80 else ("medium" if self.length <= 150 else "long")


def _word_layout(text: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    words = text.split(" ") if text else []
    starts, lens, pow_, pos = [], [], [], 0
    for w in words:
        starts.append(pos)
        lens.append(len(w))
        for i in range(len(w)):
            left = len(w) - 1 - i
            pow_.append(27 ** left if len(w) <= MAX_HASH_LEN else 0)
        pos += len(w)
    lens_a = np.array(lens, dtype=np.int64)
    return (np.array(starts, dtype=np.int64), lens_a,
            np.array(pow_, dtype=np.int64), lens_a <= MAX_HASH_LEN)


def make_instance(uid: str, split: str, plaintext: str, rng: np.random.Generator,
                  family: str = "aristocrat") -> Instance:
    enc = rng.permutation(26)                      # plain letter -> cipher letter
    true_key = np.argsort(enc)                     # cipher letter -> plain letter
    if family == "patristocrat":
        plaintext = plaintext.replace(" ", "")
    ciphertext = "".join(" " if ch == " " else chr(97 + enc[ord(ch) - 97]) for ch in plaintext)
    letters = plaintext.replace(" ", "")
    plain = to_ints(letters)
    if family == "patristocrat":
        starts = lens = pow_ = ok = np.zeros(0, dtype=np.int64)
        pow_ = np.zeros(len(plain), dtype=np.int64)
        ok = np.zeros(0, dtype=bool)
    else:
        starts, lens, pow_, ok = _word_layout(plaintext)
    return Instance(uid=uid, split=split, family=family, plaintext=plaintext,
                    ciphertext=ciphertext, cipher=enc[plain], plain=plain, true_key=true_key,
                    word_starts=starts, word_lens=lens, word_pow=pow_, word_ok=ok)


@lru_cache(maxsize=None)
def _book_words(book: str) -> Tuple[str, ...]:
    return tuple(clean(read_book(book)).split())


def _window(words: Tuple[str, ...], lo: int, hi: int, length: int, rng) -> str:
    """A run of whole words from words[lo:hi] that is close to `length` characters."""
    start = int(rng.integers(lo, hi - 200))
    out, n = [], 0
    for w in words[start:]:
        if n + len(w) + (1 if out else 0) > length and out:
            break
        out.append(w)
        n += len(w) + (1 if len(out) > 1 else 0)
    return " ".join(out)


SPLITS = {
    #  name        book          region      n   seed
    "fit":      (STEER_BOOK,   (0.00, 0.30), 16, 101),
    "steering": (STEER_BOOK,   (0.30, 0.80), 48, 202),
    "probe":    (STEER_BOOK,   (0.80, 1.00), 24, 303),
    "heldout":  (HELDOUT_BOOK, (0.00, 1.00), 96, 404),
}


@lru_cache(maxsize=None)
def load_split(name: str, family: str = "aristocrat", n: int = 0) -> Tuple[Instance, ...]:
    """The instances of a split. Lengths cycle through LENGTHS so every split has
    the same mix of short, medium and long ciphers."""
    book, (a, b), default_n, seed = SPLITS[name]
    n = n or default_n
    words = _book_words(book)
    lo, hi = int(a * len(words)), int(b * len(words))
    rng = np.random.default_rng(seed + (7 if family != "aristocrat" else 0))
    out: List[Instance] = []
    for i in range(n):
        text = _window(words, lo, hi, LENGTHS[i % len(LENGTHS)], rng)
        out.append(make_instance(f"{name}-{family[:3]}-{i:03d}", name, text, rng, family))
    return tuple(out)
