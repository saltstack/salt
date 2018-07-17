# -*- coding: utf-8 -*-
'''
Integration tests for the vault modules
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.unit import skipIf
from tests.support.case import ModuleCase, ShellCase
from tests.support.helpers import destructiveTest
from tests.support.paths import FILES

# Import Salt Libs
import salt.utils.path


@destructiveTest
@skipIf(not salt.utils.path.which('dockerd'), 'Docker not installed')
@skipIf(not salt.utils.path.which('vault'), 'Vault not installed')
class VaultTestCase(ModuleCase, ShellCase):
    '''
    Test vault module
    '''
    def setUp(self):
        '''
        '''
        config = '{"backend": {"file": {"path": "/vault/file"}}, "default_lease_ttl": "168h", "max_lease_ttl": "720h"}'
        self.run_state('docker_image.present', name='vault', tag='0.9.6')
        ret = self.run_state(
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
        ret = self.run_function(
            'cmd.run',
            cmd='vault login token=testsecret'.format(FILES),
            env={'VAULT_ADDR': 'http://127.0.0.1:8200'},
        )
        ret = self.run_function(
            'cmd.run',
            cmd='vault policy write testpolicy {0}/vault.hcl'.format(FILES),
            env={'VAULT_ADDR': 'http://127.0.0.1:8200'},
        )

    def tearDown(self):
        self.run_state('docker_container.stopped', name='vault')
        self.run_state('docker_container.absent', name='vault')
        self.run_state('docker_image.absent', name='vault', force=True)

    def test_sdb(self):
        assert self.run_function('sdb.set', uri='sdb://sdbvault/secret/test/test_sdb/foo', value='bar') is True
        assert self.run_function('sdb.get', arg=['sdb://sdbvault/secret/test/test_sdb/foo']) == 'bar'

    def test_sdb_runner(self):
        assert self.run_run('sdb.set sdb://sdbvault/secret/test/test_sdb_runner/foo bar') == ['True']
        assert self.run_run('sdb.get sdb://sdbvault/secret/test/test_sdb_runner/foo') == ['bar']

    def test_config(self):
        assert self.run_function('sdb.set', uri='sdb://sdbvault/secret/test/test_pillar_sdb/foo', value='bar') is True
        assert self.run_function('config.get', arg=['test_vault_pillar_sdb']) == 'bar'
