# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.support.mock import (
    mock_open,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)
from tests.support import mixins
from tests.support.unit import skipIf, TestCase
from tests.support.runtests import RUNTIME_VARS
from tests.support.paths import TESTS_DIR

# Import Salt Libs
import salt.config
import salt.loader
import salt.roster.ansible as ansible


EXPECTED = {
    'host1': {
        'minion_opts': {
            'escape_pods': 2,
            'halon_system_timeout': 30,
            'self_destruct_countdown': 60,
            'some_server': 'foo.southeast.example.com'
        }
    },
    'host2': {
        'minion_opts': {
            'escape_pods': 2,
            'halon_system_timeout': 30,
            'self_destruct_countdown': 60,
            'some_server': 'foo.southeast.example.com'
        }
    },
    'host3': {
        'minion_opts': {
            'escape_pods': 2,
            'halon_system_timeout': 30,
            'self_destruct_countdown': 60,
            'some_server': 'foo.southeast.example.com'
        }
    }
}


@skipIf(not salt.utils.path.which('ansible-inventory'), 'Skipping because ansible-inventory is not available')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class AnsibleRosterTestCase(TestCase, mixins.LoaderModuleMockMixin):

    @classmethod
    def setUpClass(cls):
        cls.roster_dir = os.path.join(TESTS_DIR, 'unit/files/rosters/ansible/')

    def setup_loader_modules(self):
        opts = salt.config.master_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'master'))
        utils = salt.loader.utils(opts, whitelist=['json', 'stringutils'])
        runner = salt.loader.runner(opts, utils=utils, whitelist=['salt'])
        return {ansible: {'__utils__': utils, '__opts__': {}, '__runner__': runner}}

    def test_ini(self):
        ansible.__opts__['roster_file'] = os.path.join(self.roster_dir, 'roster.ini')
        ret = ansible.targets('*')
        assert ret == EXPECTED

    def test_yml(self):
        ansible.__opts__['roster_file'] = os.path.join(self.roster_dir, 'roster.yml')
        ret = ansible.targets('*')
        assert ret == EXPECTED

    def test_script(self):
        ansible.__opts__['roster_file'] = os.path.join(self.roster_dir, 'roster.py')
        ret = ansible.targets('*')
        assert ret == EXPECTED
