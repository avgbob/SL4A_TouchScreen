// SPDX-License-Identifier: GPL-2.0
// Independent compiled-float oracle for the common score-block operation order.
#include <stdint.h>

#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

EXPORT float windows_score_block_f32(
    const float features[10],
    const uint8_t suppressed[10],
    const float packed_upper[55],
    const float means[10],
    float base_penalty,
    float limit,
    float runtime_bias)
{
    volatile float delta[10];
    volatile float transformed[10];
    unsigned packed = 0;

    for (unsigned index = 0; index < 10; ++index)
        delta[index] = suppressed[index] ? 0.0f : features[index] - means[index];

    for (unsigned row = 0; row < 10; ++row) {
        volatile float accumulator = 0.0f;
        for (unsigned column = row; column < 10; ++column) {
            volatile float product = packed_upper[packed++] * delta[column];
            accumulator = accumulator + product;
        }
        transformed[row] = accumulator;
    }

    volatile float squared_norm = 0.0f;
    for (unsigned row = 0; row < 10; ++row) {
        volatile float square = transformed[row] * transformed[row];
        squared_norm = squared_norm + square;
    }

    volatile float base_half = base_penalty * 0.5f;
    volatile float result = limit - base_half;
    result = result + runtime_bias;
    volatile float norm_half = squared_norm * 0.5f;
    result = result - norm_half;
    return result;
}
