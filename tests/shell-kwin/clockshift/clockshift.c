// SPDX-License-Identifier: GPL-3.0-or-later
// LD_PRELOAD for the benches: shifts the wall clock (CLOCK_REALTIME, gettimeofday, time) by the
// number of seconds in /tmp/clock-offset, read again every second, so a test can step the clock of
// running processes as chrony does at boot when the RTC was wrong. Monotonic clocks are untouched.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <sys/time.h>
#include <time.h>

static int (*real_gettime)(clockid_t, struct timespec *);

static long long offset(void)
{
    static long long value;
    static time_t checked = -1;
    struct timespec now;
    real_gettime(CLOCK_MONOTONIC_COARSE, &now);
    if (now.tv_sec != checked) {
        checked = now.tv_sec;
        FILE *f = fopen("/tmp/clock-offset", "r");
        value = 0;
        if (f) {
            if (fscanf(f, "%lld", &value) != 1)
                value = 0;
            fclose(f);
        }
    }
    return value;
}

int clock_gettime(clockid_t c, struct timespec *ts)
{
    if (!real_gettime)
        real_gettime = dlsym(RTLD_NEXT, "clock_gettime");
    int r = real_gettime(c, ts);
    if (r == 0 && (c == CLOCK_REALTIME || c == CLOCK_REALTIME_COARSE))
        ts->tv_sec += offset();
    return r;
}

int gettimeofday(struct timeval *tv, void *tz)
{
    (void)tz;
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    if (tv) {
        tv->tv_sec = ts.tv_sec;
        tv->tv_usec = ts.tv_nsec / 1000;
    }
    return 0;
}

time_t time(time_t *t)
{
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    if (t)
        *t = ts.tv_sec;
    return ts.tv_sec;
}
