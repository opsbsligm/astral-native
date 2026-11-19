/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#include <stdint.h>

/* Sensor-only decoder. Values already use the Switch frame: G and radians/s. */
int nd_deck_motion_decode(const unsigned char *report, size_t bytes,
                          uint32_t *packet, double acceleration_g[3], double gyro_rad_s[3]);

#ifdef __linux__
enum { DECK_IMU_FDS = 16 };
typedef struct {
    int fds[DECK_IMU_FDS];
    unsigned count;
    int selected, have_packet;
    uint32_t packet;
    uint64_t retry_ns, deadline_ns, sample_ns;
} DeckImu;
#define DECK_IMU_INIT {.selected = -1}
/* Owned by the existing motion thread. No HID writes or new reader thread. */
void nd_deck_imu_close(DeckImu *state);
/* 1: fresh sample, 0: selected native source without a new sample, -1: use SDL. */
int nd_deck_imu_read(DeckImu *state, uint64_t now_ns, double acc_g[3], double gyro_rad_s[3]);
#endif
