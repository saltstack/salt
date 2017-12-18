# -*- coding: utf-8 -*-
'''
Test cases for salt.tgt.nodegroup
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.tgt

# Import Salt Testing Libs
from tests.support.unit import TestCase
from tests.support.mock import (
    patch,
    MagicMock,
)

fake_opts = {
    'transport': 'zeromq',
    'extension_modules': '',
    'nodegroups': {
        'group1': 'L@alpha,beta',
        'group2': ['J!@abc!bar!\\w+', 'not', 'E@.*ta'],
    },
    'minion_data_cache': True
}


class NodegroupTestCase(TestCase):
    '''
    Test cases for salt.tgt.nodegroup
    '''
    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha', 'beta', 'gamma']))
    def test_nodegroup_L(self):  # pylint: disable=invalid-name
        '''
        Test cases for a list nodegroup
        '''
        ret = salt.tgt.check_minions(fake_opts, 'group1', 'nodegroup')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha', 'beta']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha', 'beta', 'gamma', 'iota']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha', 'beta', 'gamma', 'iota']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha', 'beta']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'pillar': {'abc': 'bar!baz'}}))
    def test_nodegroup_J_alt_delimiter_not_E(self):  # pylint: disable=invalid-name
        '''
        Test cases for a ( pillar PCRE with another delimiter not PCRE ) nodegroup
        '''
        ret = salt.tgt.check_minions(fake_opts, 'group2', 'nodegroup', greedy=False)
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))
