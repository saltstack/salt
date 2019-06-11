# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import textwrap

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.modules.xfs as xfs


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.modules.xfs._get_mounts', MagicMock(return_value={}))
class XFSTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.xfs
    '''
    def setup_loader_modules(self):
        return {xfs: {}}

    def test__blkid_output(self):
        '''
        Test xfs._blkid_output when there is data
        '''
        blkid_export = textwrap.dedent('''
            DEVNAME=/dev/sda1
            UUID=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
            TYPE=xfs
            PARTUUID=YYYYYYYY-YY

            DEVNAME=/dev/sdb1
            PARTUUID=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
            ''')
        self.assertEqual(xfs._blkid_output(blkid_export), {
            '/dev/sda1': {
                'label': None,
                'partuuid': 'YYYYYYYY-YY',
                'uuid': 'XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX'
            }
        })
