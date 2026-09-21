// SPDX-License-Identifier: GPL-2.0
/*
 * panel_emulator_host_test
 *
 * Deterministic virtual MSHW0231 panel for tracker/detector development.
 *
 * Instead of asking a person to place fingers at millimetre-precise spacing,
 * this harness renders synthetic contacts into the panel's real 72x48 raw
 * raster and feeds those frames through the REAL driver/mshw0231-raw.c.
 *
 * Covered stages:
 *   virtual contacts -> raw bytes -> baseline/signal -> peak detector ->
 *   CCL/split -> Hungarian -> post-association coalescing -> slot lifecycle ->
 *   Linux MT recording stubs.
 *
 * This deliberately does not emulate SPI electrical transport; transport is a
 * separate problem and would only add noise to tracker experiments.
 *
 * The raster model is simple and explicit rather than pretending to be a full
 * physical capacitance simulator: each contact contributes a Gaussian-shaped
 * drop from the resting raw byte. Contributions add before clamping. That is
 * enough to create deterministic "well separated", "barely resolvable", and
 * "merged" contact regimes while executing the production detector/tracker.
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "spi-hid-core.h"
#include "mshw0231-raw.h"
#include "mshw0231-raw-constants.h"
#include <linux/input.h>
#include <linux/input/mt.h>
#include <linux/jiffies.h>
#include <linux/slab.h>
#include "mt_record.h"

/* Include the staged real driver so this test can also pin the module params
 * and inspect the detector's pre-tracker blob arrays. */
#include "raw-pipeline-stage/mshw0231-raw.c"

#define GRID_COLS 72
#define GRID_ROWS 48
#define FRAME_BYTES (GRID_COLS * GRID_ROWS)
#define REST_RAW 200

struct vcontact {
	double x;
	double y;
	double amplitude;
	double sigma;
	int active;
};

struct frame_obs {
	int detector_blobs;
	int mt_contacts;
};

static int passed;
static int failed;

#define CHECK(cond, msg, ...) do { \
	if (!(cond)) { \
		fprintf(stderr, "FAIL: " msg "\n", ##__VA_ARGS__); \
		failed++; \
	} else { \
		passed++; \
	} \
} while (0)

static const struct spi_hid_dev_cfg sl4_cfg = {
	.capimg_raster_samples = FRAME_BYTES,
	.heatmap_baseline_needed = 30,
	.heatmap_baseline_alpha = 7,
	.grid_cols = GRID_COLS,
	.grid_rows = GRID_ROWS,
};

static void reset_tunables(void)
{
	blob_min_weight = 1000;
	ema_alpha = 2;
	ghost_dist = 6;
	blob_debounce = 3;
	blob_lift_frames = 3;
	hold_frames = 0;
	pre_assoc_ratio = 0;
	blob_max_distance = 3;
	invert_x = false;
	invert_y = false;
	swap_xy = false;
	dfa_data_offset = 0;
	grid_cols = 0;
	grid_rows = 0;
	calib_scale_x = 0;
	calib_scale_y = 0;
	calib_offset_x = 0;
	calib_offset_y = 0;
}

static void setup_device(struct spi_hid *shid, struct spi_device *spidev)
{
	unsigned char baseline[FRAME_BYTES];
	int i;

	reset_tunables();
	mt_record_reset();
	memset(shid, 0, sizeof(*shid));
	memset(spidev, 0, sizeof(*spidev));
	shid->spi = spidev;
	shid->cfg = &sl4_cfg;
	shid->raw_mode_active = true;
	mshw0231_raw_init(shid);
	if (mshw0231_raw_input_register(shid) != 0 || !shid->touch_input) {
		fprintf(stderr, "FATAL: mshw0231_raw_input_register() failed\n");
		exit(1);
	}

	memset(baseline, REST_RAW, sizeof(baseline));
	for (i = 0; i < 30; i++) {
		jiffies += 10;
		mshw0231_raw_consume_samples(shid, baseline, FRAME_BYTES, 0x0c);
	}
	if (!shid->heatmap_have_baseline) {
		fprintf(stderr, "FATAL: virtual baseline did not establish\n");
		exit(1);
	}
}

static void teardown_device(struct spi_hid *shid)
{
	input_free_device(shid->touch_input);
	kfree(shid->heatmap_buf);
}

