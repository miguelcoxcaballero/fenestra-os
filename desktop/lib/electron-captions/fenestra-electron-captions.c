// SPDX-License-Identifier: GPL-3.0-or-later
// Fenestra: no GNOME circles behind the caption buttons of Electron apps that draw their own title
// bar (titleBarStyle "hidden" + titleBarOverlay, e.g. Claude desktop).
//
// Electron 44 on Linux paints those buttons itself (FreedesktopNavButtonProvider): a 24 px circle
// of the text colour behind each glyph (libadwaita's look), whatever the GTK theme says. It uses
// that provider only when GTK 3 is already loaded, which it checks with
//     dlopen("libgtk-3.so.0", RTLD_LAZY | RTLD_NOLOAD)
// (shell/browser/ui/gtk/gtk_symbolic_icon_provider.cc). Answering "not loaded" to that one probe
// makes Electron fall back to Chromium's flat vector caption buttons (no circle at rest). GTK
// itself keeps working: every real dlopen goes through untouched.
//
// Loaded with LD_PRELOAD by the app's launcher (desktop/bin/fenestra-electron-run). It removes
// itself from LD_PRELOAD at once, so the app's child processes (helpers, shells, tools the app
// runs) never inherit it.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdlib.h>
#include <string.h>

static void *(*real_dlopen)(const char *, int);

__attribute__((constructor)) static void forget_preload(void)
{
    const char *p = getenv("LD_PRELOAD");
    if (p && strstr(p, "fenestra-electron-captions"))
        unsetenv("LD_PRELOAD");
}

void *dlopen(const char *name, int flags)
{
    if (!real_dlopen)
        real_dlopen = (void *(*)(const char *, int))dlsym(RTLD_NEXT, "dlopen");
    if (name && (flags & RTLD_NOLOAD) && strcmp(name, "libgtk-3.so.0") == 0)
        return NULL;
    return real_dlopen(name, flags);
}
