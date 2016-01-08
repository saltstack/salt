# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import systemd

# Globals
systemd.__salt__ = {}
systemd.__context__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SystemdTestCase(TestCase):
    '''
    Test case for salt.modules.systemd
    '''
    def test_get_enabled(self):
        '''
        Test to return a list of all enabled services
        '''
        _service_is_sysv = lambda x: True if x in ('d', 'e') else False
        _sysv_is_enabled = lambda x: False if x in ('e',) else True

        unit_files = MagicMock(return_value={'a': 'enabled',
                                             'b': 'enabled',
                                             'c': 'disabled'})
        all_units = MagicMock(return_value={'a': 'disabled',
                                            'b': 'disabled',
                                            'd': 'disabled',
                                            'e': 'disabled'})
        with patch.object(systemd, '_sysv_is_enabled', _sysv_is_enabled):
            with patch.object(systemd, '_service_is_sysv', _service_is_sysv):
                with patch.object(systemd, '_get_all_unit_files', unit_files):
                    with patch.object(systemd, '_get_all_units', all_units):
                        self.assertListEqual(
                            systemd.get_enabled(), ['a', 'b', 'd'])

    def test_get_disabled(self):
        '''
        Test to return a list of all disabled services
        '''
        mock = MagicMock(return_value={'a': 'enabled', 'b': 'enabled',
                                       'c': 'disabled'})
        with patch.object(systemd, '_get_all_unit_files', mock):
            mock = MagicMock(return_value={})
            with patch.object(systemd, '_get_all_legacy_init_scripts', mock):
                self.assertListEqual(systemd.get_disabled(), ['c'])

    def test_get_all(self):
        '''
        Test to return a list of all available services
        '''
        mock = MagicMock(return_value={'a': 'enabled', 'b': 'enabled',
                                       'c': 'disabled'})
        with patch.object(systemd, '_get_all_units', mock):
            mock = MagicMock(return_value={'a1': 'enabled', 'b1': 'disabled',
                                           'c1': 'enabled'})
            with patch.object(systemd, '_get_all_unit_files', mock):
                mock = MagicMock(return_value={})
                with patch.object(systemd,
                                  '_get_all_legacy_init_scripts', mock):
                    self.assertListEqual(systemd.get_all(),
                                         ['a', 'a1', 'b', 'b1', 'c', 'c1'])

    def test_available(self):
        '''
        Test to check that the given service is available
        '''
        available = (
            'sshd.service - OpenSSH server daemon\n'
            '   Loaded: loaded (/usr/lib/systemd/system/sshd.service; enabled)\n'
            '   Active: inactive (dead) since Thu 2015-12-17 15:33:06 CST; 19h ago\n'
            ' Main PID: 230 (code=exited, status=0/SUCCESS)\n'
        )
        not_available = (
            'asdf.service\n'
            '   Loaded: not-found (Reason: No such file or directory)\n'
            '   Active: inactive (dead)\n'
        )
        mock_stdout = MagicMock(return_value=available)
        with patch.dict(systemd.__salt__, {'cmd.run': mock_stdout}):
            self.assertTrue(systemd.available('sshd'))

        mock_stdout = MagicMock(return_value=not_available)
        with patch.dict(systemd.__salt__, {'cmd.run': mock_stdout}):
            self.assertFalse(systemd.available('asdf'))

    def test_show(self):
        '''
        Test to show properties of one or more units/jobs or the manager
        '''
        show_output = 'a=b\nc=d\ne={ f=g ; h=i }\nWants=foo.service bar.service\n'
        mock = MagicMock(return_value=show_output)
        with patch.dict(systemd.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(
                systemd.show('sshd'),
                {'a': 'b',
                 'c': 'd',
                 'e': {'f': 'g', 'h': 'i'},
                 'Wants': ['foo.service', 'bar.service']}
            )

    def test_execs(self):
        '''
        Test to return a list of all files specified as ``ExecStart`` for all
        services
        '''
        mock = MagicMock(return_value=['a', 'b'])
        with patch.object(systemd, 'get_all', mock):
            mock = MagicMock(return_value={'ExecStart': {'path': 'c'}})
            with patch.object(systemd, 'show', mock):
                self.assertDictEqual(systemd.execs(), {'a': 'c', 'b': 'c'})

if __name__ == '__main__':
    from integration import run_tests
    run_tests(SystemdTestCase, needs_daemon=False)
