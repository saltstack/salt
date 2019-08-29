# -*- coding: utf-8 -*-
# Import Python Libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf, WAR_ROOM_SKIP
from tests.support.mock import (
    patch,
    mock_open,
)

# Import Salt Libs
import salt.utils.master as master
import salt.utils.platform

try:
    import salt.utils.psutil_compat as psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class MasterUtilsReadProcTestCase(TestCase):

    def test_read_proc_successfully(self):
        proc_data = {"pid": 1111, "tacos": "broseph"}
        m_fopen = mock_open()
        with patch('salt.payload.Serial.load', return_value=proc_data):
            with patch('salt.utils.files.fopen', m_fopen):
                data = master.read_proc_file('/tacos', {})
                assert data == proc_data

    def test_read_proc_open_raise(self):
        m_fopen = mock_open()
        m_fopen.side_effect = Exception
        with patch('salt.utils.files.fopen', m_fopen):
            data = master.read_proc_file('x', {})
            assert data is None

    def test_read_proc_not_dict(self):
        proc_data = '}{'
        m_fopen = mock_open()
        with patch('salt.payload.Serial.load', return_value=proc_data):
            with patch('salt.utils.files.fopen', m_fopen):
                data = master.read_proc_file('/tacos', {})
                assert data is None

    def test_read_proc_no_pid(self):
        m_fopen = mock_open()
        proc_data = {"tacos": "broseph"}
        with patch('salt.payload.Serial.load', return_value=proc_data):
            with patch('salt.utils.files.fopen', m_fopen):
                data = master.read_proc_file('/tacos', {})
                assert data is None


@skipIf(not HAS_PSUTIL, "psutil needed to run test")
class MasterUtilsIsPidHealthyPsUtil(TestCase):

    @skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
    def tests_pid_not_running(self):
        assert master.is_pid_healthy(99999999) is False

    def test_is_pid_healthy_running_salt(self):
        with patch('psutil.Process.cmdline', return_value=['salt']):
            # Windows needs an actual PID, so we'll use os.getpid()
            # Unless we can figure out how to mock psutil.Process
            # so that it doesn't enter the except block
            self.assertTrue(master.is_pid_healthy(os.getpid()))

    @skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
    def test_is_pid_healthy_not_running_salt(self):
        with patch('psutil.Process.cmdline', return_value=['tacos']):
            assert master.is_pid_healthy(1) is False

    def tets_is_pid_healthy_raises(self):
        with patch("psutil.Process", side_effect=psutil.NoSuchProcess):
            assert master.is_pid_healthy(1) is False


@patch("salt.utils.master.HAS_PSUTIL", False)
class MasterUtilsIsPidHealthy(TestCase):

    def test_is_pid_healthy_unsupported_platform(self):
        with patch("salt.utils.platform.is_aix", return_value=True):
            assert master.is_pid_healthy(11) is True

        with patch("salt.utils.platform.is_windows", return_value=True):
            assert master.is_pid_healthy(1) is True

    @skipIf(salt.utils.platform.is_windows(),
            'is_pid_healthy always returns True on Windows')
    @skipIf(salt.utils.platform.is_aix(),
            'is_pid_healthy always returns True on AIX')
    def test_pid_not_running(self):
        assert master.is_pid_healthy(99999999) is False

    @skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
    def test_is_pid_healthy_running_salt(self):
        m_fopen = mock_open(read_data=b'salt')
        with patch('salt.utils.process.os_is_running', return_value=True):
            with patch('salt.utils.files.fopen', m_fopen):
                assert master.is_pid_healthy(12345) is True

    @skipIf(salt.utils.platform.is_windows(),
            'is_pid_healthy always returns True on Windows')
    @skipIf(salt.utils.platform.is_aix(),
            'is_pid_healthy always returns True on AIX')
    def test_is_pid_healthy_not_running_salt(self):
        m_fopen = mock_open(read_data=b'tacos')
        with patch('salt.utils.process.os_is_running', return_value=True):
            with patch('salt.utils.files.fopen', m_fopen):
                assert master.is_pid_healthy(12345) is False

    def tets_is_pid_healthy_raises(self):
        m_fopen = mock_open(side_effect=IOError)
        with patch('salt.utils.files.fopen', m_fopen):
            assert master.is_pid_healthy(12345) is False

        m_fopen = mock_open(side_effect=OSError)
        with patch('salt.utils.files.fopen', m_fopen):
            assert master.is_pid_healthy(12345) is False
