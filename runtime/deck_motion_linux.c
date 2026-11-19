/* SPDX-License-Identifier: MIT */
/* Native, read-only Deck IMU. The existing motion thread owns all descriptors. */
#ifdef __linux__
#define _GNU_SOURCE
#include "deck_motion.h"
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/hidraw.h>
#include <linux/input.h>
#include <poll.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <unistd.h>

#define IMU_STALE_NS UINT64_C(250000000)
#define IMU_RETRY_NS UINT64_C(1000000000)

static int hidraw_name(const char *name) {
    if (strncmp(name, "hidraw", 6) || !name[6]) return 0;
    unsigned n = 6;
    while (n < 24 && isdigit((unsigned char)name[n])) n++;
    return n < 24 && name[n] == 0;
}

void nd_deck_imu_close(DeckImu *s) {
    for (unsigned i = 0; i < s->count; i++) close(s->fds[i]);
    *s = (DeckImu)DECK_IMU_INIT;
}

static void retry_later(DeckImu *s, uint64_t now) {
    nd_deck_imu_close(s);
    s->retry_ns = now + IMU_RETRY_NS;
}

static void discover(DeckImu *s, uint64_t now) {
    DIR *dir = opendir("/dev");
    if (!dir) { s->retry_ns = now + IMU_RETRY_NS; return; }
    struct dirent *entry;
    unsigned attempts = 0;
    while (s->count < DECK_IMU_FDS && attempts < 32 && (entry = readdir(dir))) {
        if (!hidraw_name(entry->d_name)) continue;
        attempts++;
        char path[40];
        int n = snprintf(path, sizeof path, "/dev/%s", entry->d_name);
        if (n < 0 || (size_t)n >= sizeof path) continue;
        int fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC | O_NOFOLLOW);
        if (fd < 0) continue;
        struct stat st;
        struct hidraw_devinfo info = {0};
        /* Validate the opened descriptor, not a potentially reused sysfs name. */
        if (fstat(fd, &st) || !S_ISCHR(st.st_mode) || ioctl(fd, HIDIOCGRAWINFO, &info) ||
            info.bustype != BUS_USB || info.vendor != 0x28de || info.product != 0x1205) {
            close(fd); continue;
        }
        s->fds[s->count++] = fd;
    }
    closedir(dir);
    s->deadline_ns = now + IMU_STALE_NS;
    if (!s->count) s->retry_ns = now + IMU_RETRY_NS;
}

int nd_deck_imu_read(DeckImu *s, uint64_t now, double acc[3], double gyro[3]) {
    if (!s->count) {
        if (now < s->retry_ns) return -1;
        discover(s, now);
        if (!s->count) return -1;
    }
    if (now >= (s->selected >= 0 ? s->sample_ns + IMU_STALE_NS : s->deadline_ns)) {
        retry_later(s, now); return -1;
    }
    struct pollfd ready[DECK_IMU_FDS];
    for (unsigned i = 0; i < s->count; i++) ready[i] = (struct pollfd){s->fds[i], POLLIN, 0};
    int rc = poll(ready, s->count, 0);
    if (rc < 0) {
        if (errno == EINTR) return s->selected >= 0 ? 0 : -1;
        retry_later(s, now); return -1;
    }
    for (unsigned i = 0; rc > 0 && i < s->count;) {
        if (ready[i].revents & (POLLHUP | POLLERR | POLLNVAL)) {
            if (s->selected >= 0) { retry_later(s, now); return -1; }
            close(s->fds[i]);
            s->fds[i] = s->fds[--s->count]; ready[i] = ready[s->count];
            continue;
        }
        if (!(ready[i].revents & POLLIN)) { i++; continue; }
        int fresh = 0, broken = 0;
        uint32_t packet = 0;
        double latest_acc[3], latest_gyro[3];
        /* One extra byte prevents an oversized report being accepted as 64 bytes. */
        for (unsigned read_count = 0; read_count < 64; read_count++) {
            unsigned char report[65];
            ssize_t bytes = read(s->fds[i], report, sizeof report);
            if (bytes < 0) {
                if (errno == EINTR) continue;
                if (errno != EAGAIN && errno != EWOULDBLOCK) broken = 1;
                break;
            }
            if (!bytes) { broken = 1; break; }
            uint32_t next;
            double next_acc[3], next_gyro[3];
            if (!nd_deck_motion_decode(report, (size_t)bytes, &next, next_acc, next_gyro)) continue;
            uint32_t delta = next - (fresh ? packet : s->packet);
            if ((fresh || s->have_packet) && (!delta || delta >= UINT32_C(0x80000000))) continue;
            fresh = 1;packet = next;
            memcpy(latest_acc, next_acc, sizeof latest_acc);memcpy(latest_gyro, next_gyro, sizeof latest_gyro);
        }
        if (broken) {
            if (s->selected >= 0) { retry_later(s, now); return -1; }
            close(s->fds[i]);s->fds[i] = s->fds[--s->count];ready[i] = ready[s->count];
            continue;
        }
        if (fresh) {
            int selected = s->fds[i];
            for (unsigned j = 0; j < s->count; j++) if (j != i) close(s->fds[j]);
            s->fds[0] = selected;s->count = 1;s->selected = 0;
            s->packet = packet;s->have_packet = 1;s->sample_ns = now;
            memcpy(acc, latest_acc, sizeof latest_acc);memcpy(gyro, latest_gyro, sizeof latest_gyro);
            return 1;
        }
        i++;
    }
    if (!s->count) s->retry_ns = now + IMU_RETRY_NS;
    return s->selected >= 0 ? 0 : -1;
}
#endif
