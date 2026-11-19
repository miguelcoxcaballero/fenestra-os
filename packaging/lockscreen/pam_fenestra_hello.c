// SPDX-License-Identifier: GPL-3.0-or-later
// pam_fenestra_hello.so: Windows Hello for Fenestra's lock screen: face (Howdy) and fingerprint
// (fprintd) at the same time, in kscreenlocker's *non-interactive* worker (/etc/pam.d/kde-fingerprint),
// never in the password's. Everything it starts is a child with a hard deadline: a camera that never
// delivers a frame or an fprintd that hangs costs this worker its timeout, nothing else, and the
// password worker is a different process altogether.
//
//   auth [success=done default=die] pam_fenestra_hello.so [face_timeout=10] [finger_timeout=25]
//        [face_tries=2] [howdy=PATH] [fprintd=PATH]
//
// Messages (PAM_TEXT_INFO, read by the lock screen):
//   "Attempting facial authentication"            Howdy is looking (the Hello animation plays)
//   "Place your finger on the fingerprint reader" fprintd is waiting
//   "Identified face"                             face succeeded (the smile, then unlock)
//   "Fingerprint matched"                         fingerprint succeeded
//   "Face not recognised"                         face gave up (timeout, no camera, no model)
// Face is tried face_tries times per lock screen (per greeter process), then only again after
// the lock screen asks for it ($XDG_RUNTIME_DIR/fenestra-hello/retry-<greeter pid>).
// Every attempt is logged (journalctl -t pam_fenestra_hello): Howdy's exit code and how long it
// looked, fprintd-verify's, so that "face works badly" can be told apart from a camera, a
// timeout or a print that is not on the sensor any more.
// Built without pam-devel headers on purpose (the few symbols are declared below).
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <glob.h>
#include <pwd.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <syslog.h>
#include <time.h>
#include <unistd.h>

typedef struct pam_handle pam_handle_t;
#define PAM_SUCCESS 0
#define PAM_SERVICE_ERR 3
#define PAM_AUTH_ERR 7
#define PAM_AUTHINFO_UNAVAIL 9
#define PAM_USER_UNKNOWN 10
#define PAM_IGNORE 25
#define PAM_TEXT_INFO 4
extern int pam_prompt(pam_handle_t *pamh, int style, char **response, const char *fmt, ...);
extern int pam_get_user(pam_handle_t *pamh, const char **user, const char *prompt);

static void info(pam_handle_t *h, const char *msg) { pam_prompt(h, PAM_TEXT_INFO, NULL, "%s", msg); }

static long now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000L + ts.tv_nsec / 1000000L;
}

static const char *arg(int argc, const char **argv, const char *key, const char *fallback)
{
    size_t n = strlen(key);
    for (int i = 0; i < argc; i++)
        if (!strncmp(argv[i], key, n) && argv[i][n] == '=')
            return argv[i] + n + 1;
    return fallback;
}

// A child in its own process group that dies with the worker (kscreenlocker kills workers it
// cancels: nothing of ours may outlive them, the camera least of all).
static pid_t spawn(char *const cmd[])
{
    pid_t pid = fork();
    if (pid != 0)
        return pid;
    prctl(PR_SET_PDEATHSIG, SIGKILL);
    setpgid(0, 0);
    int devnull = open("/dev/null", O_RDWR);
    if (devnull >= 0) {
        dup2(devnull, 0); dup2(devnull, 1); dup2(devnull, 2);
    }
    execv(cmd[0], cmd);
    _exit(127);
}

