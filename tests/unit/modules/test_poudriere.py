# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

import os

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    mock_open,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.poudriere as poudriere

# Globals
poudriere.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PoudriereTestCase(TestCase):
    '''
    Test cases for salt.modules.poudriere
    '''
    # 'is_jail' function tests: 1

    @patch('salt.modules.poudriere._check_config_exists',
           MagicMock(return_value=True))
    def test_is_jail(self):
        '''
        Test if it return True if jail exists False if not.
        '''
        mock = MagicMock(return_value='salt stack')
        with patch.dict(poudriere.__salt__, {'cmd.run': mock}):
            self.assertTrue(poudriere.is_jail('salt'))

            self.assertFalse(poudriere.is_jail('SALT'))

    # 'make_pkgng_aware' function tests: 1

    def test_make_pkgng_aware(self):
        '''
        Test if it make jail ``jname`` pkgng aware.
        '''
        ret1 = 'Could not create or find required directory /tmp/salt'
        ret2 = 'Looks like file /tmp/salt/salt-make.conf could not be created'
        ret3 = {'changes': 'Created /tmp/salt/salt-make.conf'}
        mock = MagicMock(return_value='/tmp/salt')
        mock_true = MagicMock(return_value=True)
        with patch.dict(poudriere.__salt__, {'config.option': mock,
                                             'file.write': mock_true}):
            with patch.object(os.path, 'isdir', MagicMock(return_value=False)):
                with patch.object(os, 'makedirs', mock_true):
                    self.assertEqual(poudriere.make_pkgng_aware('salt'), ret1)

            with patch.object(os.path, 'isdir', mock_true):
                self.assertEqual(poudriere.make_pkgng_aware('salt'), ret2)

                with patch.object(os.path, 'isfile', mock_true):
                    self.assertDictEqual(poudriere.make_pkgng_aware('salt'),
                                         ret3)

    # 'parse_config' function tests: 1

    @patch('salt.utils.fopen', mock_open())
    def test_parse_config(self):
        '''
        Test if it returns a dict of poudriere main configuration definitions.
        '''
        mock = MagicMock(return_value='/tmp/salt')
        with patch.dict(poudriere.__salt__, {'config.option': mock}):
            with patch.object(poudriere, '_check_config_exists',
                              MagicMock(side_effect=[True, False])):
                self.assertDictEqual(poudriere.parse_config(), {})

                self.assertEqual(poudriere.parse_config(),
                                 'Could not find /tmp/salt on file system')

    # 'version' function tests: 1

    def test_version(self):
        '''
        Test if it return poudriere version.
        '''
        mock = MagicMock(return_value='9.0-RELEASE')
        with patch.dict(poudriere.__salt__, {'cmd.run': mock}):
            self.assertEqual(poudriere.version(), '9.0-RELEASE')

    # 'list_jails' function tests: 1

    @patch('salt.modules.poudriere._check_config_exists',
           MagicMock(return_value=True))
    def test_list_jails(self):
        '''
        Test if it return a list of current jails managed by poudriere.
        '''
        mock = MagicMock(return_value='salt stack')
        with patch.dict(poudriere.__salt__, {'cmd.run': mock}):
            self.assertListEqual(poudriere.list_jails(), ['salt stack'])

    # 'list_ports' function tests: 1

    @patch('salt.modules.poudriere._check_config_exists',
           MagicMock(return_value=True))
    def test_list_ports(self):
        '''
        Test if it return a list of current port trees managed by poudriere.
        '''
        mock = MagicMock(return_value='salt stack')
        with patch.dict(poudriere.__salt__, {'cmd.run': mock}):
            self.assertListEqual(poudriere.list_ports(), ['salt stack'])

    # 'create_jail' function tests: 1

    @patch('salt.modules.poudriere._check_config_exists',
           MagicMock(return_value=True))
    def test_create_jail(self):
        '''
        Test if it creates a new poudriere jail if one does not exist.
        '''
        mock_stack = MagicMock(return_value='90amd64 stack')
        mock_true = MagicMock(return_value=True)
        with patch.dict(poudriere.__salt__, {'cmd.run': mock_stack}):
            self.assertEqual(poudriere.create_jail('90amd64', 'amd64'),
                             '90amd64 already exists')

            with patch.object(poudriere, 'make_pkgng_aware', mock_true):
                self.assertEqual(poudriere.create_jail('80amd64', 'amd64'),
                                 'Issue creating jail 80amd64')

        with patch.object(poudriere, 'make_pkgng_aware', mock_true):
            with patch.object(poudriere, 'is_jail',
                              MagicMock(side_effect=[False, True])):
                with patch.dict(poudriere.__salt__, {'cmd.run': mock_stack}):
                    self.assertEqual(poudriere.create_jail('80amd64', 'amd64'),
                                     'Created jail 80amd64')

    # 'update_jail' function tests: 1

    @patch('salt.modules.poudriere._check_config_exists',
           MagicMock(return_value=True))
    def test_update_jail(self):
        '''
        Test if it run freebsd-update on `name` poudriere jail.
        '''
        mock = MagicMock(return_value='90amd64 stack')
        with patch.dict(poudriere.__salt__, {'cmd.run': mock}):
            self.assertEqual(poudriere.update_jail('90amd64'), '90amd64 stack')

            self.assertEqual(poudriere.update_jail('80amd64'),
                             'Could not find jail 80amd64')

    # 'delete_jail' function tests: 1

    @patch('salt.modules.poudriere._check_config_exists',
           MagicMock(return_value=True))
    def test_delete_jail(self):
        '''
        Test if it deletes poudriere jail with `name`.
        '''
        ret = 'Looks like there was an issue deleteing jail             90amd64'
        mock_stack = MagicMock(return_value='90amd64 stack')
        with patch.dict(poudriere.__salt__, {'cmd.run': mock_stack}):
            self.assertEqual(poudriere.delete_jail('90amd64'), ret)

            self.assertEqual(poudriere.delete_jail('80amd64'),
                             'Looks like jail 80amd64 has not been created')

        ret1 = 'Deleted jail "80amd64" but was unable to remove jail make file'
        with patch.object(poudriere, 'is_jail',
                          MagicMock(side_effect=[True, False, True, False])):
            with patch.dict(poudriere.__salt__, {'cmd.run': mock_stack}):
                with patch.object(poudriere, '_config_dir',
                                  MagicMock(return_value='/tmp/salt')):
                    self.assertEqual(poudriere.delete_jail('80amd64'),
                                     'Deleted jail 80amd64')

                    with patch.object(os.path, 'isfile',
                                      MagicMock(return_value=True)):
                        self.assertEqual(poudriere.delete_jail('80amd64'), ret1)

    # 'create_ports_tree' function tests: 1

    @patch('salt.modules.poudriere._check_config_exists',
           MagicMock(return_value=True))
    def test_create_ports_tree(self):
        '''
        Test if it not working need to run portfetch non interactive.
        '''
        mock = MagicMock(return_value='salt stack')
        with patch.dict(poudriere.__salt__, {'cmd.run': mock}):
            self.assertEqual(poudriere.create_ports_tree(), 'salt stack')

    # 'update_ports_tree' function tests: 1

    @patch('salt.modules.poudriere._check_config_exists',
           MagicMock(return_value=True))
    def test_update_ports_tree(self):
        '''
        Test if it updates the ports tree, either the default
        or the `ports_tree` specified.
        '''
        mock = MagicMock(return_value='salt stack')
        with patch.dict(poudriere.__salt__, {'cmd.run': mock}):
            self.assertEqual(poudriere.update_ports_tree('staging'),
                             'salt stack')

    # 'bulk_build' function tests: 1

    @patch('salt.modules.poudriere._check_config_exists',
           MagicMock(return_value=True))
    def test_bulk_build(self):
        '''
        Test if it run bulk build on poudriere server.
        '''
        ret = 'Could not find file /root/pkg_list on filesystem'
        mock = MagicMock(return_value='salt stack')
        with patch.dict(poudriere.__salt__, {'cmd.run': mock}):
            self.assertEqual(poudriere.bulk_build('90amd64', '/root/pkg_list'),
                             ret)

            with patch.object(os.path, 'isfile', MagicMock(return_value=True)):
                self.assertEqual(poudriere.bulk_build('90amd64',
                                                      '/root/pkg_list'),
                                 'Could not find jail 90amd64')

        ret = ('There may have been an issue building '
               'packages dumping output: 90amd64 stack')
        with patch.object(os.path, 'isfile', MagicMock(return_value=True)):
            mock = MagicMock(return_value='90amd64 stack packages built')
            with patch.dict(poudriere.__salt__, {'cmd.run': mock}):
                self.assertEqual(poudriere.bulk_build('90amd64',
                                                      '/root/pkg_list'),
                                 '90amd64 stack packages built')

            mock = MagicMock(return_value='90amd64 stack')
            with patch.dict(poudriere.__salt__, {'cmd.run': mock}):
                self.assertEqual(poudriere.bulk_build('90amd64',
                                                      '/root/pkg_list'), ret)
