# -*- coding: utf-8 -*-

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

NODEGROUPS = {
    'group1': 'L@host1,host2,host3',
    'group2': ['G@foo:bar', 'or', 'web1*'],
    'group3': ['N@group1', 'or', 'N@group2'],
    'group4': ['host4', 'host5', 'host6'],
}

EXPECTED = {
    'group1': ['L@host1,host2,host3'],
    'group2': ['G@foo:bar', 'or', 'web1*'],
    'group3': ['(', '(', 'L@host1,host2,host3', ')', 'or', '(', 'G@foo:bar', 'or', 'web1*', ')', ')'],
    'group4': ['L@host4,host5,host6'],
}

fake_opts = {
    'transport': 'zeromq',
    'extension_modules': ''
}

class MinionsTestCase(TestCase):
    '''
    TestCase for salt.tgt module functions
    '''
    def test_nodegroup_comp(self):
        '''
        Test a simple string nodegroup
        '''
        for nodegroup in NODEGROUPS:
            expected = EXPECTED[nodegroup]
            ret = salt.tgt.nodegroup_comp(nodegroup, NODEGROUPS)
            self.assertEqual(ret, expected)

    def test_spec_check(self):
        # Test spec-only rule
        auth_list = ['@runner']
        ret = salt.tgt.spec_check(auth_list, 'test.arg', {}, 'runner')
        self.assertTrue(ret)
        ret = salt.tgt.spec_check(auth_list, 'test.arg', {}, 'wheel')
        self.assertFalse(ret)
        ret = salt.tgt.spec_check(auth_list, 'testarg', {}, 'runner')
        mock_ret = {'error': {'name': 'SaltInvocationError',
                              'message': 'A command invocation error occurred: Check syntax.'}}
        self.assertDictEqual(mock_ret, ret)

        # Test spec in plural form
        auth_list = ['@runners']
        ret = salt.tgt.spec_check(auth_list, 'test.arg', {}, 'runner')
        self.assertTrue(ret)
        ret = salt.tgt.spec_check(auth_list, 'test.arg', {}, 'wheel')
        self.assertFalse(ret)

        # Test spec with module.function restriction
        auth_list = [{'@runner': 'test.arg'}]
        ret = salt.tgt.spec_check(auth_list, 'test.arg', {}, 'runner')
        self.assertTrue(ret)
        ret = salt.tgt.spec_check(auth_list, 'test.arg', {}, 'wheel')
        self.assertFalse(ret)
        ret = salt.tgt.spec_check(auth_list, 'tes.arg', {}, 'runner')
        self.assertFalse(ret)
        ret = salt.tgt.spec_check(auth_list, 'test.ar', {}, 'runner')
        self.assertFalse(ret)

        # Test function name is a regex
        auth_list = [{'@runner': 'test.arg.*some'}]
        ret = salt.tgt.spec_check(auth_list, 'test.arg', {}, 'runner')
        self.assertFalse(ret)
        ret = salt.tgt.spec_check(auth_list, 'test.argsome', {}, 'runner')
        self.assertTrue(ret)
        ret = salt.tgt.spec_check(auth_list, 'test.arg_aaa_some', {}, 'runner')
        self.assertTrue(ret)

        # Test a list of funcs
        auth_list = [{'@runner': ['test.arg', 'jobs.active']}]
        ret = salt.tgt.spec_check(auth_list, 'test.arg', {}, 'runner')
        self.assertTrue(ret)
        ret = salt.tgt.spec_check(auth_list, 'jobs.active', {}, 'runner')
        self.assertTrue(ret)
        ret = salt.tgt.spec_check(auth_list, 'test.active', {}, 'runner')
        self.assertFalse(ret)
        ret = salt.tgt.spec_check(auth_list, 'jobs.arg', {}, 'runner')
        self.assertFalse(ret)

        # Test args-kwargs rules
        auth_list = [{
            '@runner': {
                'test.arg': {
                    'args': ['1', '2'],
                    'kwargs': {
                        'aaa': 'bbb',
                        'ccc': 'ddd'
                    }
                }
            }
        }]
        ret = salt.tgt.spec_check(auth_list, 'test.arg', {}, 'runner')
        self.assertFalse(ret)
        args = {
            'arg': ['1', '2'],
            'kwarg': {'aaa': 'bbb', 'ccc': 'ddd'}
        }
        ret = salt.tgt.spec_check(auth_list, 'test.arg', args, 'runner')
        self.assertTrue(ret)
        args = {
            'arg': ['1', '2', '3'],
            'kwarg': {'aaa': 'bbb', 'ccc': 'ddd'}
        }
        ret = salt.tgt.spec_check(auth_list, 'test.arg', args, 'runner')
        self.assertTrue(ret)
        args = {
            'arg': ['1', '2'],
            'kwarg': {'aaa': 'bbb', 'ccc': 'ddd', 'zzz': 'zzz'}
        }
        ret = salt.tgt.spec_check(auth_list, 'test.arg', args, 'runner')
        self.assertTrue(ret)
        args = {
            'arg': ['1', '2'],
            'kwarg': {'aaa': 'bbb', 'ccc': 'ddc'}
        }
        ret = salt.tgt.spec_check(auth_list, 'test.arg', args, 'runner')
        self.assertFalse(ret)
        args = {
            'arg': ['1', '2'],
            'kwarg': {'aaa': 'bbb'}
        }
        ret = salt.tgt.spec_check(auth_list, 'test.arg', args, 'runner')
        self.assertFalse(ret)
        args = {
            'arg': ['1', '3'],
            'kwarg': {'aaa': 'bbb', 'ccc': 'ddd'}
        }
        ret = salt.tgt.spec_check(auth_list, 'test.arg', args, 'runner')
        self.assertFalse(ret)
        args = {
            'arg': ['1'],
            'kwarg': {'aaa': 'bbb', 'ccc': 'ddd'}
        }
        ret = salt.tgt.spec_check(auth_list, 'test.arg', args, 'runner')
        self.assertFalse(ret)
        args = {
            'kwarg': {'aaa': 'bbb', 'ccc': 'ddd'}
        }
        ret = salt.tgt.spec_check(auth_list, 'test.arg', args, 'runner')
        self.assertFalse(ret)
        args = {
            'arg': ['1', '2'],
        }
        ret = salt.tgt.spec_check(auth_list, 'test.arg', args, 'runner')
        self.assertFalse(ret)

        # Test kwargs only
        auth_list = [{
            '@runner': {
                'test.arg': {
                    'kwargs': {
                        'aaa': 'bbb',
                        'ccc': 'ddd'
                    }
                }
            }
        }]
        ret = salt.tgt.spec_check(auth_list, 'test.arg', {}, 'runner')
        self.assertFalse(ret)
        args = {
            'arg': ['1', '2'],
            'kwarg': {'aaa': 'bbb', 'ccc': 'ddd'}
        }
        ret = salt.tgt.spec_check(auth_list, 'test.arg', args, 'runner')
        self.assertTrue(ret)

        # Test args only
        auth_list = [{
            '@runner': {
                'test.arg': {
                    'args': ['1', '2']
                }
            }
        }]
        ret = salt.tgt.spec_check(auth_list, 'test.arg', {}, 'runner')
        self.assertFalse(ret)
        args = {
            'arg': ['1', '2'],
            'kwarg': {'aaa': 'bbb', 'ccc': 'ddd'}
        }
        ret = salt.tgt.spec_check(auth_list, 'test.arg', args, 'runner')
        self.assertTrue(ret)

        # Test list of args
        auth_list = [{'@runner': [{'test.arg': [{'args': ['1', '2'],
                                                 'kwargs': {'aaa': 'bbb',
                                                            'ccc': 'ddd'
                                                            }
                                                 },
                                                {'args': ['2', '3'],
                                                 'kwargs': {'aaa': 'aaa',
                                                            'ccc': 'ccc'
                                                            }
                                                 }]
                                   }]
                      }]
        args = {
            'arg': ['1', '2'],
            'kwarg': {'aaa': 'bbb', 'ccc': 'ddd'}
        }
        ret = salt.tgt.spec_check(auth_list, 'test.arg', args, 'runner')
        self.assertTrue(ret)
        args = {
            'arg': ['2', '3'],
            'kwarg': {'aaa': 'aaa', 'ccc': 'ccc'}
        }
        ret = salt.tgt.spec_check(auth_list, 'test.arg', args, 'runner')
        self.assertTrue(ret)

        # Test @module form
        auth_list = ['@jobs']
        ret = salt.tgt.spec_check(auth_list, 'jobs.active', {}, 'runner')
        self.assertTrue(ret)
        ret = salt.tgt.spec_check(auth_list, 'jobs.active', {}, 'wheel')
        self.assertTrue(ret)
        ret = salt.tgt.spec_check(auth_list, 'test.arg', {}, 'runner')
        self.assertFalse(ret)
        ret = salt.tgt.spec_check(auth_list, 'job.arg', {}, 'runner')
        self.assertFalse(ret)

        # Test @module: function
        auth_list = [{'@jobs': 'active'}]
        ret = salt.tgt.spec_check(auth_list, 'jobs.active', {}, 'runner')
        self.assertTrue(ret)
        ret = salt.tgt.spec_check(auth_list, 'jobs.active', {}, 'wheel')
        self.assertTrue(ret)
        ret = salt.tgt.spec_check(auth_list, 'jobs.active_jobs', {}, 'runner')
        self.assertTrue(ret)
        ret = salt.tgt.spec_check(auth_list, 'jobs.activ', {}, 'runner')
        self.assertFalse(ret)

        # Test @module: [functions]
        auth_list = [{'@jobs': ['active', 'li']}]
        ret = salt.tgt.spec_check(auth_list, 'jobs.active', {}, 'runner')
        self.assertTrue(ret)
        ret = salt.tgt.spec_check(auth_list, 'jobs.list_jobs', {}, 'runner')
        self.assertTrue(ret)
        ret = salt.tgt.spec_check(auth_list, 'jobs.last_run', {}, 'runner')
        self.assertFalse(ret)

        # Test @module: function with args
        auth_list = [{'@jobs': {'active': {'args': ['1', '2'],
                                           'kwargs': {'a': 'b', 'c': 'd'}}}}]
        args = {'arg': ['1', '2'],
                'kwarg': {'a': 'b', 'c': 'd'}}
        ret = salt.tgt.spec_check(auth_list, 'jobs.active', args, 'runner')
        self.assertTrue(ret)
        ret = salt.tgt.spec_check(auth_list, 'jobs.active', {}, 'runner')
        self.assertFalse(ret)

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha', 'beta', 'gamma']))
    def test_auth_check(self):
        # Test function-only rule
        auth_list = ['test.ping']
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.ping', None, 'alpha')
        self.assertTrue(ret)
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.arg', None, 'alpha')
        self.assertFalse(ret)

        # Test minion and function
        auth_list = [{'alpha': 'test.ping'}]
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.ping', None, 'alpha')
        self.assertTrue(ret)
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.arg', None, 'alpha')
        self.assertFalse(ret)
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.ping', None, 'beta')
        self.assertFalse(ret)

        # Test function list
        auth_list = [{'*': ['test.*', 'saltutil.cmd']}]
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.arg', None, 'alpha')
        self.assertTrue(ret)
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.ping', None, 'beta')
        self.assertTrue(ret)
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'saltutil.cmd', None, 'gamma')
        self.assertTrue(ret)
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'saltutil.running', None, 'gamma')
        self.assertFalse(ret)

        # Test an args and kwargs rule
        auth_list = [{
            'alpha': {
                'test.arg': {
                    'args': ['1', '2'],
                    'kwargs': {
                        'aaa': 'bbb',
                        'ccc': 'ddd'
                    }
                }
            }
        }]
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.arg', None, 'runner')
        self.assertFalse(ret)
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.arg', [], 'runner')
        self.assertFalse(ret)
        args = ['1', '2', {'aaa': 'bbb', 'ccc': 'ddd', '__kwarg__': True}]
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.arg', args, 'runner')
        self.assertTrue(ret)
        args = ['1', '2', '3', {'aaa': 'bbb', 'ccc': 'ddd', 'eee': 'fff', '__kwarg__': True}]
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.arg', args, 'runner')
        self.assertTrue(ret)
        args = ['1', {'aaa': 'bbb', 'ccc': 'ddd', '__kwarg__': True}]
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.arg', args, 'runner')
        self.assertFalse(ret)
        args = ['1', '2', {'aaa': 'bbb', '__kwarg__': True}]
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.arg', args, 'runner')
        self.assertFalse(ret)
        args = ['1', '3', {'aaa': 'bbb', 'ccc': 'ddd', '__kwarg__': True}]
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.arg', args, 'runner')
        self.assertFalse(ret)
        args = ['1', '2', {'aaa': 'bbb', 'ccc': 'fff', '__kwarg__': True}]
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.arg', args, 'runner')
        self.assertFalse(ret)

        # Test kwargs only rule
        auth_list = [{
            'alpha': {
                'test.arg': {
                    'kwargs': {
                        'aaa': 'bbb',
                        'ccc': 'ddd'
                    }
                }
            }
        }]
        args = ['1', '2', {'aaa': 'bbb', 'ccc': 'ddd', '__kwarg__': True}]
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.arg', args, 'runner')
        self.assertTrue(ret)
        args = [{'aaa': 'bbb', 'ccc': 'ddd', 'eee': 'fff', '__kwarg__': True}]
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.arg', args, 'runner')
        self.assertTrue(ret)

        # Test args only rule
        auth_list = [{
            'alpha': {
                'test.arg': {
                    'args': ['1', '2'],
                }
            }
        }]
        args = ['1', '2', {'aaa': 'bbb', 'ccc': 'ddd', '__kwarg__': True}]
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.arg', args, 'runner')
        self.assertTrue(ret)
        args = ['1', '2']
        ret = salt.tgt.auth_check(fake_opts, auth_list, 'test.arg', args, 'runner')
        self.assertTrue(ret)

    @patch('salt.tgt.pki_minions', MagicMock(
        return_value=['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta', 'lota', 'kappa']))
    def test_glob(self):
        ret = salt.tgt.check_minions(fake_opts, 'a*', 'glob')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.tgt.pki_minions', MagicMock(
        return_value=['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta', 'lota', 'kappa']))
    def test_list(self):
        ret = salt.tgt.check_minions(fake_opts, 'alpha,beta', 'list')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha', 'beta']))

    @patch('salt.tgt.pki_minions', MagicMock(
        return_value=['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta', 'lota', 'kappa']))
    def test_pcre(self):
        ret = salt.tgt.check_minions(fake_opts, '.*ta', 'pcre')
        self.assertEqual(sorted(ret['minions']),
                         sorted(['beta', 'delta', 'zeta', 'eta', 'theta', 'lota']))
