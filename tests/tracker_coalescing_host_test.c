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
 *   - an established track normally beats a close candidate assigned to a
 *     new slot, except for a tightly bounded recent-birth window matching the
 *     staggered close-born hardware capture;
 *   - two ambiguous same-frame new candidates retain only the stronger
 *     raw-weight blob;
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

static void test_recent_track_still_suppresses_tight_duplicate(void)
{
	struct spi_hid shid;
	struct blob_entry blobs[2];
	u8 assigned[2] = { 0, 1 };

	memset(&shid, 0, sizeof(shid));
	shid.blob_slot_state[0] = 2;
	shid.blob_slot_birth_age[0] = 8;
	blobs[0] = blob(1000, 1000, 5000);
	blobs[1] = blob(1200, 1000, 9000); /* 2 cells: observed duplicate band */

	raw_post_assoc_coalesce(&shid, blobs, 2, assigned, 6);

	CHECK(assigned[0] == 0 && assigned[1] == 0xff,
	      "recent track still suppresses a tight two-cell duplicate");
}

static void test_aged_track_suppresses_close_new_candidate(void)
{
	struct spi_hid shid;
	struct blob_entry blobs[2];
	u8 assigned[2] = { 0, 1 };

	memset(&shid, 0, sizeof(shid));
	shid.blob_slot_state[0] = 2;
	shid.blob_slot_birth_age[0] = HEATMAP_CLOSE_BIRTH_GRACE_FRAMES + 1;
	blobs[0] = blob(1000, 1000, 5000);
	blobs[1] = blob(1427, 1000, 9000); /* 4.27 cells, but peer is no longer young */

	raw_post_assoc_coalesce(&shid, blobs, 2, assigned, 6);

	CHECK(assigned[0] == 0 && assigned[1] == 0xff,
	      "aged established track keeps conservative close-new suppression");
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

static void run_tracker_frame(struct spi_hid *shid,
			      struct blob_entry *blobs, u8 count,
			      bool *new_active)
{
	u8 assigned[HEATMAP_MAX_BLOBS];
	u32 new_gx[HEATMAP_MAX_SLOTS];
	u32 new_gy[HEATMAP_MAX_SLOTS];
	u32 bmd;

	bmd = raw_hungarian_match(shid, blobs, count, assigned, 3);
	raw_post_assoc_coalesce(shid, blobs, count, assigned, 6);
	raw_update_slots(shid, blobs, count, assigned, bmd,
			 new_gx, new_gy, new_active,
			 2, 3, 3, 0);
}

static void test_recent_established_allows_staggered_close_birth(void)
{
	struct spi_hid shid;
	struct blob_entry first[1];
	struct blob_entry pair[2];
	bool active[HEATMAP_MAX_SLOTS];
	int i, claimed;

	memset(&shid, 0, sizeof(shid));

	/*
	 * Model the field capture: contact A is visible first and has about
	 * eight 100 Hz frames of lifetime before contact B resolves 4.27 cells
	 * away. A is already state 2 by then, but still inside the bounded
	 * birth grace window.
	 */
	for (i = 0; i < 8; i++) {
		first[0] = blob(1000, 1000, 5000);
		run_tracker_frame(&shid, first, 1, active);
	}

	CHECK(shid.blob_slot_state[0] == 2,
	      "first staggered contact is established before peer appears");
	CHECK(shid.blob_slot_birth_age[0] == 8,
	      "first contact retains eight-frame birth age");

	/*
	 * B must survive all three debounce frames, not merely one coalescing
	 * decision, before it becomes a published state-2 contact.
	 */
	for (i = 0; i < 3; i++) {
		pair[0] = blob(1000, 1000, 5000);
		pair[1] = blob(1427, 1000, 4800); /* 4.27 cells */
		run_tracker_frame(&shid, pair, 2, active);
	}

	claimed = 0;
	for (i = 0; i < HEATMAP_MAX_SLOTS; i++)
		if (shid.blob_slot_state[i] == 2)
			claimed++;

	CHECK(claimed == 2,
	      "staggered close-born peer reaches state 2 inside grace window");
	CHECK(active[0] && active[1],
	      "both staggered close-born contacts are published after debounce");
}

static void test_one_frame_dropout_recovers_same_slots(void)
{
	struct spi_hid shid;
	struct blob_entry one[1];
	struct blob_entry two[2];
	bool active[HEATMAP_MAX_SLOTS];

	memset(&shid, 0, sizeof(shid));
	shid.blob_slot_state[0] = 2;
	shid.blob_slot_state[1] = 2;
	shid.blob_slot_gx[0] = 1000;
	shid.blob_slot_gy[0] = 1000;
	shid.blob_slot_gx[1] = 1500;
	shid.blob_slot_gy[1] = 1000;
	shid.blob_slot_weight[0] = 5000;
	shid.blob_slot_weight[1] = 5000;

	/* The detector/split stage transiently emits one candidate even though
	 * both physical contacts remain down. The unmatched track enters state 3
	 * but is still published active during the lift grace window. */
	one[0] = blob(1000, 1000, 5000);
	run_tracker_frame(&shid, one, 1, active);

	CHECK(shid.blob_slot_state[0] == 2,
	      "surviving track remains active through one-candidate frame");
	CHECK(shid.blob_slot_state[1] == 3,
	      "missing established track enters lift-pending state 3");
	CHECK(active[0] && active[1],
	      "both slots remain published during one-frame dropout");

	/* On the next frame both close candidates return. Association runs before
	 * coalescing, so state 2 + state 3 is recognized as two established
	 * tracks and the pending slot recovers in place. */
	two[0] = blob(1000, 1000, 5000);
	two[1] = blob(1500, 1000, 5000);
	run_tracker_frame(&shid, two, 2, active);

	CHECK(shid.blob_slot_state[0] == 2 && shid.blob_slot_state[1] == 2,
	      "state-3 contact recovers to active without slot reallocation");
	CHECK(active[0] && active[1],
	      "both original slots remain published after recovery");
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
	test_recent_track_still_suppresses_tight_duplicate();
	test_aged_track_suppresses_close_new_candidate();
	test_two_new_candidates_use_raw_weight();
	test_recent_established_allows_staggered_close_birth();
	test_one_frame_dropout_recovers_same_slots();
	test_exact_boundary_is_not_coalesced();

	fprintf(stderr, "tracker_coalescing_host_test: %d assertions, %d failures\n",
		passed, failed);
	return failed ? 1 : 0;
}
