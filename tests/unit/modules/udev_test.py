# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pablo Suárez Hdez. <psuarezhernandez@suse.de>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import udev

# Globals
udev.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class UdevTestCase(TestCase):
    '''
    Test cases for salt.modules.udev
    '''
    # 'info' function tests: 1

    def test_info(self):
        '''
        Test if it returns the info of udev-created node in a dict
        '''
        cmd_out = {
            'retcode': 0,
            'stdout': "P: /devices/virtual/vc/vcsa7\n" \
                      "N: vcsa7\n" \
                      "E: DEVNAME=/dev/vcsa7\n" \
                      "E: DEVPATH=/devices/virtual/vc/vcsa7\n" \
                      "E: MAJOR=7\n" \
                      "E: MINOR=135\n" \
                      "E: SUBSYSTEM=vc\n" \
                      "\n",
            'stderr': ''
        }

        ret = {
            "E": {"DEVNAME": "/dev/vcsa7",
                  "DEVPATH": "/devices/virtual/vc/vcsa7",
                  "MAJOR": 7,
                  "MINOR": 135,
                  "SUBSYSTEM": "vc"},
            "N": "vcsa7",
            "P": "/devices/virtual/vc/vcsa7"}

        mock = MagicMock(return_value=cmd_out)
        with patch.dict(udev.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(udev.info("/dev/vcsa7"), ret)


    # 'exportdb' function tests: 1

    def test_exportdb(self):
        '''
        Test if it returns the all the udev database into a dict
        '''
        cmd_out = {
            'retcode': 0,
            'stdout': "P: /devices/virtual/vc/vcsa7\n" \
                      "N: vcsa7\n" \
                      "E: DEVNAME=/dev/vcsa7\n" \
                      "E: DEVPATH=/devices/virtual/vc/vcsa7\n" \
                      "E: MAJOR=7\n" \
                      "E: MINOR=135\n" \
                      "E: SUBSYSTEM=vc\n" \
                      "\n" \
                      "P: /devices/virtual/workqueue/writeback\n" \
                      "E: DEVPATH=/devices/virtual/workqueue/writeback\n" \
                      "E: SUBSYSTEM=workqueue\n" \
                      "\n",
            'stderr': ''
        }

        ret = [
            {"E": {"DEVNAME": "/dev/vcsa7",
                   "DEVPATH": "/devices/virtual/vc/vcsa7",
                   "MAJOR": 7,
                   "MINOR": 135,
                   "SUBSYSTEM": "vc"},
             "N": "vcsa7",
             "P": "/devices/virtual/vc/vcsa7"},
            {"E": {"DEVPATH": "/devices/virtual/workqueue/writeback",
                   "SUBSYSTEM": "workqueue"},
             "P": "/devices/virtual/workqueue/writeback"}
        ]

        mock = MagicMock(return_value=cmd_out)
        with patch.dict(udev.__salt__, {'cmd.run_all': mock}):
            self.assertListEqual(udev.exportdb(), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(UdevTestCase, needs_daemon=False)
