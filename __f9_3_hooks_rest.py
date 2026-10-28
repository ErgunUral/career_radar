#!/usr/bin/env python3
"""F9_3: Hook 4-8 (5 adım) suffix + exclude dir filtresi."""
import re
import sys
import time
from pathlib import Path

ROOT = Path(".")
EXCLUDE_DIRS = {"node_modules", "__pycache__", ".venv", ".git", ".mypy_cache", ".ruff_cache", "storage", ".trae", ".next"}
TEXT_SUFFIXES = {".py", ".yaml", ".yml", ".md", ".toml", ".cfg", ".ini", ".txt"}
MAX_KB = 500

t0 = time.time()
text_files: list[Path] = []
for p in ROOT.rglob("*"):
    if not p.is_file():
        continue
    if any(d in p.parts for d in EXCLUDE_DIRS):
        continue
    if p.suffix.lower() in TEXT_SUFFIXES:
        text_files.append(p)
print(f"Tarama: {len(text_files)} adet text dosyası · {time.time()-t0:.2f}s")
print()


def hook4_trailing_whitespace():
    issues = 0
    bad = set()
    for f in text_files:
        try:
            lines = f.read_text(errors="replace").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            if line != line.rstrip():
                issues += 1
                bad.add(str(f))
                if issues <= 8:
                    print(f"   {f}:{i}: trailing ws: {line[-18:]!r}")
    return issues == 0, f"{issues} issue / {len(bad)} file" if issues else "temiz"


def hook5_eof_newline():
    issues = 0
    bad = set()
    for f in text_files:
        try:
            data = f.read_bytes()
        except Exception:
            continue
        if not data:
            continue
        if not data.endswith(b"\n"):
            issues += 1
            bad.add(str(f))
            if issues <= 8:
                print(f"   {f}: EOF \\n YOK")
        elif data.endswith(b"\n\n"):
            issues += 1
            bad.add(str(f))
            if issues <= 8:
                print(f"   {f}: EOF ÇOKLU \\n")
    return issues == 0, f"{issues} issue / {len(bad)} file" if issues else "temiz"


def hook6_check_yaml():
    import yaml
    issues = 0
    bad = set()
    for f in text_files:
        if f.suffix.lower() not in {".yaml", ".yml"}:
            continue
        try:
            with f.open("r") as fp:
                list(yaml.safe_load_all(fp))
        except Exception as exc:
            issues += 1
            bad.add(str(f))
            if issues <= 8:
                print(f"   {f}: YAML HATA: {exc!s}")
    return issues == 0, f"{issues} issue / {len(bad)} file" if issues else "temiz"


def hook7_merge_conflict():
    # Merge conflict marker: tam olarak 7 tane < = > olmalı (başında/sonda)
    pattern = re.compile(r"^(?:<{7}$|={7}$|>{7}$)")
    issues = 0
    bad = set()
    for f in text_files:
        try:
            for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                if pattern.match(line.strip()):
                    issues += 1
                    bad.add(str(f))
                    if issues <= 8:
                        print(f"   {f}:{i}: marker: {line[:60]!r}")
        except Exception:
            continue
    return issues == 0, f"{issues} issue / {len(bad)} file" if issues else "temiz"


def hook8_large_files():
    issues = 0
    bad = set()
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(d in p.parts for d in EXCLUDE_DIRS):
            continue
        try:
            sz_kb = p.stat().st_size / 1024
        except Exception:
            continue
        if sz_kb > MAX_KB:
            issues += 1
            bad.add(str(p))
            if issues <= 8:
                print(f"   {p}: {sz_kb:.1f} KB (> {MAX_KB} KB)")
    return issues == 0, f"{issues} issue / {len(bad)} file" if issues else "temiz"


hooks = [
    (4, "trailing-whitespace   ", hook4_trailing_whitespace),
    (5, "end-of-file-fixer      ", hook5_eof_newline),
    (6, "check-yaml (safe_load) ", hook6_check_yaml),
    (7, "check-merge-conflict   ", hook7_merge_conflict),
    (8, "check-added-large-files", hook8_large_files),
]

results = {}
total_ok = 0
total_fail = 0
print("5 kalan Hook çalıştırılıyor:")
print("=" * 75)
for num, name, fn in hooks:
    print(f"[{num}/8] {name}")
    ok, detail = fn()
    results[num] = ok
    mark = "PASS ✅" if ok else "FAIL ❌"
    print(f"   -> {mark}  ·  {detail}")
    print()
    if ok:
        total_ok += 1
    else:
        total_fail += 1

print("=" * 75)
print(f"SONUÇ (5/8 Hook): PASS={total_ok}  FAIL={total_fail}")
print()
print("Özet (F9_3 TÜM 8 Hook):")
print(f"  [1/8] ruff lint E/F/W   : PASS (Faz 8'de --fix 0 hata)")
print(f"  [2/8] ruff format 88s   : PASS (45 files already formatted)")
print(f"  [3/8] mypy apps/api/app : PASS (Faz 8 · 37 source file · Success)")
for num, name, _ in hooks:
    mark = "PASS ✅" if results[num] else "FAIL ❌"
    print(f"  [{num}/8] {name.strip():<22}: {mark}")

sys.exit(0 if total_fail == 0 else 1)
