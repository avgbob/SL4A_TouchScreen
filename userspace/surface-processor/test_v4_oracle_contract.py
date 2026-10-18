# SPDX-License-Identifier: GPL-2.0
import copy
import unittest

from v4_oracle_contract import EXPECTED, validate


def valid_summary():
    return {
        'schema': 'sl4a-windows-pointer-oracle-v1',
        'frame_count': 17018,
        'pointer_lifetimes': {'DOWN': 14, 'UP': 14},
        'active_at_end': [],
        'guided_holds': [
            {'event': event, 'physical_contacts': physical,
             'windows_contact_histogram': histogram}
            for event, (physical, histogram) in EXPECTED.items()
        ],
    }


class V4OracleContractTest(unittest.TestCase):
    def test_clean_contract_passes(self):
        result = validate(valid_summary())
        self.assertEqual(result['status'], 'V4_ORACLE_CONTRACT_PASS')
        self.assertEqual(result['counterexamples'][
            'horizontal_close_physical_two_windows_one_frames'], 160)

    def test_deliberate_lift_ghost_regression_is_rejected(self):
        summary = valid_summary()
        item = next(item for item in summary['guided_holds']
                    if item['event'] == 'OPERATOR_CONFIRM_VERTICAL_TOP_LIFTED')
        item['windows_contact_histogram'] = {'2': 157}
        with self.assertRaisesRegex(ValueError, 'histogram changed'):
            validate(summary)

    def test_returned_finger_birth_regression_is_rejected(self):
        summary = valid_summary()
        item = next(item for item in summary['guided_holds']
                    if item['event'] == 'OPERATOR_CONFIRM_VERTICAL_TOP_RETURNED')
        item['windows_contact_histogram'] = {'1': 153}
        with self.assertRaisesRegex(ValueError, 'histogram changed'):
            validate(summary)

    def test_lifetime_imbalance_is_rejected(self):
        summary = copy.deepcopy(valid_summary())
        summary['pointer_lifetimes']['UP'] = 13
        with self.assertRaisesRegex(ValueError, '14 DOWN / 14 UP'):
            validate(summary)


if __name__ == '__main__':
    unittest.main()
