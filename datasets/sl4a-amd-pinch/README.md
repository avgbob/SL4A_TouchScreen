# Surface Laptop 4 AMD — capacitive pinch heatmap research dataset

This directory provides the **privacy-hardened, user-authorized public dataset**
from a controlled one-handed pinch experiment on a Surface Laptop 4 AMD
touchscreen, intended to help investigate close-finger separation on Linux
and Windows.

**Download:** [SL4A_heatmaps_privacy_hardened.zip](SL4A_heatmaps_privacy_hardened.zip)

## Integrity and contents

- Archive SHA-256: `2c77050b9356b141ff0b30acf0a99a896db86a31d43cde6922dca558174aed2a`
- Raster concatenation SHA-256: `fa4773c352178cb06fcbd686d5e021d98bae03af4ca4ccc94f93a2e3f63f71a9`
- **8,232 frames** × **72×48 unsigned 8-bit cells**, in the same sensor frame order.
- `heatmaps_u8.bin` — **28,449,792 bytes** of heatmap-only data.
- `frame_relative_ticks.csv` — frame times **relative to the first raw frame**.
- `os_contact_transitions_relative.csv` — anonymized contact DOWN/UP and
  three operator-key annotations when **two physical fingers were on the glass**
  but the app showed **one Windows pointer**; event times are relative to a
  **different clock origin** and are not formally synchronized to sensor frames.
- `metadata.json` and `README.md` — decoding, limits, and privacy notes.

## Interpretation and limitations

An exploratory connected-component analysis found two spatially separate
sensor regions in the far-apart two-finger hold and one **dominant connected
region** near each of the three manually marked close-pinch mismatches.
This **does not** prove Windows discarded a valid second raw contact:
one connected region can contain overlapping physical fingertip signals,
and actual Microsoft tracker/classifier behavior was not captured. The
OS-to-raw timestamp mapping also needs calibration before exact frame-level
causal claims.

See [correlated Windows heatmap analysis](../../docs/WINDOWS-CORRELATED-HEATMAP-RESULT-20261017.md)
for evidence boundaries and next experiments.

## Privacy

Only capacitive rasters and relative/anonymized event timing were included.
The private full 4,304-byte sensor report bodies, vendor sections, ETL, WPR
CSV, absolute wall times, OS contact IDs, usernames, paths, and pointer
screen coordinates were excluded. ZIP modification timestamps are neutralized.
However, **sensor-space touch patterns and device-specific baseline
characteristics remain**, so this is privacy-reduced, not guaranteed anonymous.

The original full trace is intentionally **not** published.
Do not upload private ETL/CSV or vendor report contents into this directory.

## Licensing

The data owner explicitly authorized **public publication** of this dataset.
The archive itself does not declare a downstream data reuse license.
The repository's GPL-2.0 software license should not be treated as a
separately granted data license without further confirmation from the
repository owner.
