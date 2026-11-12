"""Run every codelab in course order and save each one's output next to it.

    python3 run_all.py            full runs (~45-60 min on a 10-core laptop); writes labs/**/output.txt
    python3 run_all.py --quick    every lab with small budgets and 1 seed (~5 min); writes output.quick.txt
    python3 run_all.py 10.06 10.07   only the labs whose id starts with these prefixes
"""
import glob
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))


def labs():
    paths = sorted(glob.glob(os.path.join(ROOT, "labs", "0*", "*", "lab.py")))
    return [(os.path.basename(os.path.dirname(p)), p) for p in paths]


def main():
    quick = "--quick" in sys.argv
    wanted = [a for a in sys.argv[1:] if not a.startswith("--")]
    results = []
    for name, path in labs():
        lab_id = name[:5].replace("_", ".")
        if wanted and not any(lab_id.startswith(w) or name.startswith(w) for w in wanted):
            continue
        out = os.path.join(os.path.dirname(path), "output.quick.txt" if quick else "output.txt")
        cmd = [sys.executable, path] + (["--quick"] if quick else [])
        print(f"\n### {name}  ->  {os.path.relpath(out, ROOT)}", flush=True)
        t = time.time()
        with open(out, "w") as f:
            f.write(f"$ python3 {os.path.relpath(path, ROOT)}{' --quick' if quick else ''}\n")
            f.flush()
            proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                sys.stdout.write(line)
                f.write(line)
            code = proc.wait()
        results.append((name, code, time.time() - t))
    print("\n" + "=" * 60)
    for name, code, secs in results:
        print(f"  {'ok  ' if code == 0 else 'FAIL'} {name:40s} {secs:6.0f}s")
    print(f"  total {sum(r[2] for r in results) / 60:.1f} min")
    sys.exit(0 if all(c == 0 for _, c, _ in results) else 1)


if __name__ == "__main__":
    main()
