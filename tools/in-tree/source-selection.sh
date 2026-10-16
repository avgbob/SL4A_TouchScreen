#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
# Shared source selector for BOTH in-kernel layout experiments.
# Qualified PR87 source is copied BY BLOB from the original Git commit.
# The old Gate5/tracker-lab source remains in driver/ without modification.
sl4a_select_source() {
    local repo="$1" flavor="${2:-pr87}" root="" pinned="" sha="" name="" count=0
    case "$flavor" in
        pr87)
            root="$repo/kernel-pins/pr87/driver"
            [[ -f "$repo/kernel-pins/pr87/SOURCE-COMMIT" &&
               "$(cat "$repo/kernel-pins/pr87/SOURCE-COMMIT")" == "18f0fe79623e6de4fdf1ae493f82a7048397386a" ]] || {
                echo "ERROR: pinned PR87 commit identity mismatch" >&2; return 1;
            }
            [[ -f "$repo/kernel-pins/pr87/DRIVER-BLOBS.txt" ]] || {
                echo "ERROR: PR87 blob manifest missing" >&2; return 1;
            }
            while read -r sha name; do
                [[ "$sha" == \#* || -z "$sha" ]] && continue
                [[ "$name" =~ ^[A-Za-z0-9_-]+\.[ch]$ &&
                   "$sha" =~ ^[0-9a-f]{40}$ && -s "$root/$name" ]] || {
                    echo "ERROR: malformed/missing pinned PR87 file: $name" >&2; return 1;
                }
                pinned="$(git hash-object -- "$root/$name")" || return 1
                [[ "$pinned" == "$sha" ]] || {
                    echo "ERROR: immutable PR87 source drift: $name expected=$sha actual=$pinned" >&2
                    return 1
                }
                ((count += 1))
            done < "$repo/kernel-pins/pr87/DRIVER-BLOBS.txt"
            [[ "$count" -eq 14 ]] || {
                echo "ERROR: expected exactly 14 PR87 driver C/H files (got $count)" >&2; return 1;
            }
            [[ "$(find "$root" -maxdepth 1 -type f \( -name '*.c' -o -name '*.h' \) | wc -l)" -eq 14 ]] || {
                echo "ERROR: unexpected files in PR87 driver tree" >&2; return 1;
            }
            ;;
        legacy-gate5)
            root="$repo/driver"
            [[ -s "$root/spi-hid-core.c" && -s "$root/mshw0231-raw.c" ]] || {
                echo "ERROR: legacy source files missing" >&2; return 1;
            }
            ;;
        *)
            echo "ERROR: unrecognized SL4A_IN_TREE_SOURCE=$flavor; choose pr87 or legacy-gate5" >&2
            return 2 ;;
    esac
    printf '%s\n' "$root"
}
