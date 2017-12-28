# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Gareth J. Greenaway <gareth@saltstack.com>`
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
        _table_attrs_results = [u'pid',
                                u'uuid',
                                u'instance_id',
                                u'version',
                                u'config_hash',
                                u'config_valid',
                                u'extensions',
                                u'build_platform',
                                u'build_distro',
                                u'start_time',
                                u'watcher']

        _os_query_results = {'data': [{u'version': u'2.6.1'}], 'result': True}

        with patch.object(osquery, '_table_attrs',
                          MagicMock(return_value=_table_attrs_results)):
            with patch.object(osquery, '_osquery',
                              MagicMock(return_value=_os_query_results)):
                self.assertEqual(osquery.version(), u'2.6.1')

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
        _table_attrs_results = [u'name',
                                u'version',
                                u'source',
                                u'size',
                                u'arch',
                                u'revision']

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
        _table_attrs_results = [u'address',
                                u'name',
                                u'size',
                                u'status',
                                u'used_by']

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
        _table_attrs_results = [u'pid',
                                u'uuid',
                                u'instance_id',
                                u'version',
                                u'config_hash',
                                u'config_valid',
                                u'extensions',
                                u'build_platform',
                                u'build_distro',
                                u'start_time',
                                u'watcher']

        _os_query_results = {'data': [
            {u'build_platform': u'ubuntu', u'start_time': u'1514484833',
             u'uuid': u'D31FD400-7277-11E3-ABA6-B8AEED7E173B',
             u'build_distro': u'xenial',
             u'pid': u'24288',
             u'watcher': u'-1',
             u'instance_id': u'dff196b0-5c91-4105-962b-28660d7aa282',
             u'version': u'2.6.1',
             u'extensions': u'inactive',
             u'config_valid': u'0',
             u'config_hash': u''}],
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
        _table_attrs_results = [u'pid',
                                u'uuid',
                                u'instance_id',
                                u'version',
                                u'config_hash',
                                u'config_valid',
                                u'extensions',
                                u'build_platform',
                                u'build_distro',
                                u'start_time',
                                u'watcher']

        _os_query_results = {'data': [
            {u'build_platform': u'ubuntu', u'start_time': u'1514484833'}],
            'result': True}

        with patch.object(osquery, '_table_attrs',
                          MagicMock(return_value=_table_attrs_results)):
            with patch.object(osquery, '_osquery',
                              MagicMock(return_value=_os_query_results)):
                with patch.dict(osquery.__grains__, {'os_family': 'Debian'}):
                    self.assertEqual(osquery.osquery_info(attrs=['build_platform',
                                                                 'start_time']),
                                     _os_query_results)