// Face through fenestra-face-server (session/libexec): Howdy already loaded, so the comparison
// starts at once instead of after ~2 s of Python imports and models. A child connects, asks for
// `user` and exits with Howdy's code; killing it (fingerprint or password won) hangs up, which
// cancels the attempt in the server. -1: no server (the caller starts Howdy itself).
static pid_t spawn_face_server(const char *runtime, const char *user)
{
    char path[sizeof(((struct sockaddr_un *)0)->sun_path)];
    if (snprintf(path, sizeof path, "%s/fenestra-face.sock", runtime) >= (int)sizeof path || access(path, W_OK) != 0)
        return -1;
    int fd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (fd < 0)
        return -1;
    struct sockaddr_un addr = {.sun_family = AF_UNIX};
    snprintf(addr.sun_path, sizeof addr.sun_path, "%s", path);
    if (connect(fd, (struct sockaddr *)&addr, sizeof addr) != 0) {
        close(fd);
        return -1;
    }
    struct ucred cred;
    socklen_t len = sizeof cred;
    // Only a server of this user's (anyone else could answer "recognised").
    if (getsockopt(fd, SOL_SOCKET, SO_PEERCRED, &cred, &len) != 0 || cred.uid != getuid()) {
        close(fd);
        return -1;
    }
    pid_t pid = fork();
    if (pid != 0) {
        close(fd);
        return pid;
    }
    prctl(PR_SET_PDEATHSIG, SIGKILL);
    setpgid(0, 0);
    char line[300];
    int n = snprintf(line, sizeof line, "%s\n", user);
    if (n <= 0 || n >= (int)sizeof line || write(fd, line, n) != n)
        _exit(1);
    char reply[8] = {0};
    ssize_t got = 0;
    while (got < (ssize_t)sizeof reply - 1) {
        ssize_t r = read(fd, reply + got, sizeof reply - 1 - got);
        if (r <= 0)
            break;
        got += r;
        if (reply[got - 1] == '\n')
            break;
    }
    if (got < 2 || reply[got - 1] != '\n')
        _exit(1);
    _exit(atoi(reply) & 0xff);
}

static void kill_tree(pid_t pid)
{
    if (pid <= 0)
        return;
    kill(-pid, SIGKILL);
    kill(pid, SIGKILL);
    waitpid(pid, NULL, 0);
}

static int howdy_path(char *out, size_t size, const char *configured)
{
    if (configured) {
        snprintf(out, size, "%s", configured);
        return access(out, R_OK) == 0;
    }
    glob_t g;
    int ok = 0;
    if (glob("/usr/lib/python3*/site-packages/howdy/compare.py", 0, NULL, &g) == 0 && g.gl_pathc > 0) {
        snprintf(out, size, "%s", g.gl_pathv[0]);
        ok = 1;
    }
    globfree(&g);
    return ok;
}

// Per lock screen state: the worker's parent is the greeter (one per lock).
static int face_state(const char *runtime, int tries, int fail)
{
    char dir[512], file[600], retry[600];
    snprintf(dir, sizeof dir, "%s/fenestra-hello", runtime);
    mkdir(dir, 0700);
    snprintf(file, sizeof file, "%s/face-%d", dir, (int)getppid());
    snprintf(retry, sizeof retry, "%s/retry-%d", dir, (int)getppid());
    int count = 0;
    FILE *f = fopen(file, "r");
    if (f) { if (fscanf(f, "%d", &count) != 1) count = 0; fclose(f); }
    if (access(retry, F_OK) == 0) { unlink(retry); count = 0; }
    if (fail >= 0) {
        count = fail ? count + 1 : 0;
        f = fopen(file, "w");
        if (f) { fprintf(f, "%d\n", count); fclose(f); }
    }
    return count < tries;
}

