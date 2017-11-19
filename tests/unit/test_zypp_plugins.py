# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

import os
import imp
import sys
from zypp_plugin import BogusIO

if sys.version_info >= (3,):
    BUILTINS_OPEN = 'builtins.open'
else:
    BUILTINS_OPEN = '__builtin__.open'

zyppnotify = imp.load_source('zyppnotify', os.path.sep.join(os.path.dirname(__file__).split(
    os.path.sep)[:-2] + ['scripts', 'suse', 'zypper', 'plugins', 'commit', 'zyppnotify']))


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ZyppPluginsTestCase(TestCase):
    '''
    Test shipped libzypp plugins.
    '''
    def test_drift_detector(self):
        '''
        Test drift detector for a correct cookie file.
        Returns:

        '''
        drift = zyppnotify.DriftDetector()
        drift._get_mtime = MagicMock(return_value=123)
        drift._get_checksum = MagicMock(return_value='deadbeef')
        bogus_io = BogusIO()
        with patch(BUILTINS_OPEN, bogus_io):
            drift.PLUGINEND(None, None)
        self.assertEqual(str(bogus_io), 'deadbeef 123\n')
        self.assertEqual(bogus_io.mode, 'w')
        self.assertEqual(bogus_io.path, '/var/cache/salt/minion/rpmdb.cookie')
