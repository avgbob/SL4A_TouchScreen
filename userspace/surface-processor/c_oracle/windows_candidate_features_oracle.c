// SPDX-License-Identifier: GPL-2.0
#include <math.h>
#include <stdint.h>

/* Independent C-float check for the FUN_180600c40 feature transcription. */
void windows_candidate_geometry_f32(float sum_xx, float sum_yy, float sum_xy,
                                    float normalizer, uint16_t component_cells,
                                    float output[2])
{
    const double axis_scale = 0x1.6cbe44093cd36p+10;
    const float axis_fallback = 1.15f;
    const float two_pi = 0x1.921fb6p+2f;
    float scale = 1.0f / normalizer;
    float yy = sum_yy * scale;
    float xx = sum_xx * scale;
    float xy = sum_xy * scale;
    float trace = yy + xx;
    float determinant = yy * xx - xy * xy;
    float discriminant = trace * trace - determinant * 4.0f;
    float root = sqrtf(discriminant);
    float eigen_small = (trace - root) * 0.5f;
    float eigen_large = (trace + root) * 0.5f;
    float major;
    float minor;

    if (eigen_small < 0.0f)
        eigen_small = 0.0f;
    if (eigen_large < eigen_small)
        eigen_large = eigen_small;
    major = (float)(sqrtf(eigen_large) * axis_scale);
    minor = (float)(sqrtf(eigen_small) * axis_scale);
    if (major < 1.0f)
        major = axis_fallback;
    if (minor < 1.0f)
        minor = axis_fallback;
    output[0] = major / minor;
    output[1] = component_cells > 1
        ? (trace * two_pi) / (float)(component_cells - 1)
        : 1.0f;
}
