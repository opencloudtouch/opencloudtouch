#!/usr/bin/env python3
"""Scan a container root filesystem tarball for ELF objects that are unsafe on
kernels with a page size larger than 4 KB (e.g. 32 KB on some ARMv7 NAS kernels).

Why: the dynamic loader refuses to map a PT_LOAD segment unless
(p_vaddr - p_offset) is a multiple of the runtime page size ("ELF load command
address/offset not page-aligned"). Objects linked for 4 KB pages only
guarantee this modulo 0x1000.

Rules (per PT_LOAD segment):
  * hard failure:  (p_vaddr - p_offset) % 0x8000 != 0, or
                   p_align > 1 and p_align % 0x8000 != 0
  * conservative:  p_align >= 0x10000 for every PT_LOAD (64 KB safe; reported
                   separately, does not affect the exit code)

ELF files are detected by magic bytes, not by file name. Symlinks are skipped.

Input: one or more tarballs (optionally gzip), applied in order including
whiteouts, e.g. the output of `docker export`. Extracted content is untrusted
data; it is only read, never executed, and nothing is written to disk.

Usage: python3 -I scripts/elf_pagesize_scan.py --tar image.tar [--label NAME]

Exit code: 1 if any hard failure was found, 0 otherwise.

Requires: Python 3 and pyelftools (pip install pyelftools).
"""
import argparse
import io
import os
import sys
import tarfile
from collections import Counter

from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

PAGE = 0x8000
CONSERVATIVE = 0x10000
ELF_MAGIC = b"\x7fELF"


def analyze(data):
    """Return analysis dict for ELF bytes, or None if there is no PT_LOAD."""
    try:
        elf = ELFFile(io.BytesIO(data))
        loads = [
            (s["p_offset"], s["p_vaddr"], s["p_align"])
            for s in elf.iter_segments()
            if s["p_type"] == "PT_LOAD"
        ]
    except (ELFError, KeyError, OSError, ValueError, AssertionError):
        return None
    if not loads:
        return None
    reasons = []
    cons = False
    for off, vaddr, align in loads:
        if (vaddr - off) % PAGE:
            reasons.append(f"congruence off=0x{off:x} vaddr=0x{vaddr:x}")
        if align > 1 and align % PAGE:
            reasons.append(f"p_align=0x{align:x}")
        if align < CONSERVATIVE:
            cons = True
    return {"hard_fail": bool(reasons), "conservative_fail": cons,
            "reasons": sorted(set(reasons))}


def norm(path):
    path = path[2:] if path.startswith("./") else path
    return "/" + path.strip("/")


def owner_key(path):
    # merged-usr: /lib/x and /usr/lib/x are the same file
    return path[4:] if path.startswith("/usr/") else path


def collect_tar(tars):
    """Return the ELF analyses by path and the dpkg file lists by path."""
    elfs, lists = {}, {}
    for tpath in tars:
        with tarfile.open(tpath, "r|*") as tf:
            for m in tf:
                p = norm(m.name)
                d, b = os.path.split(p)
                if b == ".wh..wh..opq":
                    for k in [k for k in elfs if k.startswith(d.rstrip("/") + "/")]:
                        del elfs[k]
                    continue
                if b.startswith(".wh."):
                    gone = os.path.join(d, b[4:])
                    for k in [k for k in elfs
                              if k == gone or k.startswith(gone + "/")]:
                        del elfs[k]
                    continue
                elfs.pop(p, None)
                if m.islnk():
                    src = norm(m.linkname)
                    if src in elfs:
                        elfs[p] = elfs[src]
                    continue
                if not m.isreg():
                    continue
                f = tf.extractfile(m)
                head = f.read(4)
                if head == ELF_MAGIC:
                    res = analyze(head + f.read())
                    if res:
                        elfs[p] = res
                elif p.startswith("/var/lib/dpkg/info/") and p.endswith(".list"):
                    lists[p] = (head + f.read()).decode("utf-8", "replace")
    return elfs, lists


def owners(lists):
    """Map file path to the dpkg package that owns it."""
    own = {}
    for p, text in lists.items():
        pkg = os.path.basename(p)[:-5].split(":")[0]
        for line in text.splitlines():
            own.setdefault(owner_key(line.strip()), pkg)
    return own


def origin(path, pkg):
    if "/site-packages/" in path or "/dist-packages/" in path:
        return "bundled wheel lib" if ".libs/" in path else "pip wheel"
    return "distro package" if pkg else "unowned (python build / static)"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tar", nargs="+", required=True)
    ap.add_argument("--label", default="")
    a = ap.parse_args()

    elfs, lists = collect_tar(a.tar)
    own = owners(lists)

    rows = []
    for p in sorted(elfs):
        pkg = own.get(owner_key(p))
        rows.append({"path": p, "package": pkg, "origin": origin(p, pkg), **elfs[p]})

    summary = Counter()
    for r in rows:
        k = r["origin"]
        summary[(k, "total")] += 1
        summary[(k, "hard")] += r["hard_fail"]
        summary[(k, "cons")] += r["conservative_fail"]
    groups = sorted({k for k, _ in summary})
    hard_total = sum(r["hard_fail"] for r in rows)

    print(f"{a.label} ELF files: {len(rows)}  hard failures: {hard_total}  "
          f"conservative failures: {sum(r['conservative_fail'] for r in rows)}")
    print(f"{'origin':34} {'total':>6} {'hard':>6} {'cons':>6}")
    for g in groups:
        print(f"{g:34} {summary[(g, 'total')]:6} {summary[(g, 'hard')]:6} {summary[(g, 'cons')]:6}")
    for r in rows:
        if r["hard_fail"]:
            print(f"HARD {r['path']} [{r['package'] or '-'}] {r['origin']} "
                  f"{'; '.join(r['reasons'])}")
    return 1 if hard_total else 0


if __name__ == "__main__":
    sys.exit(main())
