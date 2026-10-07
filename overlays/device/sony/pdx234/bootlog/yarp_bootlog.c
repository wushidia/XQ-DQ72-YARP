// Device-side early boot diagnostics. No userdata decryption or GUI dependency.
#define _GNU_SOURCE 1
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/klog.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include "logging_settings.h"
#ifdef __ANDROID__
#include <sys/system_properties.h>
#endif

#define MAX_BYTES (256U * 1024U)
#define RESERVE_BYTES (4ULL * 1024ULL * 1024ULL)
#define EXT4_MAGIC 0xef53
#define F2FS_MAGIC 0xf2f52010
static volatile sig_atomic_t stopping;
static unsigned char buf[MAX_BYTES];

static void stop_handler(int sig) { (void)sig; stopping = 1; }

static int startup_logging = -1;

static int runtime_logging(void) {
#ifdef __ANDROID__
    char value[PROP_VALUE_MAX] = {0};
    if (__system_property_get(YARP_LOGGING_PROPERTY, value) > 0) {
        if (!strcmp(value, "0")) return 0;
        if (!strcmp(value, "1")) return 1;
    }
#endif
    return -1;
}

static bool logging_enabled(void) {
    if (stopping) return false;
    int current = runtime_logging();
    return (current < 0 ? startup_logging : current) == 1;
}

static void report_logging_active(bool active) {
#ifdef __ANDROID__
    (void)__system_property_set("twrp.yarp.logging_active", active ? "1" : "0");
#else
    (void)active;
#endif
}

