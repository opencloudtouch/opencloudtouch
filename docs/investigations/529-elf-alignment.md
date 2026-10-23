# 529 / 530 phase 0: ELF page-size alignment scan (linux/arm/v7)

Scanner: `scripts/elf_pagesize_scan.py` (pyelftools, ELF detected by magic bytes, symlinks skipped).
Method: the arm/v7 layers were fetched straight from the registries (OCI registry HTTP API, no Docker/skopeo) and
scanned in memory in layer order (whiteouts applied); nothing from the images was executed or written to disk.

Rules per `PT_LOAD`:

- **hard**: `(p_vaddr - p_offset) % 0x8000 != 0` (congruence, the exact ld.so "address/offset not page-aligned" check) **or** `p_align > 1 and p_align % 0x8000 != 0`
- **conservative**: `p_align >= 0x10000` for every `PT_LOAD` (in this scan the set of conservative failures is identical to the set of hard failures)

Targets:

| target | what | ELF files | hard fail | of which congruence | conservative fail |
|---|---|---|---|---|---|
| `ghcr.io/opencloudtouch/opencloudtouch:1.6.0` (arm/v7, latest release) | published image | 838 | **16** | 10 | 16 |
| `python:3.11-slim@sha256:ae52c5be...` (arm/v7, pinned in `deployment/Dockerfile`) | base image | 743 | **14** | 9 | 14 |
| `python:3.11-alpine` (arm/v7) | comparison | 131 | 131 | 101 | 131 |
| python-build-standalone 3.11.17+20261021 `armv7-unknown-linux-gnueabihf` `install_only` | comparison | 10 | 3 | 1 | 3 |

(Versions: 1.6.0 is the latest release at scan time; the #529 reporter used 1.5.7. The 14 base failures are inherited
from the Debian base, our additions contribute 2 more.)

## Counts per origin group (OCT 1.6.0 image)

| origin group | ELF files | hard fail | conservative fail |
|---|---|---|---|
| Debian base (path exists in base image) | 663 | 14 | 14 |
| our additions: Debian packages (gosu, curl and their deps) | 27 | 2 | 2 |
| Python itself and stdlib (docker-library build in `/usr/local`, not dpkg-owned) | 80 | 0 | 0 |
| pip wheels (`site-packages`) | 68 | 0 | 0 |
| bundled wheel libs (`*.libs/`) | 0 | 0 | 0 |
| static binaries (own) | 0 | 0 | 0 |

`gosu` is the Debian package `gosu` (dpkg-owned), not a separate static download.

## Failing objects in the OCT 1.6.0 image

`CONG` = congruence violation (plus `p_align=0x1000`), `align` = congruent but `p_align=0x1000` only.

| object | package | origin | kind |
|---|---|---|---|
| `/usr/lib/arm-linux-gnueabihf/libz.so.1.3.1` | zlib1g | Debian base | CONG |
| `/usr/lib/arm-linux-gnueabihf/libbz2.so.1.0.4` | libbz2-1.0 | Debian base | align |
| `/usr/lib/arm-linux-gnueabihf/libacl.so.1.1.2302` | libacl1 | Debian base | CONG |
| `/usr/lib/arm-linux-gnueabihf/libbsd.so.0.12.2` | libbsd0 | Debian base | CONG |
| `/usr/lib/arm-linux-gnueabihf/libdb-5.3.so` | libdb5.3t64 | Debian base | CONG |
| `/usr/lib/arm-linux-gnueabihf/libgdbm.so.6.0.0` | libgdbm6t64 | Debian base | CONG |
| `/usr/lib/arm-linux-gnueabihf/libgmp.so.10.5.0` | libgmp10 | Debian base | CONG |
| `/usr/lib/arm-linux-gnueabihf/libhistory.so.8.2` | libreadline8t64 | Debian base | CONG |
| `/usr/lib/arm-linux-gnueabihf/libreadline.so.8.2` | libreadline8t64 | Debian base | align |
| `/usr/lib/arm-linux-gnueabihf/libmd.so.0.1.0` | libmd0 | Debian base | align |
| `/usr/bin/find` | findutils | Debian base | CONG |
| `/usr/bin/xargs` | findutils | Debian base | CONG |
| `/usr/bin/grep` | grep | Debian base | align |
| `/usr/bin/hostname` | hostname | Debian base | align |
| `/usr/lib/arm-linux-gnueabihf/libpsl.so.5.3.4` | libpsl5t64 | our additions (curl dep) | CONG |
| `/usr/lib/arm-linux-gnueabihf/librtmp.so.1` | librtmp1 | our additions (curl dep) | align |

