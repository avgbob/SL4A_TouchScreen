// SPDX-License-Identifier: GPL-2.0
/*
 * panel_policy_ab_test
 *
 * Host-only A/B harness for HEATMAP_CLOSE_BIRTH_MIN_SEP.
 *
 * The production driver is not modified.  This translation unit reuses the
 * complete virtual-panel harness and staged real mshw0231-raw.c, while the
 * build supplies SL4A_TEST_CLOSE_BIRTH_MIN_SEP as 2.50, 2.75, or 3.00.
 *
 * It reports two things for each candidate policy:
 *   1. legitimate two-finger shape/strength sensitivity; and
 *   2. an adversarial established-finger + weaker nearby secondary-lobe
 *      scenario, including both transient (2-frame) and sustained (5-frame)
 *      lobes.  The latter approximates a persistent detector split/ghost that
 *      could become a false second contact if the guard is relaxed too far.
 */

#ifndef SL4A_TEST_CLOSE_BIRTH_MIN_SEP
#error "build with -DSL4A_TEST_CLOSE_BIRTH_MIN_SEP=<cells>"
#endif

#define main panel_emulator_original_main
#include "panel_emulator_host_test.c"
#undef main

struct lobe_result {
	int max_detector_blobs;
	int centroid_sep100;
	int max_linux_contacts;
};

static struct lobe_result run_secondary_lobe(double offset,
					      double lobe_amp,
					      int lobe_frames)
{
	struct spi_hid shid;
	struct spi_device spidev;
	struct vcontact base[1], pair[2];
	struct frame_obs obs = { 0, 0 };
	struct lobe_result out = { 0, -1, 0 };
	int i;

	setup_device(&shid, &spidev);
	base[0] = finger(30.0, 22.0);
	base[0].amplitude = 110.0;
	base[0].sigma = 1.20;

	/*
	 * Establish the real contact first while it is still well inside the
	 * close-birth grace window.  Then introduce a weaker nearby lobe.
	 */
	for (i = 0; i < 4; i++)
		feed_virtual(&shid, base, 1);

	pair[0] = base[0];
	pair[1] = finger(30.0 + offset, 22.0);
	pair[1].amplitude = lobe_amp;
	pair[1].sigma = 0.80;

	for (i = 0; i < lobe_frames; i++) {
		obs = feed_virtual(&shid, pair, 2);
		if (obs.detector_blobs > out.max_detector_blobs)
			out.max_detector_blobs = obs.detector_blobs;
		if (obs.mt_contacts > out.max_linux_contacts)
			out.max_linux_contacts = obs.mt_contacts;
	}

	out.centroid_sep100 = detector_pair_sep100(&shid);
	teardown_device(&shid);
	return out;
}

static void secondary_lobe_sweep(void)
{
	static const double amp[] = { 35.0, 50.0, 70.0, 90.0 };
	static const double offset[] = { 2.40, 2.60, 2.80, 3.00, 3.20, 3.40 };
	size_t a, o;

	printf("\n-- adversarial established-finger + secondary-lobe sweep --\n");
	printf("guard,offset,lobe_amp,max_blobs,centroid_sep,max_contacts_2f,max_contacts_5f\n");

	for (a = 0; a < sizeof(amp) / sizeof(amp[0]); a++) {
		for (o = 0; o < sizeof(offset) / sizeof(offset[0]); o++) {
			struct lobe_result short_r =
				run_secondary_lobe(offset[o], amp[a], 2);
			struct lobe_result long_r =
				run_secondary_lobe(offset[o], amp[a], 5);
			int sep100 = long_r.centroid_sep100 >= 0 ?
				     long_r.centroid_sep100 : short_r.centroid_sep100;

			printf("%.2f,%.2f,%.0f,%d,",
			       (double)SL4A_TEST_CLOSE_BIRTH_MIN_SEP,
			       offset[o], amp[a],
			       long_r.max_detector_blobs > short_r.max_detector_blobs ?
			       long_r.max_detector_blobs : short_r.max_detector_blobs);
			if (sep100 >= 0)
				printf("%.2f,", (double)sep100 / 100.0);
			else
				printf("NA,");
			printf("%d,%d\n",
			       short_r.max_linux_contacts,
			       long_r.max_linux_contacts);
		}
	}
}

int main(void)
{
	printf("panel_policy_ab_test: host-only close-birth guard %.2f cells\n",
	       (double)SL4A_TEST_CLOSE_BIRTH_MIN_SEP);
	printf("production driver source is staged unchanged; only this host build overrides the constant\n");

	shape_sensitivity_sweep();
	unequal_strength_sweep();
	secondary_lobe_sweep();
	return 0;
}
