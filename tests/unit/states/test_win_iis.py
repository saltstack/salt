# -*- coding: utf-8 -*-
'''
Mock test of win_iis state.
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import sys

# Import Salt Libs
import salt.utils.platform
import salt.states.win_iis as win_iis

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    call,
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON,
)


@skipIf(not salt.utils.platform.is_windows(), 'windows test only')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinIisTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.win_iis
    '''

    def setup_loader_modules(self):
        return {win_iis: {}}

    def test_deployed_pass(self):
        list_sites = MagicMock(return_value=['test1', 'test2', 'test3'])
        create_site = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_sites': list_sites,
                                           'win_iis.create_site': create_site}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.deployed('test0', 'C:\\User\\Person\\Folder')

                list_sites.assert_called_once_with()
                create_site.assert_called_once_with('test0',
                                                    'C:\\User\\Person\\Folder',
                                                    '',
                                                    '',
                                                    '*',
                                                    80,
                                                    'http')

                self.assertDictEqual(ret, {'changes': {'new': 'test0',
                                                       'old': None},
                                           'comment': 'Created site: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_deployed_test_pass(self):
        list_sites = MagicMock(return_value=['test1', 'test2', 'test3'])
        create_site = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_sites': list_sites,
                                           'win_iis.create_site': create_site}):
            with patch.dict(win_iis.__opts__, {'test': True}):
                ret = win_iis.deployed('test0', 'C:\\User\\Person\\Folder')

                list_sites.assert_called_once_with()
                create_site.assert_not_called()

                self.assertDictEqual(ret, {'changes': {'new': 'test0',
                                                       'old': None},
                                           'comment': 'Site will be created: test0',
                                           'name': 'test0',
                                           'result': None})

    def test_deployed_no_action_need_it(self):
        list_sites = MagicMock(return_value=['test1', 'test2', 'test3'])
        create_site = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_sites': list_sites,
                                           'win_iis.create_site': create_site}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.deployed('test1', 'C:\\User\\Person\\Folder')

                list_sites.assert_called_once_with()
                create_site.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'Site already present: test1',
                                           'name': 'test1',
                                           'result': True})

    def test_remove_site_pass(self):
        list_sites = MagicMock(return_value=['test1', 'test2', 'test3'])
        remove_site = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_sites': list_sites,
                                           'win_iis.remove_site': remove_site}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.remove_site('test1')

                list_sites.assert_called_once_with()
                remove_site.assert_called_once_with('test1')

                self.assertDictEqual(ret, {'changes': {'new': None,
                                                       'old': 'test1'},
                                           'comment': 'Removed site: test1',
                                           'name': 'test1',
                                           'result': True})

    def test_remove_test_pass(self):
        list_sites = MagicMock(return_value=['test1', 'test2', 'test3'])
        remove_site = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_sites': list_sites,
                                           'win_iis.remove_site': remove_site}):
            with patch.dict(win_iis.__opts__, {'test': True}):
                ret = win_iis.remove_site('test1')

                list_sites.assert_called_once_with()
                remove_site.assert_not_called()

                self.assertDictEqual(ret, {'changes': {'new': None,
                                                       'old': 'test1'},
                                           'comment': 'Site will be removed: test1',
                                           'name': 'test1',
                                           'result': None})

    def test_remove_no_action_need_it(self):
        list_sites = MagicMock(return_value=['test1', 'test2', 'test3'])
        remove_site = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_sites': list_sites,
                                           'win_iis.remove_site': remove_site}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.remove_site('test0')

                list_sites.assert_called_once_with()
                remove_site.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'Site has already been removed: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_create_binding_pass(self):
        list_bindings = MagicMock(return_value=['*:79:'])
        create_binding = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_bindings': list_bindings,
                                           'win_iis.create_binding': create_binding}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.create_binding('test0', 'site0')

                list_bindings.assert_called_once_with('site0')
                create_binding.assert_called_once_with('site0',
                                                       '',
                                                       '*',
                                                       80,
                                                       'http',
                                                       0)

                self.assertDictEqual(ret, {'changes': {'new': '*:80:',
                                                       'old': None},
                                           'comment': 'Created binding: *:80:',
                                           'name': 'test0',
                                           'result': True})

    def test_create_binding_test_pass(self):
        list_bindings = MagicMock(return_value=['*:79:'])
        create_binding = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_bindings': list_bindings,
                                           'win_iis.create_binding': create_binding}):
            with patch.dict(win_iis.__opts__, {'test': True}):
                ret = win_iis.create_binding('test0', 'site0')

                list_bindings.assert_called_once_with('site0')
                create_binding.assert_not_called()

                self.assertDictEqual(ret, {'changes': {'new': '*:80:',
                                                       'old': None},
                                           'comment': 'Binding will be created: *:80:',
                                           'name': 'test0',
                                           'result': None})

    def test_create_binding_no_action_need_it(self):
        list_bindings = MagicMock(return_value=['*:80:'])
        create_binding = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_bindings': list_bindings,
                                           'win_iis.create_binding': create_binding}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.create_binding('test0', 'site0')

                list_bindings.assert_called_once_with('site0')
                create_binding.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'Binding already present: *:80:',
                                           'name': 'test0',
                                           'result': True})

    def test_remove_binding_pass(self):
        list_bindings = MagicMock(return_value=['*:80:'])
        remove_binding = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_bindings': list_bindings,
                                           'win_iis.remove_binding': remove_binding}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.remove_binding('test0', 'site0')

                list_bindings.assert_called_once_with('site0')
                remove_binding.assert_called_once_with('site0',
                                                       '',
                                                       '*',
                                                       80)

                self.assertDictEqual(ret, {'changes': {'new': None,
                                                       'old': '*:80:'},
                                           'comment': 'Removed binding: *:80:',
                                           'name': 'test0',
                                           'result': True})

    def test_remove_binding_test_pass(self):
        list_bindings = MagicMock(return_value=['*:80:'])
        remove_binding = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_bindings': list_bindings,
                                           'win_iis.remove_binding': remove_binding}):
            with patch.dict(win_iis.__opts__, {'test': True}):
                ret = win_iis.remove_binding('test0', 'site0')

                list_bindings.assert_called_once_with('site0')
                remove_binding.assert_not_called()

                self.assertDictEqual(ret, {'changes': {'new': None,
                                                       'old': '*:80:'},
                                           'comment': 'Binding will be removed: *:80:',
                                           'name': 'test0',
                                           'result': None})

    def test_remove_binding_no_action_need_it(self):
        list_bindings = MagicMock(return_value=['*:79:'])
        remove_binding = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_bindings': list_bindings,
                                           'win_iis.remove_binding': remove_binding}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.remove_binding('test0', 'site0')

                list_bindings.assert_called_once_with('site0')
                remove_binding.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'Binding has already been removed: *:80:',
                                           'name': 'test0',
                                           'result': True})

    def test_create_cert_binding_pass(self):
        list_cert_bindings = MagicMock(return_value=['*:80:'])
        create_cert_binding = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_cert_bindings': list_cert_bindings,
                                           'win_iis.create_cert_binding': create_cert_binding}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.create_cert_binding('test0', 'site0')

                list_cert_bindings.assert_called_once_with('site0')
                create_cert_binding.assert_called_once_with('test0',
                                                            'site0',
                                                            '',
                                                            '*',
                                                            443,
                                                            0)

                self.assertDictEqual(ret, {'changes': {'new': 'test0',
                                                       'old': None},
                                           'comment': 'Created certificate binding: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_create_cert_binding_test_pass(self):
        list_cert_bindings = MagicMock(return_value=['*:79:'])
        create_cert_binding = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_cert_bindings': list_cert_bindings,
                                           'win_iis.create_cert_binding': create_cert_binding}):
            with patch.dict(win_iis.__opts__, {'test': True}):
                ret = win_iis.create_cert_binding('test0', 'site0')

                list_cert_bindings.assert_called_once_with('site0')
                create_cert_binding.assert_not_called()

                self.assertDictEqual(ret, {'changes': {'new': 'test0',
                                                       'old': None},
                                           'comment': 'Certificate binding will be created: test0',
                                           'name': 'test0',
                                           'result': None})

    def test_create_cert_binding_no_action_need_it(self):
        list_cert_bindings = MagicMock(return_value={'*:443:': {'certificatehash': 'test0'}})
        create_cert_binding = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_cert_bindings': list_cert_bindings,
                                           'win_iis.create_cert_binding': create_cert_binding}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.create_cert_binding('test0', 'site0')

                list_cert_bindings.assert_called_once_with('site0')
                create_cert_binding.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'Certificate binding already present: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_create_cert_binding_no_action_need_it_2(self):
        list_cert_bindings = MagicMock(return_value={'*:443:': {'certificatehash': 'test404'}})
        create_cert_binding = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_cert_bindings': list_cert_bindings,
                                           'win_iis.create_cert_binding': create_cert_binding}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.create_cert_binding('test0', 'site0')

                list_cert_bindings.assert_called_once_with('site0')
                create_cert_binding.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'Certificate binding already present with a different thumbprint: test404',
                                           'name': 'test0',
                                           'result': False})

    def test_remove_cert_binding_pass(self):
        list_cert_bindings = MagicMock(return_value={'*:443:': {'certificatehash': 'test0'}})
        remove_cert_binding = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_cert_bindings': list_cert_bindings,
                                           'win_iis.remove_cert_binding': remove_cert_binding}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.remove_cert_binding('test0', 'site0')

                list_cert_bindings.assert_called_once_with('site0')
                remove_cert_binding.assert_called_once_with('test0',
                                                            'site0',
                                                            '',
                                                            '*',
                                                            443)

                self.assertDictEqual(ret, {'changes': {'new': None,
                                                       'old': 'test0'},
                                           'comment': 'Removed certificate binding: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_remove_cert_binding_pass_2(self):
        list_cert_bindings = MagicMock(return_value={'*:443:': {'certificatehash': 'test404'}})
        remove_cert_binding = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_cert_bindings': list_cert_bindings,
                                           'win_iis.remove_cert_binding': remove_cert_binding}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.remove_cert_binding('test0', 'site0')

                list_cert_bindings.assert_called_once_with('site0')
                remove_cert_binding.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': '',
                                           'name': 'test0',
                                           'result': None})

    def test_remove_cert_binding_test_pass(self):
        list_cert_bindings = MagicMock(return_value={'*:443:': {'certificatehash': 'test0'}})
        remove_cert_binding = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_cert_bindings': list_cert_bindings,
                                           'win_iis.remove_cert_binding': remove_cert_binding}):
            with patch.dict(win_iis.__opts__, {'test': True}):
                ret = win_iis.remove_cert_binding('test0', 'site0')

                list_cert_bindings.assert_called_once_with('site0')
                remove_cert_binding.assert_not_called()

                self.assertDictEqual(ret, {'changes': {'new': None,
                                                       'old': 'test0'},
                                           'comment': 'Certificate binding will be removed: test0',
                                           'name': 'test0',
                                           'result': None})

    def test_remove_cert_binding_no_action_need_it(self):
        list_cert_bindings = MagicMock(return_value={'*:444:': {'certificatehash': 'test0'}})
        remove_cert_binding = MagicMock(return_value=True)

        with patch.dict(win_iis.__salt__, {'win_iis.list_cert_bindings': list_cert_bindings,
                                           'win_iis.remove_cert_binding': remove_cert_binding}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.remove_cert_binding('test0', 'site0')

                list_cert_bindings.assert_called_once_with('site0')
                remove_cert_binding.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'Certificate binding has already been removed: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_create_apppool_pass(self):
        list_apppools = MagicMock(return_value=['test1'])
        create_apppool = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_apppools': list_apppools,
                                           'win_iis.create_apppool': create_apppool}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.create_apppool('test0')

                list_apppools.assert_called_once_with()
                create_apppool.assert_called_once_with('test0')

                self.assertDictEqual(ret, {'changes': {'new': 'test0',
                                                       'old': None},
                                           'comment': 'Created application pool: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_create_apppool_test_pass(self):
        list_apppools = MagicMock(return_value=['test1'])
        create_apppool = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_apppools': list_apppools,
                                           'win_iis.create_apppool': create_apppool}):
            with patch.dict(win_iis.__opts__, {'test': True}):
                ret = win_iis.create_apppool('test0')

                list_apppools.assert_called_once_with()
                create_apppool.assert_not_called()

                self.assertDictEqual(ret, {'changes': {'new': 'test0', 'old': None},
                                           'comment': 'Application pool will be created: test0',
                                           'name': 'test0',
                                           'result': None})

    def test_create_apppool_no_action_need_it(self):
        list_apppools = MagicMock(return_value=['test0'])
        create_apppool = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_apppools': list_apppools,
                                           'win_iis.create_apppool': create_apppool}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.create_apppool('test0')

                list_apppools.assert_called_once_with()
                create_apppool.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'Application pool already present: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_remove_apppool_pass(self):
        list_apppools = MagicMock(return_value=['test0'])
        remove_apppool = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_apppools': list_apppools,
                                           'win_iis.remove_apppool': remove_apppool}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.remove_apppool('test0')

                list_apppools.assert_called_once_with()
                remove_apppool.assert_called_once_with('test0')

                self.assertDictEqual(ret, {'changes': {'new': None,
                                                       'old': 'test0'},
                                           'comment': 'Removed application pool: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_remove_apppool_test_pass(self):
        list_apppools = MagicMock(return_value=['test0'])
        remove_apppool = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_apppools': list_apppools,
                                           'win_iis.remove_apppool': remove_apppool}):
            with patch.dict(win_iis.__opts__, {'test': True}):
                ret = win_iis.remove_apppool('test0')

                list_apppools.assert_called_once_with()
                remove_apppool.assert_not_called()

                self.assertDictEqual(ret, {'changes': {'new': None, 'old': 'test0'},
                                           'comment': 'Application pool will be removed: test0',
                                           'name': 'test0',
                                           'result': None})

    def test_remove_apppool_no_action_need_it(self):
        list_apppools = MagicMock(return_value=['test1'])
        remove_apppool = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_apppools': list_apppools,
                                           'win_iis.remove_apppool': remove_apppool}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.remove_apppool('test0')

                list_apppools.assert_called_once_with()
                remove_apppool.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'Application pool has already been removed: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_container_setting_no_settings(self):
        get_container_setting = MagicMock(return_value=None)
        set_container_setting = MagicMock(return_value=None)
        with patch.dict(win_iis.__salt__, {'win_iis.get_container_setting': get_container_setting,
                                           'win_iis.set_container_setting': set_container_setting}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.container_setting('test0', 'AppPools', {})

                get_container_setting.assert_not_called()
                set_container_setting.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'No settings to change provided.',
                                           'name': 'test0',
                                           'result': True})

    def test_container_setting_pass(self):
        get_container_setting = MagicMock(side_effect=[{'managedPipelineMode': 'Integrated_old',
                                                        'processModel.maxProcesses': 1,
                                                        'processModel.userName': 'TestUser_old',
                                                        'processModel.password': 'TestPassword_old',
                                                        'processModel.identityType': 4},
                                                       {'managedPipelineMode': 'Integrated',
                                                        'processModel.maxProcesses': 1,
                                                        'processModel.userName': 'TestUser',
                                                        'processModel.password': 'TestPassword',
                                                        'processModel.identityType': 'ApplicationPoolIdentity'}])

        set_container_setting = MagicMock(return_value=None)

        with patch.dict(win_iis.__salt__, {'win_iis.get_container_setting': get_container_setting,
                                           'win_iis.set_container_setting': set_container_setting}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.container_setting('test0',
                                                'AppPools',
                                                {'managedPipelineMode': 'Integrated',
                                                 'processModel.maxProcesses': 1,
                                                 'processModel.userName': 'TestUser',
                                                 'processModel.password': 'TestPassword',
                                                 'processModel.identityType': 4})

                settings = {'managedPipelineMode',
                            'processModel.maxProcesses',
                            'processModel.userName',
                            'processModel.password',
                            'processModel.identityType'}

                self.assertEqual(get_container_setting.call_count, 2)
                if sys.version_info[0] >= 3:
                    self.assertEqual(get_container_setting.mock_calls[0], call(container='AppPools',
                                                                               name='test0',
                                                                               settings=settings))
                    self.assertEqual(get_container_setting.mock_calls[1], call(container='AppPools',
                                                                               name='test0',
                                                                               settings=settings))
                else:
                    for get_container_setting_call in get_container_setting.mock_calls:
                        self.assertEqual(get_container_setting_call.kwargs.get('container'), 'AppPools')
                        self.assertEqual(get_container_setting_call.kwargs.get('name'), 'test0')
                        self.assertIsInstance(get_container_setting_call.kwargs.get('settings'), list)
                        self.assertEqual(set(get_container_setting_call.kwargs.get('settings')), settings)

                set_container_setting.assert_called_once_with(container='AppPools',
                                                              name='test0',
                                                              settings={'managedPipelineMode': 'Integrated',
                                                                        'processModel.maxProcesses': 1,
                                                                        'processModel.userName': 'TestUser',
                                                                        'processModel.password': 'TestPassword',
                                                                        'processModel.identityType': 'ApplicationPoolIdentity'})

                self.assertDictEqual(ret, {'changes': {'managedPipelineMode': {'new': 'Integrated',
                                                                               'old': 'Integrated_old'},
                                                       'processModel.identityType': {'new': 'ApplicationPoolIdentity',
                                                                                     'old': 4},
                                                       'processModel.password': {'new': 'TestPassword',
                                                                                 'old': 'TestPassword_old'},
                                                       'processModel.userName': {'new': 'TestUser',
                                                                                 'old': 'TestUser_old'}},
                                           'comment': 'Set settings to contain the provided values.',
                                           'name': 'test0',
                                           'result': True})

    def test_container_setting_fail(self):
        get_container_setting = MagicMock(side_effect=[{'managedPipelineMode': 'Integrated_old',
                                                        'processModel.maxProcesses': 1,
                                                        'processModel.userName': 'TestUser_old',
                                                        'processModel.password': 'TestPassword_old',
                                                        'processModel.identityType': 4},
                                                       {'managedPipelineMode': 'ERROR',
                                                        'processModel.maxProcesses': 'ERROR',
                                                        'processModel.userName': 'ERROR',
                                                        'processModel.password': 'ERROR',
                                                        'processModel.identityType': 'ERROR'}])

        set_container_setting = MagicMock(return_value=None)

        with patch.dict(win_iis.__salt__, {'win_iis.get_container_setting': get_container_setting,
                                           'win_iis.set_container_setting': set_container_setting}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.container_setting('test0',
                                                'AppPools',
                                                {'managedPipelineMode': 'Integrated',
                                                 'processModel.maxProcesses': 1,
                                                 'processModel.userName': 'TestUser',
                                                 'processModel.password': 'TestPassword',
                                                 'processModel.identityType': 4})

                settings = {'managedPipelineMode',
                            'processModel.maxProcesses',
                            'processModel.userName',
                            'processModel.password',
                            'processModel.identityType'}

                self.assertEqual(get_container_setting.call_count, 2)
                if sys.version_info[0] >= 3:
                    self.assertEqual(get_container_setting.mock_calls[0], call(container='AppPools',
                                                                               name='test0',
                                                                               settings=settings))
                    self.assertEqual(get_container_setting.mock_calls[1], call(container='AppPools',
                                                                               name='test0',
                                                                               settings=settings))
                else:
                    for get_container_setting_call in get_container_setting.mock_calls:
                        self.assertEqual(get_container_setting_call.kwargs.get('container'), 'AppPools')
                        self.assertEqual(get_container_setting_call.kwargs.get('name'), 'test0')
                        self.assertIsInstance(get_container_setting_call.kwargs.get('settings'), list)
                        self.assertEqual(set(get_container_setting_call.kwargs.get('settings')), settings)

                set_container_setting.assert_called_once_with(container='AppPools',
                                                              name='test0',
                                                              settings={'managedPipelineMode': 'Integrated',
                                                                        'processModel.maxProcesses': 1,
                                                                        'processModel.userName': 'TestUser',
                                                                        'processModel.password': 'TestPassword',
                                                                        'processModel.identityType': 'ApplicationPoolIdentity'})

                self.assertDictEqual(ret, {'changes': {'changes': {},
                                           'failures': {'managedPipelineMode': {'new': 'ERROR',
                                                                                'old': 'Integrated_old'},
                                                        'processModel.identityType': {'new': 'ERROR',
                                                                                      'old': 4},
                                                        'processModel.maxProcesses': {'new': 'ERROR',
                                                                                      'old': 1},
                                                        'processModel.password': {'new': 'ERROR',
                                                                                  'old': 'TestPassword_old'},
                                                        'processModel.userName': {'new': 'ERROR',
                                                                                  'old': 'TestUser_old'}}},
                                           'comment': 'Some settings failed to change.',
                                           'name': 'test0',
                                           'result': False})

    def test_container_setting_test_pass(self):
        get_container_setting = MagicMock(return_value={'managedPipelineMode': 'Integrated_old',
                                                        'processModel.maxProcesses': 1,
                                                        'processModel.userName': 'TestUser_old',
                                                        'processModel.password': 'TestPassword_old',
                                                        'processModel.identityType': 4})

        set_container_setting = MagicMock(return_value=None)

        with patch.dict(win_iis.__salt__, {'win_iis.get_container_setting': get_container_setting,
                                           'win_iis.set_container_setting': set_container_setting}):
            with patch.dict(win_iis.__opts__, {'test': True}):
                ret = win_iis.container_setting('test0',
                                                'AppPools',
                                                {'managedPipelineMode': 'Integrated',
                                                 'processModel.maxProcesses': 1,
                                                 'processModel.userName': 'TestUser',
                                                 'processModel.password': 'TestPassword',
                                                 'processModel.identityType': 4})

                settings = {'managedPipelineMode',
                            'processModel.maxProcesses',
                            'processModel.userName',
                            'processModel.password',
                            'processModel.identityType'}

                if sys.version_info[0] >= 3:
                    # python 3 settings type is a set
                    get_container_setting.assert_called_with(container='AppPools',
                                                             name='test0',
                                                             settings=settings)
                else:
                    get_container_setting.assert_called_once()
                    get_container_setting_call = get_container_setting.mock_calls[0]
                    self.assertEqual(get_container_setting_call.kwargs.get('container'), 'AppPools')
                    self.assertEqual(get_container_setting_call.kwargs.get('name'), 'test0')
                    self.assertIsInstance(get_container_setting_call.kwargs.get('settings'), list)
                    self.assertEqual(set(get_container_setting_call.kwargs.get('settings')), settings)
                set_container_setting.assert_not_called()

                self.assertDictEqual(ret, {'changes': {'changes': {'managedPipelineMode': {'new': 'Integrated',
                                                                                           'old': 'Integrated_old'},
                                                                   'processModel.identityType': {'new': 'ApplicationPoolIdentity',
                                                                                                 'old': 4},
                                                                   'processModel.password': {'new': 'TestPassword',
                                                                                             'old': 'TestPassword_old'},
                                                                   'processModel.userName': {'new': 'TestUser',
                                                                                             'old': 'TestUser_old'}},
                                                       'failures': {}},
                                           'comment': 'Settings will be changed.',
                                           'name': 'test0',
                                           'result': None})

    def test_container_setting_no_action_need_it(self):
        get_container_setting = MagicMock(return_value={'managedPipelineMode': 'Integrated',
                                                        'processModel.maxProcesses': 1,
                                                        'processModel.userName': 'TestUser',
                                                        'processModel.password': 'TestPassword',
                                                        'processModel.identityType': 'ApplicationPoolIdentity'})

        set_container_setting = MagicMock(return_value=None)

        with patch.dict(win_iis.__salt__, {'win_iis.get_container_setting': get_container_setting,
                                           'win_iis.set_container_setting': set_container_setting}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.container_setting('test0',
                                                'AppPools',
                                                {'managedPipelineMode': 'Integrated',
                                                 'processModel.maxProcesses': 1,
                                                 'processModel.userName': 'TestUser',
                                                 'processModel.password': 'TestPassword',
                                                 'processModel.identityType': 4})

                settings = {'managedPipelineMode',
                            'processModel.maxProcesses',
                            'processModel.userName',
                            'processModel.password',
                            'processModel.identityType'}
                if sys.version_info[0] >= 3:
                    get_container_setting.assert_called_once_with(container='AppPools',
                                                                  name='test0',
                                                                  settings=settings)
                else:
                    get_container_setting.assert_called_once()
                    get_container_setting_call = get_container_setting.mock_calls[0]
                    self.assertEqual(get_container_setting_call.kwargs.get('container'), 'AppPools')
                    self.assertEqual(get_container_setting_call.kwargs.get('name'), 'test0')
                    self.assertIsInstance(get_container_setting_call.kwargs.get('settings'), list)
                    self.assertEqual(set(get_container_setting_call.kwargs.get('settings')), settings)

                set_container_setting.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'Settings already contain the provided values.',
                                           'name': 'test0',
                                           'result': True})

    def test_create_app_pass(self):
        list_apps = MagicMock(return_value=['test1'])
        create_app = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_apps': list_apps,
                                           'win_iis.create_app': create_app}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.create_app('test0',
                                         'site0',
                                         'C:\\User\\Person\\Folder',
                                         'pool')

                list_apps.assert_called_once_with('site0')
                create_app.assert_called_once_with('test0',
                                                   'site0',
                                                   'C:\\User\\Person\\Folder',
                                                   'pool')

                self.assertDictEqual(ret, {'changes': {'new': 'test0',
                                                       'old': None},
                                           'comment': 'Created application: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_create_app_test_pass(self):
        list_apps = MagicMock(return_value=['test1'])
        create_app = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_apps': list_apps,
                                           'win_iis.create_app': create_app}):
            with patch.dict(win_iis.__opts__, {'test': True}):
                ret = win_iis.create_app('test0',
                                         'site0',
                                         'C:\\User\\Person\\Folder',
                                         'pool')

                list_apps.assert_called_once_with('site0')
                create_app.assert_not_called()

                self.assertDictEqual(ret, {'changes': {'new': 'test0',
                                                       'old': None},
                                           'comment': 'Application will be created: test0',
                                           'name': 'test0',
                                           'result': None})

    def test_create_app_no_action_need_it(self):
        list_apps = MagicMock(return_value=['test0'])
        create_app = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_apps': list_apps,
                                           'win_iis.create_app': create_app}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.create_app('test0',
                                         'site0',
                                         'C:\\User\\Person\\Folder',
                                         'pool')

                list_apps.assert_called_once_with('site0')
                create_app.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'Application already present: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_remove_app_pass(self):
        list_apps = MagicMock(return_value=['test0'])
        remove_app = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_apps': list_apps,
                                           'win_iis.remove_app': remove_app}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.remove_app('test0', 'site0')

                list_apps.assert_called_once_with('site0')
                remove_app.assert_called_once_with('test0', 'site0')

                self.assertDictEqual(ret, {'changes': {'new': None,
                                                       'old': 'test0'},
                                           'comment': 'Removed application: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_remove_app_test_pass(self):
        list_apps = MagicMock(return_value=['test0'])
        remove_app = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_apps': list_apps,
                                           'win_iis.remove_app': remove_app}):
            with patch.dict(win_iis.__opts__, {'test': True}):
                ret = win_iis.remove_app('test0', 'site0')

                list_apps.assert_called_once_with('site0')
                remove_app.assert_not_called()

                self.assertDictEqual(ret, {'changes': {'new': None,
                                                       'old': 'test0'},
                                           'comment': 'Application will be removed: test0',
                                           'name': 'test0',
                                           'result': None})

    def test_remove_app_pass_no_action_need_it(self):
        list_apps = MagicMock(return_value=['test1'])
        remove_app = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_apps': list_apps,
                                           'win_iis.remove_app': remove_app}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.remove_app('test0', 'site0')

                list_apps.assert_called_once_with('site0')
                remove_app.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'Application has already been removed: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_create_vdir_pass(self):
        list_vdirs = MagicMock(return_value=['test1'])
        create_vdir = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_vdirs': list_vdirs,
                                           'win_iis.create_vdir': create_vdir}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.create_vdir('test0',
                                          'site0',
                                          'C:\\User\\Person\\Folder',
                                          '\\')

                list_vdirs.assert_called_once_with('site0', '\\')
                create_vdir.assert_called_once_with('test0',
                                                    'site0',
                                                    'C:\\User\\Person\\Folder',
                                                    '\\')

                self.assertDictEqual(ret, {'changes': {'new': 'test0',
                                                       'old': None},
                                           'comment': 'Created virtual directory: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_create_vdir_test_pass(self):
        list_vdirs = MagicMock(return_value=['test1'])
        create_vdir = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_vdirs': list_vdirs,
                                           'win_iis.create_vdir': create_vdir}):
            with patch.dict(win_iis.__opts__, {'test': True}):
                ret = win_iis.create_vdir('test0',
                                          'site0',
                                          'C:\\User\\Person\\Folder',
                                          '\\')

                list_vdirs.assert_called_once_with('site0', '\\')
                create_vdir.assert_not_called()

                self.assertDictEqual(ret, {'changes': {'new': 'test0',
                                                       'old': None},
                                           'comment': 'Virtual directory will be created: test0',
                                           'name': 'test0',
                                           'result': None})

    def test_create_vdir_no_action_need_it(self):
        list_vdirs = MagicMock(return_value=['test0'])
        create_vdir = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_vdirs': list_vdirs,
                                           'win_iis.create_vdir': create_vdir}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.create_vdir('test0',
                                          'site0',
                                          'C:\\User\\Person\\Folder',
                                          '\\')

                list_vdirs.assert_called_once_with('site0', '\\')
                create_vdir.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'Virtual directory already present: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_remove_vdir_pass(self):
        list_vdirs = MagicMock(return_value=['test0'])
        remove_vdir = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_vdirs': list_vdirs,
                                           'win_iis.remove_vdir': remove_vdir}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.remove_vdir('test0',
                                          'site0',
                                          '\\')

                list_vdirs.assert_called_once_with('site0', '\\')
                remove_vdir.assert_called_once_with('test0',
                                                    'site0',
                                                    '\\')

                self.assertDictEqual(ret, {'changes': {'new': None,
                                                       'old': 'test0'},
                                           'comment': 'Removed virtual directory: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_remove_vdir_test_pass(self):
        list_vdirs = MagicMock(return_value=['test0'])
        remove_vdir = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_vdirs': list_vdirs,
                                           'win_iis.remove_vdir': remove_vdir}):
            with patch.dict(win_iis.__opts__, {'test': True}):
                ret = win_iis.remove_vdir('test0',
                                          'site0',
                                          '\\')

                list_vdirs.assert_called_once_with('site0', '\\')
                remove_vdir.assert_not_called()

                self.assertDictEqual(ret, {'changes': {'new': None,
                                                       'old': 'test0'},
                                           'comment': 'Virtual directory will be removed: test0',
                                           'name': 'test0',
                                           'result': None})

    def test_remove_vdir_no_action_need_it(self):
        list_vdirs = MagicMock(return_value=['test1'])
        remove_vdir = MagicMock(return_value=True)
        with patch.dict(win_iis.__salt__, {'win_iis.list_vdirs': list_vdirs,
                                           'win_iis.remove_vdir': remove_vdir}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.remove_vdir('test0',
                                          'site0',
                                          '\\')

                list_vdirs.assert_called_once_with('site0', '\\')
                remove_vdir.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'Virtual directory has already been removed: test0',
                                           'name': 'test0',
                                           'result': True})

    def test_set_app_no_settings(self):
        get_webapp_settings = MagicMock(return_value=None)
        set_webapp_settings = MagicMock(return_value=None)
        with patch.dict(win_iis.__salt__, {'win_iis.get_webapp_settings': get_webapp_settings,
                                           'win_iis.set_webapp_settings': set_webapp_settings}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.set_app('test0', 'site0', {})

                get_webapp_settings.assert_not_called()
                set_webapp_settings.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'No settings to change provided.',
                                           'name': 'test0',
                                           'result': True})

    def test_set_app_pass(self):
        get_webapp_settings = MagicMock(side_effect=[{'userName': 'domain\\user_old',
                                                      'password': 'pass_old',
                                                      'physicalPath': 'C:\\User\\Person\\Folder_old',
                                                      'applicationPool': 'appPool0_old'},
                                                     {'userName': 'domain\\user',
                                                      'password': 'pass',
                                                      'physicalPath': 'C:\\User\\Person\\Folder',
                                                      'applicationPool': 'appPool0'}])
        set_webapp_settings = MagicMock(return_value=None)
        with patch.dict(win_iis.__salt__, {'win_iis.get_webapp_settings': get_webapp_settings,
                                           'win_iis.set_webapp_settings': set_webapp_settings}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.set_app('test0', 'site0', {'userName': 'domain\\user',
                                                         'password': 'pass',
                                                         'physicalPath': 'C:\\User\\Person\\Folder',
                                                         'applicationPool': 'appPool0'})

                settings = {'userName',
                            'password',
                            'physicalPath',
                            'applicationPool'}
                self.assertEqual(get_webapp_settings.call_count, 2)
                if sys.version_info[0] >= 3:
                    self.assertEqual(get_webapp_settings.mock_calls[0], call(name='test0',
                                                                             site='site0',
                                                                             settings=settings))

                    self.assertEqual(get_webapp_settings.mock_calls[1], call(name='test0',
                                                                             site='site0',
                                                                             settings=settings))
                else:
                    for get_webapp_call in get_webapp_settings.mock_calls:
                        self.assertEqual(get_webapp_call.kwargs.get('name'), 'test0')
                        self.assertEqual(get_webapp_call.kwargs.get('site'), 'site0')
                        self.assertIsInstance(get_webapp_call.kwargs.get('settings'), list)
                        self.assertEqual(set(get_webapp_call.kwargs.get('settings')), settings)

                set_webapp_settings.assert_called_with(name='test0',
                                                       site='site0',
                                                       settings={'userName': 'domain\\user',
                                                                 'password': 'pass',
                                                                 'physicalPath': 'C:\\User\\Person\\Folder',
                                                                 'applicationPool': 'appPool0'})

                self.assertDictEqual(ret, {'changes': {'applicationPool': {'new': 'appPool0',
                                                                           'old': 'appPool0_old'},
                                                       'password': {'new': 'pass',
                                                                    'old': 'pass_old'},
                                                       'physicalPath': {'new': 'C:\\User\\Person\\Folder',
                                                                        'old': 'C:\\User\\Person\\Folder_old'},
                                                       'userName': {'new': 'domain\\user',
                                                                    'old': 'domain\\user_old'}},
                                           'comment': 'Set settings to contain the provided values.',
                                           'name': 'test0',
                                           'result': True})

    def test_set_app_fail(self):
        get_webapp_settings = MagicMock(side_effect=[{'userName': 'domain\\user_old',
                                                      'password': 'pass_old',
                                                      'physicalPath': 'C:\\User\\Person\\Folder_old',
                                                      'applicationPool': 'appPool0_old'},
                                                     {'userName': 'ERROR',
                                                      'password': 'ERROR',
                                                      'physicalPath': 'ERROR',
                                                      'applicationPool': 'ERROR'}])
        set_webapp_settings = MagicMock(return_value=None)
        with patch.dict(win_iis.__salt__, {'win_iis.get_webapp_settings': get_webapp_settings,
                                           'win_iis.set_webapp_settings': set_webapp_settings}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.set_app('test0', 'site0', {'userName': 'domain\\user',
                                                         'password': 'pass',
                                                         'physicalPath': 'C:\\User\\Person\\Folder',
                                                         'applicationPool': 'appPool0'})

                settings = {'userName',
                            'password',
                            'physicalPath',
                            'applicationPool'}

                self.assertEqual(get_webapp_settings.call_count, 2)
                if sys.version_info[0] >= 3:
                    self.assertEqual(get_webapp_settings.mock_calls[0], call(name='test0',
                                                                             site='site0',
                                                                             settings=settings))

                    self.assertEqual(get_webapp_settings.mock_calls[1], call(name='test0',
                                                                             site='site0',
                                                                             settings=settings))
                else:
                    for get_webapp_call in get_webapp_settings.mock_calls:
                        self.assertEqual(get_webapp_call.kwargs.get('name'), 'test0')
                        self.assertEqual(get_webapp_call.kwargs.get('site'), 'site0')
                        self.assertIsInstance(get_webapp_call.kwargs.get('settings'), list)
                        self.assertEqual(set(get_webapp_call.kwargs.get('settings')), settings)

                set_webapp_settings.assert_called_with(name='test0',
                                                       site='site0',
                                                       settings={'userName': 'domain\\user',
                                                                 'password': 'pass',
                                                                 'physicalPath': 'C:\\User\\Person\\Folder',
                                                                 'applicationPool': 'appPool0'})

                self.assertDictEqual(ret, {'changes': {'changes': {},
                                                       'failures': {'applicationPool': {'new': 'ERROR',
                                                                                        'old': 'appPool0_old'},
                                                                    'password': {'new': 'ERROR',
                                                                                 'old': 'pass_old'},
                                                                    'physicalPath': {'new': 'ERROR',
                                                                                     'old': 'C:\\User\\Person\\Folder_old'},
                                                                    'userName': {'new': 'ERROR',
                                                                                 'old': 'domain\\user_old'}}},
                                           'comment': 'Some settings failed to change.',
                                           'name': 'test0',
                                           'result': False})

    def test_set_app_test_pass(self):
        get_webapp_settings = MagicMock(return_value={'userName': 'domain\\user_old',
                                                      'password': 'pass_old',
                                                      'physicalPath': 'C:\\User\\Person\\Folder_old',
                                                      'applicationPool': 'appPool0_old'})
        set_webapp_settings = MagicMock(return_value=None)
        with patch.dict(win_iis.__salt__, {'win_iis.get_webapp_settings': get_webapp_settings,
                                           'win_iis.set_webapp_settings': set_webapp_settings}):
            with patch.dict(win_iis.__opts__, {'test': True}):
                ret = win_iis.set_app('test0', 'site0', {'userName': 'domain\\user',
                                                         'password': 'pass',
                                                         'physicalPath': 'C:\\User\\Person\\Folder',
                                                         'applicationPool': 'appPool0'})

                settings = {'userName',
                            'password',
                            'physicalPath',
                            'applicationPool'}
                if sys.version_info[0] >= 3:
                    # python 3 settings type is a set
                    get_webapp_settings.assert_called_with(name='test0',
                                                           site='site0',
                                                           settings=settings)
                else:
                    get_webapp_settings.assert_called_once()
                    get_webapp_call = get_webapp_settings.mock_calls[0]
                    self.assertEqual(get_webapp_call.kwargs.get('name'), 'test0')
                    self.assertEqual(get_webapp_call.kwargs.get('site'), 'site0')
                    self.assertIsInstance(get_webapp_call.kwargs.get('settings'), list)
                    self.assertEqual(set(get_webapp_call.kwargs.get('settings')), settings)

                set_webapp_settings.assert_not_called()

                self.assertDictEqual(ret, {'changes': {'changes': {'applicationPool': {'new': 'appPool0',
                                                                                       'old': 'appPool0_old'},
                                                                   'password': {'new': 'pass',
                                                                                'old': 'pass_old'},
                                                                   'physicalPath': {'new': 'C:\\User\\Person\\Folder',
                                                                                    'old': 'C:\\User\\Person\\Folder_old'},
                                                                   'userName': {'new': 'domain\\user',
                                                                                'old': 'domain\\user_old'}},
                                                       'failures': {}},
                                           'comment': 'Settings will be changed.',
                                           'name': 'test0',
                                           'result': None})

    def test_set_app_test_no_action_need_it(self):
        get_webapp_settings = MagicMock(return_value={'userName': 'domain\\user',
                                                      'password': 'pass',
                                                      'physicalPath': 'C:\\User\\Person\\Folder',
                                                      'applicationPool': 'appPool0'})
        set_webapp_settings = MagicMock(return_value=None)
        with patch.dict(win_iis.__salt__, {'win_iis.get_webapp_settings': get_webapp_settings,
                                           'win_iis.set_webapp_settings': set_webapp_settings}):
            with patch.dict(win_iis.__opts__, {'test': False}):
                ret = win_iis.set_app('test0', 'site0', {'userName': 'domain\\user',
                                                         'password': 'pass',
                                                         'physicalPath': 'C:\\User\\Person\\Folder',
                                                         'applicationPool': 'appPool0'})

                settings = {'userName',
                            'password',
                            'physicalPath',
                            'applicationPool'}
                if sys.version_info[0] >= 3:
                    # python 3 settings type is a set
                    get_webapp_settings.assert_called_with(name='test0',
                                                           site='site0',
                                                           settings=settings)
                else:
                    get_webapp_settings.assert_called_once()
                    get_webapp_call = get_webapp_settings.mock_calls[0]
                    self.assertEqual(get_webapp_call.kwargs.get('name'), 'test0')
                    self.assertEqual(get_webapp_call.kwargs.get('site'), 'site0')
                    self.assertIsInstance(get_webapp_call.kwargs.get('settings'), list)
                    self.assertEqual(set(get_webapp_call.kwargs.get('settings')), settings)

                set_webapp_settings.assert_not_called()

                self.assertDictEqual(ret, {'changes': {},
                                           'comment': 'Settings already contain the provided values.',
                                           'name': 'test0',
                                           'result': True})
