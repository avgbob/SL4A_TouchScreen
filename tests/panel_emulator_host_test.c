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

/*
 * Host-only policy experiments can override the close-birth minimum separation
 * at compile time without editing driver/ or the production constants header.
 * Normal panel_emulator_host_test builds do not define this macro and therefore
 * exercise the production value unchanged.
 */
#ifdef SL4A_TEST_CLOSE_BIRTH_MIN_SEP
#undef HEATMAP_CLOSE_BIRTH_MIN_SEP
#define HEATMAP_CLOSE_BIRTH_MIN_SEP SL4A_TEST_CLOSE_BIRTH_MIN_SEP
#endif

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

static unsigned long long active_slot_mask(void)
{
	unsigned long long mask = 0;
	int i;

	for (i = 0; i < MT_RECORD_MAX_SLOTS && i < 64; i++)
		if (mt_slots[i].active)
			mask |= 1ULL << i;
	return mask;
}

static int single_active_tracking_id(void)
{
	int i, found = -1;

	for (i = 0; i < MT_RECORD_MAX_SLOTS; i++) {
		if (!mt_slots[i].active)
			continue;
		if (found >= 0)
			return -1;
		found = mt_slots[i].tracking_id;
	}
	return found;
}

/*
 * The motion scenarios below never cross the two logical fingers. Sorting
 * active reports by X therefore binds tracking identity to the logical
 * left/right finger, not merely to a Linux slot number.
 */
static int pair_tracking_ids_by_x(int *left_id, int *right_id)
{
	int i, count = 0;
	int left_slot = -1, right_slot = -1;

	for (i = 0; i < MT_RECORD_MAX_SLOTS; i++) {
		if (!mt_slots[i].active)
			continue;
		count++;
		if (left_slot < 0 || mt_slots[i].x < mt_slots[left_slot].x)
			left_slot = i;
		if (right_slot < 0 || mt_slots[i].x > mt_slots[right_slot].x)
			right_slot = i;
	}

	if (count != 2 || left_slot < 0 || right_slot < 0 ||
	    left_slot == right_slot)
		return 0;

	*left_id = mt_slots[left_slot].tracking_id;
	*right_id = mt_slots[right_slot].tracking_id;
	return *left_id >= 0 && *right_id >= 0 && *left_id != *right_id;
}