## Answers

- libc.so.6, libm, libdl, libpthread, ld-linux-armhf.so.3 (libc6): **not affected** (`p_align` 0x10000).
- libpython3.11.so.1.0, libpython3.so, the `python3.11` binary and all `lib-dynload/*.so`: **not affected** (0x10000).
- gosu, curl, libcurl, libssl/libcrypto, libffi, liblzma, libsqlite3, libuuid, bash, dash, getconf: **not affected**.
- **libz.so.1 (zlib1g) is affected**, with a real congruence violation (offset 0x10e1c / vaddr 0x11e1c), which matches the error in #529.
- All pip wheels (pydantic_core, cryptography, uvloop, zeroconf, ...) are fine; there are no auditwheel `.libs/` directories in the image.
- The bare `Segmentation fault` lines in #529 are plausibly `grep`, `find`, `xargs`, `hostname` (affected executables, probably used by entrypoint/healthcheck scripts); not verified on hardware.

Comparison targets: Alpine is worse (all 131 objects fail, including `ld-musl`, `python3.11` and libpython). The python-build-standalone armv7 build is nearly clean: only `python3.11`, `libpython3.so` (`p_align=0x1000` but congruent) and `_tkinter` (congruence) fail, and it has only 10 ELF files because it is largely static.

## Full table (all 838 ELF files of 1.6.0)

