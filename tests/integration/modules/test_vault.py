# -*- coding: utf-8 -*-
'''
Integration tests for the vault execution module
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import inspect
import time

# Import Salt Testing Libs
from tests.support.unit import skipIf
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest, flaky
from tests.support.paths import FILES

# Import Salt Libs
import salt.utils.path

import logging
log = logging.getLogger(__name__)


@destructiveTest
@skipIf(not salt.utils.path.which('dockerd'), 'Docker not installed')
@skipIf(not salt.utils.path.which('vault'), 'Vault not installed')
class VaultTestCase(ModuleCase):
    '''
    Test vault module
    '''
    count = 0

    def setUp(self):
        '''
        SetUp vault container
        '''
        if self.count == 0:
            config = '{"backend": {"file": {"path": "/vault/file"}}, "default_lease_ttl": "168h", "max_lease_ttl": "720h"}'
            self.run_state('docker_image.present', name='vault', tag='0.9.6')
            self.run_state(
                'docker_container.running',
                name='vault',
                image='vault:0.9.6',
                port_bindings='8200:8200',
                environment={
                    'VAULT_DEV_ROOT_TOKEN_ID': 'testsecret',
                    'VAULT_LOCAL_CONFIG': config,
                },
                cap_add='IPC_LOCK',
            )
            time.sleep(5)
            ret = self.run_function(
                'cmd.retcode',
                cmd='/usr/local/bin/vault login token=testsecret',
                env={'VAULT_ADDR': 'http://127.0.0.1:8200'},
            )
            if ret != 0:
                self.skipTest('unable to login to vault')
            ret = self.run_function(
                'cmd.retcode',
                cmd='/usr/local/bin/vault policy write testpolicy {0}/vault.hcl'.format(FILES),
                env={'VAULT_ADDR': 'http://127.0.0.1:8200'},
            )
            if ret != 0:
                self.skipTest('unable to assign policy to vault')
        self.count += 1

    def tearDown(self):
        '''
        TearDown vault container
        '''
        def count_tests(funcobj):
            return inspect.ismethod(funcobj) and funcobj.__name__.startswith('test_')
        numtests = len(inspect.getmembers(VaultTestCase, predicate=count_tests))
        if self.count >= numtests:
            self.run_state('docker_container.stopped', name='vault')
            self.run_state('docker_container.absent', name='vault')
            self.run_state('docker_image.absent', name='vault', force=True)

    @flaky
    def test_write_read_secret(self):
        write_return = self.run_function('vault.write_secret', path='secret/my/secret', user='foo', password='bar')
        self.assertTrue(write_return)
        assert self.run_function('vault.read_secret', arg=['secret/my/secret']) == {'password': 'bar', 'user': 'foo'}
        assert self.run_function('vault.read_secret', arg=['secret/my/secret', 'user']) == 'foo'

    @flaky
    def test_write_raw_read_secret(self):
        assert self.run_function('vault.write_raw',
                                 path='secret/my/secret2',
                                 raw={"user2": "foo2", "password2": "bar2"}) is True
        assert self.run_function('vault.read_secret', arg=['secret/my/secret2']) == {'password2': 'bar2', 'user2': 'foo2'}

    @flaky
    def test_delete_secret(self):
        assert self.run_function('vault.write_secret', path='secret/my/secret', user='foo', password='bar') is True
        assert self.run_function('vault.delete_secret', arg=['secret/my/secret']) is True

    @flaky
    def test_list_secrets(self):
        assert self.run_function('vault.write_secret', path='secret/my/secret', user='foo', password='bar') is True
        assert self.run_function('vault.list_secrets', arg=['secret/my/']) == {'keys': ['secret']}

@destructiveTest
@skipIf(not salt.utils.path.which('dockerd'), 'Docker not installed')
@skipIf(not salt.utils.path.which('vault'), 'Vault not installed')
class VaultTestCaseCurrent(ModuleCase):
    '''
    Test vault module against current vault
    '''
    count = 0

    def setUp(self):
        '''
        SetUp vault container
        '''
        if self.count == 0:
            config = '{"backend": {"file": {"path": "/vault/file"}}, "default_lease_ttl": "168h", "max_lease_ttl": "720h"}'
            self.run_state('docker_image.present', name='vault', tag='latest')
            self.run_state(
                'docker_container.running',
                name='vault',
                image='vault:latest',
                port_bindings='8200:8200',
                environment={
                    'VAULT_DEV_ROOT_TOKEN_ID': 'testsecret',
                    'VAULT_LOCAL_CONFIG': config,
                },
                cap_add='IPC_LOCK',
            )
            time.sleep(5)
            ret = self.run_function(
                'cmd.retcode',
                cmd='/usr/local/bin/vault login token=testsecret',
                env={'VAULT_ADDR': 'http://127.0.0.1:8200'},
            )
            if ret != 0:
                self.skipTest('unable to login to vault')
            ret = self.run_function(
                'cmd.retcode',
                cmd='/usr/local/bin/vault policy write testpolicy {0}/vault.hcl'.format(FILES),
                env={'VAULT_ADDR': 'http://127.0.0.1:8200'},
            )
            if ret != 0:
                self.skipTest('unable to assign policy to vault')
        self.count += 1

    def tearDown(self):
        '''
        TearDown vault container
        '''
        def count_tests(funcobj):
            return inspect.ismethod(funcobj) and funcobj.__name__.startswith('test_')
        numtests = len(inspect.getmembers(VaultTestCase, predicate=count_tests))
        if self.count >= numtests:
            self.run_state('docker_container.stopped', name='vault')
            self.run_state('docker_container.absent', name='vault')
            self.run_state('docker_image.absent', name='vault', force=True)

    @flaky
    def test_write_read_secret_kv2(self):
        write_return = self.run_function('vault.write_secret', path='secret/my/secret', user='foo', password='bar')
        # write_secret output:
        # {'created_time': '2020-01-12T23:09:34.571294241Z', 'destroyed': False,
        # 'version': 1, 'deletion_time': ''}
        expected_write = {'destroyed': False, 'deletion_time': ''}
        self.assertDictContainsSubset(expected_write, write_return)

        read_return = self.run_function('vault.read_secret', arg=['secret/my/secret'])
        # read_secret output:
        # {'data': {'password': 'bar', 'user': 'foo'},
        # 'metadata': {'created_time': '2020-01-12T23:07:18.829326918Z', 'destroyed': False,
        # 'version': 1, 'deletion_time': ''}}
        expected_read = {'data': {'password': 'bar', 'user': 'foo'}}
        self.assertDictContainsSubset(expected_read, read_return)

        read_return = self.run_function('vault.read_secret', arg=['secret/my/secret', 'user'])
        self.assertEqual(read_return, 'foo')

    @flaky
    def test_write_raw_read_secret_kv2(self):
        write_return = self.run_function('vault.write_raw',
                                           path='secret/my/secret2',
                                           raw={"user2": "foo2", "password2": "bar2"})
        expected_write = {'destroyed': False, 'deletion_time': ''}
        self.assertDictContainsSubset(expected_write, write_return)

        read_return = self.run_function('vault.read_secret', arg=['secret/my/secret2'])
        expected_read = {'data': {'password2': 'bar2', 'user2': 'foo2'}}
        self.assertDictContainsSubset(expected_read, read_return)

    @flaky
    def test_delete_secret_kv2(self):
        write_return = self.run_function('vault.write_secret', path='secret/my/secret3', user3='foo3', password3='bar3')
        expected_write = {'destroyed': False, 'deletion_time': ''}
        self.assertDictContainsSubset(expected_write, write_return)

        delete_return = self.run_function('vault.delete_secret', arg=['secret/my/secret3'])
        log.info('XXXX delete_return: %s', delete_return)
        self.assertTrue(delete_return)
        read_return = self.run_function('vault.read_secret', arg=['secret/my/secret3'])
        log.info('ZZZZ read after delete: %s', read_return)

    @flaky
    def test_destroy_secret_kv2(self):
        write_return = self.run_function('vault.write_secret', path='secret/my/secret3', user3='foo3', password3='bar3')
        expected_write = {'destroyed': False, 'deletion_time': ''}
        self.assertDictContainsSubset(expected_write, write_return)

        destroy_return = self.run_function('vault.destroy_secret', arg=['secret/my/secret3'])
        log.info('AAAA destroy_return: %s', destroy_return)
        self.assertTrue(destroy_return)
        read_return = self.run_function('vault.read_secret', arg=['secret/my/secret3'])
        log.info('BBBB read after destroy: %s', read_return)

    @flaky
    def test_list_secrets_kv2(self):
        write_return = self.run_function('vault.write_secret', path='secret/my/secret', user='foo', password='bar')
        expected_write = {'destroyed': False, 'deletion_time': ''}
        self.assertDictContainsSubset(expected_write, write_return)

        list_return = self.run_function('vault.list_secrets', arg=['secret/my/'])
        log.info('YYYY list_return: %s', list_return)
        self.assertDictContainsSubset({'keys': ['secret']}, list_return)
