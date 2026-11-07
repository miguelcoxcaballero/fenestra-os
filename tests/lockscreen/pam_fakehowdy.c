// SPDX-License-Identifier: GPL-3.0-or-later
// pam_fakehowdy.so: a stand-in for pam_howdy on the lock screen bench. It talks like Howdy 3
// ("Attempting facial authentication" at once, "Face detection timeout reached" when it gives up)
// and answers what /tmp/face says (success | fail | wait) after /tmp/face-delay seconds.
// Built without pam-devel: the few libpam symbols it needs are declared here.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef struct pam_handle pam_handle_t;
#define PAM_SUCCESS 0
#define PAM_AUTH_ERR 7
#define PAM_IGNORE 25
#define PAM_TEXT_INFO 4
extern int pam_prompt(pam_handle_t *pamh, int style, char **response, const char *fmt, ...);

static void readfile(const char *path, char *buf, size_t n, const char *fallback)
{
    FILE *f = fopen(path, "r");
    if (!f || !fgets(buf, n, f)) { snprintf(buf, n, "%s", fallback); if (f) fclose(f); return; }
    fclose(f);
    buf[strcspn(buf, "\n")] = 0;
}

int pam_sm_authenticate(pam_handle_t *pamh, int flags, int argc, const char **argv)
{
    char mode[32], delay[32];
    pam_prompt(pamh, PAM_TEXT_INFO, NULL, "%s", "Attempting facial authentication");
    readfile("/tmp/face-delay", delay, sizeof delay, "2");
    for (int i = 0; i < atoi(delay) * 10; i++) {
        readfile("/tmp/face", mode, sizeof mode, "wait");
        if (!strcmp(mode, "success")) break;
        usleep(100000);
    }
    readfile("/tmp/face", mode, sizeof mode, "wait");
    FILE *log = fopen("/out/pam.log", "a");
    if (log) { fprintf(log, "face %s\n", mode); fclose(log); }
    if (!strcmp(mode, "success")) return PAM_SUCCESS;
    pam_prompt(pamh, PAM_TEXT_INFO, NULL, "%s", "Face detection timeout reached");
    return PAM_AUTH_ERR;
}

int pam_sm_setcred(pam_handle_t *pamh, int flags, int argc, const char **argv) { return PAM_SUCCESS; }
