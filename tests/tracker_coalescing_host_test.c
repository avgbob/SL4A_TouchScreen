// SPDX-License-Identifier: GPL-2.0
/*
 * tracker_coalescing_host_test
 *
 * Pins the ordering rule recovered from TouchPenProcessor0C19 and proven by
 * the MSHW0231 field pinch capture: candidate/track association happens before
 * close-contact coalescing.  This test includes the real staged driver source
 * so it exercises raw_post_assoc_coalesce() directly rather than a mirror.
 *
 * The policy is intentionally conservative until candidate classification is
 * recovered:
 *   - close candidates assigned to two established tracks survive;
 *   - state-3 (lift-pending) counts as established continuity so a one-frame
 *     detector/split hiccup can recover without an ID drop;
 *   - an established track beats a close candidate assigned to a new slot;
 *   - two ambiguous new candidates retain only the stronger raw-weight blob;
 *   - the six-cell threshold is strict: exactly six cells is not coalesced.
 */
#include <stdio.h>
#include <string.h>

#include "spi-hid-core.h"
#include "mshw0231-raw.h"
#include "mshw0231-raw-constants.h"
#include <linux/input.h>
#include <linux/input/mt.h>
#include <linux/jiffies.h>
#include <linux/slab.h>
#include "mt_record.h"

#include "raw-pipeline-stage/mshw0231-raw.c"

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

static struct blob_entry blob(u32 gx, u32 gy, u32 raw_w)
{
	struct blob_entry b = {
		.gx = gx,
		.gy = gy,
		.w = raw_w,
		.raw_w = raw_w,
		.idx = 0,
	};

	return b;
}

static void test_two_established_close_survive(void)
{
	struct spi_hid shid;
	struct blob_entry blobs[2];
	u8 assigned[2] = { 0, 1 };

	memset(&shid, 0, sizeof(shid));
	shid.blob_slot_state[0] = 2;
	shid.blob_slot_state[1] = 2;
	blobs[0] = blob(1000, 1000, 5000);
	blobs[1] = blob(1490, 1000, 4500); /* 4.9 cells */

	raw_post_assoc_coalesce(&shid, blobs, 2, assigned, 6);

	CHECK(assigned[0] == 0 && assigned[1] == 1,
	      "two established close tracks must both survive");
	CHECK(blobs[0].w != 0 && blobs[1].w != 0,
	      "preserved established candidates keep their weights");
}

static void test_lift_pending_continuity_survives(void)
{
	struct spi_hid shid;
	struct blob_entry blobs[2];
	u8 assigned[2] = { 3, 7 };

	memset(&shid, 0, sizeof(shid));
	shid.blob_slot_state[3] = 2;
	shid.blob_slot_state[7] = 3;
	blobs[0] = blob(2000, 2000, 5200);
	blobs[1] = blob(2500, 2000, 5100); /* 5 cells */

	raw_post_assoc_coalesce(&shid, blobs, 2, assigned, 6);

	CHECK(assigned[0] == 3 && assigned[1] == 7,
	      "state 2 + state 3 pair must preserve continuity");
}

static void test_established_beats_new_duplicate(void)
{
	struct spi_hid shid;
	struct blob_entry blobs[2];
	u8 assigned[2] = { 4, 9 };

	memset(&shid, 0, sizeof(shid));
	shid.blob_slot_state[4] = 2;
	shid.blob_slot_state[9] = 0;
	/* Make the new candidate heavier on purpose: continuity still wins. */
	blobs[0] = blob(3000, 3000, 4000);
	blobs[1] = blob(3450, 3000, 9000);

	raw_post_assoc_coalesce(&shid, blobs, 2, assigned, 6);

	CHECK(assigned[0] == 4,
	      "established assignment survives close new candidate");
	CHECK(assigned[1] == 0xff && blobs[1].w == 0,
	      "close new candidate is suppressed instead of stealing continuity");
}

static void test_two_new_candidates_use_raw_weight(void)
{
	struct spi_hid shid;
	struct blob_entry blobs[2];
	u8 assigned[2] = { 2, 8 };

	memset(&shid, 0, sizeof(shid));
	shid.blob_slot_state[2] = 0;
	shid.blob_slot_state[8] = 0;
	blobs[0] = blob(4000, 4000, 7000);
	blobs[1] = blob(4450, 4000, 3000);

	raw_post_assoc_coalesce(&shid, blobs, 2, assigned, 6);

	CHECK(assigned[0] == 2,
	      "stronger ambiguous new candidate survives");
	CHECK(assigned[1] == 0xff && blobs[1].w == 0,
	      "weaker ambiguous new candidate is suppressed");
}

static void test_exact_boundary_is_not_coalesced(void)
{
	struct spi_hid shid;
	struct blob_entry blobs[2];
	u8 assigned[2] = { 0, 1 };

	memset(&shid, 0, sizeof(shid));
	blobs[0] = blob(1000, 1000, 5000);
	blobs[1] = blob(1600, 1000, 4000); /* exactly 6 cells */

	raw_post_assoc_coalesce(&shid, blobs, 2, assigned, 6);

	CHECK(assigned[0] == 0 && assigned[1] == 1,
	      "exactly ghost_dist must not coalesce (strict comparison)");
}

int main(void)
{
	fprintf(stderr, "tracker_coalescing_host_test: running...\n");

	test_two_established_close_survive();
	test_lift_pending_continuity_survives();
	test_established_beats_new_duplicate();
	test_two_new_candidates_use_raw_weight();
	test_exact_boundary_is_not_coalesced();

	fprintf(stderr, "tracker_coalescing_host_test: %d assertions, %d failures\n",
		passed, failed);
	return failed ? 1 : 0;
}
