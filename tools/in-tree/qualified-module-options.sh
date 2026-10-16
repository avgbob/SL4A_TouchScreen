#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
# Verify a candidate load command uses ONLY parameters from the exact PR87.
set -Eeuo pipefail
repo="$(cd "$(dirname "$0")/../.." && pwd)"
source "$repo/tools/in-tree/source-selection.sh"
root="$(sl4a_select_source "$repo" pr87)"
core="$root/spi-hid-core.c"
[[ -r "$core" ]] || exit 1
# Known-good exact-PR87 first-HID parameters from the Oct. 16 coldboot.
options=(
  raw_mode=N
  raw_input_beta=Y
  wire_double_opcode=1
  skip_std_getfeat=1
  std_raw_transition=1
  get_noread=0
  getfeat_delay_ms=0
  std_liveness_ms=0
  std_liveness_recover=0
  wait_reset_kick_ms=0
)
for kv in "${options[@]}"; do
    key="${kv%%=*}"
    grep -Eq "^[[:space:]]*module_param\\($key[[:space:]]*," "$core" || {
        echo "ERROR: PR87 source does not accept $key from cold-qualified command" >&2
        exit 1
    }
done
if grep -Eq '^[[:space:]]*module_param\(gate3_observe_only[[:space:]]*,' "$core"; then
    echo "ERROR: Gate5-only parameter unexpectedly present" >&2
    exit 1
fi
printf 'PR87 COLD-QUALIFIED MODULE PARAMETERS: %s\n' "${options[*]}"
printf 'REJECT OLD GATE5 ARGUMENT: gate3_observe_only=1 (not supported)\n'
printf 'PR87 module parameter contract: PASS\n'
