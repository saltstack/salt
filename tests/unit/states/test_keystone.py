# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
import salt.states.keystone as keystone


@skipIf(NO_MOCK, NO_MOCK_REASON)
class KeystoneTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.keystone
    '''
    def setup_loader_modules(self):
        return {keystone: {}}

    # 'user_present' function tests: 1

    def test_user_present(self):
        '''
        Test to ensure that the keystone user is present
        with the specified properties.
        '''
        name = 'nova'
        password = '$up3rn0v4'
        email = 'nova@domain.com'
        tenant = 'demo'

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}

        mock_f = MagicMock(return_value=False)
        mock_lst = MagicMock(return_value=['Error'])
        with patch.dict(keystone.__salt__, {'keystone.tenant_get': mock_lst}):
            comt = ('Tenant / project "{0}" does not exist'.format(tenant))
            ret.update({'comment': comt})
            self.assertDictEqual(keystone.user_present(name, password, email,
                                                       tenant), ret)

        mock_dict = MagicMock(side_effect=[{name: {'email': 'a@a.com'}},
                                           {name: {'email': email,
                                                   'enabled': False}},
                                           {name: {'email': email,
                                                   'enabled': True}},
                                           {name: {'email': email,
                                                   'enabled': True}},
                                           {'Error': 'error'},
                                           {'Error': 'error'}])
        mock_l = MagicMock(return_value={tenant: {'id': 'abc'}})
        with patch.dict(keystone.__salt__,
                        {'keystone.user_get': mock_dict,
                         'keystone.tenant_get': mock_l,
                         'keystone.user_verify_password': mock_f,
                         'keystone.user_create': mock_f}):
            with patch.dict(keystone.__opts__, {'test': True}):
                comt = ('User "{0}" will be updated'.format(name))
                ret.update({'comment': comt, 'result': None,
                            'changes': {'Email': 'Will be updated',
                                        'Enabled': 'Will be True',
                                        'Password': 'Will be updated'}})
                self.assertDictEqual(keystone.user_present(name, password,
                                                           email), ret)

                ret.update({'comment': comt, 'result': None,
                            'changes': {'Enabled': 'Will be True',
                                        'Password': 'Will be updated'}})
                self.assertDictEqual(keystone.user_present(name, password,
                                                           email), ret)

                ret.update({'comment': comt, 'result': None,
                            'changes': {'Tenant': 'Will be added to "demo" tenant',
                                        'Password': 'Will be updated'}})
                self.assertDictEqual(keystone.user_present(name, password,
                                                           email, tenant), ret)

                ret.update({'comment': comt, 'result': None,
                            'changes': {'Password': 'Will be updated'}})
                self.assertDictEqual(keystone.user_present(name, password,
                                                           email), ret)

                comt = ('Keystone user "nova" will be added')
                ret.update({'comment': comt, 'result': None,
                            'changes': {'User': 'Will be created'}})
                self.assertDictEqual(keystone.user_present(name, password,
                                                           email), ret)

            with patch.dict(keystone.__opts__, {'test': False}):
                comt = ('Keystone user {0} has been added'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {'User': 'Created'}})
                self.assertDictEqual(keystone.user_present(name, password,
                                                           email), ret)

    # 'user_absent' function tests: 1

    def test_user_absent(self):
        '''
        Test to ensure that the keystone user is absent.
        '''
        name = 'nova'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': 'User "{0}" is already absent'.format(name)}

        mock_lst = MagicMock(side_effect=[['Error'], []])
        with patch.dict(keystone.__salt__, {'keystone.user_get': mock_lst}):
            self.assertDictEqual(keystone.user_absent(name), ret)

            with patch.dict(keystone.__opts__, {'test': True}):
                comt = 'User "{0}" will be deleted'.format(name)
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(keystone.user_absent(name), ret)

    # 'tenant_present' function tests: 1

    def test_tenant_present(self):
        '''
        Test to ensures that the keystone tenant exists
        '''
        name = 'nova'
        description = 'OpenStack Compute Service'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': 'Tenant / project "{0}" already exists'.format(name)}

        mock_dict = MagicMock(side_effect=[{name: {'description': 'desc'}},
                                           {name: {'description': description,
                                                   'enabled': False}},
                                           {'Error': 'error'},
                                           {'Error': 'error'}])
        mock_t = MagicMock(return_value=True)
        with patch.dict(keystone.__salt__, {'keystone.tenant_get': mock_dict,
                                            'keystone.tenant_create': mock_t}):
            with patch.dict(keystone.__opts__, {'test': True}):
                comt = ('Tenant / project "{0}" will be updated'.format(name))
                ret.update({'comment': comt, 'result': None,
                            'changes': {'Description': 'Will be updated'}})
                self.assertDictEqual(keystone.tenant_present(name), ret)

                comt = ('Tenant / project "{0}" will be updated'.format(name))
                ret.update({'comment': comt, 'result': None,
                            'changes': {'Enabled': 'Will be True'}})
                self.assertDictEqual(keystone.tenant_present(name,
                                                             description), ret)

                comt = ('Tenant / project "{0}" will be added'.format(name))
                ret.update({'comment': comt, 'result': None,
                            'changes': {'Tenant': 'Will be created'}})
                self.assertDictEqual(keystone.tenant_present(name), ret)

            with patch.dict(keystone.__opts__, {'test': False}):
                comt = ('Tenant / project "{0}" has been added'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {'Tenant': 'Created'}})
                self.assertDictEqual(keystone.tenant_present(name), ret)

    # 'tenant_absent' function tests: 1

    def test_tenant_absent(self):
        '''
        Test to ensure that the keystone tenant is absent.
        '''
        name = 'nova'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': 'Tenant / project "{0}" is already absent'.format(name)}

        mock_lst = MagicMock(side_effect=[['Error'], []])
        with patch.dict(keystone.__salt__, {'keystone.tenant_get': mock_lst}):
            self.assertDictEqual(keystone.tenant_absent(name), ret)

            with patch.dict(keystone.__opts__, {'test': True}):
                comt = 'Tenant / project "{0}" will be deleted'.format(name)
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(keystone.tenant_absent(name), ret)

    # 'role_present' function tests: 1

    def test_role_present(self):
        '''
        Test to ensures that the keystone role exists
        '''
        name = 'nova'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': 'Role "{0}" already exists'.format(name)}

        mock_lst = MagicMock(side_effect=[[], ['Error']])
        with patch.dict(keystone.__salt__, {'keystone.role_get': mock_lst}):
            self.assertDictEqual(keystone.role_present(name), ret)

            with patch.dict(keystone.__opts__, {'test': True}):
                comt = ('Role "{0}" will be added'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(keystone.role_present(name), ret)

    # 'role_absent' function tests: 1

    def test_role_absent(self):
        '''
        Test to ensure that the keystone role is absent.
        '''
        name = 'nova'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': 'Role "{0}" is already absent'.format(name)}

        mock_lst = MagicMock(side_effect=[['Error'], []])
        with patch.dict(keystone.__salt__, {'keystone.role_get': mock_lst}):
            self.assertDictEqual(keystone.role_absent(name), ret)

            with patch.dict(keystone.__opts__, {'test': True}):
                comt = 'Role "{0}" will be deleted'.format(name)
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(keystone.role_absent(name), ret)

    # 'service_present' function tests: 1

    def test_service_present(self):
        '''
        Test to ensure service present in Keystone catalog
        '''
        name = 'nova'
        service_type = 'compute'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': 'Service "{0}" already exists'.format(name)}

        mock_lst = MagicMock(side_effect=[[], ['Error']])
        with patch.dict(keystone.__salt__, {'keystone.service_get': mock_lst}):
            self.assertDictEqual(keystone.service_present(name, service_type),
                                 ret)

            with patch.dict(keystone.__opts__, {'test': True}):
                comt = ('Service "{0}" will be added'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(keystone.service_present(name,
                                                              service_type),
                                     ret)

    # 'service_absent' function tests: 1

    def test_service_absent(self):
        '''
        Test to ensure that the service doesn't exist in Keystone catalog
        '''
        name = 'nova'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': 'Service "{0}" is already absent'.format(name)}

        mock_lst = MagicMock(side_effect=[['Error'], []])
        with patch.dict(keystone.__salt__, {'keystone.service_get': mock_lst}):
            self.assertDictEqual(keystone.service_absent(name), ret)

            with patch.dict(keystone.__opts__, {'test': True}):
                comt = 'Service "{0}" will be deleted'.format(name)
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(keystone.service_absent(name), ret)

    # 'endpoint_present' function tests: 1

    def test_endpoint_present(self):
        '''
        Test to ensure the specified endpoints exists for service
        '''
        name = 'nova'
        region = 'RegionOne'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': ''}

        endpoint = {'adminurl': None,
                    'region': None,
                    'internalurl': None,
                    'publicurl': None,
                    'id': 1, 'service_id': None}

        mock_lst = MagicMock(side_effect=[endpoint, ['Error'],
                                          {'id': 1, 'service_id': None}, []])
        mock = MagicMock(return_value=True)
        with patch.dict(keystone.__salt__, {'keystone.endpoint_get': mock_lst,
                                            'keystone.endpoint_create': mock}):

            comt = ('Endpoint for service "{0}" already exists'.format(name))
            ret.update({'comment': comt, 'result': None, 'changes': {}})
            self.assertDictEqual(keystone.endpoint_present(name), ret)

            with patch.dict(keystone.__opts__, {'test': True}):
                comt = ('Endpoint for service "{0}" will be added'.format(name))
                ret.update({'comment': comt, 'result': None, 'changes': {'Endpoint': 'Will be created'}})
                self.assertDictEqual(keystone.endpoint_present(name), ret)

                comt = ('Endpoint for service "{0}" already exists'.format(name))
                ret.update({'comment': comt, 'result': None,'changes': {}})
                self.assertDictEqual(keystone.endpoint_present(name), ret)

            with patch.dict(keystone.__opts__, {'test': False}):
                comt = ('Endpoint for service "{0}" has been added'.format(name))
                ret.update({'comment': comt, 'result': True, 'changes': True})
                self.assertDictEqual(keystone.endpoint_present(name), ret)

    # 'endpoint_absent' function tests: 1

    def test_endpoint_absent(self):
        '''
        Test to ensure that the endpoint for a service doesn't
         exist in Keystone catalog
        '''
        name = 'nova'
        region = 'RegionOne'
        comment = ('Endpoint for service "{0}" is already absent'.format(name))
        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': comment}

        mock_lst = MagicMock(side_effect=[[], ['Error']])
        with patch.dict(keystone.__salt__, {'keystone.endpoint_get': mock_lst}):
            self.assertDictEqual(keystone.endpoint_absent(name, region), ret)

            with patch.dict(keystone.__opts__, {'test': True}):
                comt = ('Endpoint for service "{0}" will be deleted'
                        .format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(keystone.endpoint_absent(name, region), ret)
