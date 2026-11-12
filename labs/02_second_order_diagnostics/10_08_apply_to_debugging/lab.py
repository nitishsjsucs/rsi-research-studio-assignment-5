"""Lab 10.08 · Apply SO-RSI to a debugging task.

A real failing test, a real sequence of fixes (each one is executed), and the
same three anomaly detectors run over the attempt log. Then a second-order
probe asks the question nobody asked while patching: is the function wrong,
or is the test?

    decrypt(ciphertext, key)   key[i] = plaintext letter for cipher letter i
    test_roundtrip()           encrypts with `enc`, then calls decrypt(ct, enc)
"""
import os
import random
import string
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

ENC = "qwertyuiopasdfghjklzxcvbnm"  # plain letter i -> cipher letter ENC[i]


def encrypt(text, enc):
    return "".join(" " if c == " " else enc[ord(c) - 97] for c in text)


def invert(enc):
    dec = [""] * 26
    for i, c in enumerate(enc):
        dec[ord(c) - 97] = chr(97 + i)
    return "".join(dec)


# Each attempt: (label, inverse label, what changed, expected, source of decrypt, test passes `dec` or `enc`)
ATTEMPTS = [
    ("index_plus_one", "index_minus_one", "use ord(c) - 96 (suspect off-by-one)", "pass",
     "lambda ct, key: ''.join(' ' if c == ' ' else key[(ord(c) - 96) % 26] for c in ct)", "enc"),
    ("index_minus_one", "index_plus_one", "back to ord(c) - 97", "pass",
     "lambda ct, key: ''.join(' ' if c == ' ' else key[ord(c) - 97] for c in ct)", "enc"),
    ("index_plus_one", "index_minus_one", "try ord(c) - 96 again, with lower()", "pass",
     "lambda ct, key: ''.join(' ' if c == ' ' else key[(ord(c.lower()) - 96) % 26] for c in ct)", "enc"),
    ("search_key", "index_lookup", "look the letter up with key.index(c)", "pass",
     "lambda ct, key: ''.join(' ' if c == ' ' else chr(97 + key.index(c)) for c in ct)", "enc"),
]
FIX = ("fix_test", "-", "keep decrypt as written; pass invert(enc) in the test", "pass",
       "lambda ct, key: ''.join(' ' if c == ' ' else key[ord(c) - 97] for c in ct)", "dec")


def run_attempt(src, key_kind):
    decrypt = eval(src)  # noqa: S307 - our own fixed attempt strings
    key = ENC if key_kind == "enc" else invert(ENC)
    out = decrypt(encrypt("attack at dawn", ENC), key)
    return out == "attack at dawn", out, decrypt


def contract_probe(decrypt, trials=200, seed=0):
    """The documented contract: decrypt(encrypt(x, k), invert(k)) == x for every key k."""
    rng = random.Random(seed)
    ok = 0
    for _ in range(trials):
        k = "".join(rng.sample(string.ascii_lowercase, 26))
        x = " ".join("".join(rng.choice(string.ascii_lowercase) for _ in range(rng.randint(1, 8))) for _ in range(5))
        ok += decrypt(encrypt(x, k), invert(k)) == x
    return ok / trials


def detect(log, i):
    cur, out = log[i], []
    if not cur["passed"] and sum(1 for x in log[: i + 1] if x["label"] == cur["label"] and not x["passed"]) >= 2:
        out.append("recurrence")
    if any(x["label"] == cur["inverse"] for x in log[max(0, i - 3): i]):
        out.append("opposing")
    if cur["expected"] == "pass" and not cur["passed"]:
        out.append("mismatch")
    if cur["passed"] and cur["contract"] < 1.0:
        out.append("mismatch (test passes, contract breaks)")
    return out


def main():
    _lab.args(default_seeds=1)
    _lab.banner("10.08", "Apply SO-RSI to a debugging task", "Is the function wrong, or is the test?")
    print("  test: assert decrypt(encrypt('attack at dawn', ENC), ENC) == 'attack at dawn'")

    _lab.section("First-order debugging: patch, run, repeat")
    log = []
    for label, inv, what, expected, src, key_kind in ATTEMPTS:
        passed, out, fn = run_attempt(src, key_kind)
        log.append({"label": label, "inverse": inv, "what": what, "expected": expected, "passed": passed,
                    "out": out, "contract": contract_probe(fn)})
    rows = []
    for i, x in enumerate(log):
        rows.append((i + 1, x["what"], "PASS" if x["passed"] else "fail", x["out"], ", ".join(detect(log, i)) or "-"))
    _lab.table(rows, ["#", "change", "test", "output", "anomalies"])

    _lab.section("Second-order inquiry: probe before the next patch")
    original = eval(ATTEMPTS[1][4])  # noqa: S307
    print(f"  probe 1 (contract on 200 random keys) for the ORIGINAL decrypt: {contract_probe(original):.0%} hold")
    print(f"  probe 1 for attempt 4 (key.index, the 'passing' fix):           {log[3]['contract']:.0%} hold")
    print(f"  probe 2 (what kind of key does the test pass?): decrypt(encrypt(x, ENC), ENC) is the identity only if "
          f"ENC is its own inverse -> {ENC == invert(ENC)}")
    print("  diagnosis: the function satisfies its contract; the test passes an ENCRYPTION key where the")
    print("  contract asks for a DECRYPTION key. Attempt 4 'fixed' the test by breaking the contract.")

    _lab.section("Systematic edit: fix the mechanism, not the symptom")
    passed, out, fn = run_attempt(FIX[4], FIX[5])
    print(f"  {FIX[2]}: test {'PASS' if passed else 'fail'} ({out!r}); contract holds {contract_probe(fn):.0%}")
    print("\n  inquiry memory entry:")
    print("    finding : test oracle used enc where dec is required")
    print("    evidence: contract probe 100% on original; 0 recurrences after the fix; attempt 4 broke the contract")
    print("    status  : supported")


if __name__ == "__main__":
    main()
