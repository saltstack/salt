# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)
from tests.support import mixins
from tests.support.unit import skipIf, TestCase
from tests.support.runtests import RUNTIME_VARS

# Import Salt Libs
import salt.config
import salt.loader
import salt.roster.sshknownhosts as sshknownhosts

_ALL = {
    'server1': {'host': 'server1'},
    'server2': {'host': 'server2'},
    'server3.local': {'host': 'server3.local'},
    'eu-mysql-1.local': {'host': 'eu-mysql-1.local'},
    'eu-mysql-2': {'host': 'eu-mysql-2'},
    'eu-mysql-2.local': {'host': 'eu-mysql-2.local'}
}

_TEST_GLOB = {
    'server1': {'host': 'server1'},
    'server2': {'host': 'server2'},
    'server3.local': {'host': 'server3.local'}
}

_TEST_PCRE = {
    'eu-mysql-2': {'host': 'eu-mysql-2'}
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SSHKnownHostsRosterTestCase(TestCase, mixins.LoaderModuleMockMixin):

    @classmethod
    def setUpClass(cls):
        cls.tests_dir = os.path.join(RUNTIME_VARS.TESTS_DIR, 'unit/files/rosters/sshknownhosts/')
        cls.opts = {'ssh_known_hosts_file': 'known_hosts'}

    @classmethod
    def tearDownClass(cls):
        delattr(cls, 'tests_dir')
        delattr(cls, 'opts')

    def setup_loader_modules(self):
        opts = salt.config.master_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'master'))
        utils = salt.loader.utils(opts)
        runner = salt.loader.runner(opts, utils=utils)

        return {
            sshknownhosts: {
                '__utils__': utils,
                '__opts__': {},
                '__runner__': runner
            }
        }

    @skipIf(True, 'WAR ROOM TEMPORARY SKIP')
    def test_all(self):
        self.opts['ssh_known_hosts_file'] = os.path.join(self.tests_dir, 'known_hosts')
        with patch.dict(sshknownhosts.__opts__, self.opts):
            targets = sshknownhosts.targets(tgt='*')
            self.assertDictEqual(targets, _ALL)

    @skipIf(True, 'WAR ROOM TEMPORARY SKIP')
    def test_glob(self):
        self.opts['ssh_known_hosts_file'] = os.path.join(self.tests_dir, 'known_hosts')
        with patch.dict(sshknownhosts.__opts__, self.opts):
            targets = sshknownhosts.targets(tgt='server*')
            self.assertDictEqual(targets, _TEST_GLOB)

    @skipIf(True, 'WAR ROOM TEMPORARY SKIP')
    def test_pcre(self):
        self.opts['ssh_known_hosts_file'] = os.path.join(self.tests_dir, 'known_hosts')
        with patch.dict(sshknownhosts.__opts__, self.opts):
            targets = sshknownhosts.targets(tgt='eu-mysql-2$', tgt_type='pcre')
            self.assertDictEqual(targets, _TEST_PCRE)
