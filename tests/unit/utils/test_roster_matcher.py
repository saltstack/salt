# -*- coding: utf-8 -*-

'''
Test generic roster matching utility.
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.support import mixins
from tests.support.unit import skipIf, TestCase
from tests.support.runtests import RUNTIME_VARS

# Import Salt Libs
import salt.config
import salt.loader
import salt.utils.roster_matcher
import pytest

EXPECTED = {
    'host1': {
        'host': 'host1',
        'passwd': 'test123',
        'minion_opts': {
            'escape_pods': 2,
            'halon_system_timeout': 30,
            'self_destruct_countdown': 60,
            'some_server': 'foo.southeast.example.com'
        }
    },
    'host2': {
        'host': 'host2',
        'passwd': 'test123',
        'minion_opts': {
            'escape_pods': 2,
            'halon_system_timeout': 30,
            'self_destruct_countdown': 60,
            'some_server': 'foo.southeast.example.com'
        }
    },
    'host3': {
        'host': 'host3',
        'passwd': 'test123',
        'minion_opts': {}
    },
    'host4': 'host4.example.com',  # For testing get_data -> string_types branch
    'host5': None,  # For testing get_data -> False
}


class RosterMatcherTestCase(TestCase, mixins.LoaderModuleMockMixin):
    """
    Test the RosterMatcher Utility
    """

    def setup_loader_modules(self):
        opts = salt.config.master_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'master'))
        utils = salt.loader.utils(opts, whitelist=['json', 'stringutils'])
        runner = salt.loader.runner(opts, utils=utils, whitelist=['salt'])
        return {
            salt.utils.roster_matcher: {
                '__utils__': utils,
                '__opts__': {
                    'ssh_list_nodegroups': {
                        'list_nodegroup': ['host5', 'host1', 'host2'],
                        'string_nodegroup': 'host3,host5,host1,host4',
                    }
                },
                '__runner__': runner
            }
        }

    def test_get_data(self):
        """
        Test that the get_data method returns the expected dictionaries.
        """
        # We don't care about tgt and tgt_type here.
        roster_matcher = salt.utils.roster_matcher.RosterMatcher(EXPECTED, 'tgt', 'tgt_type')
        assert EXPECTED['host1'] == roster_matcher.get_data('host1')
        assert EXPECTED['host2'] == roster_matcher.get_data('host2')
        assert EXPECTED['host3'] == roster_matcher.get_data('host3')
        assert {'host': EXPECTED['host4']} == roster_matcher.get_data('host4')

    def test_ret_glob_minions(self):
        """
        Test that we return minions matching a glob.
        """
        result = salt.utils.roster_matcher.targets(EXPECTED, '*[245]', 'glob')
        assert 'host1' not in result
        assert 'host2' in result
        assert 'host3' not in result
        assert 'host4' in result
        assert 'host5' not in result

    def test_ret_pcre_minions(self):
        """
        Test that we return minions matching a regular expression.
        """
        result = salt.utils.roster_matcher.targets(EXPECTED, '.*[^23]$', 'pcre')
        assert 'host1' in result
        assert 'host2' not in result
        assert 'host3' not in result
        assert 'host4' in result
        assert 'host5' not in result

    def test_ret_literal_list_minions(self):
        """
        Test that we return minions that are in a literal list.
        """
        result = salt.utils.roster_matcher.targets(EXPECTED, ['host1', 'host2', 'host5'], 'list')
        assert 'host1' in result
        assert 'host2' in result
        assert 'host3' not in result
        assert 'host4' not in result
        assert 'host5' not in result

    def test_ret_comma_delimited_string_minions(self):
        """
        Test that we return minions that are in a comma-delimited
        string of literal minion names.
        """
        result = salt.utils.roster_matcher.targets(EXPECTED, 'host5,host3,host2', 'list')
        assert 'host1' not in result
        assert 'host2' in result
        assert 'host3' in result
        assert 'host4' not in result
        assert 'host5' not in result

    def test_ret_oops_minions(self):
        """
        Test that we return no minions when we try to use a matching
        method that is not defined.
        """
        result = salt.utils.roster_matcher.targets(EXPECTED, None, 'xyzzy')
        assert {} == result

    def test_ret_literal_list_nodegroup_minions(self):
        """
        Test that we return minions that are in a nodegroup
        where the nodegroup expresses a literal list of minion names.
        """
        result = salt.utils.roster_matcher.targets(EXPECTED, 'list_nodegroup', 'nodegroup')
        assert 'host1' in result
        assert 'host2' in result
        assert 'host3' not in result
        assert 'host4' not in result
        assert 'host5' not in result

    def test_ret_comma_delimited_string_nodegroup_minions(self):
        """
        Test that we return minions that are in a nodegroup
        where the nodegroup expresses a comma delimited string
        of minion names.
        """
        result = salt.utils.roster_matcher.targets(EXPECTED, 'string_nodegroup', 'nodegroup')
        assert 'host1' in result
        assert 'host2' not in result
        assert 'host3' in result
        assert 'host4' in result
        assert 'host5' not in result

    def test_ret_no_range_installed_minions(self):
        """
        Test that range matcher raises a Runtime Error if seco.range is not installed.
        """
        salt.utils.roster_matcher.HAS_RANGE = False
        with pytest.raises(RuntimeError):
            salt.utils.roster_matcher.targets(EXPECTED, None, 'range')

    @skipIf(not salt.utils.roster_matcher.HAS_RANGE, 'seco.range is not installed')
    def test_ret_range_minions(self):
        """
        Test that range matcher raises a Runtime Error if seco.range is not installed.
        """
        self.fail('Not implemented')
