#!/usr/bin/env python3
"""Scan a container root filesystem for ELF objects that are unsafe on kernels
with a page size larger than 4 KB (e.g. 32 KB on some ARMv7 NAS kernels).

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

Input (extracted content is untrusted data; it is only read, never executed):
  --dir ROOT            an already extracted root filesystem
  --tar T [T ...]       layer / export tarballs (optionally gzip), applied in
                        order, including whiteouts; nothing is written to disk
                        (e.g. the output of `docker export`, or OCI layers)

Optional:
  --base-json FILE      JSON of an earlier scan of the base image; objects whose
                        path exists in the base are marked as in_base (they may
                        still have been upgraded; compare sha256 in the JSON)
  --json FILE           write machine-readable results
  --markdown FILE       write a full result table (all ELF files)
  --all                 print all ELF files, not only failing ones

Exit code: 1 if any hard failure was found, 0 otherwise.

Requires: Python 3 and pyelftools (pip install pyelftools).
Run with `python3 -I scripts/elf_pagesize_scan.py ...` on untrusted data.
"""
import argparse
import hashlib
import io
import json
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
        info = {"machine": elf["e_machine"], "type": elf["e_type"],
                "class": elf.elfclass}
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
    info.update(
        hard_fail=bool(reasons),
        conservative_fail=cons,
        reasons=sorted(set(reasons)),
        min_align=min(a for _, _, a in loads),
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
    )
    return info


def norm(path):
    path = path[2:] if path.startswith("./") else path
    return "/" + path.strip("/")


def owner_key(path):
    # merged-usr: /lib/x and /usr/lib/x are the same file
    return path[4:] if path.startswith("/usr/") else path


def collect_tar(tars):
    elfs, small, hard = {}, {}, {}
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
                elif (p.startswith("/var/lib/dpkg/info/") and p.endswith(".list")
                      or p == "/lib/apk/db/installed"):
                    small[p] = (head + f.read()).decode("utf-8", "replace")
    return elfs, small


def collect_dir(root):
    elfs, small = {}, {}
    for dp, _, files in os.walk(root):
        for fn in files:
            full = os.path.join(dp, fn)
            if os.path.islink(full) or not os.path.isfile(full):
                continue
            p = "/" + os.path.relpath(full, root).replace(os.sep, "/")
            try:
                with open(full, "rb") as f:
                    head = f.read(4)
                    if head == ELF_MAGIC:
                        res = analyze(head + f.read())
                        if res:
                            elfs[p] = res
                    elif (p.startswith("/var/lib/dpkg/info/") and p.endswith(".list")
                          or p == "/lib/apk/db/installed"):
                        small[p] = (head + f.read()).decode("utf-8", "replace")
            except OSError:
                pass
    return elfs, small


def owners(small):
    own = {}
    for p, text in small.items():
        if p.endswith(".list"):
            pkg = os.path.basename(p)[:-5].split(":")[0]
            for line in text.splitlines():
                own.setdefault(owner_key(line.strip()), pkg)
        else:  # apk database
            pkg, d = None, ""
            for line in text.splitlines():
                if line.startswith("P:"):
                    pkg = line[2:]
                elif line.startswith("F:"):
                    d = line[2:]
                elif line.startswith("R:") and pkg:
                    own.setdefault(owner_key("/" + (d + "/" if d else "") + line[2:]), pkg)
    return own


def origin(path, pkg, in_base):
    if "/site-packages/" in path or "/dist-packages/" in path:
        return "bundled wheel lib" if ".libs/" in path else "pip wheel"
    if pkg:
        return "distro base" if in_base in (True, None) else "our additions (distro pkg)"
    if in_base is False:
        return "our additions (other)"
    return "unowned (python build / static)"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--dir")
    src.add_argument("--tar", nargs="+")
    ap.add_argument("--base-json")
    ap.add_argument("--json")
    ap.add_argument("--markdown")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--label", default="")
    a = ap.parse_args()

    elfs, small = collect_dir(a.dir) if a.dir else collect_tar(a.tar)
    own = owners(small)
    base = None
    if a.base_json:
        with open(a.base_json) as f:
            base = {r["path"]: r["sha256"] for r in json.load(f)["files"]}

    rows = []
    for p in sorted(elfs):
        e = elfs[p]
        pkg = own.get(owner_key(p))
        in_base = None if base is None else (p in base)
        rows.append({"path": p, "package": pkg, "in_base": in_base,
                     "origin": origin(p, pkg, in_base), **e})

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
        if r["hard_fail"] or a.all:
            print(f"{'HARD' if r['hard_fail'] else 'ok  '} {r['path']} "
                  f"[{r['package'] or '-'}] {r['origin']} {'; '.join(r['reasons'])}")

    if a.json:
        with open(a.json, "w") as f:
            json.dump({"label": a.label, "files": rows,
                       "summary": {g: {k: summary[(g, k)] for k in ("total", "hard", "cons")}
                                   for g in groups}}, f, indent=1)
    if a.markdown:
        with open(a.markdown, "w") as f:
            f.write("| file | package | origin | hard-fail | conservative-fail | min p_align | reasons |\n"
                    "|---|---|---|---|---|---|---|\n")
            for r in rows:
                f.write(f"| `{r['path']}` | {r['package'] or ''} | {r['origin']} | "
                        f"{'yes' if r['hard_fail'] else 'no'} | "
                        f"{'yes' if r['conservative_fail'] else 'no'} | 0x{r['min_align']:x} | "
                        f"{'; '.join(r['reasons'])} |\n")
    return 1 if hard_total else 0


if __name__ == "__main__":
    sys.exit(main())
