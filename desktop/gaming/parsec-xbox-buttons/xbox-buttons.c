// SPDX-License-Identifier: GPL-3.0-or-later
// Parsec (Linux) swaps X and Y on Xbox controllers: its input library (libmatoya,
// src/unix/linux/x11/evdev.c) maps BTN_X to Y and BTN_Y to X, following the kernel's
// gamepad document (BTN_NORTH == BTN_X). The Xbox drivers (xpad, xpadneo, hid-microsoft) send
// BTN_X for the left button labelled X and BTN_Y for the top one labelled Y, so a game asking
// for Y got X. PlayStation pads are right in Parsec (hid-playstation follows the document).
//
// Loaded into Parsec only (LD_PRELOAD, see install.sh): read() on an evdev node whose driver
// is one of the Xbox drivers swaps the two key codes before Parsec sees them. Nothing else is
// touched.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <linux/input.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>

#define INPUT_MAJOR 13
#define MAX_FD 1024

// per fd: the evdev node it was checked for (0 = not checked) and whether to swap
static dev_t checked[MAX_FD];
static unsigned char swap_xy[MAX_FD];

static int xbox_driver(dev_t rdev)
{
    // /sys/dev/char/13:N -> .../inputM/eventN; inputM/device is the USB interface or HID device
    char path[128], target[256];
    snprintf(path, sizeof path, "/sys/dev/char/%u:%u/device/device/driver", major(rdev), minor(rdev));
    ssize_t n = readlink(path, target, sizeof target - 1);
    if (n <= 0)
        return 0;
    target[n] = 0;
    const char *name = strrchr(target, '/');
    name = name ? name + 1 : target;
    return !strcmp(name, "xpad") || !strcmp(name, "xpadneo") || !strcmp(name, "hid-xpadneo")
        || !strcmp(name, "microsoft");
}

static int should_swap(int fd)
{
    struct stat st;
    if (fd < 0 || fd >= MAX_FD || fstat(fd, &st) != 0 || !S_ISCHR(st.st_mode) || major(st.st_rdev) != INPUT_MAJOR)
        return 0;
    if (checked[fd] != st.st_rdev) {   // first read, or the fd now names another device
        checked[fd] = st.st_rdev;
        swap_xy[fd] = (unsigned char)xbox_driver(st.st_rdev);
    }
    return swap_xy[fd];
}

ssize_t read(int fd, void *buf, size_t count)
{
    static ssize_t (*real_read)(int, void *, size_t);
    if (!real_read)
        real_read = (ssize_t (*)(int, void *, size_t))dlsym(RTLD_NEXT, "read");
    ssize_t r = real_read(fd, buf, count);
    if (r >= (ssize_t)sizeof(struct input_event) && should_swap(fd)) {
        struct input_event *ev = buf;
        for (size_t i = 0; i < (size_t)r / sizeof *ev; ++i) {
            if (ev[i].type != EV_KEY)
                continue;
            if (ev[i].code == BTN_X)
                ev[i].code = BTN_Y;
            else if (ev[i].code == BTN_Y)
                ev[i].code = BTN_X;
        }
    }
    return r;
}
