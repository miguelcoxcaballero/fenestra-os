// SPDX-License-Identifier: GPL-3.0-or-later
// fakeinput: input for the nested KWin of the lock screen bench (org_kde_kwin_fake_input; KWin
// lets it in through a .desktop entry with X-KDE-Wayland-Interfaces=org_kde_kwin_fake_input).
//   fakeinput key CODE...        evdev key codes, pressed and released in order ("29+38": chord)
//   fakeinput type TEXT          keysyms (Latin-1), one press/release each
//   fakeinput move X Y           pointer to logical X, Y
//   fakeinput click X Y [hold-ms] left button at X, Y
//   fakeinput down X Y / up      left button pressed / released
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <wayland-client.h>
#include "fake-input-client-protocol.h"

static struct org_kde_kwin_fake_input *fake;

static void global(void *data, struct wl_registry *reg, uint32_t name, const char *iface, uint32_t version)
{
    if (strcmp(iface, org_kde_kwin_fake_input_interface.name) == 0)
        fake = wl_registry_bind(reg, name, &org_kde_kwin_fake_input_interface, version < 6 ? version : 6);
}
static void global_remove(void *data, struct wl_registry *reg, uint32_t name) {}
static const struct wl_registry_listener listener = {global, global_remove};

static void flush(struct wl_display *d, int ms) { wl_display_roundtrip(d); usleep(ms * 1000); }

int main(int argc, char **argv)
{
    if (argc < 2) return 2;
    struct wl_display *d = wl_display_connect(NULL);
    if (!d) { fprintf(stderr, "no wayland display\n"); return 1; }
    struct wl_registry *reg = wl_display_get_registry(d);
    wl_registry_add_listener(reg, &listener, NULL);
    wl_display_roundtrip(d);
    if (!fake) { fprintf(stderr, "no org_kde_kwin_fake_input\n"); return 1; }
    org_kde_kwin_fake_input_authenticate(fake, "lockscreen-bench", "lock screen tests");
    flush(d, 20);
    const char *op = argv[1];
    if (!strcmp(op, "key")) {
        for (int i = 2; i < argc; i++) {
            int codes[4], n = 0;
            char *s = strdup(argv[i]), *tok = strtok(s, "+");
            while (tok && n < 4) { codes[n++] = atoi(tok); tok = strtok(NULL, "+"); }
            for (int k = 0; k < n; k++) { org_kde_kwin_fake_input_keyboard_key(fake, codes[k], 1); flush(d, 15); }
            for (int k = n - 1; k >= 0; k--) { org_kde_kwin_fake_input_keyboard_key(fake, codes[k], 0); flush(d, 15); }
            free(s);
            usleep(40000);
        }
    } else if (!strcmp(op, "type") && argc > 2) {
        for (const unsigned char *c = (const unsigned char *)argv[2]; *c; c++) {
            org_kde_kwin_fake_input_keyboard_keysym(fake, *c, 1); flush(d, 10);
            org_kde_kwin_fake_input_keyboard_keysym(fake, *c, 0); flush(d, 30);
        }
    } else if ((!strcmp(op, "move") || !strcmp(op, "click") || !strcmp(op, "down")) && argc > 3) {
        org_kde_kwin_fake_input_pointer_motion_absolute(fake, wl_fixed_from_double(atof(argv[2])), wl_fixed_from_double(atof(argv[3])));
        flush(d, 60);
        if (strcmp(op, "move")) {
            org_kde_kwin_fake_input_button(fake, 0x110, 1); flush(d, argc > 4 ? atoi(argv[4]) : 40);
            if (!strcmp(op, "click")) { org_kde_kwin_fake_input_button(fake, 0x110, 0); flush(d, 20); }
        }
    } else if (!strcmp(op, "up")) {
        org_kde_kwin_fake_input_button(fake, 0x110, 0); flush(d, 20);
    } else return 2;
    wl_display_disconnect(d);
    return 0;
}
