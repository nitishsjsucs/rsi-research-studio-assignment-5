"""Paste real captured output into the lab READMEs.

A README marks a block like this:

    <!-- output from="--- Results" lines=30 -->
    ```text
    (replaced)
    ```
    <!-- /output -->

and this script replaces the fenced block with the lines of the lab's
output.txt starting at the first line that contains `from` (default: the top),
at most `lines` lines. Run it after run_all.py; it never invents text.
"""
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = re.compile(r'<!-- output(?: from="([^"]*)")?(?: lines=(\d+))? -->\n.*?<!-- /output -->', re.S)


def excerpt(out_lines, start, n):
    i = 0
    if start:
        i = next((k for k, l in enumerate(out_lines) if start in l), None)
        if i is None:
            raise SystemExit(f"marker text not found in output: {start!r}")
    chunk = out_lines[i:i + n]
    if i + n < len(out_lines):
        chunk.append("...")
    return chunk


def main():
    for readme in sorted(glob.glob(os.path.join(ROOT, "labs", "0*", "*", "README.md"))):
        out = os.path.join(os.path.dirname(readme), "output.txt")
        if not os.path.exists(out):
            print(f"skip (no output.txt): {os.path.relpath(readme, ROOT)}")
            continue
        lines = open(out).read().rstrip("\n").split("\n")
        text = open(readme).read()

        def sub(m):
            start, n = m.group(1), int(m.group(2) or 40)
            body = "\n".join(excerpt(lines, start, n))
            head = '<!-- output' + (f' from="{start}"' if start else "") + (f" lines={m.group(2)}" if m.group(2) else "") + " -->"
            return f"{head}\n```text\n{body}\n```\n<!-- /output -->"

        new, k = MARK.subn(sub, text)
        if new != text:
            open(readme, "w").write(new)
        print(f"{k} block(s): {os.path.relpath(readme, ROOT)}")


if __name__ == "__main__":
    main()
