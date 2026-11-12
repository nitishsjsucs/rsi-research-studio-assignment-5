# 10.08 · Apply SO-RSI to a debugging task

**Group 02 · SO-RSI** · Previous: [10.07](../10_07_analyze_probes/README.md) · Next: [10.09 Compare scaling](../../03_scaling_coordination/10_09_compare_scaling/README.md)

> **Question.** Is the function wrong, or is the test?

## The task

```python
def decrypt(ciphertext, key):           # key[i] = plaintext letter for cipher letter i
    ...
def test_roundtrip():
    ct = encrypt("attack at dawn", ENC)
    assert decrypt(ct, ENC) == "attack at dawn"     # the test fails
```

## What the code does

1. **First-order debugging** — four real attempts, each one is executed against the test (`ATTEMPTS` in [lab.py](lab.py)):
   an off-by-one guess, reverting it, the same guess again, then `key.index(c)`, which makes the test **pass**.
2. **The same three detectors**, generalised to an attempt log (`detect()`): recurrence, opposing (an attempt
   and its inverse within three steps), mismatch (expected pass, got fail), plus a second-order mismatch
   the first-order view cannot see: *the test passes but the documented contract breaks*.
3. **Probes** — `contract_probe()` checks the contract `decrypt(encrypt(x, k), invert(k)) == x` on 200 random keys;
   a second probe asks what kind of key the test passes.
4. **Systematic edit** — fix the mechanism (the test's oracle), keep the function: test and contract both pass.

## Run it

```bash
python3 labs/02_second_order_diagnostics/10_08_apply_to_debugging/lab.py     # instant
```

## Output (full run)

<!-- output lines=40 -->
```text
$ python3 labs/02_second_order_diagnostics/10_08_apply_to_debugging/lab.py
==============================================================================
Lab 10.08 · Apply SO-RSI to a debugging task
Question: Is the function wrong, or is the test?
==============================================================================
  test: assert decrypt(encrypt('attack at dawn', ENC), ENC) == 'attack at dawn'

--- First-order debugging: patch, run, repeat -------------------------------
  #  change                                test  output          anomalies                              
  -  ------------------------------------  ----  --------------  ---------------------------------------
  1  use ord(c) - 96 (suspect off-by-one)  fail  kqqkyw kq lkvu  mismatch                               
  2  back to ord(c) - 97                   fail  jmmjtq jm kjcy  opposing, mismatch                     
  3  try ord(c) - 96 again, with lower()   fail  kqqkyw kq lkvu  recurrence, opposing, mismatch         
  4  look the letter up with key.index(c)  PASS  attack at dawn  mismatch (test passes, contract breaks)

--- Second-order inquiry: probe before the next patch -----------------------
  probe 1 (contract on 200 random keys) for the ORIGINAL decrypt: 100% hold
  probe 1 for attempt 4 (key.index, the 'passing' fix):           0% hold
  probe 2 (what kind of key does the test pass?): decrypt(encrypt(x, ENC), ENC) is the identity only if ENC is its own inverse -> False
  diagnosis: the function satisfies its contract; the test passes an ENCRYPTION key where the
  contract asks for a DECRYPTION key. Attempt 4 'fixed' the test by breaking the contract.

--- Systematic edit: fix the mechanism, not the symptom ---------------------
  keep decrypt as written; pass invert(enc) in the test: test PASS ('attack at dawn'); contract holds 100%

  inquiry memory entry:
    finding : test oracle used enc where dec is required
    evidence: contract probe 100% on original; 0 recurrences after the fix; attempt 4 broke the contract
    status  : supported
```
<!-- /output -->

## What the numbers say

- Attempts 1–3 fail and trip all three detectors: attempt 2 *opposes* attempt 1, attempt 3 *recurs* (the same
  off-by-one idea again) and every failure is a *mismatch* against the expected pass.
- Attempt 4 passes the test and is the worst change of all: the contract holds for **0%** of 200 random keys.
  Only the second-order mismatch ("test passes, contract breaks") flags it.
- The contract probe holds for **100%** on the original function: the function was right all along; the test
  passed an encryption key where the contract asks for a decryption key. Fixing the test makes both pass.

## Quiz

1. *How does SO-RSI differ from ordinary debugging?* Ordinary debugging edits, runs, repeats. SO-RSI watches the *sequence* of attempts for patterns that mean the hypothesis is wrong, then tests the hypothesis directly.
2. *Why is attempt 4 the most dangerous?* It is the only one that turns the test green, by breaking the function's contract. A first-order loop would accept it and stop.
3. *Can this be automated?* The detectors and the contract probe are automated here. Choosing which contract to probe still needs domain knowledge (a docstring, a spec, a property).