static int pair_tracking_ids_match(int left_id, int right_id)
{
	int now_left, now_right;

	if (!pair_tracking_ids_by_x(&now_left, &now_right))
		return 0;
	return now_left == left_id && now_right == right_id;
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

struct shape_result {
	int max_blobs;
	int final_contacts;
	int centroid_sep100;
};

static int detector_pair_sep100(const struct spi_hid *shid)
{
	int idx[2] = { -1, -1 };
	int i, n = 0;
	double dx, dy;

	for (i = 0; i < HEATMAP_MAX_BLOBS && n < 2; i++) {
		if (!shid->blob_active[i] ||
		    shid->blob_raw_wsum[i] < (u32)blob_min_weight)
			continue;
		idx[n++] = i;
	}
	if (n != 2)
		return -1;

	dx = (double)((s32)shid->blob_x[idx[0]] -
		      (s32)shid->blob_x[idx[1]]);
	dy = (double)((s32)shid->blob_y[idx[0]] -
		      (s32)shid->blob_y[idx[1]]);
	return (int)(sqrt(dx * dx + dy * dy) + 0.5);
}

static struct shape_result hold_pair_shape(double spacing, int frames,
					   double amp_a, double amp_b,
					   double sigma)
{
	struct spi_hid shid;
	struct spi_device spidev;
	struct vcontact c[2];
	struct frame_obs obs = { 0, 0 };
	struct shape_result out = { 0, 0, -1 };
	int i;

	setup_device(&shid, &spidev);
	c[0] = finger(30.0, 22.0);
	c[1] = finger(30.0 + spacing, 22.0);
	c[0].amplitude = amp_a;
	c[1].amplitude = amp_b;
	c[0].sigma = sigma;
	c[1].sigma = sigma;

	for (i = 0; i < frames; i++) {
		obs = feed_virtual(&shid, c, 2);
		if (obs.detector_blobs > out.max_blobs)
			out.max_blobs = obs.detector_blobs;
	}

	out.final_contacts = obs.mt_contacts;
	out.centroid_sep100 = detector_pair_sep100(&shid);
	teardown_device(&shid);
	return out;
}

static void print_shape_threshold(const char *kind, double shape_value,
				  double amp_a, double amp_b, double sigma)
{
	int hundredths;
	int det_nominal = -1, det_sep100 = -1;
	int linux_nominal = -1, linux_sep100 = -1;

	/*
	 * Sweep in 0.05-cell increments. We record both transitions separately:
	 * detector-resolvable and finally publishable after coalescing/debounce.
	 */
	for (hundredths = 300; hundredths <= 450; hundredths += 5) {
		double spacing = (double)hundredths / 100.0;
		struct shape_result r =
			hold_pair_shape(spacing, 12, amp_a, amp_b, sigma);

		if (det_nominal < 0 && r.max_blobs >= 2) {
			det_nominal = hundredths;
			det_sep100 = r.centroid_sep100;
		}
		if (linux_nominal < 0 && r.final_contacts >= 2) {
			linux_nominal = hundredths;
			linux_sep100 = r.centroid_sep100;
			break;
		}
	}

	printf("%s,%.2f,%.0f,%.0f,%.2f,",
	       kind, shape_value, amp_a, amp_b, sigma);
	if (det_nominal >= 0)
		printf("%.2f,%.2f,", (double)det_nominal / 100.0,
		       (double)det_sep100 / 100.0);
	else
		printf("NA,NA,");
	if (linux_nominal >= 0)
		printf("%.2f,%.2f\n", (double)linux_nominal / 100.0,
		       (double)linux_sep100 / 100.0);
	else
		printf("NA,NA\n");
}

static void shape_sensitivity_sweep(void)
{
	static const double sigmas[] = { 0.90, 1.05, 1.20, 1.35, 1.50 };
	static const double amplitudes[] = { 70.0, 90.0, 110.0, 130.0, 150.0 };
	size_t i;

	printf("\n-- close-birth shape sensitivity thresholds --\n");
	printf("kind,value,amp_a,amp_b,sigma,detector_nominal,detector_centroid_sep,linux_nominal,linux_centroid_sep\n");

	for (i = 0; i < sizeof(sigmas) / sizeof(sigmas[0]); i++)
		print_shape_threshold("sigma", sigmas[i],
				      110.0, 110.0, sigmas[i]);

	for (i = 0; i < sizeof(amplitudes) / sizeof(amplitudes[0]); i++)
		print_shape_threshold("amplitude", amplitudes[i],
				      amplitudes[i], amplitudes[i], 1.20);
}

static void unequal_strength_sweep(void)
{
	static const double weak_amp[] = { 55.0, 70.0, 85.0, 100.0, 110.0 };
	size_t i;

	printf("\n-- unequal-strength pair at nominal 3.65 cells --\n");
	printf("amp_a,amp_b,sigma,max_detector_blobs,centroid_sep,final_linux_contacts\n");
	for (i = 0; i < sizeof(weak_amp) / sizeof(weak_amp[0]); i++) {
		struct shape_result r =
			hold_pair_shape(3.65, 12, 110.0, weak_amp[i], 1.20);

		printf("110,%.0f,1.20,%d,", weak_amp[i], r.max_blobs);
		if (r.centroid_sep100 >= 0)
			printf("%.2f,", (double)r.centroid_sep100 / 100.0);
		else
			printf("NA,");
		printf("%d\n", r.final_contacts);
	}
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

static void fine_spacing_sweep(void)
{
	int tenth;

	printf("\n-- fine detector boundary sweep (3.40..4.20 cells) --\n");
	printf("spacing_cells,max_detector_blobs,final_linux_contacts\n");
	for (tenth = 34; tenth <= 42; tenth++) {
		double spacing = (double)tenth / 10.0;
		int max_blobs = 0;
		int mt = hold_pair(spacing, 12, &max_blobs);

		printf("%.2f,%d,%d\n", spacing, max_blobs, mt);
	}
}

static void test_birth_min_sep_centroid_boundary(void)
{
	int max_blobs = 0;
	int mt;

	/*
	 * At nominal 3.60-cell virtual spacing the detector resolves two peaks,
	 * but their weighted centroids land at 3042 and 3339 (2.97 cells apart).
	 * That is intentionally below HEATMAP_CLOSE_BIRTH_MIN_SEP=3, so the
	 * weaker same-frame new candidate is treated as an ambiguous duplicate.
	 */
	mt = hold_pair(3.60, 12, &max_blobs);
	CHECK(max_blobs >= 2,
	      "3.60-cell boundary case is detector-resolved, max blobs %d",
	      max_blobs);
	CHECK(mt == 1,
	      "3.60-cell boundary remains one Linux contact below 3-cell centroid guard, got %d",
	      mt);

	/*
	 * At nominal 3.65-cell virtual spacing the centroids land at 3040 and
	 * 3343 (3.03 cells apart), just clearing the same guard. The recent first
	 * track's birth grace then preserves the second candidate through debounce.
	 */
	mt = hold_pair(3.65, 12, &max_blobs);
	CHECK(max_blobs >= 2,
	      "3.65-cell boundary case is detector-resolved, max blobs %d",
	      max_blobs);
	CHECK(mt == 2,
	      "3.65-cell boundary becomes two Linux contacts above 3-cell centroid guard, got %d",
	      mt);
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

static void fine_delay_sweep(void)
{
	int frames;

	printf("\n-- fine birth-window sweep at 4.27 cells (70..130 ms) --\n");
	printf("delay_frames,delay_ms,max_detector_blobs,final_linux_contacts\n");
	for (frames = 7; frames <= 13; frames++) {
		int max_blobs = 0;
		int mt = staggered_result(frames, 4.27, &max_blobs);

		printf("%d,%d,%d,%d\n",
		       frames, frames * 10, max_blobs, mt);
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

static void test_established_motion_slot_stability(void)
{
	struct spi_hid shid;
	struct spi_device spidev;
	struct vcontact c[2];
	struct frame_obs obs = { 0, 0 };
	unsigned long long slot_mask;
	int left_tid = -1, right_tid = -1;
	int i;

	setup_device(&shid, &spidev);
	c[0] = finger(28.0, 20.0);
	c[1] = finger(32.27, 20.0);

	for (i = 0; i < 6; i++)
		obs = feed_virtual(&shid, c, 2);
	CHECK(obs.mt_contacts == 2,
	      "motion setup publishes two close established contacts, got %d",
	      obs.mt_contacts);
	slot_mask = active_slot_mask();
	CHECK(slot_mask != 0,
	      "motion setup records a non-empty Linux slot mask");
	CHECK(pair_tracking_ids_by_x(&left_tid, &right_tid),
	      "motion setup assigns distinct tracking IDs to logical left/right fingers");

	/* Translate the close pair together. Association should follow both
	 * contacts without reallocating Linux slots. */
	for (i = 0; i < 12; i++) {
		c[0].x += 0.25;
		c[1].x += 0.25;
		c[0].y += 0.10;
		c[1].y += 0.10;
		obs = feed_virtual(&shid, c, 2);
		CHECK(obs.mt_contacts == 2,
		      "translated close pair frame %d keeps two contacts, got %d",
		      i, obs.mt_contacts);
		CHECK(active_slot_mask() == slot_mask,
		      "translated close pair frame %d keeps the same Linux slots",
		      i);
		CHECK(pair_tracking_ids_match(left_tid, right_tid),
		      "translated close pair frame %d keeps tracking IDs bound to left/right fingers",
		      i);
	}

	/* Spread from the barely-resolvable regime to a comfortable 8 cells,
	 * then pinch back to 4.27 without crossing the detector-merged band. */
	for (i = 1; i <= 16; i++) {
		double spacing = 4.27 + (8.0 - 4.27) * ((double)i / 16.0);

		c[1].x = c[0].x + spacing;
		obs = feed_virtual(&shid, c, 2);
		CHECK(obs.mt_contacts == 2,
		      "spread frame %d keeps two contacts at %.2f cells, got %d",
		      i, spacing, obs.mt_contacts);
		CHECK(active_slot_mask() == slot_mask,
		      "spread frame %d keeps the same Linux slots", i);
		CHECK(pair_tracking_ids_match(left_tid, right_tid),
		      "spread frame %d keeps tracking IDs bound to left/right fingers", i);
	}

	for (i = 1; i <= 16; i++) {
		double spacing = 8.0 - (8.0 - 4.27) * ((double)i / 16.0);

		c[1].x = c[0].x + spacing;
		obs = feed_virtual(&shid, c, 2);
		CHECK(obs.mt_contacts == 2,
		      "repinch frame %d keeps two contacts at %.2f cells, got %d",
		      i, spacing, obs.mt_contacts);
		CHECK(active_slot_mask() == slot_mask,
		      "repinch frame %d keeps the same Linux slots", i);
		CHECK(pair_tracking_ids_match(left_tid, right_tid),
		      "repinch frame %d keeps tracking IDs bound to left/right fingers", i);
	}

	teardown_device(&shid);
}

static void test_short_dropout_recovery(int missing_frames)
{
	struct spi_hid shid;
	struct spi_device spidev;
	struct vcontact pair[2], one[1];
	struct frame_obs obs = { 0, 0 };
	unsigned long long slot_mask;
	int left_tid = -1, right_tid = -1;
	int i;

	setup_device(&shid, &spidev);
	pair[0] = finger(26.0, 24.0);
	pair[1] = finger(30.27, 24.0);
	one[0] = pair[0];

	for (i = 0; i < 6; i++)
		obs = feed_virtual(&shid, pair, 2);
	CHECK(obs.mt_contacts == 2,
	      "%d-frame dropout setup publishes two contacts, got %d",
	      missing_frames, obs.mt_contacts);
	slot_mask = active_slot_mask();
	CHECK(pair_tracking_ids_by_x(&left_tid, &right_tid),
	      "%d-frame dropout setup assigns distinct logical tracking IDs",
	      missing_frames);

	for (i = 0; i < missing_frames; i++) {
		obs = feed_virtual(&shid, one, 1);
		CHECK(obs.mt_contacts == 2,
		      "%d-frame dropout miss %d remains published through lift grace, got %d",
		      missing_frames, i + 1, obs.mt_contacts);
		CHECK(active_slot_mask() == slot_mask,
		      "%d-frame dropout miss %d preserves the original Linux slots",
		      missing_frames, i + 1);
		CHECK(pair_tracking_ids_match(left_tid, right_tid),
		      "%d-frame dropout miss %d preserves logical tracking IDs",
		      missing_frames, i + 1);
	}

	for (i = 0; i < 5; i++) {
		obs = feed_virtual(&shid, pair, 2);
		CHECK(obs.mt_contacts == 2,
		      "%d-frame dropout recovery frame %d returns/keeps two contacts, got %d",
		      missing_frames, i, obs.mt_contacts);
		CHECK(active_slot_mask() == slot_mask,
		      "%d-frame dropout recovery frame %d keeps the same Linux slots",
		      missing_frames, i);
		CHECK(pair_tracking_ids_match(left_tid, right_tid),
		      "%d-frame dropout recovery frame %d preserves logical tracking IDs",
		      missing_frames, i);
	}

	teardown_device(&shid);
}

static void test_capture_shaped_close_birth(void)
{
	struct spi_hid shid;
	struct spi_device spidev;
	struct vcontact first[1], pair[2];
	struct frame_obs obs = { 0, 0 };
	unsigned long long slot_mask;
	int left_tid = -1, right_tid = -1;
	int i;

	setup_device(&shid, &spidev);
	first[0] = finger(30.0, 22.0);
	pair[0] = first[0];
	pair[1] = finger(34.27, 22.0);

	/* Mirrors the measured close-born capture shape: A leads by about
	 * 80 ms, B resolves 4.27 cells away, then the pair spreads apart. */
	for (i = 0; i < 8; i++)
		obs = feed_virtual(&shid, first, 1);
	CHECK(obs.mt_contacts == 1,
	      "capture-shaped lead contact is established before peer, got %d",
	      obs.mt_contacts);

	for (i = 0; i < 4; i++)
		obs = feed_virtual(&shid, pair, 2);
	CHECK(obs.detector_blobs >= 2,
	      "capture-shaped 4.27-cell peer is detector-resolvable, got %d blobs",
	      obs.detector_blobs);
	CHECK(obs.mt_contacts == 2,
	      "capture-shaped 80 ms close birth publishes two contacts, got %d",
	      obs.mt_contacts);
	slot_mask = active_slot_mask();
	CHECK(pair_tracking_ids_by_x(&left_tid, &right_tid),
	      "capture-shaped close birth assigns distinct logical tracking IDs");

	for (i = 1; i <= 16; i++) {
		double spacing = 4.27 + (8.0 - 4.27) * ((double)i / 16.0);

		pair[1].x = pair[0].x + spacing;
		obs = feed_virtual(&shid, pair, 2);
		CHECK(obs.mt_contacts == 2,
		      "capture-shaped spread frame %d keeps two contacts at %.2f cells, got %d",
		      i, spacing, obs.mt_contacts);
		CHECK(active_slot_mask() == slot_mask,
		      "capture-shaped spread frame %d preserves Linux slot identity",
		      i);
		CHECK(pair_tracking_ids_match(left_tid, right_tid),
		      "capture-shaped spread frame %d preserves logical tracking IDs",
		      i);
	}

	teardown_device(&shid);
}

static void test_tracking_id_lifecycle(void)
{
	struct spi_hid shid;
	struct spi_device spidev;
	struct vcontact one[1];
	struct frame_obs obs = { 0, 0 };
	int first_tid, second_tid;
	int i;

	setup_device(&shid, &spidev);
	one[0] = finger(30.0, 22.0);

	for (i = 0; i < 5; i++)
		obs = feed_virtual(&shid, one, 1);
	CHECK(obs.mt_contacts == 1,
	      "tracking-ID lifecycle setup publishes one contact, got %d",
	      obs.mt_contacts);
	first_tid = single_active_tracking_id();
	CHECK(first_tid >= 0,
	      "first contact receives a synthetic tracking ID");

	for (i = 0; i < 5; i++)
		obs = feed_virtual(&shid, NULL, 0);
	CHECK(obs.mt_contacts == 0,
	      "true lift clears the contact before rebirth, got %d",
	      obs.mt_contacts);

	for (i = 0; i < 5; i++)
		obs = feed_virtual(&shid, one, 1);
	CHECK(obs.mt_contacts == 1,
	      "reborn contact publishes again, got %d",
	      obs.mt_contacts);
	second_tid = single_active_tracking_id();
	CHECK(second_tid >= 0 && second_tid != first_tid,
	      "reborn contact gets a fresh tracking ID (%d -> %d)",
	      first_tid, second_tid);

	teardown_device(&shid);
}

static void test_detector_resolution_regimes(void)
{
	int max_blobs = 0;
	int mt;

	mt = hold_pair(2.40, 12, &max_blobs);
	CHECK(max_blobs == 1,
	      "2.40-cell virtual pair stays one detector blob in the tight/merged regime, got %d",
	      max_blobs);
	CHECK(mt == 1,
	      "2.40-cell virtual pair therefore publishes one Linux contact, got %d",
	      mt);

	mt = hold_pair(4.27, 12, &max_blobs);
	CHECK(max_blobs >= 2,
	      "4.27-cell virtual pair reaches two detector blobs, max %d",
	      max_blobs);
	CHECK(mt == 2,
	      "4.27-cell virtual pair publishes two Linux contacts, got %d",
	      mt);
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

	mt = staggered_result(10, 4.27, &max_blobs);
	CHECK(mt == 2,
	      "100 ms staggered 4.27-cell pair still qualifies, got %d",
	      mt);

	mt = staggered_result(12, 4.27, &max_blobs);
	CHECK(mt == 1,
	      "120 ms staggered 4.27-cell pair is outside the effective birth window, got %d",
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

static int transient_third_max_contacts(int duration_frames)
{
	struct spi_hid shid;
	struct spi_device spidev;
	struct vcontact two[2], three[3];
	struct frame_obs obs = { 0, 0 };
	int i, max_contacts = 0;

	setup_device(&shid, &spidev);
	two[0] = finger(18.0, 18.0);
	two[1] = finger(52.0, 18.0);
	three[0] = two[0];
	three[1] = two[1];
	three[2] = finger(35.0, 36.0);

	for (i = 0; i < 6; i++)
		feed_virtual(&shid, two, 2);
	for (i = 0; i < duration_frames; i++) {
		obs = feed_virtual(&shid, three, 3);
		if (obs.mt_contacts > max_contacts)
			max_contacts = obs.mt_contacts;
	}

	teardown_device(&shid);
	return max_contacts;
}

static void third_duration_sweep(void)
{
	int frames;

	printf("\n-- transient third-contact debounce sweep --\n");
	printf("third_frames,third_ms,max_linux_contacts\n");
	for (frames = 1; frames <= 5; frames++)
		printf("%d,%d,%d\n", frames, frames * 10,
		       transient_third_max_contacts(frames));
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
	test_detector_resolution_regimes();
	test_birth_min_sep_centroid_boundary();
	test_tracking_id_lifecycle();
	test_established_pinch();
	test_established_motion_slot_stability();
	test_staggered_birth_window();
	test_short_dropout_recovery(1);
	test_short_dropout_recovery(2);
	test_capture_shaped_close_birth();
	test_accidental_third_finger();

	/* Diagnostic matrices are intentionally printed even when assertions pass:
	 * they let us compare algorithm changes without another physical gesture. */
	spacing_sweep();
	fine_spacing_sweep();
	shape_sensitivity_sweep();
	unequal_strength_sweep();
	delay_sweep();
	fine_delay_sweep();
	third_duration_sweep();

	printf("\npanel_emulator_host_test: %d assertions, %d failures\n",
	       passed, failed);
	return failed ? 1 : 0;
}
