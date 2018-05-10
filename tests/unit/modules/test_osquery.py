# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Gareth J. Greenaway <gareth@saltstack.com>`
'''

# Import Python Libs
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
import salt.modules.osquery as osquery


@skipIf(NO_MOCK, NO_MOCK_REASON)
class OSQueryTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.iptables
    '''
    def setup_loader_modules(self):
        return {osquery: {}}

    def test_version(self):
        '''
        Test the version returned from OSQuery
        '''
        _table_attrs_results = ['pid',
                                'uuid',
                                'instance_id',
                                'version',
                                'config_hash',
                                'config_valid',
                                'extensions',
                                'build_platform',
                                'build_distro',
                                'start_time',
                                'watcher']

        _os_query_results = {'data': [{'version': '2.6.1'}], 'result': True}

        with patch.object(osquery, '_table_attrs',
                          MagicMock(return_value=_table_attrs_results)):
            with patch.object(osquery, '_osquery',
                              MagicMock(return_value=_os_query_results)):
                self.assertEqual(osquery.version(), '2.6.1')

    def test_deb_packages(self):
        '''
        Test the results returned from the deb_packages function
        '''
        _os_query_results = {'data': [
            {'arch': 'amd64', 'name': 'accountsservice', 'revision': '1',
             'size': '451', 'source': '', 'version': '0.6.45-1'},
            {'arch': 'amd64', 'name': 'acetoneiso', 'revision': '2+b2',
             'size': '1820', 'source': 'acetoneiso (2.4-2)',
             'version': '2.4-2+b2'},
            {'arch': 'amd64', 'name': 'acl', 'revision': '3+b1',
             'size': '200', 'source': 'acl (2.2.52-3)',
             'version': '2.2.52-3+b1'},
            {'arch': 'amd64', 'name': 'adb', 'revision': '2', 'size': '189',
             'source': 'android-platform-system-core',
             'version': '1: 7.0.0+r33-2'}],
            'result': True
        }
        with patch.object(osquery, '_osquery',
                          MagicMock(return_value=_os_query_results)):
            with patch.dict(osquery.__grains__, {'os_family': 'Debian'}):
                self.assertEqual(osquery.deb_packages(), _os_query_results)

    def test_deb_packages_with_attrs(self):
        '''
        Test the results returned from the deb_packages function
        with attributes
        '''
        _table_attrs_results = ['name',
                                'version',
                                'source',
                                'size',
                                'arch',
                                'revision']

        _os_query_results = {'data': [
            {'name': 'accountsservice', 'version': '0.6.45-1'},
            {'name': 'acetoneiso', 'version': '2.4-2+b2'},
            {'name': 'acl', 'version': '2.2.52-3+b1'},
            {'name': 'adb', 'version': '1: 7.0.0+r33-2'}],
            'result': True}

        with patch.object(osquery, '_table_attrs',
                          MagicMock(return_value=_table_attrs_results)):
            with patch.object(osquery, '_osquery',
                              MagicMock(return_value=_os_query_results)):
                with patch.dict(osquery.__grains__, {'os_family': 'Debian'}):
                    self.assertEqual(osquery.deb_packages(attrs=['name',
                                                                 'version']),
                                     _os_query_results)

    def test_kernel_modules(self):
        '''
        Test the results returned from the kernel_modules function
        '''
        _os_query_results = {'data': [
            {'address': '0xffffffffc14f2000', 'name': 'nls_utf8',
             'size': '16384', 'status': 'Live', 'used_by': '-'},
            {'address': '0xffffffffc1599000', 'name': 'udf',
             'size': '90112', 'status': 'Live', 'used_by': '-'},
            {'address': '0xffffffffc14b5000', 'name': 'crc_itu_t',
             'size': '16384', 'status': 'Live', 'used_by': 'udf'}],
            'result': True
        }
        with patch.object(osquery, '_osquery',
                          MagicMock(return_value=_os_query_results)):
            with patch.dict(osquery.__grains__, {'os_family': 'Debian'}):
                self.assertEqual(osquery.kernel_modules(),
                                 _os_query_results)

    def test_kernel_modules_with_attrs(self):
        '''
        Test the results returned from the kernel_modules function
        with attributes
        '''
        _table_attrs_results = ['address',
                                'name',
                                'size',
                                'status',
                                'used_by']

        _os_query_results = {'data': [
            {'name': 'nls_utf8', 'status': 'Live'},
            {'name': 'udf', 'status': 'Live'},
            {'name': 'crc_itu_t', 'status': 'Live'}],
            'result': True
        }
        with patch.object(osquery, '_table_attrs',
                          MagicMock(return_value=_table_attrs_results)):
            with patch.object(osquery, '_osquery',
                              MagicMock(return_value=_os_query_results)):
                with patch.dict(osquery.__grains__, {'os_family': 'Debian'}):
                    self.assertEqual(osquery.kernel_modules(attrs=['name',
                                                                   'status']),
                                     _os_query_results)

    def test_osquery_info(self):
        '''
        Test the results returned from the kernel_modules function
        with attributes
        '''
        _table_attrs_results = ['pid',
                                'uuid',
                                'instance_id',
                                'version',
                                'config_hash',
                                'config_valid',
                                'extensions',
                                'build_platform',
                                'build_distro',
                                'start_time',
                                'watcher']

        _os_query_results = {'data': [
            {'build_platform': 'ubuntu', 'start_time': '1514484833',
             'uuid': 'D31FD400-7277-11E3-ABA6-B8AEED7E173B',
             'build_distro': 'xenial',
             'pid': '24288',
             'watcher': '-1',
             'instance_id': 'dff196b0-5c91-4105-962b-28660d7aa282',
             'version': '2.6.1',
             'extensions': 'inactive',
             'config_valid': '0',
             'config_hash': ''}],
            'result': True}

        with patch.object(osquery, '_table_attrs',
                          MagicMock(return_value=_table_attrs_results)):
            with patch.object(osquery, '_osquery',
                              MagicMock(return_value=_os_query_results)):
                with patch.dict(osquery.__grains__, {'os_family': 'Debian'}):
                    self.assertEqual(osquery.osquery_info(),
                                     _os_query_results)

    def test_osquery_info_with_attrs(self):
        '''
        Test the results returned from the kernel_modules function
        with attributes
        '''
        _table_attrs_results = ['pid',
                                'uuid',
                                'instance_id',
                                'version',
                                'config_hash',
                                'config_valid',
                                'extensions',
                                'build_platform',
                                'build_distro',
                                'start_time',
                                'watcher']

        _os_query_results = {'data': [
            {'build_platform': 'ubuntu', 'start_time': '1514484833'}],
            'result': True}

        with patch.object(osquery, '_table_attrs',
                          MagicMock(return_value=_table_attrs_results)):
            with patch.object(osquery, '_osquery',
                              MagicMock(return_value=_os_query_results)):
                with patch.dict(osquery.__grains__, {'os_family': 'Debian'}):
                    self.assertEqual(osquery.osquery_info(attrs=['build_platform', 'start_time']),
                                     _os_query_results)
