# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import textwrap

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import rh_service

# Globals
rh_service.__salt__ = {}

RET = ['hostname', 'mountall', 'network-interface', 'network-manager',
       'salt-api', 'salt-master', 'salt-minion']

HAS_UPSTART = None


def _m_disable():
    '''
    Mock _upstart_disable method.
    '''
    if HAS_UPSTART:
        return MagicMock(return_value=True)
    else:
        return MagicMock(return_value=False)


def _m_enable():
    '''
    Mock _upstart_enable method.
    '''
    if HAS_UPSTART:
        return MagicMock(return_value=True)
    else:
        return MagicMock(return_value=False)


def _m_isenabled():
    '''
    Mock _upstart_is_enabled method.
    '''
    if HAS_UPSTART:
        return MagicMock(return_value=True)
    else:
        return MagicMock(return_value=False)

rh_service._upstart_disable = _m_disable()
rh_service._upstart_enable = _m_enable()
rh_service._upstart_is_enabled = _m_isenabled()


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RhServiceTestCase(TestCase):
    '''
    Test cases for salt.modules.rh_service
    '''
    @staticmethod
    def _m_lst():
        '''
        Return value for [].
        '''
        return MagicMock(return_value=[])

    @staticmethod
    def _m_ret():
        '''
        Return value for RET.
        '''
        return MagicMock(return_value=RET)

    @staticmethod
    def _m_bool(bol=True):
        '''
        Return Bool value.
        '''
        return MagicMock(return_value=bol)

    def test__chkconfig_is_enabled(self):
        '''
        test _chkconfig_is_enabled function
        '''
        name = 'atd'
        chkconfig_out = textwrap.dedent('''\

            {0}           0:off   1:off   2:off   3:on    4:on    5:on    6:off
            '''.format(name))
        xinetd_out = textwrap.dedent('''\
            xinetd based services:
                    {0}  on
            '''.format(name))

        with patch.object(rh_service, '_runlevel', MagicMock(return_value=3)):
            mock_run = MagicMock(return_value={'retcode': 0,
                                               'stdout': chkconfig_out})
            with patch.dict(rh_service.__salt__, {'cmd.run_all': mock_run}):
                self.assertTrue(rh_service._chkconfig_is_enabled(name))
                self.assertFalse(rh_service._chkconfig_is_enabled(name, 2))
                self.assertTrue(rh_service._chkconfig_is_enabled(name, 3))

            mock_run = MagicMock(return_value={'retcode': 0,
                                               'stdout': xinetd_out})
            with patch.dict(rh_service.__salt__, {'cmd.run_all': mock_run}):
                self.assertTrue(rh_service._chkconfig_is_enabled(name))
                self.assertTrue(rh_service._chkconfig_is_enabled(name, 2))
                self.assertTrue(rh_service._chkconfig_is_enabled(name, 3))

    # 'get_enabled' function tests: 1

    def test_get_enabled(self):
        '''
        Test if it return the enabled services. Use the ``limit``
        param to restrict results to services of that type.
        '''
        with patch.object(rh_service, '_upstart_services', self._m_ret()):
            global HAS_UPSTART
            HAS_UPSTART = True
            self.assertListEqual(rh_service.get_enabled('upstart'), [])

        mock_run = MagicMock(return_value='salt stack')
        with patch.dict(rh_service.__salt__, {'cmd.run': mock_run}):
            with patch.object(rh_service, '_sysv_services', self._m_ret()):
                with patch.object(rh_service, '_sysv_is_enabled',
                                  self._m_bool()):
                    self.assertListEqual(rh_service.get_enabled('sysvinit'),
                                         RET)

                    with patch.object(rh_service, '_upstart_services',
                                      self._m_lst()):
                        HAS_UPSTART = True
                        self.assertListEqual(rh_service.get_enabled(), RET)

    # 'get_disabled' function tests: 1

    def test_get_disabled(self):
        '''
        Test if it return the disabled services. Use the ``limit``
        param to restrict results to services of that type.
        '''
        with patch.object(rh_service, '_upstart_services', self._m_ret()):
            global HAS_UPSTART
            HAS_UPSTART = False
            self.assertListEqual(rh_service.get_disabled('upstart'), RET)

        mock_run = MagicMock(return_value='salt stack')
        with patch.dict(rh_service.__salt__, {'cmd.run': mock_run}):
            with patch.object(rh_service, '_sysv_services', self._m_ret()):
                with patch.object(rh_service, '_sysv_is_enabled',
                                  self._m_bool(False)):
                    self.assertListEqual(rh_service.get_disabled('sysvinit'),
                                         RET)

                    with patch.object(rh_service, '_upstart_services',
                                      self._m_lst()):
                        HAS_UPSTART = False
                        self.assertListEqual(rh_service.get_disabled(), RET)

    # 'get_all' function tests: 1

    def test_get_all(self):
        '''
        Test if it return all installed services. Use the ``limit``
        param to restrict results to services of that type.
        '''
        with patch.object(rh_service, '_upstart_services', self._m_ret()):
            self.assertListEqual(rh_service.get_all('upstart'), RET)

        with patch.object(rh_service, '_sysv_services', self._m_ret()):
            self.assertListEqual(rh_service.get_all('sysvinit'), RET)

            with patch.object(rh_service, '_upstart_services', self._m_lst()):
                self.assertListEqual(rh_service.get_all(), RET)

    # 'available' function tests: 1

    def test_available(self):
        '''
        Test if it return True if the named service is available.
        '''
        with patch.object(rh_service, '_service_is_upstart', self._m_bool()):
            self.assertTrue(rh_service.available('salt-api', 'upstart'))

        with patch.object(rh_service, '_service_is_sysv', self._m_bool()):
            self.assertTrue(rh_service.available('salt-api', 'sysvinit'))

            with patch.object(rh_service, '_service_is_upstart',
                              self._m_bool()):
                self.assertTrue(rh_service.available('salt-api'))

    # 'missing' function tests: 1

    def test_missing(self):
        '''
        Test if it return True if the named service is not available.
        '''
        with patch.object(rh_service, '_service_is_upstart',
                          self._m_bool(False)):
            self.assertTrue(rh_service.missing('sshd', 'upstart'))

            with patch.object(rh_service, '_service_is_sysv',
                              self._m_bool(False)):
                self.assertTrue(rh_service.missing('sshd'))

        with patch.object(rh_service, '_service_is_sysv', self._m_bool()):
            self.assertFalse(rh_service.missing('sshd', 'sysvinit'))

            with patch.object(rh_service, '_service_is_upstart',
                              self._m_bool()):
                self.assertFalse(rh_service.missing('sshd'))

    # 'start' function tests: 1

    def test_start(self):
        '''
        Test if it start the specified service.
        '''
        with patch.object(rh_service, '_service_is_upstart', self._m_bool()):
            with patch.dict(rh_service.__salt__, {'cmd.retcode':
                                                  self._m_bool(False)}):
                self.assertTrue(rh_service.start('salt-api'))

    # 'stop' function tests: 1

    def test_stop(self):
        '''
        Test if it stop the specified service.
        '''
        with patch.object(rh_service, '_service_is_upstart', self._m_bool()):
            with patch.dict(rh_service.__salt__, {'cmd.retcode':
                                                  self._m_bool(False)}):
                self.assertTrue(rh_service.stop('salt-api'))

    # 'restart' function tests: 1

    def test_restart(self):
        '''
        Test if it restart the specified service.
        '''
        with patch.object(rh_service, '_service_is_upstart', self._m_bool()):
            with patch.dict(rh_service.__salt__, {'cmd.retcode':
                                                  self._m_bool(False)}):
                self.assertTrue(rh_service.restart('salt-api'))

    # 'reload_' function tests: 1

    def test_reload(self):
        '''
        Test if it reload the specified service.
        '''
        with patch.object(rh_service, '_service_is_upstart', self._m_bool()):
            with patch.dict(rh_service.__salt__, {'cmd.retcode':
                                                  self._m_bool(False)}):
                self.assertTrue(rh_service.reload_('salt-api'))

    # 'status' function tests: 1

    def test_status(self):
        '''
        Test if it return the status for a service,
        returns a bool whether the service is running.
        '''
        with patch.object(rh_service, '_service_is_upstart', self._m_bool()):
            mock_run = MagicMock(return_value='start/running')
            with patch.dict(rh_service.__salt__, {'cmd.run': mock_run}):
                self.assertTrue(rh_service.status('salt-api'))

        with patch.object(rh_service, '_service_is_upstart',
                          self._m_bool(False)):
            with patch.dict(rh_service.__salt__, {'status.pid':
                                                  self._m_bool()}):
                self.assertTrue(rh_service.status('salt-api', sig=True))

            mock_ret = MagicMock(return_value=0)
            with patch.dict(rh_service.__salt__, {'cmd.retcode': mock_ret}):
                self.assertTrue(rh_service.status('salt-api'))

    # 'enable' function tests: 1

    def test_enable(self):
        '''
        Test if it enable the named service to start at boot.
        '''
        mock_bool = MagicMock(side_effect=[True, False])
        with patch.object(rh_service, '_service_is_upstart', mock_bool):
            global HAS_UPSTART
            HAS_UPSTART = True
            self.assertFalse(rh_service.enable('salt-api'))

            with patch.object(rh_service, '_sysv_enable', self._m_bool()):
                self.assertTrue(rh_service.enable('salt-api'))

    # 'disable' function tests: 1

    def test_disable(self):
        '''
        Test if it disable the named service to start at boot.
        '''
        mock_bool = MagicMock(side_effect=[True, False])
        with patch.object(rh_service, '_service_is_upstart', mock_bool):
            global HAS_UPSTART
            HAS_UPSTART = True
            self.assertFalse(rh_service.disable('salt-api'))

            with patch.object(rh_service, '_sysv_disable', self._m_bool()):
                self.assertTrue(rh_service.disable('salt-api'))

    # 'enabled' function tests: 1

    def test_enabled(self):
        '''
        Test if it check to see if the named service is enabled
        to start on boot.
        '''
        mock_bool = MagicMock(side_effect=[True, False])
        with patch.object(rh_service, '_service_is_upstart', mock_bool):
            global HAS_UPSTART
            HAS_UPSTART = True
            self.assertFalse(rh_service.enabled('salt-api'))

            with patch.object(rh_service, '_sysv_is_enabled', self._m_bool()):
                self.assertTrue(rh_service.enabled('salt-api'))

    # 'disabled' function tests: 1

    def test_disabled(self):
        '''
        Test if it check to see if the named service is disabled
        to start on boot.
        '''
        mock_bool = MagicMock(side_effect=[True, False])
        with patch.object(rh_service, '_service_is_upstart', mock_bool):
            global HAS_UPSTART
            HAS_UPSTART = False
            self.assertTrue(rh_service.disabled('salt-api'))

            with patch.object(rh_service, '_sysv_is_enabled',
                              self._m_bool(False)):
                self.assertTrue(rh_service.disabled('salt-api'))