| file | package | origin | hard-fail | conservative-fail | min p_align | reasons |
|---|---|---|---|---|---|---|
| `/usr/bin/[` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/apt` | apt | distro base | no | no | 0x10000 |  |
| `/usr/bin/apt-cache` | apt | distro base | no | no | 0x10000 |  |
| `/usr/bin/apt-cdrom` | apt | distro base | no | no | 0x10000 |  |
| `/usr/bin/apt-config` | apt | distro base | no | no | 0x10000 |  |
| `/usr/bin/apt-get` | apt | distro base | no | no | 0x10000 |  |
| `/usr/bin/apt-mark` | apt | distro base | no | no | 0x10000 |  |
| `/usr/bin/arch` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/b2sum` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/base32` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/base64` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/basename` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/basenc` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/bash` | bash | distro base | no | no | 0x10000 |  |
| `/usr/bin/cat` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/chage` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/bin/chcon` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/chfn` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/bin/chgrp` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/chmod` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/choom` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/chown` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/chrt` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/chsh` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/bin/cksum` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/clear` | ncurses-bin | distro base | no | no | 0x10000 |  |
| `/usr/bin/clear_console` | bash | distro base | no | no | 0x10000 |  |
| `/usr/bin/cmp` | diffutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/comm` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/cp` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/csplit` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/curl` | curl | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/bin/cut` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/dash` | dash | distro base | no | no | 0x10000 |  |
| `/usr/bin/date` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/dd` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/df` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/diff` | diffutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/diff3` | diffutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/dir` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/dircolors` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/dirname` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/dmesg` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/dpkg` | dpkg | distro base | no | no | 0x10000 |  |
| `/usr/bin/dpkg-deb` | dpkg | distro base | no | no | 0x10000 |  |
| `/usr/bin/dpkg-divert` | dpkg | distro base | no | no | 0x10000 |  |
| `/usr/bin/dpkg-query` | dpkg | distro base | no | no | 0x10000 |  |
| `/usr/bin/dpkg-realpath` | dpkg | distro base | no | no | 0x10000 |  |
| `/usr/bin/dpkg-split` | dpkg | distro base | no | no | 0x10000 |  |
| `/usr/bin/dpkg-statoverride` | dpkg | distro base | no | no | 0x10000 |  |
| `/usr/bin/dpkg-trigger` | dpkg | distro base | no | no | 0x10000 |  |
| `/usr/bin/du` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/echo` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/env` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/expand` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/expiry` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/bin/expr` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/factor` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/fallocate` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/false` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/find` | findutils | distro base | yes | yes | 0x1000 | congruence off=0x23d80 vaddr=0x24d80; p_align=0x1000 |
| `/usr/bin/findmnt` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/flock` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/fmt` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/fold` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/getconf` | libc-bin | distro base | no | no | 0x10000 |  |
| `/usr/bin/getent` | libc-bin | distro base | no | no | 0x10000 |  |
| `/usr/bin/getopt` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/gpasswd` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/bin/grep` | grep | distro base | yes | yes | 0x1000 | p_align=0x1000 |
| `/usr/bin/groups` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/gzip` | gzip | distro base | no | no | 0x10000 |  |
| `/usr/bin/hardlink` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/head` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/hostid` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/hostname` | hostname | distro base | yes | yes | 0x1000 | p_align=0x1000 |
| `/usr/bin/iconv` | libc-bin | distro base | no | no | 0x10000 |  |
| `/usr/bin/id` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/infocmp` | ncurses-bin | distro base | no | no | 0x10000 |  |
| `/usr/bin/install` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/ionice` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/ipcmk` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/ipcrm` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/ipcs` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/ischroot` | debianutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/join` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/link` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/ln` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/locale` | libc-bin | distro base | no | no | 0x10000 |  |
| `/usr/bin/localedef` | libc-bin | distro base | no | no | 0x10000 |  |
| `/usr/bin/logger` | bsdutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/login` | login | distro base | no | no | 0x10000 |  |
| `/usr/bin/logname` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/ls` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/lsblk` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/lscpu` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/lsipc` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/lslocks` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/lslogins` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/lsmem` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/lsns` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/mawk` | mawk | distro base | no | no | 0x10000 |  |
| `/usr/bin/mcookie` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/md5sum` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/mkdir` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/mkfifo` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/mknod` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/mktemp` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/more` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/mount` | mount | distro base | no | no | 0x10000 |  |
| `/usr/bin/mountpoint` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/mv` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/namei` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/newgrp` | login | distro base | no | no | 0x10000 |  |
| `/usr/bin/nice` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/nl` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/nohup` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/nproc` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/nsenter` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/numfmt` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/od` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/openssl` | openssl | distro base | no | no | 0x10000 |  |
| `/usr/bin/partx` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/passwd` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/bin/paste` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/pathchk` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/perl` | perl-base | distro base | no | no | 0x10000 |  |
| `/usr/bin/perl5.40.1` | perl-base | distro base | no | no | 0x10000 |  |
| `/usr/bin/pinky` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/pldd` | libc-bin | distro base | no | no | 0x10000 |  |
| `/usr/bin/pr` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/printenv` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/printf` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/prlimit` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/ptx` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/pwd` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/readlink` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/realpath` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/rename.ul` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/renice` | bsdutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/rev` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/rm` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/rmdir` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/run-parts` | debianutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/runcon` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/script` | bsdutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/scriptlive` | bsdutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/scriptreplay` | bsdutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/sdiff` | diffutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/sed` | sed | distro base | no | no | 0x10000 |  |
| `/usr/bin/seq` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/setarch` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/setpriv` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/setsid` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/setterm` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/sha1sum` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/sha224sum` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/sha256sum` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/sha384sum` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/sha512sum` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/shred` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/shuf` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/sleep` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/sort` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/split` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/sqv` | sqv | distro base | no | no | 0x10000 |  |
| `/usr/bin/stat` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/stdbuf` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/stty` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/su` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/sum` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/sync` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/tabs` | ncurses-bin | distro base | no | no | 0x10000 |  |
| `/usr/bin/tac` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/tail` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/tar` | tar | distro base | no | no | 0x10000 |  |
| `/usr/bin/taskset` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/tee` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/tempfile` | debianutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/test` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/tic` | ncurses-bin | distro base | no | no | 0x10000 |  |
| `/usr/bin/timeout` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/toe` | ncurses-bin | distro base | no | no | 0x10000 |  |
| `/usr/bin/touch` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/tput` | ncurses-bin | distro base | no | no | 0x10000 |  |
| `/usr/bin/tr` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/true` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/truncate` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/tset` | ncurses-bin | distro base | no | no | 0x10000 |  |
| `/usr/bin/tsort` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/tty` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/uclampset` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/umount` | mount | distro base | no | no | 0x10000 |  |
| `/usr/bin/uname` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/unexpand` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/uniq` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/unlink` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/unshare` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/update-alternatives` | dpkg | distro base | no | no | 0x10000 |  |
| `/usr/bin/users` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/vdir` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/wall` | bsdutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/wc` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/wdctl` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/whereis` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/bin/who` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/whoami` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/xargs` | findutils | distro base | yes | yes | 0x1000 | congruence off=0xbbf4 vaddr=0xcbf4; p_align=0x1000 |
| `/usr/bin/yes` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/bin/zdump` | libc-bin | distro base | no | no | 0x10000 |  |
| `/usr/lib/apt/apt-extracttemplates` | apt | distro base | no | no | 0x10000 |  |
| `/usr/lib/apt/apt-helper` | apt | distro base | no | no | 0x10000 |  |
| `/usr/lib/apt/methods/cdrom` | apt | distro base | no | no | 0x10000 |  |
| `/usr/lib/apt/methods/copy` | apt | distro base | no | no | 0x10000 |  |
| `/usr/lib/apt/methods/file` | apt | distro base | no | no | 0x10000 |  |
| `/usr/lib/apt/methods/gpgv` | apt | distro base | no | no | 0x10000 |  |
| `/usr/lib/apt/methods/http` | apt | distro base | no | no | 0x10000 |  |
| `/usr/lib/apt/methods/mirror` | apt | distro base | no | no | 0x10000 |  |
| `/usr/lib/apt/methods/rred` | apt | distro base | no | no | 0x10000 |  |
| `/usr/lib/apt/methods/sqv` | apt | distro base | no | no | 0x10000 |  |
| `/usr/lib/apt/methods/store` | apt | distro base | no | no | 0x10000 |  |
| `/usr/lib/apt/solvers/dump` | apt | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/engines-3/afalg.so` | libssl3t64 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/engines-3/loader_attic.so` | libssl3t64 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ANSI_X3.110.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ARMSCII-8.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ASMO_449.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/BIG5.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/BIG5HKSCS.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/BRF.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP10007.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP1125.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP1250.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP1251.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP1252.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP1253.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP1254.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP1255.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP1256.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP1257.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP1258.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP737.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP770.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP771.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP772.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP773.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP774.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP775.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CP932.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CSN_369103.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/CWI.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/DEC-MCS.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EBCDIC-AT-DE-A.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EBCDIC-AT-DE.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EBCDIC-CA-FR.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EBCDIC-DK-NO-A.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EBCDIC-DK-NO.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EBCDIC-ES-A.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EBCDIC-ES-S.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EBCDIC-ES.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EBCDIC-FI-SE-A.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EBCDIC-FI-SE.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EBCDIC-FR.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EBCDIC-IS-FRISS.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EBCDIC-IT.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EBCDIC-PT.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EBCDIC-UK.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EBCDIC-US.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ECMA-CYRILLIC.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EUC-CN.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EUC-JISX0213.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EUC-JP-MS.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EUC-JP.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EUC-KR.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/EUC-TW.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/GB18030.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/GBBIG5.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/GBGBK.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/GBK.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/GEORGIAN-ACADEMY.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/GEORGIAN-PS.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/GOST_19768-74.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/GREEK-CCITT.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/GREEK7-OLD.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/GREEK7.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/HP-GREEK8.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/HP-ROMAN8.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/HP-ROMAN9.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/HP-THAI8.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/HP-TURKISH8.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM037.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM038.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1004.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1008.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1008_420.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1025.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1026.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1046.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1047.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1097.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1112.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1122.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1123.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1124.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1129.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1130.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1132.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1133.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1137.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1140.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1141.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1142.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1143.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1144.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1145.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1146.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1147.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1148.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1149.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1153.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1154.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1155.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1156.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1157.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1158.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1160.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1161.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1162.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1163.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1164.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1166.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1167.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM12712.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1364.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1371.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1388.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1390.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM1399.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM16804.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM256.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM273.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM274.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM275.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM277.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM278.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM280.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM281.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM284.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM285.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM290.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM297.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM420.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM423.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM424.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM437.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM4517.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM4899.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM4909.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM4971.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM500.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM5347.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM803.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM850.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM851.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM852.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM855.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM856.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM857.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM858.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM860.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM861.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM862.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM863.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM864.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM865.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM866.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM866NAV.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM868.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM869.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM870.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM871.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM874.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM875.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM880.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM891.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM901.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM902.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM903.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM9030.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM904.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM905.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM9066.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM918.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM921.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM922.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM930.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM932.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM933.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM935.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM937.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM939.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM943.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IBM9448.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/IEC_P27-1.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/INIS-8.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/INIS-CYRILLIC.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/INIS.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISIRI-3342.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO-2022-CN-EXT.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO-2022-CN.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO-2022-JP-3.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO-2022-JP.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO-2022-KR.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO-IR-197.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO-IR-209.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO646.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO8859-1.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO8859-10.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO8859-11.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO8859-13.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO8859-14.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO8859-15.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO8859-16.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO8859-2.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO8859-3.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO8859-4.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO8859-5.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO8859-6.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO8859-7.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO8859-8.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO8859-9.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO8859-9E.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO_10367-BOX.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO_11548-1.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO_2033.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO_5427-EXT.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO_5427.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO_5428.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO_6937-2.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/ISO_6937.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/JOHAB.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/KOI-8.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/KOI8-R.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/KOI8-RU.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/KOI8-T.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/KOI8-U.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/LATIN-GREEK-1.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/LATIN-GREEK.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/MAC-CENTRALEUROPE.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/MAC-IS.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/MAC-SAMI.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/MAC-UK.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/MACINTOSH.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/MIK.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/NATS-DANO.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/NATS-SEFI.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/PT154.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/RK1048.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/SAMI-WS2.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/SHIFT_JISX0213.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/SJIS.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/T.61.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/TCVN5712-1.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/TIS-620.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/TSCII.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/UHC.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/UNICODE.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/UTF-16.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/UTF-32.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/UTF-7.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/VISCII.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/libCNS.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/libGB.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/libISOIR165.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/libJIS.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/libJISX0213.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/gconv/libKSC.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/krb5/plugins/preauth/spake.so` | libkrb5-3 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/ld-linux-armhf.so.3` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libBrokenLocale.so.1` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libacl.so.1.1.2302` | libacl1 | distro base | yes | yes | 0x1000 | congruence off=0x4ddc vaddr=0x5ddc; p_align=0x1000 |
| `/usr/lib/arm-linux-gnueabihf/libanl.so.1` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libapt-pkg.so.7.0.0` | libapt-pkg7.0 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libapt-private.so.0.0.0` | apt | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libattr.so.1.1.2502` | libattr1 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libaudit.so.1.0.0` | libaudit1 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libblkid.so.1.1.0` | libblkid1 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libbrotlicommon.so.1.1.0` | libbrotli1 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libbrotlidec.so.1.1.0` | libbrotli1 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libbrotlienc.so.1.1.0` | libbrotli1 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libbsd.so.0.12.2` | libbsd0 | distro base | yes | yes | 0x1000 | congruence off=0xbcb8 vaddr=0xccb8; p_align=0x1000 |
| `/usr/lib/arm-linux-gnueabihf/libbz2.so.1.0.4` | libbz2-1.0 | distro base | yes | yes | 0x1000 | p_align=0x1000 |
| `/usr/lib/arm-linux-gnueabihf/libc.so.6` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libc_malloc_debug.so.0` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libcap-ng.so.0.0.0` | libcap-ng0 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libcap.so.2.75` | libcap2 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libcom_err.so.2.1` | libcom-err2 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libcrypt.so.1.1.0` | libcrypt1 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libcrypto.so.3` | libssl3t64 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libcurl.so.4.8.0` | libcurl4t64 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libdb-5.3.so` | libdb5.3t64 | distro base | yes | yes | 0x1000 | congruence off=0x115a24 vaddr=0x116a24; p_align=0x1000 |
| `/usr/lib/arm-linux-gnueabihf/libdebconfclient.so.0.0.0` | libdebconfclient0 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libdl.so.2` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libdrop_ambient.so.0.0.0` | libcap-ng0 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libffi.so.8.1.4` | libffi8 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libformw.so.6.5` | libncursesw6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libgcc_s.so.1` | libgcc-s1 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libgdbm.so.6.0.0` | libgdbm6t64 | distro base | yes | yes | 0x1000 | congruence off=0xab94 vaddr=0xbb94; p_align=0x1000 |
| `/usr/lib/arm-linux-gnueabihf/libgmp.so.10.5.0` | libgmp10 | distro base | yes | yes | 0x1000 | congruence off=0x51d60 vaddr=0x52d60; p_align=0x1000 |
| `/usr/lib/arm-linux-gnueabihf/libgnutls.so.30.40.3` | libgnutls30t64 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libgssapi_krb5.so.2.2` | libgssapi-krb5-2 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libhistory.so.8.2` | libreadline8t64 | distro base | yes | yes | 0x1000 | congruence off=0x6f08 vaddr=0x7f08; p_align=0x1000 |
| `/usr/lib/arm-linux-gnueabihf/libhogweed.so.6.10` | libhogweed6t64 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libidn2.so.0.4.0` | libidn2-0 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libk5crypto.so.3.1` | libk5crypto3 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libkeyutils.so.1.10` | libkeyutils1 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libkrb5.so.3.3` | libkrb5-3 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libkrb5support.so.0.1` | libkrb5support0 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/liblastlog2.so.2.0.0` | liblastlog2-2 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/liblber.so.2.0.200` | libldap2 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libldap.so.2.0.200` | libldap2 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/liblz4.so.1.10.0` | liblz4-1 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/liblzma.so.5.8.1` | liblzma5 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libm.so.6` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libmd.so.0.1.0` | libmd0 | distro base | yes | yes | 0x1000 | p_align=0x1000 |
| `/usr/lib/arm-linux-gnueabihf/libmemusage.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libmenuw.so.6.5` | libncursesw6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libmount.so.1.1.0` | libmount1 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libncursesw.so.6.5` | libncursesw6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libnettle.so.8.10` | libnettle8t64 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libnghttp2.so.14.28.3` | libnghttp2-14 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libnghttp3.so.9.2.6` | libnghttp3-9 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libnsl.so.1` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libnss_compat.so.2` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libnss_dns.so.2` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libnss_files.so.2` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libnss_hesiod.so.2` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libp11-kit.so.0.4.1` | libp11-kit0 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libpam.so.0.85.1` | libpam0g | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libpam_misc.so.0.82.1` | libpam0g | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libpamc.so.0.82.1` | libpam0g | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libpanelw.so.6.5` | libncursesw6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libpcprofile.so` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libpcre2-8.so.0.14.0` | libpcre2-8-0 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libpsl.so.5.3.4` | libpsl5t64 | our additions (distro pkg) | yes | yes | 0x1000 | congruence off=0xee30 vaddr=0xfe30; p_align=0x1000 |
| `/usr/lib/arm-linux-gnueabihf/libpsx.so.2.75` | libcap2 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libpthread.so.0` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libreadline.so.8.2` | libreadline8t64 | distro base | yes | yes | 0x1000 | p_align=0x1000 |
| `/usr/lib/arm-linux-gnueabihf/libresolv.so.2` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/librt.so.1` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/librtmp.so.1` | librtmp1 | our additions (distro pkg) | yes | yes | 0x1000 | p_align=0x1000 |
| `/usr/lib/arm-linux-gnueabihf/libsasl2.so.2.0.25` | libsasl2-2 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libseccomp.so.2.6.0` | libseccomp2 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libselinux.so.1` | libselinux1 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libsemanage.so.2` | libsemanage2 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libsepol.so.2` | libsepol2 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libsmartcols.so.1.1.0` | libsmartcols1 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libsqlite3.so.0.8.6` | libsqlite3-0 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libssh2.so.1.0.1` | libssh2-1t64 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libssl.so.3` | libssl3t64 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libstdc++.so.6.0.33` | libstdc++6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libsystemd.so.0.40.0` | libsystemd0 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libtasn1.so.6.6.4` | libtasn1-6 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libthread_db.so.1` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libtic.so.6.5` | libtinfo6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libtinfo.so.6.5` | libtinfo6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libudev.so.1.7.10` | libudev1 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libunistring.so.5.2.0` | libunistring5 | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libutil.so.1` | libc6 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libuuid.so.1.3.0` | libuuid1 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libxxhash.so.0.8.3` | libxxhash0 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/libz.so.1.3.1` | zlib1g | distro base | yes | yes | 0x1000 | congruence off=0x10e1c vaddr=0x11e1c; p_align=0x1000 |
| `/usr/lib/arm-linux-gnueabihf/libzstd.so.1.5.7` | libzstd1 | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/ossl-modules/legacy.so` | openssl-provider-legacy | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/perl-base/auto/Cwd/Cwd.so` | perl-base | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/perl-base/auto/Fcntl/Fcntl.so` | perl-base | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/perl-base/auto/File/Glob/Glob.so` | perl-base | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/perl-base/auto/Hash/Util/Util.so` | perl-base | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/perl-base/auto/IO/IO.so` | perl-base | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/perl-base/auto/List/Util/Util.so` | perl-base | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/perl-base/auto/POSIX/POSIX.so` | perl-base | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/perl-base/auto/Socket/Socket.so` | perl-base | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/perl-base/auto/attributes/attributes.so` | perl-base | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/perl-base/auto/re/re.so` | perl-base | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/sasl2/libsasldb.so.2.0.25` | libsasl2-modules-db | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_access.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_canonicalize_user.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_debug.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_deny.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_echo.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_env.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_exec.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_faildelay.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_faillock.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_filter.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_ftp.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_group.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_issue.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_keyinit.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_limits.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_listfile.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_localuser.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_loginuid.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_mail.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_mkhomedir.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_motd.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_namespace.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_nologin.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_permit.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_pwhistory.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_rhosts.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_rootok.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_securetty.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_selinux.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_sepermit.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_setquota.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_shells.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_stress.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_succeed_if.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_time.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_timestamp.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_tty_audit.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_umask.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_unix.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_userdb.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_usertype.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_warn.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_wheel.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/lib/arm-linux-gnueabihf/security/pam_xauth.so` | libpam-modules | distro base | no | no | 0x10000 |  |
| `/usr/libexec/coreutils/libstdbuf.so` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/local/bin/python3.11` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/libpython3.11.so.1.0` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/libpython3.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_asyncio.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_bisect.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_blake2.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_bz2.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_codecs_cn.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_codecs_hk.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_codecs_iso2022.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_codecs_jp.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_codecs_kr.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_codecs_tw.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_contextvars.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_crypt.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_csv.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_ctypes.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_ctypes_test.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_curses.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_curses_panel.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_datetime.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_dbm.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_decimal.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_elementtree.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_gdbm.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_hashlib.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_heapq.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_json.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_lsprof.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_lzma.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_md5.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_multibytecodec.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_multiprocessing.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_opcode.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_pickle.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_posixshmem.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_posixsubprocess.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_queue.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_random.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_sha1.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_sha256.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_sha3.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_sha512.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_socket.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_sqlite3.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_ssl.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_statistics.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_struct.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_testbuffer.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_testcapi.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_testclinic.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_testimportmultiple.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_testinternalcapi.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_testmultiphase.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_tkinter.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_typing.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_uuid.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_xxsubinterpreters.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_xxtestfuzz.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/_zoneinfo.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/array.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/audioop.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/binascii.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/cmath.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/fcntl.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/grp.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/math.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/mmap.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/ossaudiodev.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/pyexpat.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/readline.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/resource.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/select.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/spwd.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/syslog.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/termios.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/unicodedata.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/xxlimited.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/xxlimited_35.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/lib-dynload/zlib.cpython-311-arm-linux-gnueabihf.so` |  | unowned (python build / static) | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_ARC4.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_Salsa20.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_chacha20.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_pkcs1_decode.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_raw_aes.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_raw_arc2.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_raw_blowfish.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_raw_cast.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_raw_cbc.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_raw_cfb.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_raw_ctr.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_raw_des.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_raw_des3.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_raw_ecb.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_raw_eksblowfish.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_raw_ocb.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Cipher/_raw_ofb.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Hash/_BLAKE2b.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Hash/_BLAKE2s.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Hash/_MD2.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Hash/_MD4.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Hash/_MD5.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Hash/_RIPEMD160.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Hash/_SHA1.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Hash/_SHA224.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Hash/_SHA256.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Hash/_SHA384.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Hash/_SHA512.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Hash/_ghash_portable.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Hash/_k12.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Hash/_keccak.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Hash/_poly1305.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Math/_nat.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Protocol/_scrypt.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/PublicKey/_curve25519.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/PublicKey/_ec_nat.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/PublicKey/_ed25519.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Util/_cpuid_c.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/Crypto/Util/_strxor.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/_cffi_backend.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/charset_normalizer/cd.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/charset_normalizer/md.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/cryptography/hazmat/bindings/_rust.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/httptools/parser/parser.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/httptools/parser/url_parser.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/psutil/_psutil_linux.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/pydantic_core/_pydantic_core.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/uvloop/loop.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/watchfiles/_rust_notify.abi3.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/websockets/speedups.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_cache.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_dns.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_handlers/answers.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_handlers/multicast_outgoing_queue.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_handlers/query_handler.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_handlers/record_manager.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_history.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_listener.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_protocol/incoming.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_protocol/outgoing.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_record_update.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_services/__init__.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_services/browser.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_services/info.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_services/registry.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_updates.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_utils/ipaddress.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/local/lib/python3.11/site-packages/zeroconf/_utils/time.cpython-311-arm-linux-gnueabihf.so` |  | pip wheel | no | no | 0x10000 |  |
| `/usr/sbin/agetty` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/blkdiscard` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/blkid` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/blkzone` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/blockdev` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/chcpu` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/chgpasswd` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/chmem` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/chpasswd` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/chroot` | coreutils | distro base | no | no | 0x10000 |  |
| `/usr/sbin/faillock` | libpam-modules-bin | distro base | no | no | 0x10000 |  |
| `/usr/sbin/findfs` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/fsck` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/fsfreeze` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/fstab-decode` | sysvinit-utils | distro base | no | no | 0x10000 |  |
| `/usr/sbin/fstrim` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/gosu` | gosu | our additions (distro pkg) | no | no | 0x10000 |  |
| `/usr/sbin/groupadd` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/groupdel` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/groupmod` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/grpck` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/grpconv` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/grpunconv` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/iconvconfig` | libc-bin | distro base | no | no | 0x10000 |  |
| `/usr/sbin/isosize` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/killall5` | sysvinit-utils | distro base | no | no | 0x10000 |  |
| `/usr/sbin/ldattach` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/ldconfig` | libc-bin | distro base | no | no | 0x10000 |  |
| `/usr/sbin/losetup` | mount | distro base | no | no | 0x10000 |  |
| `/usr/sbin/mkfs` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/mkhomedir_helper` | libpam-modules-bin | distro base | no | no | 0x10000 |  |
| `/usr/sbin/mkswap` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/newusers` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/nologin` | login | distro base | no | no | 0x10000 |  |
| `/usr/sbin/pam_timestamp_check` | libpam-modules-bin | distro base | no | no | 0x10000 |  |
| `/usr/sbin/pivot_root` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/pwck` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/pwconv` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/pwhistory_helper` | libpam-modules-bin | distro base | no | no | 0x10000 |  |
| `/usr/sbin/pwunconv` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/readprofile` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/rmt-tar` | tar | distro base | no | no | 0x10000 |  |
| `/usr/sbin/rtcwake` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/runuser` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/start-stop-daemon` | dpkg | distro base | no | no | 0x10000 |  |
| `/usr/sbin/sulogin` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/swaplabel` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/swapoff` | mount | distro base | no | no | 0x10000 |  |
| `/usr/sbin/swapon` | mount | distro base | no | no | 0x10000 |  |
| `/usr/sbin/switch_root` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/unix_chkpwd` | libpam-modules-bin | distro base | no | no | 0x10000 |  |
| `/usr/sbin/unix_update` | libpam-modules-bin | distro base | no | no | 0x10000 |  |
| `/usr/sbin/update-passwd` | base-passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/useradd` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/userdel` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/usermod` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/vipw` | passwd | distro base | no | no | 0x10000 |  |
| `/usr/sbin/wipefs` | util-linux | distro base | no | no | 0x10000 |  |
| `/usr/sbin/zic` | libc-bin | distro base | no | no | 0x10000 |  |
| `/usr/sbin/zramctl` | util-linux | distro base | no | no | 0x10000 |  |
