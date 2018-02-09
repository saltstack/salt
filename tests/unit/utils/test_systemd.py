# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import errno
import os

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import Mock, patch, NO_MOCK, NO_MOCK_REASON

# Import Salt libs
import salt.utils.systemd as _systemd
from salt.exceptions import SaltInvocationError


def _booted_effect(path):
    return True if path == '/run/systemd/system' else os.stat(path)


def _not_booted_effect(path):
    if path == '/run/systemd/system':
        raise OSError(errno.ENOENT, 'No such file or directory', path)
    return os.stat(path)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SystemdTestCase(TestCase):
    '''
    Tests the functions in salt.utils.systemd
    '''
    def test_booted(self):
        '''
        Test that salt.utils.systemd.booted() returns True when minion is
        systemd-booted.
        '''
        # Ensure that os.stat returns True. os.stat doesn't return a bool
        # normally, but the code is doing a simple truth check on the return
        # data, so it is sufficient enough to mock it as True for these tests.
        with patch('os.stat', side_effect=_booted_effect):
            # Test without context dict passed
            self.assertTrue(_systemd.booted())
            # Test that context key is set when context dict is passed
            context = {}
            self.assertTrue(_systemd.booted(context))
            self.assertEqual(context, {'salt.utils.systemd.booted': True})

    def test_not_booted(self):
        '''
        Test that salt.utils.systemd.booted() returns False when minion is not
        systemd-booted.
        '''
        # Ensure that os.stat raises an exception even if test is being run on
        # a systemd-booted host.
        with patch('os.stat', side_effect=_not_booted_effect):
            # Test without context dict passed
            self.assertFalse(_systemd.booted())
            # Test that context key is set when context dict is passed
            context = {}
            self.assertFalse(_systemd.booted(context))
            self.assertEqual(context, {'salt.utils.systemd.booted': False})

    def test_booted_return_from_context(self):
        '''
        Test that the context data is returned when present. To ensure we're
        getting data from the context dict, we use a non-boolean value to
        differentiate it from the True/False return this function normally
        produces.
        '''
        context = {'salt.utils.systemd.booted': 'foo'}
        self.assertEqual(_systemd.booted(context), 'foo')

    def test_booted_invalid_context(self):
        '''
        Test with invalid context data. The context value must be a dict, so
        this should raise a SaltInvocationError.
        '''
        # Test with invalid context data
        with self.assertRaises(SaltInvocationError):
            _systemd.booted(99999)

    def test_version(self):
        '''
        Test that salt.utils.systemd.booted() returns True when minion is
        systemd-booted.
        '''
        with patch('subprocess.Popen') as popen_mock:
            _version = 231
            output = 'systemd {0}\n-SYSVINIT'.format(_version)
            popen_mock.return_value = Mock(
                communicate=lambda *args, **kwargs: (output, None),
                pid=lambda: 12345,
                retcode=0
            )

            # Test without context dict passed
            self.assertEqual(_systemd.version(), _version)
            # Test that context key is set when context dict is passed
            context = {}
            self.assertTrue(_systemd.version(context))
            self.assertEqual(context, {'salt.utils.systemd.version': _version})

    def test_version_return_from_context(self):
        '''
        Test that the context data is returned when present. To ensure we're
        getting data from the context dict, we use a non-integer value to
        differentiate it from the integer return this function normally
        produces.
        '''
        context = {'salt.utils.systemd.version': 'foo'}
        self.assertEqual(_systemd.version(context), 'foo')

    def test_version_invalid_context(self):
        '''
        Test with invalid context data. The context value must be a dict, so
        this should raise a SaltInvocationError.
        '''
        # Test with invalid context data
        with self.assertRaises(SaltInvocationError):
            _systemd.version(99999)

    def test_version_parse_problem(self):
        '''
        Test with invalid context data. The context value must be a dict, so
        this should raise a SaltInvocationError.
        '''
        with patch('subprocess.Popen') as popen_mock:
            popen_mock.return_value = Mock(
                communicate=lambda *args, **kwargs: ('invalid', None),
                pid=lambda: 12345,
                retcode=0
            )
            # Test without context dict passed
            self.assertIsNone(_systemd.version())
            # Test that context key is set when context dict is passed. A failure
            # to parse the systemctl output should not set a context key, so it
            # should not be present in the context dict.
            context = {}
            self.assertIsNone(_systemd.version(context))
            self.assertEqual(context, {})

    def test_has_scope_systemd204(self):
        '''
        Scopes are available in systemd>=205. Make sure that this function
        returns the expected boolean. We do three separate unit tests for
        versions 204 through 206 because mock doesn't like us altering the
        return_value in a loop.
        '''
        with patch('subprocess.Popen') as popen_mock:
            _expected = False
            _version = 204
            _output = 'systemd {0}\n-SYSVINIT'.format(_version)
            popen_mock.return_value = Mock(
                communicate=lambda *args, **kwargs: (_output, None),
                pid=lambda: 12345,
                retcode=0
            )
            # Ensure that os.stat returns True. os.stat doesn't return a bool
            # normally, but the code is doing a simple truth check on the
            # return data, so it is sufficient enough to mock it as True for
            # these tests.
            with patch('os.stat', side_effect=_booted_effect):
                # Test without context dict passed
                self.assertEqual(_systemd.has_scope(), _expected)
                # Test that context key is set when context dict is passed
                context = {}
                self.assertEqual(_systemd.has_scope(context), _expected)
                self.assertEqual(
                    context,
                    {'salt.utils.systemd.booted': True,
                     'salt.utils.systemd.version': _version},
                )

    def test_has_scope_systemd205(self):
        '''
        Scopes are available in systemd>=205. Make sure that this function
        returns the expected boolean. We do three separate unit tests for
        versions 204 through 206 because mock doesn't like us altering the
        return_value in a loop.
        '''
        with patch('subprocess.Popen') as popen_mock:
            _expected = True
            _version = 205
            _output = 'systemd {0}\n-SYSVINIT'.format(_version)
            popen_mock.return_value = Mock(
                communicate=lambda *args, **kwargs: (_output, None),
                pid=lambda: 12345,
                retcode=0
            )
            # Ensure that os.stat returns True. os.stat doesn't return a bool
            # normally, but the code is doing a simple truth check on the
            # return data, so it is sufficient enough to mock it as True for
            # these tests.
            with patch('os.stat', side_effect=_booted_effect):
                # Test without context dict passed
                self.assertEqual(_systemd.has_scope(), _expected)
                # Test that context key is set when context dict is passed
                context = {}
                self.assertEqual(_systemd.has_scope(context), _expected)
                self.assertEqual(
                    context,
                    {'salt.utils.systemd.booted': True,
                     'salt.utils.systemd.version': _version},
                )

    def test_has_scope_systemd206(self):
        '''
        Scopes are available in systemd>=205. Make sure that this function
        returns the expected boolean. We do three separate unit tests for
        versions 204 through 206 because mock doesn't like us altering the
        return_value in a loop.
        '''
        with patch('subprocess.Popen') as popen_mock:
            _expected = True
            _version = 206
            _output = 'systemd {0}\n-SYSVINIT'.format(_version)
            popen_mock.return_value = Mock(
                communicate=lambda *args, **kwargs: (_output, None),
                pid=lambda: 12345,
                retcode=0
            )
            # Ensure that os.stat returns True. os.stat doesn't return a bool
            # normally, but the code is doing a simple truth check on the
            # return data, so it is sufficient enough to mock it as True for
            # these tests.
            with patch('os.stat', side_effect=_booted_effect):
                # Test without context dict passed
                self.assertEqual(_systemd.has_scope(), _expected)
                # Test that context key is set when context dict is passed
                context = {}
                self.assertEqual(_systemd.has_scope(context), _expected)
                self.assertEqual(
                    context,
                    {'salt.utils.systemd.booted': True,
                     'salt.utils.systemd.version': _version},
                )

    def test_has_scope_no_systemd(self):
        '''
        Test the case where the system is not systemd-booted. We should not be
        performing a version check in these cases as there is no need.
        '''
        with patch('os.stat', side_effect=_not_booted_effect):
            # Test without context dict passed
            self.assertFalse(_systemd.has_scope())
            # Test that context key is set when context dict is passed.
            # Because we are not systemd-booted, there should be no key in the
            # context dict for the version check, as we shouldn't have
            # performed this check.
            context = {}
            self.assertFalse(_systemd.has_scope(context))
            self.assertEqual(context, {'salt.utils.systemd.booted': False})

    def test_has_scope_version_parse_problem(self):
        '''
        Test the case where the system is systemd-booted, but we failed to
        parse the "systemctl --version" output.
        '''
        with patch('subprocess.Popen') as popen_mock:
            popen_mock.return_value = Mock(
                communicate=lambda *args, **kwargs: ('invalid', None),
                pid=lambda: 12345,
                retcode=0
            )
            with patch('os.stat', side_effect=_booted_effect):
                # Test without context dict passed
                self.assertFalse(_systemd.has_scope())
                # Test that context key is set when context dict is passed. A
                # failure to parse the systemctl output should not set a context
                # key, so it should not be present in the context dict.
                context = {}
                self.assertFalse(_systemd.has_scope(context))
                self.assertEqual(context, {'salt.utils.systemd.booted': True})

    def test_has_scope_invalid_context(self):
        '''
        Test with invalid context data. The context value must be a dict, so
        this should raise a SaltInvocationError.
        '''
        # Test with invalid context data
        with self.assertRaises(SaltInvocationError):
            _systemd.has_scope(99999)
