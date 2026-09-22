// SPDX-License-Identifier: GPL-2.0
/*
 * SL4A virtual tablet-mode switch.
 *
 * Experimental companion module for Surface Laptop 4-class systems that have
 * a real touchscreen but no hardware tablet-mode switch.  While loaded, this
 * module exposes EV_SW/SW_TABLET_MODE=1 through the Linux input subsystem.
 *
 * Mutter/Clutter then sees a real libinput tablet-mode switch.  GNOME's native
 * KeyboardManager still requires the last non-keyboard device to be a
 * touchscreen before auto-enabling the on-screen keyboard, so mouse/touchpad
 * use remains part of GNOME's normal policy.
 *
 * This module is intentionally independent from sl4a-spi-hid.  Loading or
 * unloading it does not bind, reset, reload, or otherwise alter the touchscreen
 * transport/tracker driver.
 */

#include <linux/init.h>
#include <linux/input.h>
#include <linux/module.h>

static struct input_dev *sl4a_tablet_mode_input;

static int __init sl4a_tablet_mode_init(void)
{
	struct input_dev *input;
	int ret;

	input = input_allocate_device();
	if (!input)
		return -ENOMEM;

	input->name = "SL4A Virtual Tablet Mode";
	input->phys = "sl4a/tablet-mode";
	input->id.bustype = BUS_HOST;
	input->id.vendor = 0x045e;
	input->id.product = 0x0231;
	input->id.version = 0x0001;

	input_set_capability(input, EV_SW, SW_TABLET_MODE);

	/*
	 * Seed the initial state before registration, matching in-tree tablet-mode
	 * switch drivers such as surface_dtx and surface_aggregator_tabletsw.
	 */
	input_report_switch(input, SW_TABLET_MODE, 1);

	ret = input_register_device(input);
	if (ret) {
		input_free_device(input);
		return ret;
	}

	sl4a_tablet_mode_input = input;

	pr_info("sl4a_tablet_mode: registered virtual SW_TABLET_MODE=1 switch\n");
	return 0;
}

static void __exit sl4a_tablet_mode_exit(void)
{
	if (!sl4a_tablet_mode_input)
		return;

	/*
	 * Publish OFF before removal so listeners can observe a clean transition.
	 * input_unregister_device() also removes the input device from the seat.
	 */
	input_report_switch(sl4a_tablet_mode_input, SW_TABLET_MODE, 0);
	input_sync(sl4a_tablet_mode_input);
	input_unregister_device(sl4a_tablet_mode_input);
	sl4a_tablet_mode_input = NULL;

	pr_info("sl4a_tablet_mode: unregistered virtual tablet-mode switch\n");
}

module_init(sl4a_tablet_mode_init);
module_exit(sl4a_tablet_mode_exit);

MODULE_AUTHOR("SL4A_TouchScreen contributors");
MODULE_DESCRIPTION("Experimental virtual SW_TABLET_MODE switch for SL4A touchscreen systems");
MODULE_LICENSE("GPL");
