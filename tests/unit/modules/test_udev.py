# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pablo Suárez Hdez. <psuarezhernandez@suse.de>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.udev as udev


@skipIf(NO_MOCK, NO_MOCK_REASON)
class UdevTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.udev
    '''
    loader_module = udev
    # 'info' function tests: 1

    def test_info(self):
        '''
        Test if it returns the info of udev-created node in a dict
        '''
        cmd_out = {
            'retcode': 0,
            'stdout': "P: /devices/virtual/vc/vcsa7\n"
                      "N: vcsa7\n"
                      "E: DEVNAME=/dev/vcsa7\n"
                      "E: DEVPATH=/devices/virtual/vc/vcsa7\n"
                      "E: MAJOR=7\n"
                      "E: MINOR=135\n"
                      "E: SUBSYSTEM=vc\n"
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
            data = udev.info("/dev/vcsa7")

            assert ret['P'] == data['P']
            assert ret.get('N') == data.get('N')
            for key, value in data['E'].items():
                assert ret['E'][key] == value

    # 'exportdb' function tests: 1

    def test_exportdb(self):
        '''
        Test if it returns the all the udev database into a dict
        '''
        udev_data = """
P: /devices/LNXSYSTM:00/LNXPWRBN:00
E: DEVPATH=/devices/LNXSYSTM:00/LNXPWRBN:00
E: DRIVER=button
E: MODALIAS=acpi:LNXPWRBN:
E: SUBSYSTEM=acpi

P: /devices/LNXSYSTM:00/LNXPWRBN:00/input/input2
E: DEVPATH=/devices/LNXSYSTM:00/LNXPWRBN:00/input/input2
E: EV=3
E: ID_FOR_SEAT=input-acpi-LNXPWRBN_00
E: ID_INPUT=1
E: ID_INPUT_KEY=1
E: ID_PATH=acpi-LNXPWRBN:00
E: ID_PATH_TAG=acpi-LNXPWRBN_00
E: KEY=10000000000000 0
E: MODALIAS=input:b0019v0000p0001e0000-e0,1,k74,ramlsfw
E: NAME="Power Button"
E: PHYS="LNXPWRBN/button/input0"
E: PRODUCT=19/0/1/0
E: PROP=0
E: SUBSYSTEM=input
E: TAGS=:seat:
E: USEC_INITIALIZED=2010022

P: /devices/LNXSYSTM:00/LNXPWRBN:00/input/input2/event2
N: input/event2
E: BACKSPACE=guess
E: DEVNAME=/dev/input/event2
E: DEVPATH=/devices/LNXSYSTM:00/LNXPWRBN:00/input/input2/event2
E: ID_INPUT=1
E: ID_INPUT_KEY=1
E: ID_PATH=acpi-LNXPWRBN:00
E: ID_PATH_TAG=acpi-LNXPWRBN_00
E: MAJOR=13
E: MINOR=66
E: SUBSYSTEM=input
E: TAGS=:power-switch:
E: USEC_INITIALIZED=2076101
E: XKBLAYOUT=us
E: XKBMODEL=pc105
    """

        out = [{'P': '/devices/LNXSYSTM:00/LNXPWRBN:00',
                'E': {'MODALIAS': 'acpi:LNXPWRBN:',
                      'SUBSYSTEM': 'acpi',
                      'DRIVER': 'button',
                      'DEVPATH': '/devices/LNXSYSTM:00/LNXPWRBN:00'}},
               {'P': '/devices/LNXSYSTM:00/LNXPWRBN:00/input/input2',
                'E': {'SUBSYSTEM': 'input',
                      'PRODUCT': '19/0/1/0',
                      'PHYS': '"LNXPWRBN/button/input0"',
                      'NAME': '"Power Button"',
                      'ID_INPUT': 1,
                      'DEVPATH': '/devices/LNXSYSTM:00/LNXPWRBN:00/input/input2',
                      'MODALIAS': 'input:b0019v0000p0001e0000-e0,1,k74,ramlsfw',
                      'ID_PATH_TAG': 'acpi-LNXPWRBN_00',
                      'TAGS': ':seat:',
                      'PROP': 0,
                      'ID_FOR_SEAT': 'input-acpi-LNXPWRBN_00',
                      'KEY': '10000000000000 0',
                      'USEC_INITIALIZED': 2010022,
                      'ID_PATH': 'acpi-LNXPWRBN:00',
                      'EV': 3,
                      'ID_INPUT_KEY': 1}},
               {'P': '/devices/LNXSYSTM:00/LNXPWRBN:00/input/input2/event2',
                'E': {'SUBSYSTEM': 'input',
                      'XKBLAYOUT': 'us',
                      'MAJOR': 13,
                      'ID_INPUT': 1,
                      'DEVPATH': '/devices/LNXSYSTM:00/LNXPWRBN:00/input/input2/event2',
                      'ID_PATH_TAG': 'acpi-LNXPWRBN_00',
                      'DEVNAME': '/dev/input/event2',
                      'TAGS': ':power-switch:',
                      'BACKSPACE': 'guess',
                      'MINOR': 66,
                      'USEC_INITIALIZED': 2076101,
                      'ID_PATH': 'acpi-LNXPWRBN:00',
                      'XKBMODEL': 'pc105',
                      'ID_INPUT_KEY': 1},
                'N': 'input/event2'}]

        mock = MagicMock(return_value={'retcode': 0, 'stdout': udev_data})
        with patch.dict(udev.__salt__, {'cmd.run_all': mock}):
            data = udev.exportdb()
            assert data == [x for x in data if x]

            for d_idx, d_section in enumerate(data):
                assert out[d_idx]['P'] == d_section['P']
                assert out[d_idx].get('N') == d_section.get('N')
                for key, value in d_section['E'].items():
                    assert out[d_idx]['E'][key] == value

    def test_normalize_info(self):
        '''
        Test if udevdb._normalize_info does not returns nested lists that contains only one item.

        :return:
        '''
        data = {'key': ['value', 'here'], 'foo': ['bar'], 'some': 'data'}
        assert udev._normalize_info(data) == {'foo': 'bar', 'some': 'data', 'key': ['value', 'here']}
