# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

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
import salt.modules.debian_service as debian_service


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DebianServicesTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.debian_service
    '''
    def setup_loader_modules(self):
        return {debian_service: {}}

    def test_get_enabled(self):
        '''
        Test for Return a list of service that are enabled on boot
        '''
        mock_runlevel = MagicMock(return_value=1)
        mock_prefix = '/etc/rc1.d/S'
        mock_glob = MagicMock(return_value=[mock_prefix + '01name'])

        with patch.object(debian_service, '_get_runlevel', mock_runlevel):
            with patch.object(debian_service.glob, 'glob', mock_glob):
                self.assertEqual(debian_service.get_enabled()[0], 'name')

    def test_get_disabled(self):
        '''
        Test for Return a set of services that are installed but disabled
        '''
        mock = MagicMock(return_value=['A'])
        with patch.object(debian_service, 'get_all', mock):
            mock = MagicMock(return_value=['B'])
            with patch.object(debian_service, 'get_enabled', mock):
                self.assertEqual(debian_service.get_disabled(), ['A'])

    def test_available(self):
        '''
        Test for Returns ``True`` if the specified service is
        available, otherwise returns
        ``False``.
        '''
        mock = MagicMock(return_value=['A'])
        with patch.object(debian_service, 'get_all', mock):
            self.assertFalse(debian_service.available('name'))

    def test_missing(self):
        '''
        Test for The inverse of service.available.
        '''
        mock = MagicMock(return_value=['A'])
        with patch.object(debian_service, 'get_all', mock):
            self.assertTrue(debian_service.missing('name'))

    def test_getall(self):
        '''
        Test for Return all available boot services
        '''
        mock = MagicMock(return_value=('A'))
        with patch.object(debian_service, 'get_enabled', mock):
            self.assertEqual(debian_service.get_all()[0], 'A')

    def test_start(self):
        '''
        Test for Start the specified service
        '''
        mock = MagicMock(return_value=True)
        with patch.object(debian_service, '_service_cmd', mock):
            with patch.dict(debian_service.__salt__, {'cmd.retcode': mock}):
                self.assertFalse(debian_service.start('name'))

    def test_stop(self):
        '''
        Test for Stop the specified service
        '''
        mock = MagicMock(return_value=True)
        with patch.object(debian_service, '_service_cmd', mock):
            with patch.dict(debian_service.__salt__, {'cmd.retcode': mock}):
                self.assertFalse(debian_service.stop('name'))

    def test_restart(self):
        '''
        Test for Restart the named service
        '''
        mock = MagicMock(return_value=True)
        with patch.object(debian_service, '_service_cmd', mock):
            with patch.dict(debian_service.__salt__, {'cmd.retcode': mock}):
                self.assertFalse(debian_service.restart('name'))

    def test_reload_(self):
        '''
        Test for Reload the named service
        '''
        mock = MagicMock(return_value=True)
        with patch.object(debian_service, '_service_cmd', mock):
            with patch.dict(debian_service.__salt__, {'cmd.retcode': mock}):
                self.assertFalse(debian_service.reload_('name'))

    def test_force_reload(self):
        '''
        Test for Force-reload the named service
        '''
        mock = MagicMock(return_value=True)
        with patch.object(debian_service, '_service_cmd', mock):
            with patch.dict(debian_service.__salt__, {'cmd.retcode': mock}):
                self.assertFalse(debian_service.force_reload('name'))

    def test_status(self):
        '''
        Test for Return the status for a service
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(debian_service.__salt__, {'status.pid': mock}):
            self.assertTrue(debian_service.status('name', 1))

        mock = MagicMock(return_value='A')
        with patch.object(debian_service, '_service_cmd', mock):
            mock = MagicMock(return_value=True)
            with patch.dict(debian_service.__salt__, {'cmd.retcode': mock}):
                self.assertFalse(debian_service.status('name'))

    def test_enable(self):
        '''
        Test for Enable the named service to start at boot
        '''
        mock = MagicMock(return_value='5')
        with patch.object(debian_service, '_osrel', mock):
            mock = MagicMock(return_value='')
            with patch.object(debian_service, '_cmd_quote', mock):
                mock = MagicMock(return_value=True)
                with patch.dict(debian_service.__salt__,
                                {'cmd.retcode': mock}):
                    self.assertFalse(debian_service.enable('name'))

    def test_disable(self):
        '''
        Test for Disable the named service to start at boot
        '''
        mock = MagicMock(return_value='5')
        with patch.object(debian_service, '_osrel', mock):
            mock = MagicMock(return_value=True)
            with patch.dict(debian_service.__salt__, {'cmd.retcode': mock}):
                self.assertFalse(debian_service.disable('name'))

    def test_enabled(self):
        '''
        Test for Return True if the named service is enabled, false otherwise
        '''
        mock = MagicMock(return_value=['A'])
        with patch.object(debian_service, 'get_enabled', mock):
            self.assertFalse(debian_service.enabled('name'))

    def test_disabled(self):
        '''
        Test for Return True if the named service is enabled, false otherwise
        '''
        mock = MagicMock(return_value=['A'])
        with patch.object(debian_service, 'get_enabled', mock):
            self.assertFalse(debian_service.disabled('name'))
