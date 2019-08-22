# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.logrotate as logrotate
import salt.utils.platform

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    Mock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(salt.utils.platform.is_windows(), 'Only works on POSIX-like systems')
class LogrotateTestMakeFile(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.logrotate
    '''
    def setup_loader_modules(self):
        return {logrotate: {}}

    def test_make_file(self):
        with patch.dict(logrotate.__opts__, {'test': True}, clear=True):
            with patch.object(logrotate.os.path, 'isfile', return_value=False) as isfile:
                with patch.object(logrotate.salt.utils.files, 'fopen', return_value=Mock()) as fopen:
                    with patch.dict(logrotate.__salt__, {'logrotate.get': Mock(return_value=None)}, clear=True):
                        ret = logrotate.set_('logrotate-wtmp-rotate',
                                             '/var/log/wtmp',
                                             'rotate',
                                             '2',
                                             '/etc/logrotate.d/defaults',
                                             True)

                        isfile.assert_called_once_with('/etc/logrotate.d/defaults')
                        fopen.assert_called_once_with('/etc/logrotate.d/defaults', 'w')

                        self.assertEqual(ret, {'name': 'logrotate-wtmp-rotate',
                                                'changes': {'old': None, 'new': 2},
                                                'comment': 'Block \'/var/log/wtmp\' command \'rotate\' will be set to value: 2',
                                                'result': None})

    def test_file_already_made(self):
        with patch.dict(logrotate.__opts__, {'test': True}, clear=True):
            with patch.object(logrotate.os.path, 'isfile', return_value=True) as isfile:
                with patch.object(logrotate.salt.utils.files, 'fopen', return_value=Mock()) as fopen:
                    with patch.dict(logrotate.__salt__, {'logrotate.get': Mock(return_value=None)}, clear=True):
                        ret = logrotate.set_('logrotate-wtmp-rotate',
                                             '/var/log/wtmp',
                                             'rotate',
                                             '2',
                                             '/etc/logrotate.d/defaults',
                                             True)

                        self.assertEqual(isfile.call_count, 2)
                        fopen.assert_not_called()

                        self.assertEqual(ret, {'name': 'logrotate-wtmp-rotate',
                                                'changes': {'old': None, 'new': 2},
                                                'comment': 'Block \'/var/log/wtmp\' command \'rotate\' will be set to value: 2',
                                                'result': None})

    def test_do_not_make_file(self):
        with patch.dict(logrotate.__opts__, {'test': True}, clear=True):
            with patch.object(logrotate.os.path, 'isfile', return_value=True) as isfile:
                with patch.object(logrotate.salt.utils.files, 'fopen', return_value=Mock()) as fopen:
                    with patch.dict(logrotate.__salt__, {'logrotate.get': Mock(return_value=None)}, clear=True):
                        ret = logrotate.set_('logrotate-wtmp-rotate',
                                             '/var/log/wtmp',
                                             'rotate',
                                             '2',
                                             '/etc/logrotate.d/defaults',
                                             False)

                        self.assertEqual(isfile.call_count, 1)
                        fopen.assert_not_called()

                        self.assertEqual(ret, {'name': 'logrotate-wtmp-rotate',
                                                'changes': {'old': None, 'new': 2},
                                                'comment': 'Block \'/var/log/wtmp\' command \'rotate\' will be set to value: 2',
                                                'result': None})

    def test_do_not_make_file_2(self):
        with patch.dict(logrotate.__opts__, {'test': True}, clear=True):
            with patch.object(logrotate.os.path, 'isfile', return_value=False) as isfile:
                with patch.object(logrotate.salt.utils.files, 'fopen', return_value=Mock()) as fopen:
                    with patch.dict(logrotate.__salt__, {'logrotate.get': Mock(return_value=None)}, clear=True):
                        ret = logrotate.set_('logrotate-wtmp-rotate',
                                             '/var/log/wtmp',
                                             'rotate',
                                             '2',
                                             '/etc/logrotate.d/defaults',
                                             False)

                        self.assertEqual(isfile.call_count, 1)
                        fopen.assert_not_called()

                        self.assertEqual(ret, {'name': 'logrotate-wtmp-rotate',
                                                'changes': {},
                                                'comment': '/etc/logrotate.d/defaults can not be found!',
                                                'result': None})

    def test_do_not_make_file_3(self):
        with patch.dict(logrotate.__opts__, {'test': False}, clear=True):
            with patch.object(logrotate.os.path, 'isfile', return_value=False) as isfile:
                with patch.object(logrotate.salt.utils.files, 'fopen', return_value=Mock()) as fopen:
                    with patch.dict(logrotate.__salt__, {'logrotate.get': Mock(return_value=None)}, clear=True):
                        ret = logrotate.set_('logrotate-wtmp-rotate',
                                             '/var/log/wtmp',
                                             'rotate',
                                             '2',
                                             '/etc/logrotate.d/defaults',
                                             False)

                        self.assertEqual(isfile.call_count, 1)
                        fopen.assert_not_called()

                        self.assertEqual(ret, {'name': 'logrotate-wtmp-rotate',
                                                'changes': {},
                                                'comment': '/etc/logrotate.d/defaults can not be found!',
                                                'result': False})
