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
    def test_systemctl_reload(self):
        '''
            Test to Reloads systemctl
        '''
        mock = MagicMock(side_effect=[1, 0])
        with patch.dict(systemd.__salt__, {'cmd.retcode': mock}):
            self.assertFalse(systemd.systemctl_reload())

            self.assertTrue(systemd.systemctl_reload())

    def test_get_enabled(self):
        '''
            Test to return a list of all enabled services
        '''
        def sysv(name):
            if name in ['d', 'e']:
                return True
            return False

        def sysve(name):
            if name in ['e']:
                return True
            return False

        mock = MagicMock(return_value={"a": "enabled", "b": "enabled",
                                       "c": "disabled"})
        lmock = MagicMock(return_value={"d": "disabled",
                                        "a": "disabled",
                                        "b": "disabled",
                                        "e": "disabled"})
        with patch.object(systemd, "_sysv_is_disabled", sysve):
            with patch.object(systemd, "_service_is_sysv", sysv):
                with patch.object(systemd, '_get_all_unit_files', mock):
                    with patch.object(systemd, '_get_all_units', lmock):
                        self.assertListEqual(
                            systemd.get_enabled(), ["a", "b", "d"])

    def test_get_disabled(self):
        '''
            Test to return a list of all disabled services
        '''
        mock = MagicMock(return_value={"a": "enabled", "b": "enabled",
                                       "c": "disabled"})
        with patch.object(systemd, '_get_all_unit_files', mock):
            mock = MagicMock(return_value={})
            with patch.object(systemd, '_get_all_legacy_init_scripts', mock):
                self.assertListEqual(systemd.get_disabled(), ["c"])

    def test_get_all(self):
        '''
            Test to return a list of all available services
        '''
        mock = MagicMock(return_value={"a": "enabled", "b": "enabled",
                                       "c": "disabled"})
        with patch.object(systemd, '_get_all_units', mock):
            mock = MagicMock(return_value={"a1": "enabled", "b1": "disabled",
                                           "c1": "enabled"})
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
        mock = MagicMock(side_effect=["a", "@", "c"])
        with patch.object(systemd, '_canonical_template_unit_name', mock):
            mock = MagicMock(side_effect=[{"a": "z", "b": "z"},
                                          {"@": "z", "b": "z"},
                                          {"a": "z", "b": "z"}])
            with patch.object(systemd, 'get_all', mock):
                self.assertTrue(systemd.available("sshd"))

                self.assertTrue(systemd.available("sshd"))

                self.assertFalse(systemd.available("sshd"))

    def test_missing(self):
        '''
            Test to the inverse of service.available.
        '''
        mock = MagicMock(return_value=True)
        with patch.object(systemd, 'available', mock):
            self.assertFalse(systemd.missing("sshd"))

    def test_unmask(self):
        '''
            Test to unmask the specified service with systemd
        '''
        mock = MagicMock(return_value=False)
        with patch.object(systemd, '_untracked_custom_unit_found', mock):
            with patch.object(systemd, '_unit_file_changed', mock):
                with patch.dict(systemd.__salt__, {'cmd.retcode': mock}):
                    self.assertTrue(systemd.unmask("sshd"))

    def test_start(self):
        '''
            Test to start the specified service with systemd
        '''
        mock = MagicMock(return_value=False)
        with patch.object(systemd, '_untracked_custom_unit_found', mock):
            with patch.object(systemd, '_unit_file_changed', mock):
                with patch.dict(systemd.__salt__, {'cmd.retcode': mock}):
                    self.assertTrue(systemd.start("sshd"))

    def test_stop(self):
        '''
            Test to stop the specified service with systemd
        '''
        mock = MagicMock(return_value=False)
        with patch.object(systemd, '_untracked_custom_unit_found', mock):
            with patch.object(systemd, '_unit_file_changed', mock):
                with patch.dict(systemd.__salt__, {'cmd.retcode': mock}):
                    self.assertTrue(systemd.stop("sshd"))

    def test_restart(self):
        '''
            Test to restart the specified service with systemd
        '''
        mock = MagicMock(return_value=False)
        with patch.object(systemd, '_untracked_custom_unit_found', mock):
            with patch.object(systemd, '_unit_file_changed', mock):
                with patch.dict(systemd.__salt__, {'cmd.retcode': mock}):
                    self.assertTrue(systemd.restart("sshd"))

    def test_reload_(self):
        '''
            Test to Reload the specified service with systemd
        '''
        mock = MagicMock(return_value=False)
        with patch.object(systemd, '_untracked_custom_unit_found', mock):
            with patch.object(systemd, '_unit_file_changed', mock):
                with patch.dict(systemd.__salt__, {'cmd.retcode': mock}):
                    self.assertTrue(systemd.reload_("sshd"))

    def test_force_reload(self):
        '''
            Test to force-reload the specified service with systemd
        '''
        mock = MagicMock(return_value=False)
        with patch.object(systemd, '_untracked_custom_unit_found', mock):
            with patch.object(systemd, '_unit_file_changed', mock):
                with patch.dict(systemd.__salt__, {'cmd.retcode': mock}):
                    self.assertTrue(systemd.force_reload("sshd"))

    def test_status(self):
        '''
            Test to return the status for a service via systemd
        '''
        mock = MagicMock(return_value=False)
        with patch.object(systemd, '_untracked_custom_unit_found', mock):
            with patch.object(systemd, '_unit_file_changed', mock):
                with patch.dict(systemd.__salt__, {'cmd.retcode': mock}):
                    self.assertTrue(systemd.status("sshd"))

    def test_enable(self):
        '''
            Test to enable the named service to start when the system boots
        '''
        exe = MagicMock(return_value='foo')
        tmock = MagicMock(return_value=True)
        mock = MagicMock(return_value=False)
        with patch.object(systemd, '_untracked_custom_unit_found', mock):
            with patch.object(systemd, '_unit_file_changed', mock):
                with patch.dict(systemd.__salt__, {'cmd.retcode': mock}):
                    with patch.object(systemd, "_service_is_sysv", mock):
                        self.assertTrue(systemd.enable("sshd"))
                    with patch.object(systemd, "_get_service_exec", exe):
                        with patch.object(systemd, "_service_is_sysv", tmock):
                            self.assertTrue(systemd.enable("sshd"))

    def test_disable(self):
        '''
            Test to disable the named service to not
            start when the system boots
        '''
        exe = MagicMock(return_value='foo')
        tmock = MagicMock(return_value=True)
        mock = MagicMock(return_value=False)
        with patch.object(systemd, '_untracked_custom_unit_found', mock):
            with patch.object(systemd, '_unit_file_changed', mock):
                with patch.dict(systemd.__salt__, {'cmd.retcode': mock}):
                    with patch.object(systemd, "_service_is_sysv", mock):
                        self.assertTrue(systemd.disable("sshd"))
                    with patch.object(systemd, "_get_service_exec", exe):
                        with patch.object(systemd, "_service_is_sysv", tmock):
                            self.assertTrue(systemd.disable("sshd"))

    def test_enabled(self):
        '''
            Test to return if the named service is enabled to start on boot
        '''
        mock = MagicMock(return_value=True)
        with patch.object(systemd, '_enabled', mock):
            self.assertTrue(systemd.enabled("sshd"))

    def test_disabled(self):
        '''
            Test to Return if the named service is disabled to start on boot
        '''
        mock = MagicMock(return_value=True)
        with patch.object(systemd, '_enabled', mock):
            self.assertFalse(systemd.disabled("sshd"))

    def test_show(self):
        '''
            Test to show properties of one or more units/jobs or the manager
        '''
        mock = MagicMock(return_value="a = b , c = d")
        with patch.dict(systemd.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(systemd.show("sshd"), {'a ': ' b , c = d'})

    def test_execs(self):
        '''
            Test to return a list of all files specified as ``ExecStart``
            for all services
        '''
        mock = MagicMock(return_value=["a", "b"])
        with patch.object(systemd, 'get_all', mock):
            mock = MagicMock(return_value={"ExecStart": {"path": "c"}})
            with patch.object(systemd, 'show', mock):
                self.assertDictEqual(systemd.execs(), {'a': 'c', 'b': 'c'})

if __name__ == '__main__':
    from integration import run_tests
    run_tests(SystemdTestCase, needs_daemon=False)
