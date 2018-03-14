# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rajvi Dhimar <rajvidhimar95@gmail.com>`
'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import test libs
from tests.support.mixins import LoaderModuleMockMixin, XMLEqualityMixin
from tests.support.mock import patch, mock_open
from tests.support.unit import skipIf, TestCase

# Import 3rd-party libs
try:
    from lxml import etree
except ImportError:
    from salt._compat import ElementTree as etree

try:
    from jnpr.junos.utils.config import Config
    from jnpr.junos.utils.sw import SW
    from jnpr.junos.device import Device
    HAS_JUNOS = True
except ImportError:
    HAS_JUNOS = False

# Import salt modules
import salt.modules.junos as junos


@skipIf(not HAS_JUNOS, 'Install junos-eznc to be able to run this test.')
class Test_Junos_Module(TestCase, LoaderModuleMockMixin, XMLEqualityMixin):

    def setup_loader_modules(self):
        return {
            junos: {
                '__proxy__': {
                    'junos.conn': self.make_connect,
                    'junos.get_serialized_facts': self.get_facts
                },
                '__salt__': {'cp.get_template': self.mock_cp,
                             'cp.get_file': self.mock_cp}
            }
        }

    def mock_cp(self, *args, **kwargs):
        pass

    def make_connect(self):
        with patch('ncclient.manager.connect') as mock_connect:
            self.dev = self.dev = Device(
                host='1.1.1.1',
                user='test',
                password='test123',
                fact_style='old',
                gather_facts=False)
            self.dev.open()
            self.dev.timeout = 30
            self.dev.bind(cu=Config)
            self.dev.bind(sw=SW)
            self.addCleanup(delattr, self, 'dev')
            return self.dev

    def raise_exception(self, *args, **kwargs):
        raise Exception('Test exception')

    def get_facts(self):
        facts = {'2RE': True,
                 'HOME': '/var/home/regress',
                 'RE0': {'last_reboot_reason': '0x200:normal shutdown',
                         'mastership_state': 'master',
                         'model': 'RE-VMX',
                         'status': 'OK',
                         'up_time': '11 days, 23 hours, 16 minutes, 54 seconds'},
                 'RE1': {'last_reboot_reason': '0x200:normal shutdown',
                         'mastership_state': 'backup',
                         'model': 'RE-VMX',
                         'status': 'OK',
                         'up_time': '11 days, 23 hours, 16 minutes, 41 seconds'},
                 'RE_hw_mi': False,
                 'current_re': ['re0', 'master', 'node', 'fwdd', 'member', 'pfem'],
                 'domain': 'englab.juniper.net',
                 'fqdn': 'R1_re0.englab.juniper.net',
                 'hostname': 'R1_re0',
                 'hostname_info': {'re0': 'R1_re0', 're1': 'R1_re01'},
                 'ifd_style': 'CLASSIC',
                 'junos_info': {'re0': {'object': {'build': None,
                                                   'major': (16, 1),
                                                   'minor': '20160413_0837_aamish',
                                                   'type': 'I'},
                                        'text': '16.1I20160413_0837_aamish'},
                                're1': {'object': {'build': None,
                                                   'major': (16, 1),
                                                   'minor': '20160413_0837_aamish',
                                                   'type': 'I'},
                                        'text': '16.1I20160413_0837_aamish'}},
                 'master': 'RE0',
                 'model': 'MX240',
                 'model_info': {'re0': 'MX240', 're1': 'MX240'},
                 'personality': 'MX',
                 're_info': {'default': {'0': {'last_reboot_reason': '0x200:normal shutdown',
                                               'mastership_state': 'master',
                                               'model': 'RE-VMX',
                                               'status': 'OK'},
                                         '1': {'last_reboot_reason': '0x200:normal shutdown',
                                               'mastership_state': 'backup',
                                               'model': 'RE-VMX',
                                               'status': 'OK'},
                                         'default': {'last_reboot_reason': '0x200:normal shutdown',
                                                     'mastership_state': 'master',
                                                     'model': 'RE-VMX',
                                                     'status': 'OK'}}},
                 're_master': {'default': '0'},
                 'serialnumber': 'VMX4eaf',
                 'srx_cluster': None,
                 'switch_style': 'BRIDGE_DOMAIN',
                 'vc_capable': False,
                 'vc_fabric': None,
                 'vc_master': None,
                 'vc_mode': None,
                 'version': '16.1I20160413_0837_aamish',
                 'version_RE0': '16.1I20160413_0837_aamish',
                 'version_RE1': '16.1I20160413_0837_aamish',
                 'version_info': {'build': None,
                                  'major': (16, 1),
                                  'minor': '20160413_0837_aamish',
                                  'type': 'I'},
                 'virtual': True}
        return facts

    def test_facts_refresh(self):
        with patch('salt.modules.saltutil.sync_grains') as mock_sync_grains:
            ret = dict()
            ret['facts'] = {'2RE': True,
                            'HOME': '/var/home/regress',
                            'RE0': {'last_reboot_reason': '0x200:normal shutdown',
                                    'mastership_state': 'master',
                                    'model': 'RE-VMX',
                                    'status': 'OK',
                                    'up_time': '11 days, 23 hours, 16 minutes, 54 seconds'},
                            'RE1': {'last_reboot_reason': '0x200:normal shutdown',
                                    'mastership_state': 'backup',
                                    'model': 'RE-VMX',
                                    'status': 'OK',
                                    'up_time': '11 days, 23 hours, 16 minutes, 41 seconds'},
                            'RE_hw_mi': False,
                            'current_re': ['re0', 'master', 'node', 'fwdd', 'member', 'pfem'],
                            'domain': 'englab.juniper.net',
                            'fqdn': 'R1_re0.englab.juniper.net',
                            'hostname': 'R1_re0',
                            'hostname_info': {'re0': 'R1_re0', 're1': 'R1_re01'},
                            'ifd_style': 'CLASSIC',
                            'junos_info': {'re0': {'object': {'build': None,
                                                              'major': (16, 1),
                                                              'minor': '20160413_0837_aamish',
                                                              'type': 'I'},
                                                   'text': '16.1I20160413_0837_aamish'},
                                           're1': {'object': {'build': None,
                                                              'major': (16, 1),
                                                              'minor': '20160413_0837_aamish',
                                                              'type': 'I'},
                                                   'text': '16.1I20160413_0837_aamish'}},
                            'master': 'RE0',
                            'model': 'MX240',
                            'model_info': {'re0': 'MX240', 're1': 'MX240'},
                            'personality': 'MX',
                            're_info': {'default': {'0': {'last_reboot_reason': '0x200:normal shutdown',
                                                          'mastership_state': 'master',
                                                          'model': 'RE-VMX',
                                                          'status': 'OK'},
                                                    '1': {'last_reboot_reason': '0x200:normal shutdown',
                                                          'mastership_state': 'backup',
                                                          'model': 'RE-VMX',
                                                          'status': 'OK'},
                                                    'default': {'last_reboot_reason': '0x200:normal shutdown',
                                                                'mastership_state': 'master',
                                                                'model': 'RE-VMX',
                                                                'status': 'OK'}}},
                            're_master': {'default': '0'},
                            'serialnumber': 'VMX4eaf',
                            'srx_cluster': None,
                            'switch_style': 'BRIDGE_DOMAIN',
                            'vc_capable': False,
                            'vc_fabric': None,
                            'vc_master': None,
                            'vc_mode': None,
                            'version': '16.1I20160413_0837_aamish',
                            'version_RE0': '16.1I20160413_0837_aamish',
                            'version_RE1': '16.1I20160413_0837_aamish',
                            'version_info': {'build': None,
                                             'major': (16, 1),
                                             'minor': '20160413_0837_aamish',
                                             'type': 'I'},
                            'virtual': True}
            ret['out'] = True
            self.assertEqual(junos.facts_refresh(), ret)

    def test_facts_refresh_exception(self):
        with patch('jnpr.junos.device.Device.facts_refresh') as mock_facts_refresh:
            mock_facts_refresh.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = 'Execution failed due to "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.facts_refresh(), ret)

    def test_facts(self):
        ret = dict()
        ret['facts'] = {'2RE': True,
                        'HOME': '/var/home/regress',
                        'RE0': {'last_reboot_reason': '0x200:normal shutdown',
                                'mastership_state': 'master',
                                'model': 'RE-VMX',
                                'status': 'OK',
                                'up_time': '11 days, 23 hours, 16 minutes, 54 seconds'},
                        'RE1': {'last_reboot_reason': '0x200:normal shutdown',
                                'mastership_state': 'backup',
                                'model': 'RE-VMX',
                                'status': 'OK',
                                'up_time': '11 days, 23 hours, 16 minutes, 41 seconds'},
                        'RE_hw_mi': False,
                        'current_re': ['re0', 'master', 'node', 'fwdd', 'member', 'pfem'],
                        'domain': 'englab.juniper.net',
                        'fqdn': 'R1_re0.englab.juniper.net',
                        'hostname': 'R1_re0',
                        'hostname_info': {'re0': 'R1_re0', 're1': 'R1_re01'},
                        'ifd_style': 'CLASSIC',
                        'junos_info': {'re0': {'object': {'build': None,
                                                          'major': (16, 1),
                                                          'minor': '20160413_0837_aamish',
                                                          'type': 'I'},
                                               'text': '16.1I20160413_0837_aamish'},
                                       're1': {'object': {'build': None,
                                                          'major': (16, 1),
                                                          'minor': '20160413_0837_aamish',
                                                          'type': 'I'},
                                               'text': '16.1I20160413_0837_aamish'}},
                        'master': 'RE0',
                        'model': 'MX240',
                        'model_info': {'re0': 'MX240', 're1': 'MX240'},
                        'personality': 'MX',
                        're_info': {'default': {'0': {'last_reboot_reason': '0x200:normal shutdown',
                                                      'mastership_state': 'master',
                                                      'model': 'RE-VMX',
                                                      'status': 'OK'},
                                                '1': {'last_reboot_reason': '0x200:normal shutdown',
                                                      'mastership_state': 'backup',
                                                      'model': 'RE-VMX',
                                                      'status': 'OK'},
                                                'default': {'last_reboot_reason': '0x200:normal shutdown',
                                                            'mastership_state': 'master',
                                                            'model': 'RE-VMX',
                                                            'status': 'OK'}}},
                        're_master': {'default': '0'},
                        'serialnumber': 'VMX4eaf',
                        'srx_cluster': None,
                        'switch_style': 'BRIDGE_DOMAIN',
                        'vc_capable': False,
                        'vc_fabric': None,
                        'vc_master': None,
                        'vc_mode': None,
                        'version': '16.1I20160413_0837_aamish',
                        'version_RE0': '16.1I20160413_0837_aamish',
                        'version_RE1': '16.1I20160413_0837_aamish',
                        'version_info': {'build': None,
                                         'major': (16, 1),
                                         'minor': '20160413_0837_aamish',
                                         'type': 'I'},
                        'virtual': True}
        ret['out'] = True
        self.assertEqual(junos.facts(), ret)

    def test_facts_exception(self):
        with patch.dict(junos.__proxy__, {'junos.get_serialized_facts': self.raise_exception}):
            ret = dict()
            ret['message'] = 'Could not display facts due to "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.facts(), ret)

    def test_set_hostname_without_args(self):
        ret = dict()
        ret['message'] = 'Please provide the hostname.'
        ret['out'] = False
        self.assertEqual(junos.set_hostname(), ret)

    def test_set_hostname_load_called_with_valid_name(self):
        with patch('jnpr.junos.utils.config.Config.load') as mock_load:
            junos.set_hostname('test-name')
            mock_load.assert_called_with(
                'set system host-name test-name', format='set')

    def test_set_hostname_raise_exception_for_load(self):
        with patch('jnpr.junos.utils.config.Config.load') as mock_load:
            mock_load.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = 'Could not load configuration due to error "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.set_hostname('Test-name'), ret)

    def test_set_hostname_raise_exception_for_commit_check(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check:
            mock_commit_check.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = 'Could not commit check due to error "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.set_hostname('test-name'), ret)

    def test_set_hostname_one_arg_parsed_correctly(self):
        with patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit:
            mock_commit_check.return_value = True
            args = {'comment': 'Committed via salt', '__pub_user': 'root',
                    '__pub_arg': ['test-name', {'comment': 'Committed via salt'}],
                    '__pub_fun': 'junos.set_hostname', '__pub_jid':
                        '20170220210915624885', '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob', '__pub_ret': ''}

            junos.set_hostname('test-name', **args)
            mock_commit.assert_called_with(comment='Committed via salt')

    def test_set_hostname_more_than_one_args_parsed_correctly(self):
        with patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit:
            mock_commit_check.return_value = True
            args = {'comment': 'Committed via salt',
                    '__pub_user': 'root',
                    '__pub_arg': ['test-name',
                                  {'comment': 'Committed via salt',
                                   'confirm': 5}],
                    '__pub_fun': 'junos.set_hostname',
                    '__pub_jid': '20170220210915624885',
                    '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': ''}

            junos.set_hostname('test-name', **args)
            mock_commit.assert_called_with(comment='Committed via salt', confirm=5)

    def test_set_hostname_successful_return_message(self):
        with patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit:
            mock_commit_check.return_value = True
            args = {'comment': 'Committed via salt',
                    '__pub_user': 'root',
                    '__pub_arg': ['test-name',
                                  {'comment': 'Committed via salt'}],
                    '__pub_fun': 'junos.set_hostname',
                    '__pub_jid': '20170220210915624885',
                    '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': ''}
            ret = dict()
            ret['message'] = 'Successfully changed hostname.'
            ret['out'] = True
            self.assertEqual(junos.set_hostname('test-name', **args), ret)

    def test_set_hostname_raise_exception_for_commit(self):
        with patch('jnpr.junos.utils.config.Config.commit') as mock_commit:
            mock_commit.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = 'Successfully loaded host-name but commit failed with "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.set_hostname('test-name'), ret)

    def test_set_hostname_fail_commit_check(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('salt.modules.junos.rollback') as mock_rollback:
            mock_commit_check.return_value = False
            ret = dict()
            ret['out'] = False
            ret['message'] = 'Successfully loaded host-name but pre-commit check failed.'
            self.assertEqual(junos.set_hostname('test'), ret)

    def test_commit_without_args(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit:
            mock_commit.return_value = True
            mock_commit_check.return_value = True
            ret = dict()
            ret['message'] = 'Commit Successful.'
            ret['out'] = True
            self.assertEqual(junos.commit(), ret)

    def test_commit_raise_commit_check_exeception(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check:
            mock_commit_check.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = 'Could not perform commit check due to "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.commit(), ret)

    def test_commit_raise_commit_exception(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit:
            mock_commit_check.return_value = True
            mock_commit.side_effect = self.raise_exception
            ret = dict()
            ret['out'] = False
            ret['message'] = \
                'Commit check succeeded but actual commit failed with "Test exception"'
            self.assertEqual(junos.commit(), ret)

    def test_commit_with_single_argument(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit:
            mock_commit_check.return_value = True
            args = {'__pub_user': 'root',
                    '__pub_arg': [{'sync': True}],
                    'sync': True,
                    '__pub_fun': 'junos.commit',
                    '__pub_jid': '20170221182531323467',
                    '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': ''}
            junos.commit(**args)
            mock_commit.assert_called_with(detail=False, sync=True)

    def test_commit_with_multiple_arguments(
            self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit:
            mock_commit_check.return_value = True
            args = {'comment': 'comitted via salt',
                    '__pub_user': 'root',
                    '__pub_arg': [{'comment': 'comitted via salt',
                                   'confirm': 3,
                                   'detail': True}],
                    'confirm': 3,
                    'detail': True,
                    '__pub_fun': 'junos.commit',
                    '__pub_jid': '20170221182856987820',
                    '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': ''}
            junos.commit(**args)
            mock_commit.assert_called_with(
                comment='comitted via salt', detail=True, confirm=3)

    def test_commit_pyez_commit_returning_false(
            self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit:
            mock_commit.return_value = False
            mock_commit_check.return_value = True
            ret = dict()
            ret['message'] = 'Commit failed.'
            ret['out'] = False
            self.assertEqual(junos.commit(), ret)

    def test_commit_pyez_commit_check_returns_false(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check:
            mock_commit_check.return_value = False
            ret = dict()
            ret['out'] = False
            ret['message'] = 'Pre-commit check failed.'
            self.assertEqual(junos.commit(), ret)

    def test_rollback_exception(self):
        with patch('jnpr.junos.utils.config.Config.rollback') as mock_rollback:
            mock_rollback.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = 'Rollback failed due to "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.rollback(), ret)

    def test_rollback_without_args_success(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.rollback') as mock_rollback:
            mock_commit_check.return_value = True
            mock_rollback.return_value = True
            ret = dict()
            ret['message'] = 'Rollback successful'
            ret['out'] = True
            self.assertEqual(junos.rollback(), ret)

    def test_rollback_without_args_fail(self):
        with patch('jnpr.junos.utils.config.Config.rollback') as mock_rollback:
            mock_rollback.return_value = False
            ret = dict()
            ret['message'] = 'Rollback failed'
            ret['out'] = False
            self.assertEqual(junos.rollback(), ret)

    def test_rollback_with_id(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.rollback') as mock_rollback:
            mock_commit_check.return_value = True
            junos.rollback(id=5)
            mock_rollback.assert_called_with(5)

    def test_rollback_with_id_and_single_arg(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.rollback') as mock_rollback:
            mock_commit_check.return_value = True
            args = {'__pub_user': 'root', '__pub_arg': [2, {'confirm': 2}],
                    'confirm': 2, '__pub_fun': 'junos.rollback',
                    '__pub_jid': '20170221184518526067', '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob', '__pub_ret': ''}
            junos.rollback(2, **args)
            mock_rollback.assert_called_with(2)
            mock_commit.assert_called_with(confirm=2)

    def test_rollback_with_id_and_multiple_args(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.rollback') as mock_rollback:
            mock_commit_check.return_value = True
            args = {'comment': 'Comitted via salt',
                    '__pub_user': 'root',
                    'dev_timeout': 40,
                    '__pub_arg': [2,
                                  {'comment': 'Comitted via salt',
                                   'timeout': 40,
                                   'confirm': 1}],
                    'confirm': 1,
                    '__pub_fun': 'junos.rollback',
                    '__pub_jid': '20170221192708251721',
                    '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': ''}
            junos.rollback(id=2, **args)
            mock_rollback.assert_called_with(2)
            mock_commit.assert_called_with(
                comment='Comitted via salt', confirm=1, timeout=40)

    def test_rollback_with_only_single_arg(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.rollback') as mock_rollback:
            mock_commit_check.return_value = True
            args = {'__pub_user': 'root',
                    '__pub_arg': [{'sync': True}],
                    'sync': True,
                    '__pub_fun': 'junos.rollback',
                    '__pub_jid': '20170221193615696475',
                    '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': ''}
            junos.rollback(**args)
            mock_rollback.assert_called_once_with(0)
            mock_commit.assert_called_once_with(sync=True)

    def test_rollback_with_only_multiple_args_no_id(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.rollback') as mock_rollback:
            mock_commit_check.return_value = True
            args = {'comment': 'Comitted via salt',
                    '__pub_user': 'root',
                    '__pub_arg': [{'comment': 'Comitted via salt',
                                   'confirm': 3,
                                   'sync': True}],
                    'confirm': 3,
                    'sync': True,
                    '__pub_fun': 'junos.rollback',
                    '__pub_jid': '20170221193945996362',
                    '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': ''}
            junos.rollback(**args)
            mock_rollback.assert_called_with(0)
            mock_commit.assert_called_once_with(
                sync=True, confirm=3, comment='Comitted via salt')

    def test_rollback_with_diffs_file_option_when_diff_is_None(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.rollback') as mock_rollback, \
                patch('salt.utils.files.fopen') as mock_fopen, \
                patch('jnpr.junos.utils.config.Config.diff') as mock_diff:
            mock_commit_check.return_value = True
            mock_diff.return_value = 'diff'
            args = {'__pub_user': 'root',
                    '__pub_arg': [{'diffs_file': '/home/regress/diff',
                                   'confirm': 2}],
                    'confirm': 2,
                    '__pub_fun': 'junos.rollback',
                    '__pub_jid': '20170221205153884009',
                    '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': '',
                    'diffs_file': '/home/regress/diff'}
            junos.rollback(**args)
            mock_fopen.assert_called_with('/home/regress/diff', 'w')

    def test_rollback_with_diffs_file_option(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.rollback') as mock_rollback, \
                patch('salt.utils.files.fopen') as mock_fopen, \
                patch('jnpr.junos.utils.config.Config.diff') as mock_diff:
            mock_commit_check.return_value = True
            mock_diff.return_value = None
            args = {'__pub_user': 'root',
                    '__pub_arg': [{'diffs_file': '/home/regress/diff',
                                   'confirm': 2}],
                    'confirm': 2,
                    '__pub_fun': 'junos.rollback',
                    '__pub_jid': '20170221205153884009',
                    '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': '',
                    'diffs_file': '/home/regress/diff'}
            junos.rollback(**args)
            assert not mock_fopen.called

    def test_rollback_commit_check_exception(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.rollback') as mock_rollback:
            mock_commit_check.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = 'Could not commit check due to "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.rollback(), ret)

    def test_rollback_commit_exception(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.rollback') as mock_rollback:
            mock_commit_check.return_value = True
            mock_commit.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = \
                'Rollback successful but commit failed with error "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.rollback(), ret)

    def test_rollback_commit_check_fails(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.rollback') as mock_rollback:
            mock_commit_check.return_value = False
            ret = dict()
            ret['message'] = 'Rollback succesfull but pre-commit check failed.'
            ret['out'] = False
            self.assertEqual(junos.rollback(), ret)

    def test_diff_without_args(self):
        with patch('jnpr.junos.utils.config.Config.diff') as mock_diff:
            junos.diff()
            mock_diff.assert_called_with(rb_id=0)

    def test_diff_with_arg(self):
        with patch('jnpr.junos.utils.config.Config.diff') as mock_diff:
            junos.diff(2)
            mock_diff.assert_called_with(rb_id=2)

    def test_diff_exception(self):
        with patch('jnpr.junos.utils.config.Config.diff') as mock_diff:
            mock_diff.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = 'Could not get diff with error "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.diff(), ret)

    def test_ping_without_args(self):
        ret = dict()
        ret['message'] = 'Please specify the destination ip to ping.'
        ret['out'] = False
        self.assertEqual(junos.ping(), ret)

    def test_ping(self):
        with patch('jnpr.junos.device.Device.execute') as mock_execute:
            junos.ping('1.1.1.1')
            args = mock_execute.call_args
            rpc = '<ping><count>5</count><host>1.1.1.1</host></ping>'
            self.assertEqualXML(args[0][0], rpc)

    def test_ping_ttl(self):
        with patch('jnpr.junos.device.Device.execute') as mock_execute:
            args = {'__pub_user': 'sudo_drajvi',
                    '__pub_arg': ['1.1.1.1',
                                  {'ttl': 3}],
                    '__pub_fun': 'junos.ping',
                    '__pub_jid': '20170306165237683279',
                    '__pub_tgt': 'mac_min',
                    'ttl': 3,
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': ''}
            junos.ping('1.1.1.1', **args)
            exec_args = mock_execute.call_args
            rpc = '<ping><count>5</count><host>1.1.1.1</host><ttl>3</ttl></ping>'
            self.assertEqualXML(exec_args[0][0], rpc)

    def test_ping_exception(self):
        with patch('jnpr.junos.device.Device.execute') as mock_execute:
            mock_execute.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = 'Execution failed due to "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.ping('1.1.1.1'), ret)

    def test_cli_without_args(self):
        ret = dict()
        ret['message'] = 'Please provide the CLI command to be executed.'
        ret['out'] = False
        self.assertEqual(junos.cli(), ret)

    def test_cli_with_format_as_empty_string(self):
        with patch('jnpr.junos.device.Device.cli') as mock_cli:
            junos.cli('show version', '')
            mock_cli.assert_called_with('show version', 'text', warning=False)

    def test_cli(self):
        with patch('jnpr.junos.device.Device.cli') as mock_cli:
            mock_cli.return_vale = 'CLI result'
            ret = dict()
            ret['message'] = 'CLI result'
            ret['out'] = True
            junos.cli('show version')
            mock_cli.assert_called_with('show version', 'text', warning=False)

    def test_cli_format_xml(self):
        with patch('salt.modules.junos.jxmlease.parse') as mock_jxml, \
                patch('salt.modules.junos.etree.tostring') as mock_to_string, \
                patch('jnpr.junos.device.Device.cli') as mock_cli:
            mock_cli.return_value = '<root><a>test</a></root>'
            mock_jxml.return_value = '<root><a>test</a></root>'
            args = {'__pub_user': 'root',
                    '__pub_arg': [{'format': 'xml'}],
                    'format': 'xml',
                    '__pub_fun': 'junos.cli',
                    '__pub_jid': '20170221182531323467',
                    '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': ''}
            ret = dict()
            ret['message'] = '<root><a>test</a></root>'
            ret['out'] = True
            self.assertEqual(junos.cli('show version', **args), ret)
            mock_cli.assert_called_with('show version', 'xml', warning=False)
            mock_to_string.assert_called_once_with('<root><a>test</a></root>')
            assert mock_jxml.called

    def test_cli_exception_in_cli(self):
        with patch('jnpr.junos.device.Device.cli') as mock_cli:
            mock_cli.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = 'Execution failed due to "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.cli('show version'), ret)

    def test_shutdown_without_args(self):
        ret = dict()
        ret['message'] = \
            'Provide either one of the arguments: shutdown or reboot.'
        ret['out'] = False
        self.assertEqual(junos.shutdown(), ret)

    def test_shutdown_with_reboot_args(self):
        with patch('salt.modules.junos.SW.reboot') as mock_reboot:
            ret = dict()
            ret['message'] = 'Successfully powered off/rebooted.'
            ret['out'] = True
            args = {'__pub_user': 'root', '__pub_arg': [{'reboot': True}],
                    'reboot': True, '__pub_fun': 'junos.shutdown',
                    '__pub_jid': '20170222213858582619', '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob', '__pub_ret': ''}
            self.assertEqual(junos.shutdown(**args), ret)
            assert mock_reboot.called

    def test_shutdown_with_poweroff_args(self):
        with patch('salt.modules.junos.SW.poweroff') as mock_poweroff:
            ret = dict()
            ret['message'] = 'Successfully powered off/rebooted.'
            ret['out'] = True
            args = {'__pub_user': 'root', '__pub_arg': [{'shutdown': True}],
                    'reboot': True, '__pub_fun': 'junos.shutdown',
                    '__pub_jid': '20170222213858582619', '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob', '__pub_ret': ''}
            self.assertEqual(junos.shutdown(**args), ret)
            assert mock_poweroff.called

    def test_shutdown_with_shutdown_as_false(self):
        ret = dict()
        ret['message'] = 'Nothing to be done.'
        ret['out'] = False
        args = {'__pub_user': 'root', '__pub_arg': [{'shutdown': False}],
                'reboot': True, '__pub_fun': 'junos.shutdown',
                '__pub_jid': '20170222213858582619', '__pub_tgt': 'mac_min',
                '__pub_tgt_type': 'glob', '__pub_ret': ''}
        self.assertEqual(junos.shutdown(**args), ret)

    def test_shutdown_with_in_min_arg(self):
        with patch('salt.modules.junos.SW.poweroff') as mock_poweroff:
            args = {'__pub_user': 'root',
                    'in_min': 10,
                    '__pub_arg': [{'in_min': 10,
                                   'shutdown': True}],
                    'reboot': True,
                    '__pub_fun': 'junos.shutdown',
                    '__pub_jid': '20170222231445709212',
                    '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': ''}
            junos.shutdown(**args)
            mock_poweroff.assert_called_with(in_min=10)

    def test_shutdown_with_at_arg(self):
        with patch('salt.modules.junos.SW.reboot') as mock_reboot:
            args = {'__pub_user': 'root',
                    '__pub_arg': [{'at': '12:00 pm',
                                   'reboot': True}],
                    'reboot': True,
                    '__pub_fun': 'junos.shutdown',
                    '__pub_jid': '201702276857',
                    'at': '12:00 pm',
                    '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': ''}
            junos.shutdown(**args)
            mock_reboot.assert_called_with(at='12:00 pm')

    def test_shutdown_fail_with_exception(self):
        with patch('salt.modules.junos.SW.poweroff') as mock_poweroff:
            mock_poweroff.side_effect = self.raise_exception
            args = {'__pub_user': 'root', '__pub_arg': [{'shutdown': True}],
                    'shutdown': True, '__pub_fun': 'junos.shutdown',
                    '__pub_jid': '20170222213858582619', '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob', '__pub_ret': ''}
            ret = dict()
            ret['message'] = 'Could not poweroff/reboot beacause "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.shutdown(**args), ret)

    def test_install_config_without_args(self):
        ret = dict()
        ret['message'] = \
            'Please provide the salt path where the configuration is present'
        ret['out'] = False
        self.assertEqual(junos.install_config(), ret)

    def test_install_config_cp_fails(self):
        with patch('os.path.isfile') as mock_isfile:
            mock_isfile.return_value = False
            ret = dict()
            ret['message'] = 'Invalid file path.'
            ret['out'] = False
            self.assertEqual(junos.install_config('path'), ret)

    def test_install_config_file_cp_fails(self):
        with patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 0
            ret = dict()
            ret['message'] = 'Template failed to render'
            ret['out'] = False
            self.assertEqual(junos.install_config('path'), ret)

    def test_install_config(self):
        with patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.diff') as mock_diff, \
                patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = 'test/path/config'
            mock_diff.return_value = 'diff'
            mock_commit_check.return_value = True

            ret = dict()
            ret['message'] = 'Successfully loaded and committed!'
            ret['out'] = True
            self.assertEqual(junos.install_config('actual/path/config.set'), ret)
            mock_load.assert_called_with(path='test/path/config', format='set')

    def test_install_config_xml_file(self):
        with patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.diff') as mock_diff, \
                patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = 'test/path/config'
            mock_diff.return_value = 'diff'
            mock_commit_check.return_value = True

            ret = dict()
            ret['message'] = 'Successfully loaded and committed!'
            ret['out'] = True
            self.assertEqual(junos.install_config('actual/path/config.xml'), ret)
            mock_load.assert_called_with(path='test/path/config', format='xml')

    def test_install_config_text_file(self):
        with patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.diff') as mock_diff, \
                patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = 'test/path/config'
            mock_diff.return_value = 'diff'
            mock_commit_check.return_value = True

            ret = dict()
            ret['message'] = 'Successfully loaded and committed!'
            ret['out'] = True
            self.assertEqual(junos.install_config('actual/path/config'), ret)
            mock_load.assert_called_with(path='test/path/config', format='text')

    def test_install_config_replace(self):
        with patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.diff') as mock_diff, \
                patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = 'test/path/config'
            mock_diff.return_value = 'diff'
            mock_commit_check.return_value = True

            args = {'__pub_user': 'root', '__pub_arg': [{'replace': True}],
                    'replace': True, '__pub_fun': 'junos.install_config',
                    '__pub_jid': '20170222213858582619', '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob', '__pub_ret': ''}

            ret = dict()
            ret['message'] = 'Successfully loaded and committed!'
            ret['out'] = True
            self.assertEqual(
                junos.install_config(
                    'actual/path/config.set',
                    **args),
                ret)
            mock_load.assert_called_with(
                path='test/path/config',
                format='set',
                merge=False)

    def test_install_config_overwrite(self):
        with patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.diff') as mock_diff, \
                patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = 'test/path/config'
            mock_diff.return_value = 'diff'
            mock_commit_check.return_value = True

            args = {'__pub_user': 'root', '__pub_arg': [{'overwrite': True}],
                    'overwrite': True, '__pub_fun': 'junos.install_config',
                    '__pub_jid': '20170222213858582619', '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob', '__pub_ret': ''}

            ret = dict()
            ret['message'] = 'Successfully loaded and committed!'
            ret['out'] = True
            self.assertEqual(
                junos.install_config(
                    'actual/path/config.xml',
                    **args),
                ret)
            mock_load.assert_called_with(
                path='test/path/config',
                format='xml',
                overwrite=True)

    def test_install_config_overwrite_false(self):
        with patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.diff') as mock_diff, \
                patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = 'test/path/config'
            mock_diff.return_value = 'diff'
            mock_commit_check.return_value = True

            args = {'__pub_user': 'root', '__pub_arg': [{'overwrite': False}],
                    'overwrite': False, '__pub_fun': 'junos.install_config',
                    '__pub_jid': '20170222213858582619', '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob', '__pub_ret': ''}

            ret = dict()
            ret['message'] = 'Successfully loaded and committed!'
            ret['out'] = True
            self.assertEqual(
                junos.install_config(
                    'actual/path/config',
                    **args),
                ret)
            mock_load.assert_called_with(
                path='test/path/config', format='text', merge=True)

    def test_install_config_load_causes_exception(self):
        with patch('jnpr.junos.utils.config.Config.diff') as mock_diff, \
                patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = 'test/path/config'
            mock_load.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = 'Could not load configuration due to : "Test exception"'
            ret['format'] = 'set'
            ret['out'] = False
            self.assertEqual(
                junos.install_config(
                    path='actual/path/config.set'), ret)

    def test_install_config_no_diff(self):
        with patch('jnpr.junos.utils.config.Config.diff') as mock_diff, \
                patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = 'test/path/config'
            mock_diff.return_value = None
            ret = dict()
            ret['message'] = 'Configuration already applied!'
            ret['out'] = True
            self.assertEqual(junos.install_config('actual/path/config'), ret)

    def test_install_config_write_diff(self):
        with patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.diff') as mock_diff, \
                patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('salt.utils.files.fopen') as mock_fopen, \
                patch('os.path.getsize') as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = 'test/path/config'
            mock_diff.return_value = 'diff'
            mock_commit_check.return_value = True

            args = {'__pub_user': 'root',
                    '__pub_arg': [{'diffs_file': 'copy/config/here'}],
                    'diffs_file': 'copy/config/here',
                    '__pub_fun': 'junos.install_config',
                    '__pub_jid': '20170222213858582619',
                    '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': ''}

            ret = dict()
            ret['message'] = 'Successfully loaded and committed!'
            ret['out'] = True
            self.assertEqual(
                junos.install_config(
                    'actual/path/config',
                    **args),
                ret)
            mock_fopen.assert_called_with('copy/config/here', 'w')

    def test_install_config_write_diff_exception(self):
        with patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.diff') as mock_diff, \
                patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('salt.utils.files.fopen') as mock_fopen, \
                patch('os.path.getsize') as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = 'test/path/config'
            mock_diff.return_value = 'diff'
            mock_commit_check.return_value = True
            mock_fopen.side_effect = self.raise_exception

            args = {'__pub_user': 'root',
                    '__pub_arg': [{'diffs_file': 'copy/config/here'}],
                    'diffs_file': 'copy/config/here',
                    '__pub_fun': 'junos.install_config',
                    '__pub_jid': '20170222213858582619',
                    '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': ''}

            ret = dict()
            ret['message'] = 'Could not write into diffs_file due to: "Test exception"'
            ret['out'] = False
            self.assertEqual(
                junos.install_config(
                    'actual/path/config',
                    **args),
                ret)
            mock_fopen.assert_called_with('copy/config/here', 'w')

    def test_install_config_commit_params(self):
        with patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.diff') as mock_diff, \
                patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = 'test/path/config'
            mock_diff.return_value = 'diff'
            mock_commit_check.return_value = True
            args = {'comment': 'comitted via salt',
                    '__pub_user': 'root',
                    '__pub_arg': [{'comment': 'comitted via salt',
                                   'confirm': 3}],
                    'confirm': 3,
                    '__pub_fun': 'junos.commit',
                    '__pub_jid': '20170221182856987820',
                    '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': ''}
            ret = dict()
            ret['message'] = 'Successfully loaded and committed!'
            ret['out'] = True
            self.assertEqual(
                junos.install_config(
                    'actual/path/config',
                    **args),
                ret)
            mock_commit.assert_called_with(comment='comitted via salt', confirm=3)

    def test_install_config_commit_check_exception(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.diff') as mock_diff, \
                patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = 'test/path/config'
            mock_diff.return_value = 'diff'
            mock_commit_check.side_effect = self.raise_exception

            ret = dict()
            ret['message'] = 'Commit check threw the following exception: "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.install_config('actual/path/config.xml'), ret)

    def test_install_config_commit_check_fails(self):
        with patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.diff') as mock_diff, \
                patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = 'test/path/config'
            mock_diff.return_value = 'diff'
            mock_commit_check.return_value = False

            ret = dict()
            ret['message'] = 'Loaded configuration but commit check failed.'
            ret['out'] = False
            self.assertEqual(junos.install_config('actual/path/config.xml'), ret)

    def test_install_config_commit_exception(self):
        with patch('jnpr.junos.utils.config.Config.commit') as mock_commit, \
                patch('jnpr.junos.utils.config.Config.commit_check') as mock_commit_check, \
                patch('jnpr.junos.utils.config.Config.diff') as mock_diff, \
                patch('jnpr.junos.utils.config.Config.load') as mock_load, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = 'test/path/config'
            mock_diff.return_value = 'diff'
            mock_commit_check.return_value = True
            mock_commit.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = \
                'Commit check successful but commit failed with "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.install_config('actual/path/config'), ret)

    def test_zeroize(self):
        with patch('jnpr.junos.device.Device.cli') as mock_cli:
            result = junos.zeroize()
            ret = dict()
            ret['out'] = True
            ret['message'] = 'Completed zeroize and rebooted'
            mock_cli.assert_called_once_with('request system zeroize')
            self.assertEqual(result, ret)

    def test_zeroize_throw_exception(self):
        with patch('jnpr.junos.device.Device.cli') as mock_cli:
            mock_cli.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = 'Could not zeroize due to : "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.zeroize(), ret)

    def test_install_os_without_args(self):
        ret = dict()
        ret['message'] = \
            'Please provide the salt path where the junos image is present.'
        ret['out'] = False
        self.assertEqual(junos.install_os(), ret)

    def test_install_os_cp_fails(self):
        with patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_getsize.return_value = 10
            mock_isfile.return_value = False
            ret = dict()
            ret['message'] = 'Invalid image path.'
            ret['out'] = False
            self.assertEqual(junos.install_os('/image/path/'), ret)

    def test_install_os_image_cp_fails(self):
        with patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_getsize.return_value = 0
            mock_isfile.return_value = True
            ret = dict()
            ret['message'] = 'Failed to copy image'
            ret['out'] = False
            self.assertEqual(junos.install_os('/image/path/'), ret)

    def test_install_os(self):
        with patch('jnpr.junos.utils.sw.SW.install') as mock_install, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_getsize.return_value = 10
            mock_isfile.return_value = True
            ret = dict()
            ret['out'] = True
            ret['message'] = 'Installed the os.'
            self.assertEqual(junos.install_os('path'), ret)

    def test_install_os_with_reboot_arg(self):
        with patch('jnpr.junos.utils.sw.SW.install') as mock_install, \
                patch('jnpr.junos.utils.sw.SW.reboot') as mock_reboot, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_getsize.return_value = 10
            mock_isfile.return_value = True
            args = {'__pub_user': 'root', '__pub_arg': [{'reboot': True}],
                    'reboot': True, '__pub_fun': 'junos.install_os',
                    '__pub_jid': '20170222213858582619', '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob', '__pub_ret': ''}
            ret = dict()
            ret['message'] = 'Successfully installed and rebooted!'
            ret['out'] = True
            self.assertEqual(junos.install_os('path', **args), ret)

    def test_install_os_pyez_install_throws_exception(self):
        with patch('jnpr.junos.utils.sw.SW.install') as mock_install, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_getsize.return_value = 10
            mock_isfile.return_value = True
            mock_install.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = 'Installation failed due to: "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.install_os('path'), ret)

    def test_install_os_with_reboot_raises_exception(self):
        with patch('jnpr.junos.utils.sw.SW.install') as mock_install, \
                patch('jnpr.junos.utils.sw.SW.reboot') as mock_reboot, \
                patch('salt.utils.files.safe_rm') as mock_safe_rm, \
                patch('salt.utils.files.mkstemp') as mock_mkstemp, \
                patch('os.path.isfile') as mock_isfile, \
                patch('os.path.getsize') as mock_getsize:
            mock_getsize.return_value = 10
            mock_isfile.return_value = True
            mock_reboot.side_effect = self.raise_exception
            args = {'__pub_user': 'root', '__pub_arg': [{'reboot': True}],
                    'reboot': True, '__pub_fun': 'junos.install_os',
                    '__pub_jid': '20170222213858582619', '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob', '__pub_ret': ''}
            ret = dict()
            ret['message'] = \
                'Installation successful but reboot failed due to : "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.install_os('path', **args), ret)

    def test_file_copy_without_args(self):
        ret = dict()
        ret['message'] = \
            'Please provide the absolute path of the file to be copied.'
        ret['out'] = False
        self.assertEqual(junos.file_copy(), ret)

    def test_file_copy_invalid_src(self):
        with patch('os.path.isfile') as mock_isfile:
            mock_isfile.return_value = False
            ret = dict()
            ret['message'] = 'Invalid source file path'
            ret['out'] = False
            self.assertEqual(junos.file_copy('invalid/file/path', 'file'), ret)

    def test_file_copy_without_dest(self):
        ret = dict()
        ret['message'] = \
            'Please provide the absolute path of the destination where the file is to be copied.'
        ret['out'] = False
        with patch('salt.modules.junos.os.path.isfile') as mck:
            mck.return_value = True
            self.assertEqual(junos.file_copy('/home/user/config.set'), ret)

    def test_file_copy(self):
        with patch('salt.modules.junos.SCP') as mock_scp, \
                patch('os.path.isfile') as mock_isfile:
            mock_isfile.return_value = True
            ret = dict()
            ret['message'] = 'Successfully copied file from test/src/file to file'
            ret['out'] = True
            self.assertEqual(
                junos.file_copy(
                    dest='file',
                    src='test/src/file'),
                ret)

    def test_file_copy_exception(self):
        with patch('salt.modules.junos.SCP') as mock_scp, \
                patch('os.path.isfile') as mock_isfile:
            mock_isfile.return_value = True
            mock_scp.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = 'Could not copy file : "Test exception"'
            ret['out'] = False
            self.assertEqual(
                junos.file_copy(
                    dest='file',
                    src='test/src/file'),
                ret)

    # These test cases test the __virtual__ function, used internally by salt
    # to check if the given module is loadable. This function is not used by
    # an external user.

    def test_virtual_proxy_unavailable(self):
        with patch.dict(junos.__opts__, {}):
            res = (False, 'The junos module could not be '
                          'loaded: junos-eznc or jxmlease or proxy could not be loaded.')
            self.assertEqual(junos.__virtual__(), res)

    def test_virtual_all_true(self):
        with patch.dict(junos.__opts__, {'proxy': 'test'}):
            self.assertEqual(junos.__virtual__(), 'junos')

    def test_rpc_without_args(self):
        ret = dict()
        ret['message'] = 'Please provide the rpc to execute.'
        ret['out'] = False
        self.assertEqual(junos.rpc(), ret)

    def test_rpc_get_config_exception(self):
        with patch('jnpr.junos.device.Device.execute') as mock_execute:
            mock_execute.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = 'RPC execution failed due to "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.rpc('get_config'), ret)

    def test_rpc_get_config_filter(self):
        with patch('jnpr.junos.device.Device.execute') as mock_execute:
            mock_execute.return_value = etree.XML('<reply><rpc/></reply>')
            args = {'__pub_user': 'root',
                    '__pub_arg': ['get-config',
                                  {'filter': '<configuration><system/></configuration>'}],
                    '__pub_fun': 'junos.rpc',
                    '__pub_jid': '20170314162715866528',
                    '__pub_tgt': 'mac_min',
                    '__pub_tgt_type': 'glob',
                    'filter': '<configuration><system/></configuration>',
                    '__pub_ret': ''}
            junos.rpc('get-config', **args)
            exec_args = mock_execute.call_args
            expected_rpc = '<get-configuration dev_timeout="30" ' \
                           'format="xml"><configuration><system/></configuration></get-configuration>'
            self.assertEqualXML(exec_args[0][0], expected_rpc)

    def test_rpc_get_interface_information(self):
        with patch('jnpr.junos.device.Device.execute') as mock_execute:
            junos.rpc('get-interface-information', format='json')
            args = mock_execute.call_args
            expected_rpc = '<get-interface-information format="json"/>'
            self.assertEqualXML(args[0][0], expected_rpc)
            self.assertEqual(args[1], {'dev_timeout': 30})

    def test_rpc_get_interface_information_with_kwargs(self):
        with patch('jnpr.junos.device.Device.execute') as mock_execute:
            args = {'__pub_user': 'root',
                    '__pub_arg': ['get-interface-information',
                                  '',
                                  'text',
                                  {'terse': True,
                                   'interface_name': 'lo0'}],
                    'terse': True,
                    '__pub_fun': 'junos.rpc',
                    '__pub_jid': '20170314160943363563',
                    '__pub_tgt': 'mac_min',
                    'interface_name': 'lo0',
                    '__pub_tgt_type': 'glob',
                    '__pub_ret': ''}
            junos.rpc('get-interface-information', format='text', **args)
            args = mock_execute.call_args
            expected_rpc = (
                    '<get-interface-information format="text">'
                    '<terse/><interface-name>lo0</interface-name></get-interface-information>'
            )
            self.assertEqualXML(etree.tostring(args[0][0]), expected_rpc)

    def test_rpc_get_chassis_inventory_filter_as_arg(self):
        with patch('salt.modules.junos.jxmlease.parse') as mock_jxmlease, \
                patch('salt.modules.junos.etree.tostring') as mock_tostring, \
                patch('salt.modules.junos.logging.Logger.warning') as mock_warning, \
                patch('jnpr.junos.device.Device.execute') as mock_execute:
            junos.rpc(
                'get-chassis-inventory',
                filter='<configuration><system/></configuration>')
            mock_warning.assert_called_with(
                'Filter ignored as it is only used with "get-config" rpc')

    def test_rpc_get_interface_information_exception(self):
        with patch('jnpr.junos.device.Device.execute') as mock_execute:
            mock_execute.side_effect = self.raise_exception
            ret = dict()
            ret['message'] = 'RPC execution failed due to "Test exception"'
            ret['out'] = False
            self.assertEqual(junos.rpc('get_interface_information'), ret)

    def test_rpc_write_file_format_text(self):
        with patch('jnpr.junos.device.Device.execute') as mock_execute:
            mock_execute.return_value = etree.XML(
                '<rpc-reply>text rpc reply</rpc-reply>')
            m = mock_open()
            with patch('salt.utils.files.fopen', m, create=True):
                junos.rpc('get-chassis-inventory', '/path/to/file', 'text')
                handle = m()
                handle.write.assert_called_with('text rpc reply')

    def test_rpc_write_file_format_json(self):
        with patch('jnpr.junos.device.Device.execute') as mock_execute, \
                patch('salt.utils.json.dumps') as mock_dumps:
            mock_dumps.return_value = 'json rpc reply'
            m = mock_open()
            with patch('salt.utils.files.fopen', m, create=True):
                junos.rpc('get-chassis-inventory', '/path/to/file', format='json')
                handle = m()
                handle.write.assert_called_with('json rpc reply')

    def test_rpc_write_file(self):
        with patch('salt.modules.junos.jxmlease.parse') as mock_parse, \
                patch('salt.modules.junos.etree.tostring') as mock_tostring, \
                patch('jnpr.junos.device.Device.execute') as mock_execute:
            mock_tostring.return_value = 'xml rpc reply'
            m = mock_open()
            with patch('salt.utils.files.fopen', m, create=True):
                junos.rpc('get-chassis-inventory', '/path/to/file')
                handle = m()
                handle.write.assert_called_with('xml rpc reply')