static void render_frame(unsigned char *buf,
			 const struct vcontact *contacts, size_t ncontacts)
{
	int r, c;
	size_t k;

	for (r = 0; r < GRID_ROWS; r++) {
		for (c = 0; c < GRID_COLS; c++) {
			double drop = 0.0;
			int raw;

			for (k = 0; k < ncontacts; k++) {
				double dx, dy, denom;

				if (!contacts[k].active)
					continue;
				dx = (double)c - contacts[k].x;
				dy = (double)r - contacts[k].y;
				denom = 2.0 * contacts[k].sigma * contacts[k].sigma;
				drop += contacts[k].amplitude *
					exp(-(dx * dx + dy * dy) / denom);
			}

			raw = REST_RAW - (int)(drop + 0.5);
			if (raw < 16)
				raw = 16;
			if (raw > 255)
				raw = 255;
			buf[r * GRID_COLS + c] = (unsigned char)raw;
		}
	}
}

static int detector_blob_count(const struct spi_hid *shid)
{
	int i, n = 0;

	for (i = 0; i < HEATMAP_MAX_BLOBS; i++)
		if (shid->blob_active[i] &&
		    shid->blob_raw_wsum[i] >= (u32)blob_min_weight)
			n++;
	return n;
}

static struct frame_obs feed_virtual(struct spi_hid *shid,
				     const struct vcontact *contacts,
				     size_t ncontacts)
{
	unsigned char buf[FRAME_BYTES];
	struct frame_obs obs;

	render_frame(buf, contacts, ncontacts);
	jiffies += 10;
	mshw0231_raw_consume_samples(shid, buf, FRAME_BYTES, 0x0c);
	obs.detector_blobs = detector_blob_count(shid);
	obs.mt_contacts = mt_record_active_count();
	return obs;
}

static struct vcontact finger(double x, double y)
{
	struct vcontact c = {
		.x = x,
		.y = y,
		.amplitude = 110.0,
		.sigma = 1.20,
		.active = 1,
	};

	return c;
}

static int hold_pair(double spacing, int frames, int *max_blobs)
{
	struct spi_hid shid;
	struct spi_device spidev;
	struct vcontact c[2];
	struct frame_obs obs = { 0, 0 };
	int i;

	setup_device(&shid, &spidev);
	c[0] = finger(30.0, 22.0);
	c[1] = finger(30.0 + spacing, 22.0);
	*max_blobs = 0;

	for (i = 0; i < frames; i++) {
		obs = feed_virtual(&shid, c, 2);
		if (obs.detector_blobs > *max_blobs)
			*max_blobs = obs.detector_blobs;
	}

	i = obs.mt_contacts;
	teardown_device(&shid);
	return i;
}

static void spacing_sweep(void)
{
	static const double spacing[] = {
		2.00, 2.40, 2.75, 3.00, 3.50, 4.00, 4.27,
		4.50, 5.00, 5.50, 5.90, 6.00, 7.00, 8.00,
	};
	size_t i;

	printf("\n-- virtual simultaneous-close spacing sweep --\n");
	printf("spacing_cells,max_detector_blobs,final_linux_contacts\n");
	for (i = 0; i < sizeof(spacing) / sizeof(spacing[0]); i++) {
		int max_blobs = 0;
		int mt = hold_pair(spacing[i], 12, &max_blobs);

		printf("%.2f,%d,%d\n", spacing[i], max_blobs, mt);
	}
}

static int staggered_result(int delay_frames, double spacing,
			    int *max_blobs_after_b)
{
	struct spi_hid shid;
	struct spi_device spidev;
	struct vcontact a[1], pair[2];
	struct frame_obs obs = { 0, 0 };
	int i;

	setup_device(&shid, &spidev);
	a[0] = finger(30.0, 22.0);
	pair[0] = a[0];
	pair[1] = finger(30.0 + spacing, 22.0);

	for (i = 0; i < delay_frames; i++)
		feed_virtual(&shid, a, 1);

	*max_blobs_after_b = 0;
	for (i = 0; i < 8; i++) {
		obs = feed_virtual(&shid, pair, 2);
		if (obs.detector_blobs > *max_blobs_after_b)
			*max_blobs_after_b = obs.detector_blobs;
	}

	i = obs.mt_contacts;
	teardown_device(&shid);
	return i;
}

static void delay_sweep(void)
{
	static const int delays[] = { 0, 2, 4, 6, 8, 10, 12, 14, 16 };
	size_t i;

	printf("\n-- virtual staggered close-born sweep at 4.27 cells --\n");
	printf("delay_frames,delay_ms,max_detector_blobs,final_linux_contacts\n");
	for (i = 0; i < sizeof(delays) / sizeof(delays[0]); i++) {
		int max_blobs = 0;
		int mt = staggered_result(delays[i], 4.27, &max_blobs);

		printf("%d,%d,%d,%d\n",
		       delays[i], delays[i] * 10, max_blobs, mt);
	}
}