int pam_sm_authenticate(pam_handle_t *pamh, int flags, int argc, const char **argv)
{
    (void)flags;
    const char *user = NULL;
    if (pam_get_user(pamh, &user, NULL) != PAM_SUCCESS || !user || !*user)
        return PAM_USER_UNKNOWN;
    const long face_timeout = atol(arg(argc, argv, "face_timeout", "10")) * 1000L;
    const long finger_timeout = atol(arg(argc, argv, "finger_timeout", "25")) * 1000L;
    const int face_tries = atoi(arg(argc, argv, "face_tries", "2"));
    const char *fprintd = arg(argc, argv, "fprintd", "/usr/bin/fprintd-verify");
    struct passwd *pw = getpwnam(user);
    char runtime[256];
    snprintf(runtime, sizeof runtime, "/run/user/%d", pw ? (int)pw->pw_uid : (int)getuid());
    if (getenv("XDG_RUNTIME_DIR"))
        snprintf(runtime, sizeof runtime, "%s", getenv("XDG_RUNTIME_DIR"));

    // Face: Howdy installed, this user enrolled (and the model readable: the worker runs as the user).
    char compare[512], model[512];
    int face = howdy_path(compare, sizeof compare, arg(argc, argv, "howdy", NULL));
    snprintf(model, sizeof model, "/etc/howdy/models/%s.dat", user);
    if (face && !arg(argc, argv, "howdy", NULL))
        face = access(model, R_OK) == 0;
    if (face)
        face = face_state(runtime, face_tries, -1);
    int finger = access(fprintd, X_OK) == 0;
    if (!face && !finger)
        return PAM_AUTHINFO_UNAVAIL;
    openlog("pam_fenestra_hello", LOG_PID, LOG_AUTHPRIV);

    pid_t face_pid = -1, finger_pid = -1;
    const long start = now_ms();
    if (face) {
        if (!arg(argc, argv, "howdy", NULL))
            face_pid = spawn_face_server(runtime, user);
        if (face_pid > 0) {
            syslog(LOG_INFO, "face: through fenestra-face-server");
        } else {
            char *cmd[] = {"/usr/bin/python3", compare, (char *)user, NULL};
            if (arg(argc, argv, "howdy", NULL)) { cmd[0] = compare; cmd[1] = (char *)user; cmd[2] = NULL; }
            face_pid = spawn(cmd);
        }
        info(pamh, "Attempting facial authentication");
    }
    if (finger) {
        char *cmd[] = {(char *)fprintd, (char *)user, NULL};
        finger_pid = spawn(cmd);
        info(pamh, "Place your finger on the fingerprint reader");
    }
    int result = PAM_AUTH_ERR, quick = 0;
    long finger_started = now_ms();
    while (face_pid > 0 || finger_pid > 0) {
        const long t = now_ms() - start;
        int status;
        if (face_pid > 0) {
            pid_t r = waitpid(face_pid, &status, WNOHANG);
            if (r == face_pid) {
                face_pid = -1;
                // Howdy's codes: 0 recognised, 10 no model, 11 timed out (no match), 12 aborted,
                // 13 every frame too dark, 14 no camera.
                syslog(LOG_INFO, "face: exit %d after %ld ms", WIFEXITED(status) ? WEXITSTATUS(status) : -WTERMSIG(status), t);
                if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
                    face_state(runtime, face_tries, 0);
                    info(pamh, "Identified face");
                    result = PAM_SUCCESS;
                    break;
                }
                face_state(runtime, face_tries, 1);
                info(pamh, "Face not recognised");
            } else if (t > face_timeout) {
                kill_tree(face_pid);   // a camera that delivers nothing: Howdy would wait forever
                face_pid = -1;
                syslog(LOG_INFO, "face: no answer within %ld ms, stopped", face_timeout);
                face_state(runtime, face_tries, 1);
                info(pamh, "Face not recognised");
            }
        }
        if (finger_pid > 0) {
            pid_t r = waitpid(finger_pid, &status, WNOHANG);
            if (r == finger_pid) {
                finger_pid = -1;
                syslog(LOG_INFO, "finger: fprintd-verify exit %d after %ld ms", WIFEXITED(status) ? WEXITSTATUS(status) : -WTERMSIG(status),
                       now_ms() - finger_started);
                if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
                    info(pamh, "Fingerprint matched");
                    result = PAM_SUCCESS;
                    break;
                }
                // No match: keep listening until the deadline, as Windows. An fprintd-verify that
                // gives up at once (no print on the sensor any more, device claimed by someone
                // else) twice in a row is not retried in this attempt: no busy loop.
                quick = (now_ms() - finger_started < 1500) ? quick + 1 : 0;
                if (quick < 2 && t + 1000 < finger_timeout) {
                    usleep(300 * 1000);
                    char *cmd[] = {(char *)fprintd, (char *)user, NULL};
                    finger_pid = spawn(cmd);
                    finger_started = now_ms();
                }
            } else if (t > finger_timeout) {
                kill_tree(finger_pid);  // fprintd hung (or nobody touched the reader)
                finger_pid = -1;
            }
        }
        usleep(50 * 1000);
    }
    kill_tree(face_pid);
    kill_tree(finger_pid);
    syslog(LOG_INFO, "result: %s after %ld ms", result == PAM_SUCCESS ? "unlocked" : "not recognised", now_ms() - start);
    closelog();
    return result;
}

int pam_sm_setcred(pam_handle_t *pamh, int flags, int argc, const char **argv)
{
    (void)pamh; (void)flags; (void)argc; (void)argv;
    return PAM_SUCCESS;
}
