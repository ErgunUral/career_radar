#!/usr/bin/env python3
"""F9_3: Pre-commit Hook 8 tanesini MANUEL çalıştır (config ile aynı argümanlar)."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PY_FILES = list(ROOT.glob("apps/api/app/**/*.py")) + list(ROOT.glob("apps/api/tests/**/*.py")) + list(ROOT.glob("apps/frontend/**/*.py"))
YAML_FILES = [ROOT / ".pre-commit-config.yaml"] + list(ROOT.glob("apps/**/*.yaml")) + list(ROOT.glob("apps/**/*.yml"))
TXT_PY_YAML = PY_FILES + YAML_FILES + list(ROOT.glob("apps/**/*.md"))

def sh(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

def hook1_ruff_lint() -> bool:
    code, out, err = sh(["ruff", "check", "apps/api/app", "apps/api/tests", "--select=E,F,W", "--fix", "--show-fixes"])
    summary = [l for l in (out + err).splitlines() if l.strip()]
    print(f"  [{'PASS' if code == 0 else 'FAIL'}] Hook 1: ruff lint (apps/api)  ({len(summary)} lines)")
    for l in summary[-3:]: print(f"     · {l[:110]}")
    return code == 0

def hook2_ruff_format() -> bool:
    code, out, err = sh(["ruff", "format", "apps/api/app", "apps/api/tests", "--line-length=88", "--check"])
    summary = [l for l in (out + err).splitlines() if l.strip()]
    print(f"  [{'PASS' if code == 0 else 'FAIL'}] Hook 2: ruff format (apps/api)  ({len(summary)} lines)")
    return code == 0

def hook3_mypy() -> bool:
    code, out, err = sh(["mypy", "apps/api/app", "--ignore-missing-imports", "--no-error-summary", "--disable-error-code=import-untyped", "--disable-error-code=union-attr"])
    lines = [l for l in (out + err).splitlines() if l.strip()]
    print(f"  [{'PASS' if code == 0 else 'FAIL'}] Hook 3: mypy apps/api/app  ({len(lines)} lines)")
    for l in lines[-5:]: print(f"     · {l[:120]}")
    return code == 0

def hook4_trailing_whitespace() -> bool:
    bad = []
    for f in TXT_PY_YAML:
        if not f.is_file() or f.name.startswith("."):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if line != line.rstrip():
                    bad.append((str(f), i))
                    break
        except Exception:
            pass
    print(f"  [{'PASS' if len(bad) == 0 else 'FAIL'}] Hook 4: trailing whitespace  (offenders={len(bad)})")
    for p, l in bad[:3]: print(f"     · {Path(p).relative_to(ROOT)}:{l}")
    return len(bad) == 0

def hook5_eof_newline() -> bool:
    bad = []
    for f in PY_FILES + YAML_FILES:
        try:
            data = f.read_bytes()
            if not data.endswith(b"\n") or data.endswith(b"\n\n"):
                bad.append(str(f))
        except Exception:
            pass
    print(f"  [{'PASS' if len(bad) == 0 else 'FAIL'}] Hook 5: EOF newline fix  (offenders={len(bad)})")
    for p in bad[:3]: print(f"     · {Path(p).relative_to(ROOT)}")
    return len(bad) == 0

def hook6_check_yaml() -> bool:
    try:
        import yaml  # type: ignore
    except Exception:
        print("  [SKIP] Hook 6: check-yaml (PyYAML kurulu değil)")
        return True
    bad = []
    for f in YAML_FILES:
        try:
            list(yaml.safe_load_all(f.open(encoding="utf-8", errors="replace")))
        except Exception as e:
            bad.append((str(f), str(e)[:90]))
    print(f"  [{'PASS' if len(bad) == 0 else 'FAIL'}] Hook 6: check-yaml  (offenders={len(bad)})")
    for p, e in bad[:3]: print(f"     · {Path(p).relative_to(ROOT)}: {e}")
    return len(bad) == 0

def hook7_merge_conflict() -> bool:
    bad = []
    pat = re.compile(r"^(<{7}|={7}|>{7})")
    for f in TXT_PY_YAML:
        try:
            for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if pat.match(line):
                    bad.append((str(f), i, line[:40]))
                    break
        except Exception:
            pass
    print(f"  [{'PASS' if len(bad) == 0 else 'FAIL'}] Hook 7: merge conflict markers  (offenders={len(bad)})")
    for p, l, s in bad[:3]: print(f"     · {Path(p).relative_to(ROOT)}:{l}  {s!r}")
    return len(bad) == 0

def hook8_large_files() -> bool:
    MAX_KB = 500
    bad = []
    exclude_dirs = {"node_modules", "__pycache__", ".venv", "venv", ".git"}
    for dirpath, dirnames, filenames in os.walk(str(ROOT / "apps")):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for name in filenames:
            fp = Path(dirpath) / name
            try:
                kb = fp.stat().st_size / 1024
                if kb > MAX_KB:
                    bad.append((str(fp), kb))
            except Exception:
                pass
    bad.sort(key=lambda x: x[1], reverse=True)
    print(f"  [{'PASS' if len(bad) == 0 else 'FAIL'}] Hook 8: check-large-files >{MAX_KB}KB  (offenders={len(bad)})")
    for p, kb in bad[:3]: print(f"     · {Path(p).relative_to(ROOT)}  {kb:.0f}KB")
    return len(bad) == 0

def main() -> int:
    print("=" * 70)
    print("F9_3: Pre-commit 8 Hook MANUEL onay")
    print("=" * 70)
    print(f"  Hedef PY  : {len(PY_FILES)} dosya")
    print(f"  Hedef YAML: {len(YAML_FILES)} dosya")
    print()
    results = {
        "1_ruff_lint": hook1_ruff_lint(),
        "2_ruff_format": hook2_ruff_format(),
        "3_mypy": hook3_mypy(),
        "4_trailing_ws": hook4_trailing_whitespace(),
        "5_eof_newline": hook5_eof_newline(),
        "6_check_yaml": hook6_check_yaml(),
        "7_merge_conflict": hook7_merge_conflict(),
        "8_large_files": hook8_large_files(),
    }
    print()
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print("-" * 70)
    print(f"SONUÇ: {passed}/{total} HOOK PASSED")
    for k, v in results.items():
        print(f"  [{'✔' if v else '✘'}] {k}")
    print("=" * 70)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
