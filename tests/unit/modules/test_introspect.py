# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

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
import salt.modules.introspect as introspect


@skipIf(NO_MOCK, NO_MOCK_REASON)
class IntrospectTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.introspect
    '''
    def setup_loader_modules(self):
        return {introspect: {}}

    # 'running_service_owners' function tests: 1

    def test_running_service_owners(self):
        '''
        Test if it determine which packages own the currently running services.
        '''
        err1 = ('The module for the package manager on this system does not'
                ' support looking up which package(s) owns which file(s)')
        err2 = ('The file module on this system does not '
                'support looking up open files on the system')
        ret = {'Error': {'Unsupported File Module': '{0}'.format(err2),
                         'Unsupported Package Manager': '{0}'.format(err1)}}
        self.assertDictEqual(introspect.running_service_owners(), ret)

        mock = MagicMock(return_value={})
        with patch.dict(introspect.__salt__, {'pkg.owner': mock,
                        'file.open_files': mock, 'service.execs': mock}):
            self.assertDictEqual(introspect.running_service_owners(), {})

    # 'enabled_service_owners' function tests: 1

    def test_enabled_service_owners(self):
        '''
        Test if it return which packages own each of the services
        that are currently enabled.
        '''
        err1 = ('The module for the package manager on this system does not'
                ' support looking up which package(s) owns which file(s)')
        err2 = ('The module for the service manager on this system does not'
                ' support showing descriptive service data')
        ret = {'Error': {'Unsupported Service Manager': '{0}'.format(err2),
                         'Unsupported Package Manager': '{0}'.format(err1)}}
        self.assertDictEqual(introspect.enabled_service_owners(), ret)

        mock = MagicMock(return_value={})
        with patch.dict(introspect.__salt__, {'pkg.owner': mock,
                        'service.show': mock, 'service.get_enabled': mock}):
            self.assertDictEqual(introspect.enabled_service_owners(), {})

    # 'service_highstate' function tests: 1

    @patch('salt.modules.introspect.running_service_owners',
           MagicMock(return_value={}))
    @patch('salt.modules.introspect.enabled_service_owners',
           MagicMock(return_value={}))
    def test_service_highstate(self):
        '''
        Test if it return running and enabled services in a highstate structure.
        '''
        self.assertDictEqual(introspect.service_highstate(), {})
