// SPDX-License-Identifier: GPL-2.0
#include <stdint.h>

static float f32(float value) {
    volatile float rounded = value;
    return rounded;
}

uint32_t windows_8bit_destination(uint32_t destination, uint16_t width) {
    return destination + (0x120u - width) * (destination / width);
}

uint8_t windows_convert_u16(uint16_t sample, float scale, float bias) {
    float product = f32(f32((float) sample) * f32(scale));
    int32_t converted = (int32_t) f32(product + f32(bias));
    if (converted < 0)
        return 0;
    if (converted > 255)
        return 255;
    return (uint8_t) converted;
}
