"""2단계 전체: assets → enrich → term_audit → eval."""
import os, sys, runpy
HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "lib"))
sys.path.insert(0, HERE)
os.chdir(os.path.join(HERE, ".."))

for s in ("10_assets.py", "enrich.py", "95_term_audit.py", "eval.py"):
    print(f"\n{'='*22} {s} {'='*22}")
    runpy.run_path(os.path.join(HERE, s), run_name="__main__")
