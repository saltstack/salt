# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import
from tempfile import NamedTemporaryFile
import os

# Import Salt Testing Libs
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.timezone as timezone
import salt.ext.six as six
import salt.utils

# Globals
timezone.__salt__ = {}
timezone.__opts__ = {}
timezone.__grains__ = {}

GET_ZONE_FILE = 'salt.modules.timezone._get_zone_file'
GET_ETC_LOCALTIME_PATH = 'salt.modules.timezone._get_etc_localtime_path'


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch.dict(timezone.__grains__, {'os_family': 'Ubuntu'})
class TimezoneTestCase(TestCase):

    def setUp(self):
        self.tempfiles = []

    def tearDown(self):
        for tempfile in self.tempfiles:
            try:
                os.remove(tempfile.name)
            except OSError:
                pass
        del self.tempfiles

    def test_zone_compare_equal(self):
        etc_localtime = self.create_tempfile_with_contents('a')
        zone_path = self.create_tempfile_with_contents('a')

        with patch(GET_ZONE_FILE, lambda p: zone_path.name):
            with patch(GET_ETC_LOCALTIME_PATH, lambda: etc_localtime.name):

                self.assertTrue(timezone.zone_compare('foo'))

    def test_zone_compare_nonexistent(self):
        etc_localtime = self.create_tempfile_with_contents('a')

        with patch(GET_ZONE_FILE, lambda p: '/foopath/nonexistent'):
            with patch(GET_ETC_LOCALTIME_PATH, lambda: etc_localtime.name):

                self.assertRaises(SaltInvocationError, timezone.zone_compare, 'foo')

    def test_zone_compare_unequal(self):
        etc_localtime = self.create_tempfile_with_contents('a')
        zone_path = self.create_tempfile_with_contents('b')

        with patch(GET_ZONE_FILE, lambda p: zone_path.name):
            with patch(GET_ETC_LOCALTIME_PATH, lambda: etc_localtime.name):

                self.assertFalse(timezone.zone_compare('foo'))

    def test_missing_localtime(self):
        with patch(GET_ZONE_FILE, lambda p: '/nonexisting'):
            with patch(GET_ETC_LOCALTIME_PATH, lambda: '/also-missing'):
                self.assertRaises(CommandExecutionError, timezone.zone_compare, 'foo')

    def create_tempfile_with_contents(self, contents):
        temp = NamedTemporaryFile(delete=False)
        if six.PY3:
            temp.write(salt.utils.to_bytes(contents))
        else:
            temp.write(contents)
        temp.close()
        self.tempfiles.append(temp)
        return temp
