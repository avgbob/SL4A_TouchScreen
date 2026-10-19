# Experimental virtual tablet-mode switch

This branch adds a separate `sl4a-tablet-mode.ko` companion module. It does
not bind to the MSHW0231 touchscreen and does not reload or modify
`sl4a-spi-hid`.

While loaded it registers a Linux input device named:

```text
SL4A Virtual Tablet Mode
```

with `EV_SW / SW_TABLET_MODE=1`.

Mutter 46 uses a libinput tablet-mode switch as one of the inputs to its native
`touch-mode` state. GNOME Shell's KeyboardManager still additionally checks
that the last non-keyboard input device is a touchscreen before automatically
enabling the OSK.

## Build without installing anything

```bash
cd "$HOME/SL4A_TouchScreen-current"

git fetch origin experiment/tablet-mode-switch
git switch --detach origin/experiment/tablet-mode-switch

make -C driver clean
make -C driver

ls -lh driver/sl4a-tablet-mode.ko
```

Building the branch does not install or load any module.

## Test only the companion switch

Disable any userspace touch-mode overrides first:

```bash
gnome-extensions disable touchx@neuromorph 2>/dev/null
gnome-extensions disable touch-only-native-v8@jo.local 2>/dev/null

gsettings set org.gnome.desktop.a11y.applications screen-keyboard-enabled false
```

Then load only the new companion module:

```bash
sudo insmod "$HOME/SL4A_TouchScreen-current/driver/sl4a-tablet-mode.ko"

grep -A8 -B2 'SL4A Virtual Tablet Mode' /proc/bus/input/devices

libinput list-devices | sed -n '/SL4A Virtual Tablet Mode/,+18p'
```

Do not unload or reload `sl4a-spi-hid` for this experiment.

## Roll back immediately

```bash
sudo rmmod sl4a_tablet_mode
```

The module publishes `SW_TABLET_MODE=0` before unregistering the virtual input
device. No F108 touchscreen module state is changed.