static int settings_policy_at(const char* mountpoint) {
    char name[PATH_MAX];
    if (snprintf(name, sizeof(name), "%s/TWRP/.twrp_settings", mountpoint) >=
        (int)sizeof(name)) return -1;
    int fd = open(name, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return errno == ENOENT ? 1 : -1;
    FILE* file = fdopen(fd, "rb");
    if (!file) { close(fd); return -1; }
    int enabled = yarp_logging_from_settings(file);
    if (fclose(file) != 0) return -1;
    return enabled;
}

static bool persist_is_mounted(void) {
    struct stat partition, parent;
    return stat("/mnt/vendor/persist", &partition) == 0 &&
        stat("/mnt/vendor", &parent) == 0 && partition.st_dev != parent.st_dev;
}

static int read_startup_policy(void) {
    if (persist_is_mounted()) return settings_policy_at("/mnt/vendor/persist");
    // Mount privately, read-only, and release it before recovery mounts persist.
    // This probe never creates a settings file and never touches Metadata.
    const char* mountpoint = "/tmp/yarp-bootlog-persist";
    if (mkdir(mountpoint, 0700) < 0 && errno != EEXIST) return -1;
    const char* devices[] = {"/dev/block/by-name/persist",
                             "/dev/block/bootdevice/by-name/persist"};
    for (size_t i = 0; i < sizeof(devices) / sizeof(devices[0]); ++i) {
        if (access(devices[i], F_OK)) continue;
        if (mount(devices[i], mountpoint, "ext4",
                  MS_RDONLY | MS_NOSUID | MS_NODEV | MS_NOATIME, "") != 0)
            continue;
        int enabled = settings_policy_at(mountpoint);
        if (umount(mountpoint) != 0) return -1;
        return enabled;
    }
    return -1;
}

static int write_all(int fd, const void* data, size_t n) {
    const unsigned char* p = data;
    while (n) {
        ssize_t w = write(fd, p, n);
        if (w < 0 && errno == EINTR) continue;
        if (w <= 0) return -1;
        n -= (size_t)w;
        p += w;
    }
    return 0;
}

static bool enough_space(void) {
    struct statfs s;
    return statfs("/metadata", &s) == 0 &&
        (unsigned long long)s.f_bavail * s.f_bsize > RESERVE_BYTES + MAX_BYTES;
}

static bool mounted_metadata(void) {
    struct statfs s, parent;
    struct stat a, b;
    if (statfs("/metadata", &s) || statfs("/", &parent) ||
        stat("/metadata", &a) || stat("/", &b)) return false;
    return a.st_dev != b.st_dev &&
        ((unsigned long)s.f_type == EXT4_MAGIC ||
         (unsigned long)s.f_type == F2FS_MAGIC);
}

static bool ensure_metadata(void) {
    if (!logging_enabled()) return false;
    if (mounted_metadata()) return true;
    struct stat s;
    if (lstat("/metadata", &s) == 0 && !S_ISDIR(s.st_mode)) return false;
    if (mkdir("/metadata", 0755) < 0 && errno != EEXIST) return false;
    const char* devs[] = {"/dev/block/by-name/metadata",
                         "/dev/block/bootdevice/by-name/metadata"};
    for (size_t i = 0; i < sizeof(devs) / sizeof(devs[0]); ++i) {
        if (access(devs[i], F_OK)) continue;
        // Try the existing filesystem only. Never format or run a repair tool.
        if (mount(devs[i], "/metadata", "ext4", MS_NOSUID | MS_NODEV | MS_NOATIME, "") == 0 ||
            mount(devs[i], "/metadata", "f2fs", MS_NOSUID | MS_NODEV | MS_NOATIME, "") == 0)
            return mounted_metadata();
        if (mounted_metadata()) return true;
    }
    return false;
}

static int directory_at(int parent, const char* name) {
    if (!logging_enabled()) { errno = ECANCELED; return -1; }
    if (mkdirat(parent, name, 0755) < 0 && errno != EEXIST) return -1;
    return openat(parent, name, O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
}

static ssize_t read_tail_fd(int fd, unsigned char* out, size_t cap) {
    size_t used = 0;
    unsigned char chunk[4096];
    // Seek regular files to their tail. sysfs/procfs often cannot be sought.
    struct stat s;
    if (fstat(fd, &s) == 0 && S_ISREG(s.st_mode) && s.st_size > (off_t)cap)
        (void)lseek(fd, s.st_size - (off_t)cap, SEEK_SET);
    for (;;) {
        ssize_t n = read(fd, chunk, sizeof(chunk));
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) return used ? (ssize_t)used : -1;
        if (!n) return (ssize_t)used;
        if (used + (size_t)n > cap) {
            size_t drop = used + (size_t)n - cap;
            memmove(out, out + drop, used - drop);
            used -= drop;
        }
        memcpy(out + used, chunk, (size_t)n);
        used += (size_t)n;
    }
}

static int save_bytes(int dir, const char* name, const void* data, size_t n) {
    if (!logging_enabled() || n > MAX_BYTES || !enough_space()) return -1;
    // Skip unchanged snapshots to reduce flash writes.
    int old = openat(dir, name, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (old >= 0) {
        struct stat s;
        unsigned char* check = malloc(n ? n : 1);
        bool same = false;
        if (check && fstat(old, &s) == 0 && s.st_size == (off_t)n) {
            size_t got = 0;
            while (got < n) {
                ssize_t r = read(old, check + got, n - got);
                if (r <= 0) break;
                got += (size_t)r;
            }
            same = got == n && !memcmp(check, data, n);
        }
        free(check);
        close(old);
        if (same) return 0;
    }
    char temp[NAME_MAX + 1];
    if (snprintf(temp, sizeof(temp), ".%s.new", name) >= (int)sizeof(temp)) return -1;
    if (!logging_enabled()) return -1;
    int fd = openat(dir, temp, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC | O_NOFOLLOW, 0644);
    if (fd < 0) return -1;
    int rc = write_all(fd, data, n);
    if (!logging_enabled()) rc = -1;
    if (rc == 0) rc = fsync(fd);
    close(fd);
    if (!logging_enabled()) rc = -1;
    if (rc == 0) rc = renameat(dir, temp, dir, name);
    if (rc == 0) rc = fsync(dir);
    if (rc && logging_enabled()) (void)unlinkat(dir, temp, 0);
    return rc;
}

static int snapshot_file(int dir, const char* source, const char* name, size_t cap) {
    int fd = open(source, O_RDONLY | O_NONBLOCK | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return -1;
    ssize_t n = read_tail_fd(fd, buf, cap);
    close(fd);
    return n >= 0 ? save_bytes(dir, name, buf, (size_t)n) : -1;
}

static int remove_snapshot_dir(int root, const char* name) {
    if (!logging_enabled()) return -1;
    int fd = openat(root, name, O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return errno == ENOENT ? 0 : -1;
    DIR* d = fdopendir(fd);
    if (!d) { close(fd); return -1; }
    struct dirent* e;
    int rc = 0;
    while ((e = readdir(d))) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
        if (!logging_enabled()) { rc = -1; break; }
        struct stat s;
        // Do not descend into subdirectories or follow symlinks.
        if (fstatat(fd, e->d_name, &s, AT_SYMLINK_NOFOLLOW) ||
            !S_ISREG(s.st_mode) || unlinkat(fd, e->d_name, 0)) { rc = -1; break; }
    }
    closedir(d);
    return rc || !logging_enabled() ? -1 : unlinkat(root, name, AT_REMOVEDIR);
}

static int session_dir(int root, const char* bootid) {
    if (!logging_enabled()) return -1;
    int latest = openat(root, "latest", O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    if (latest >= 0) {
        int id = openat(latest, "boot-id.txt", O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
        char saved[80] = {0};
        ssize_t n = id < 0 ? -1 : read(id, saved, sizeof(saved) - 1);
        if (id >= 0) close(id);
        if (n > 0 && !strcmp(saved, bootid)) return latest;
        close(latest);
        if (remove_snapshot_dir(root, "previous")) return -1;
        if (!logging_enabled() || renameat(root, "latest", root, "previous")) return -1;
        if (fsync(root)) return -1;
    } else if (errno != ENOENT) return -1;
    latest = directory_at(root, "latest");
    if (latest >= 0 && save_bytes(latest, "boot-id.txt", bootid, strlen(bootid))) {
        close(latest);
        return -1;
    }
    return latest;
}

static void save_pstore(int dir) {
    DIR* d = opendir("/sys/fs/pstore");
    if (!d) return;
    struct dirent* e;
    unsigned count = 0;
    while (count < 4 && (e = readdir(d))) {
        if (strncmp(e->d_name, "console-", 8) &&
            strncmp(e->d_name, "dmesg-", 6) &&
            strncmp(e->d_name, "pmsg-", 5)) continue;
        if (strspn(e->d_name, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
            != strlen(e->d_name)) continue;
        char source[PATH_MAX], name[NAME_MAX + 1];
        if (snprintf(source, sizeof(source), "/sys/fs/pstore/%s", e->d_name) >= (int)sizeof(source) ||
            snprintf(name, sizeof(name), "pstore-%s", e->d_name) >= (int)sizeof(name)) continue;
        if (!snapshot_file(dir, source, name, 128U * 1024U)) ++count;
    }
    closedir(d);
}

struct properties { size_t used; };
#ifdef __ANDROID__
static void property_value(void* cookie, const char* name, const char* value, uint32_t serial) {
    (void)serial;
    struct properties* p = cookie;
    if (p->used >= 64U * 1024U) return;
    int n = snprintf((char*)buf + p->used, 64U * 1024U - p->used, "[%s]: [%s]\n", name, value);
    if (n > 0 && (size_t)n < 64U * 1024U - p->used) p->used += (size_t)n;
}
static void property_entry(const prop_info* pi, void* cookie) {
    __system_property_read_callback(pi, property_value, cookie);
}
#endif

static void save_properties(int dir) {
    struct properties p = {0};
#ifdef __ANDROID__
    __system_property_foreach(property_entry, &p);
#endif
    (void)save_bytes(dir, "getprop.txt", buf, p.used);
}

static double monotime(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1000000000.0;
}

static void save_logcat(int dir) {
    int fds[2];
    if (pipe2(fds, O_CLOEXEC)) return;
    pid_t pid = fork();
    if (pid == 0) {
        close(fds[0]);
        dup2(fds[1], STDOUT_FILENO);
        dup2(fds[1], STDERR_FILENO);
        close(fds[1]);
        execl("/system/bin/logcat", "logcat", "-b", "all", "-d", "-t", "400", "-v", "threadtime", (char*)NULL);
        dprintf(STDERR_FILENO, "logcat exec failed: %s\n", strerror(errno));
        _exit(127);
    }
    close(fds[1]);
    if (pid < 0) { close(fds[0]); return; }
    size_t used = 0;
    const size_t cap = 128U * 1024U;
    double deadline = monotime() + 1.0;
    unsigned char chunk[4096];
    while (logging_enabled() && monotime() < deadline) {
        struct pollfd p = {.fd = fds[0], .events = POLLIN};
        int ready = poll(&p, 1, 100);
        if (ready <= 0) continue;
        ssize_t n = read(fds[0], chunk, sizeof(chunk));
        if (n <= 0) break;
        if (used + (size_t)n > cap) {
            size_t drop = used + (size_t)n - cap;
            memmove(buf, buf + drop, used - drop);
            used -= drop;
        }
        memcpy(buf + used, chunk, (size_t)n);
        used += (size_t)n;
    }
    close(fds[0]);
    // Never let a stuck logd/logcat delay the boot or logger.
    kill(pid, SIGKILL);
    while (waitpid(pid, NULL, 0) < 0 && errno == EINTR) {}
    if (used) (void)save_bytes(dir, "logcat.txt", buf, used);
}

static void snapshot(int dir, unsigned sequence) {
    if (!logging_enabled() || !mounted_metadata() || !enough_space()) return;
    int kernel = klogctl(3 /* SYSLOG_ACTION_READ_ALL */, (char*)buf, MAX_BYTES);
    if (kernel >= 0) {
        (void)save_bytes(dir, "dmesg.txt", buf, (size_t)kernel);
        if (sequence == 1 || sequence == 4 || sequence == 15) {
            char name[32];
            snprintf(name, sizeof(name), "dmesg-early-%u.txt", sequence);
            (void)save_bytes(dir, name, buf, (size_t)kernel);
        }
    }
    else {
        char error[128];
        int n = snprintf(error, sizeof(error), "klogctl failed: %s\n", strerror(errno));
        (void)save_bytes(dir, "dmesg-error.txt", error, (size_t)n);
    }
    (void)snapshot_file(dir, "/tmp/recovery.log", "recovery.log", MAX_BYTES);
    (void)snapshot_file(dir, "/proc/cmdline", "cmdline.txt", 16U * 1024U);
    (void)snapshot_file(dir, "/proc/bootconfig", "bootconfig.txt", 16U * 1024U);
    (void)snapshot_file(dir, "/proc/mounts", "mounts.txt", 32U * 1024U);
    (void)snapshot_file(dir, "/proc/last_kmsg", "last-kmsg.txt", 128U * 1024U);
    (void)snapshot_file(dir, "/system/etc/yarp-build-id", "yarp-build-id.txt", 1024);
    (void)snapshot_file(dir, "/init.recovery.yarp-services.rc", "service-config.txt", 16U * 1024U);
    (void)snapshot_file(dir, "/sys/class/leds/cs40l25:vibrator/state", "haptics-state.txt", 1024);
    (void)snapshot_file(dir, "/sys/class/leds/cs40l25:vibrator/device/vibe_state", "haptics-vibe-state.txt", 1024);
    (void)snapshot_file(dir, "/sys/class/leds/cs40l25:vibrator/device/fw_rev", "haptics-fw-rev.txt", 1024);
    DIR* leds = opendir("/sys/class/leds");
    char nodes[4096] = {0};
    size_t used = 0;
    if (leds) {
        struct dirent* entry;
        while ((entry = readdir(leds)) != NULL && used < sizeof(nodes) - 1) {
            if (entry->d_name[0] == '.') continue;
            int n = snprintf(nodes + used, sizeof(nodes) - used, "%s\n", entry->d_name);
            if (n < 0 || (size_t)n >= sizeof(nodes) - used) break;
            used += (size_t)n;
        }
        closedir(leds);
    } else {
        used = (size_t)snprintf(nodes, sizeof(nodes), "LED directory unavailable: %s\n", strerror(errno));
    }
    (void)save_bytes(dir, "haptics-nodes.txt", nodes, used);
    save_pstore(dir);
    save_properties(dir);
    save_logcat(dir);
    char status[512];
    int n = snprintf(status, sizeof(status),
        "YARP boot logger v1\nsnapshot=%u\nuptime_seconds=%.3f\n"
        "tmp_recovery_log_exists=%s\n"
        "kernel_log_bytes=%d\nmetadata_reserve_bytes=%llu\n"
        "Logger started independently of recovery/GUI; absence of recovery.log does not imply boot success.\n"
        "pstore/last-kmsg, if present, describe the PREVIOUS kernel boot.\n",
        sequence, monotime(), access("/tmp/recovery.log", F_OK) == 0 ? "yes" : "no",
        kernel, RESERVE_BYTES);
    (void)save_bytes(dir, "status.txt", status, (size_t)n);
}

int main(void) {
    umask(022);
    signal(SIGTERM, stop_handler);
    signal(SIGINT, stop_handler);
    signal(SIGPIPE, SIG_IGN);
    report_logging_active(false);
    while (!stopping && startup_logging < 0 && runtime_logging() < 0) {
        startup_logging = read_startup_policy();
        if (startup_logging < 0) sleep(1);
    }
    char bootid[80] = {0};
    int id = open("/proc/sys/kernel/random/boot_id", O_RDONLY | O_CLOEXEC);
    ssize_t n = id < 0 ? -1 : read(id, bootid, sizeof(bootid) - 1);
    if (id >= 0) close(id);
    if (n <= 0) return 1;

    unsigned sequence = 0;
    while (!stopping) {
        // Paused mode never mounts Metadata, creates logs, rotates previous
        // sessions, or writes a final snapshot. Re-enable resumes this boot.
        report_logging_active(false);
        while (!stopping && !logging_enabled()) sleep(1);
        if (stopping) break;
        report_logging_active(true);
        while (logging_enabled() && !ensure_metadata()) sleep(1);
        if (!logging_enabled()) continue;
        if (!enough_space()) break;
        int meta = open("/metadata", O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
        if (meta < 0) break;
        int project = directory_at(meta, "XQ-DQ72-YARP");
        close(meta);
        if (project < 0) { if (!logging_enabled()) continue; break; }
        int root = directory_at(project, "logs");
        close(project);
        if (root < 0) { if (!logging_enabled()) continue; break; }
        int lock = -1;
        if (logging_enabled())
            lock = openat(root, "service.lock", O_RDWR | O_CREAT | O_CLOEXEC | O_NOFOLLOW, 0644);
        if (lock < 0 || flock(lock, LOCK_EX | LOCK_NB)) {
            if (lock >= 0) close(lock);
            close(root);
            if (!logging_enabled()) continue;
            break;
        }
        int dir = session_dir(root, bootid);
        if (dir < 0) {
            close(lock); close(root);
            if (!logging_enabled()) continue;
            break;
        }
        const char* readme =
            "Copy /metadata/XQ-DQ72-YARP/logs using the recovery file manager.\n"
            "Mount Metadata first; do not format it. Userdata decryption is not required.\n"
            "Settings > General Settings > Save logs to Metadata controls automatic logging.\n"
            "It defaults to enabled; the saved choice applies before the next boot's first write.\n"
            "latest is this YARP boot; previous is the preceding logged YARP boot.\n"
            "Missing recovery.log does not imply boot success. Sources and storage use are capped.\n";
        (void)save_bytes(root, "README.txt", readme, strlen(readme));
        while (logging_enabled()) {
            snapshot(dir, ++sequence);
            unsigned interval = sequence <= 15 ? 1 : 5;
            for (unsigned i = 0; i < interval && logging_enabled(); ++i) sleep(1);
        }
        // In particular, no shutdown snapshot after the switch was disabled.
        close(dir); close(lock); close(root);
        report_logging_active(false);
    }
    report_logging_active(false);
    return stopping ? 0 : 1;
}
