// SPDX-License-Identifier: GPL-2.0
#include <stdint.h>

static const float signal_one = 0x1.000000p+0f;
static const float signal_offset = 0x1.333334p-1f;
static const float signal_step = 0x1.2306bap-9f;
static const float weight_epsilon = 0x1.a36e2ep-14f;

float windows_c590_value(uint8_t raw)
{
    return signal_one - ((float)raw * signal_step + signal_offset);
}

uint8_t windows_threshold_raw(float threshold)
{
    return (uint8_t)(int)(((signal_one - threshold) - signal_offset) /
                          signal_step + 0.5f);
}

float windows_adjusted_weight(uint8_t raw, float threshold)
{
    float weight = windows_c590_value(raw) - (threshold - signal_step);
    return weight <= weight_epsilon ? weight_epsilon : weight;
}
