# syntax=docker/dockerfile:1

# ============================================================
# Syscall probe image (experiment #529). Not the application.
#
# Prints how the container's seccomp filter answers the system calls that
# newer libc versions use, once with a binary built on Debian 13 (glibc 2.41)
# and once on Debian 11 (glibc 2.31). Run it twice on an affected host:
# with the default profile and with --security-opt seccomp=unconfined.
# ============================================================

# Unused: the CI workflow passes a named build context with this name.
FROM scratch AS frontend-build

FROM scratch AS probe-src
COPY <<'PROBE_C' /probe.c
/*
 * Syscall / seccomp probe (experiment #529).
 *
 * Shows how the container's seccomp filter answers system calls that newer
 * libc versions use: calls the kernel does not know must fail with ENOSYS so
 * glibc can fall back; old Docker profiles (< 20.10.9) answer EPERM instead.
 * Nothing here changes any state. Dummy arguments are chosen to be harmless.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <gnu/libc-version.h>
#include <linux/futex.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>

#if defined(__arm__)
#ifndef __NR_clock_gettime64
#define __NR_clock_gettime64 403
#endif
#ifndef __NR_clock_nanosleep_time64
#define __NR_clock_nanosleep_time64 407
#endif
#ifndef __NR_ppoll_time64
#define __NR_ppoll_time64 414
#endif
#ifndef __NR_futex_time64
#define __NR_futex_time64 422
#endif
#ifndef __NR_pidfd_open
#define __NR_pidfd_open 434
#endif
#ifndef __NR_clone3
#define __NR_clone3 435
#endif
#ifndef __NR_close_range
#define __NR_close_range 436
#endif
#ifndef __NR_openat2
#define __NR_openat2 437
#endif
#ifndef __NR_faccessat2
#define __NR_faccessat2 439
#endif
#ifndef __NR_epoll_pwait2
#define __NR_epoll_pwait2 441
#endif
#endif

struct kts64 {
    int64_t tv_sec;
    int64_t tv_nsec;
};

static int n_eperm;

static void report(const char *name, long rc, int err, int is_new)
{
    const char *v;
    if (rc >= 0) {
        v = "ok";
    } else if (err == ENOSYS) {
        v = "ENOSYS  (kernel does not implement it; libc can fall back)";
    } else if (err == EPERM) {
        v = "EPERM   <== answered by the seccomp filter";
        if (is_new)
            n_eperm++;
    } else {
        v = "implemented (kernel rejected the dummy arguments)";
    }
    printf("  %-24s rc=%-4ld errno=%-3d %s\n", name, rc, rc >= 0 ? 0 : err, v);
}

#define PROBE(label, is_new, ...)                                              \
    do {                                                                       \
        errno = 0;                                                             \
        long rc_ = syscall(__VA_ARGS__);                                       \
        report(label, rc_, errno, is_new);                                     \
        if (rc_ >= 0 && (is_new == 2))                                         \
            close((int)rc_);                                                   \
    } while (0)

static void *thread_fn(void *arg)
{
    (void)arg;
    return NULL;
}

int main(void)
{
    struct utsname u;
    char line[256];
    FILE *f;
    int control_errno;
    long rc;

    setvbuf(stdout, NULL, _IONBF, 0);

    uname(&u);
    printf("kernel          : %s %s\n", u.release, u.machine);
    printf("page size       : %ld\n", sysconf(_SC_PAGESIZE));
    printf("libc            : glibc %s, sizeof(time_t)=%zu\n",
           gnu_get_libc_version(), sizeof(time_t));
    f = fopen("/proc/self/status", "r");
    if (f) {
        while (fgets(line, sizeof line, f))
            if (!strncmp(line, "Seccomp", 7) || !strncmp(line, "NoNewPrivs", 10))
                printf("proc status     : %s", line);
        fclose(f);
    }

    printf("\nControl (a system call number that exists nowhere):\n");
    errno = 0;
    rc = syscall(1000);
    control_errno = errno;
    report("syscall(1000)", rc, control_errno, 0);

    printf("\nBaseline calls (old, always whitelisted):\n");
    {
        long ts[2];
        PROBE("getpid", 0, __NR_getpid);
        PROBE("clock_gettime (32-bit)", 0, __NR_clock_gettime, CLOCK_REALTIME, ts);
    }

    printf("\nCalls used by newer libc versions:\n");
    {
        struct kts64 k = {0, 0};
        struct kts64 zero = {0, 0};
        int futex_word = 0;
        long how[3] = {0, 0, 0};
        unsigned char buf[8];
        char statx_buf[256];
        (void)k;
        (void)zero;
        (void)futex_word;
#ifdef __NR_clock_gettime64
        PROBE("clock_gettime64", 1, __NR_clock_gettime64, CLOCK_REALTIME, &k);
#endif
#ifdef __NR_clock_nanosleep_time64
        PROBE("clock_nanosleep_time64", 1, __NR_clock_nanosleep_time64,
              CLOCK_MONOTONIC, 0, &zero, NULL);
#endif
#ifdef __NR_futex_time64
        PROBE("futex_time64", 1, __NR_futex_time64, &futex_word,
              FUTEX_WAKE_PRIVATE, 1, NULL, NULL, 0);
#endif
#ifdef __NR_ppoll_time64
        PROBE("ppoll_time64", 1, __NR_ppoll_time64, NULL, 0, &zero, NULL, 0);
#endif
#ifdef __NR_faccessat2
        PROBE("faccessat2", 1, __NR_faccessat2, AT_FDCWD, "/", F_OK, 0);
#endif
#ifdef __NR_clone3
        PROBE("clone3", 1, __NR_clone3, NULL, 0);
#endif
#ifdef __NR_close_range
        PROBE("close_range", 1, __NR_close_range, 1000u, 999u, 0);
#endif
#ifdef __NR_openat2
        PROBE("openat2", 2, __NR_openat2, AT_FDCWD, "/", how, 24);
#endif
#ifdef __NR_pidfd_open
        PROBE("pidfd_open", 2, __NR_pidfd_open, getpid(), 0);
#endif
#ifdef __NR_epoll_pwait2
        PROBE("epoll_pwait2", 1, __NR_epoll_pwait2, -1, NULL, 1, NULL, NULL, 0);
#endif
        PROBE("statx", 0, __NR_statx, AT_FDCWD, "/", 0, 0x7ffu, statx_buf);
        PROBE("getrandom", 0, __NR_getrandom, buf, sizeof buf, 0);
        PROBE("memfd_create", 2, __NR_memfd_create, "probe", 0);
        PROBE("copy_file_range", 0, __NR_copy_file_range, -1, NULL, -1, NULL, 0, 0);
    }

    printf("\nWhat the C library makes of it:\n");
    {
        struct timespec ts;
        struct tm tm;
        time_t t;
        pthread_t th;
        int prc;

        errno = 0;
        t = time(NULL);
        printf("  time()                 = %lld\n", (long long)t);
        errno = 0;
        rc = clock_gettime(CLOCK_REALTIME, &ts);
        printf("  clock_gettime(REALTIME)  rc=%ld errno=%d (%s) sec=%lld\n", rc,
               errno, strerror(errno), (long long)ts.tv_sec);
        errno = 0;
        rc = clock_gettime(CLOCK_MONOTONIC, &ts);
        printf("  clock_gettime(MONOTONIC) rc=%ld errno=%d (%s) sec=%lld\n", rc,
               errno, strerror(errno), (long long)ts.tv_sec);
        errno = 0;
        if (localtime_r(&t, &tm))
            printf("  localtime_r()            ok (year %d)\n", tm.tm_year + 1900);
        else
            printf("  localtime_r()            FAILED errno=%d (%s)\n", errno,
                   strerror(errno));
        prc = pthread_create(&th, NULL, thread_fn, NULL);
        if (prc == 0) {
            pthread_join(th, NULL);
            printf("  pthread_create()         ok\n");
        } else {
            printf("  pthread_create()         FAILED rc=%d (%s)\n", prc,
                   strerror(prc));
        }
        errno = 0;
        if (faccessat(AT_FDCWD, "/", W_OK, 0) == 0)
            printf("  faccessat(W_OK)          ok\n");
        else
            printf("  faccessat(W_OK)          FAILED errno=%d (%s)\n", errno,
                   strerror(errno));
    }

    printf("\nVERDICT\n");
    if (control_errno == EPERM) {
        printf("  The seccomp profile answers EPERM for system calls it does not\n"
               "  list (old Docker, < 20.10.9). %d newer call(s) above got EPERM.\n"
               "  glibc 2.33+/2.34+ only falls back to the old calls on ENOSYS,\n"
               "  so images based on a newer libc break on this host.\n",
               n_eperm);
    } else if (control_errno == ENOSYS) {
        printf("  Unknown system calls are answered with ENOSYS (kernel or a\n"
               "  modern seccomp profile). Newer libc versions can fall back.\n"
               "  %d newer call(s) above got EPERM.\n",
               n_eperm);
    } else {
        printf("  Unexpected result for the control call (errno %d).\n",
               control_errno);
    }
    return 0;
}
PROBE_C

FROM debian:trixie-slim AS build-glibc241
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libc6-dev && \
    rm -rf /var/lib/apt/lists/*
COPY --from=probe-src /probe.c /src/probe.c
RUN gcc -O1 -Wall -static -pthread -o /probe /src/probe.c

FROM python:3.11-slim-bullseye@sha256:9e25f400253a5fa3191813d6a67eb801ca1e6f012b3bd2588fa6920b59e3eba6 AS build-glibc231
RUN printf '%s\n' \
        'deb http://archive.debian.org/debian bullseye main' \
        'deb http://archive.debian.org/debian-security bullseye-security main' \
        > /etc/apt/sources.list && \
    echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99archive && \
    apt-get update && \
    apt-get install -y --no-install-recommends gcc libc6-dev && \
    rm -rf /var/lib/apt/lists/*
COPY --from=probe-src /probe.c /src/probe.c
RUN gcc -O1 -Wall -static -pthread -o /probe /src/probe.c

FROM python:3.11-slim-bullseye@sha256:9e25f400253a5fa3191813d6a67eb801ca1e6f012b3bd2588fa6920b59e3eba6 AS probe
COPY --from=build-glibc241 /probe /opt/probe/probe-glibc241
COPY --from=build-glibc231 /probe /opt/probe/probe-glibc231
COPY <<'RUN_SH' /run.sh
#!/bin/sh
echo "##### Build A: static binary built on Debian 13 (glibc 2.41) #####"
/opt/probe/probe-glibc241
echo
echo "##### Build B: static binary built on Debian 11 (glibc 2.31) #####"
/opt/probe/probe-glibc231
RUN_SH
RUN chmod +x /run.sh
ENTRYPOINT ["/run.sh"]