static void test_established_pinch(void)
{
	struct spi_hid shid;
	struct spi_device spidev;
	struct vcontact c[2];
	struct frame_obs obs = { 0, 0 };
	int i;

	setup_device(&shid, &spidev);
	c[0] = finger(28.0, 22.0);
	c[1] = finger(36.0, 22.0);

	for (i = 0; i < 6; i++)
		obs = feed_virtual(&shid, c, 2);
	CHECK(obs.mt_contacts == 2,
	      "established pinch setup publishes two contacts, got %d",
	      obs.mt_contacts);

	for (i = 1; i <= 24; i++) {
		double spacing = 8.0 - (8.0 - 4.27) * ((double)i / 24.0);

		c[1].x = c[0].x + spacing;
		obs = feed_virtual(&shid, c, 2);
		CHECK(obs.mt_contacts == 2,
		      "established pinch frame %d keeps two contacts at %.2f cells, got %d",
		      i, spacing, obs.mt_contacts);
	}
	for (i = 0; i < 8; i++)
		obs = feed_virtual(&shid, c, 2);
	CHECK(obs.mt_contacts == 2,
	      "established 4.27-cell hold keeps two contacts, got %d",
	      obs.mt_contacts);

	teardown_device(&shid);
}

static void test_staggered_birth_window(void)
{
	int max_blobs = 0;
	int mt;

	mt = staggered_result(8, 4.27, &max_blobs);
	CHECK(max_blobs >= 2,
	      "4.27-cell synthetic pair is detector-resolvable after 80 ms skew (max blobs %d)",
	      max_blobs);
	CHECK(mt == 2,
	      "80 ms staggered 4.27-cell pair becomes two Linux contacts, got %d",
	      mt);

	mt = staggered_result(14, 4.27, &max_blobs);
	CHECK(mt == 1,
	      "140 ms staggered 4.27-cell pair stays conservative after birth grace, got %d",
	      mt);
}

static void test_accidental_third_finger(void)
{
	struct spi_hid shid;
	struct spi_device spidev;
	struct vcontact two[2], three[3];
	struct frame_obs obs = { 0, 0 };
	int i;

	setup_device(&shid, &spidev);
	two[0] = finger(18.0, 18.0);
	two[1] = finger(52.0, 18.0);
	three[0] = two[0];
	three[1] = two[1];
	three[2] = finger(35.0, 36.0);

	for (i = 0; i < 6; i++)
		obs = feed_virtual(&shid, two, 2);
	CHECK(obs.mt_contacts == 2,
	      "third-finger setup starts with two contacts, got %d",
	      obs.mt_contacts);

	/* A two-frame accidental brush must never finish the 3-frame debounce. */
	for (i = 0; i < 2; i++) {
		obs = feed_virtual(&shid, three, 3);
		CHECK(obs.mt_contacts == 2,
		      "two-frame accidental third touch stays unpublished (frame %d got %d)",
		      i, obs.mt_contacts);
	}
	for (i = 0; i < 4; i++)
		obs = feed_virtual(&shid, two, 2);
	CHECK(obs.mt_contacts == 2,
	      "after accidental brush, original two contacts remain, got %d",
	      obs.mt_contacts);

	/* A real third finger held through debounce should become visible. */
	for (i = 0; i < 4; i++)
		obs = feed_virtual(&shid, three, 3);
	CHECK(obs.mt_contacts == 3,
	      "sustained third contact publishes a third Linux slot, got %d",
	      obs.mt_contacts);

	for (i = 0; i < 5; i++)
		obs = feed_virtual(&shid, two, 2);
	CHECK(obs.mt_contacts == 2,
	      "after third finger lifts, tracker returns to two contacts, got %d",
	      obs.mt_contacts);

	teardown_device(&shid);
}

static void test_far_sanity(void)
{
	int max_blobs = 0;
	int mt = hold_pair(8.0, 8, &max_blobs);

	CHECK(max_blobs >= 2,
	      "virtual far pair reaches two detector blobs, max %d",
	      max_blobs);
	CHECK(mt == 2,
	      "virtual far pair publishes two Linux contacts, got %d",
	      mt);
}

int main(void)
{
	printf("panel_emulator_host_test: virtual 72x48 panel -> real driver pipeline\n");
	printf("model: resting raw=%d, gaussian finger amplitude=110 sigma=1.20 cells\n",
	       REST_RAW);

	test_far_sanity();
	test_established_pinch();
	test_staggered_birth_window();
	test_accidental_third_finger();

	/* Diagnostic matrices are intentionally printed even when assertions pass:
	 * they let us compare algorithm changes without another physical gesture. */
	spacing_sweep();
	delay_sweep();

	printf("\npanel_emulator_host_test: %d assertions, %d failures\n",
	       passed, failed);
	return failed ? 1 : 0;
}
