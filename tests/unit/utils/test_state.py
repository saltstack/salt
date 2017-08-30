# -*- coding: utf-8 -*-
'''
Unit Tests for functions located in salt.utils.state.py.
'''

# Import python libs
from __future__ import absolute_import

# Import Salt libs
from salt.ext import six
import salt.utils.odict
import salt.utils.state

# Import Salt Testing libs
from tests.support.unit import TestCase


class StateUtilTestCase(TestCase):
    '''
    Test case for state util.
    '''
    def test_check_state_result(self):
        self.assertFalse(salt.utils.state.check_state_result(None),
                         'Failed to handle None as an invalid data type.')
        self.assertFalse(salt.utils.state.check_state_result([]),
                         'Failed to handle an invalid data type.')
        self.assertFalse(salt.utils.state.check_state_result({}),
                         'Failed to handle an empty dictionary.')
        self.assertFalse(salt.utils.state.check_state_result({'host1': []}),
                         'Failed to handle an invalid host data structure.')
        test_valid_state = {'host1': {'test_state': {'result': 'We have liftoff!'}}}
        self.assertTrue(salt.utils.state.check_state_result(test_valid_state))
        test_valid_false_states = {
            'test1': salt.utils.odict.OrderedDict([
                ('host1',
                 salt.utils.odict.OrderedDict([
                     ('test_state0', {'result':  True}),
                     ('test_state', {'result': False}),
                 ])),
            ]),
            'test2': salt.utils.odict.OrderedDict([
                ('host1',
                 salt.utils.odict.OrderedDict([
                     ('test_state0', {'result':  True}),
                     ('test_state', {'result': True}),
                 ])),
                ('host2',
                 salt.utils.odict.OrderedDict([
                     ('test_state0', {'result':  True}),
                     ('test_state', {'result': False}),
                 ])),
            ]),
            'test3': ['a'],
            'test4': salt.utils.odict.OrderedDict([
                ('asup', salt.utils.odict.OrderedDict([
                    ('host1',
                     salt.utils.odict.OrderedDict([
                         ('test_state0', {'result':  True}),
                         ('test_state', {'result': True}),
                     ])),
                    ('host2',
                     salt.utils.odict.OrderedDict([
                         ('test_state0', {'result':  True}),
                         ('test_state', {'result': False}),
                     ]))
                ]))
            ]),
            'test5': salt.utils.odict.OrderedDict([
                ('asup', salt.utils.odict.OrderedDict([
                    ('host1',
                     salt.utils.odict.OrderedDict([
                         ('test_state0', {'result':  True}),
                         ('test_state', {'result': True}),
                     ])),
                    ('host2', salt.utils.odict.OrderedDict([]))
                ]))
            ])
        }
        for test, data in six.iteritems(test_valid_false_states):
            self.assertFalse(
                salt.utils.state.check_state_result(data),
                msg='{0} failed'.format(test))
        test_valid_true_states = {
            'test1': salt.utils.odict.OrderedDict([
                ('host1',
                 salt.utils.odict.OrderedDict([
                     ('test_state0', {'result':  True}),
                     ('test_state', {'result': True}),
                 ])),
            ]),
            'test3': salt.utils.odict.OrderedDict([
                ('host1',
                 salt.utils.odict.OrderedDict([
                     ('test_state0', {'result':  True}),
                     ('test_state', {'result': True}),
                 ])),
                ('host2',
                 salt.utils.odict.OrderedDict([
                     ('test_state0', {'result':  True}),
                     ('test_state', {'result': True}),
                 ])),
            ]),
            'test4': salt.utils.odict.OrderedDict([
                ('asup', salt.utils.odict.OrderedDict([
                    ('host1',
                     salt.utils.odict.OrderedDict([
                         ('test_state0', {'result':  True}),
                         ('test_state', {'result': True}),
                     ])),
                    ('host2',
                     salt.utils.odict.OrderedDict([
                         ('test_state0', {'result':  True}),
                         ('test_state', {'result': True}),
                     ]))
                ]))
            ]),
            'test2': salt.utils.odict.OrderedDict([
                ('host1',
                 salt.utils.odict.OrderedDict([
                     ('test_state0', {'result':  None}),
                     ('test_state', {'result': True}),
                 ])),
                ('host2',
                 salt.utils.odict.OrderedDict([
                     ('test_state0', {'result':  True}),
                     ('test_state', {'result': 'abc'}),
                 ]))
            ])
        }
        for test, data in six.iteritems(test_valid_true_states):
            self.assertTrue(
                salt.utils.state.check_state_result(data),
                msg='{0} failed'.format(test))
        test_invalid_true_ht_states = {
            'test_onfail_simple2': (
                salt.utils.odict.OrderedDict([
                    ('host1',
                     salt.utils.odict.OrderedDict([
                         ('test_vstate0', {'result':  False}),
                         ('test_vstate1', {'result': True}),
                     ])),
                ]),
                {
                    'test_vstate0': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                'run',
                                {'order': 10002}]},
                    'test_vstate1': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                salt.utils.odict.OrderedDict([
                                    ('onfail_stop', True),
                                    ('onfail',
                                     [salt.utils.odict.OrderedDict([('cmd', 'test_vstate0')])])
                                ]),
                                'run',
                                {'order': 10004}]},
                }
            ),
            'test_onfail_integ2': (
                salt.utils.odict.OrderedDict([
                    ('host1',
                     salt.utils.odict.OrderedDict([
                         ('t_|-test_ivstate0_|-echo_|-run', {
                             'result':  False}),
                         ('cmd_|-test_ivstate0_|-echo_|-run', {
                             'result':  False}),
                         ('cmd_|-test_ivstate1_|-echo_|-run', {
                             'result': False}),
                     ])),
                ]),
                {
                    'test_ivstate0': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                'run',
                                {'order': 10002}],
                        't': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                              'run',
                              {'order': 10002}]},
                    'test_ivstate1': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                salt.utils.odict.OrderedDict([
                                    ('onfail_stop', False),
                                    ('onfail',
                                     [salt.utils.odict.OrderedDict([('cmd', 'test_ivstate0')])])
                                ]),
                                'run',
                                {'order': 10004}]},
                }
            ),
            'test_onfail_integ3': (
                salt.utils.odict.OrderedDict([
                    ('host1',
                     salt.utils.odict.OrderedDict([
                         ('t_|-test_ivstate0_|-echo_|-run', {
                             'result':  True}),
                         ('cmd_|-test_ivstate0_|-echo_|-run', {
                             'result': False}),
                         ('cmd_|-test_ivstate1_|-echo_|-run', {
                             'result': False}),
                     ])),
                ]),
                {
                    'test_ivstate0': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                'run',
                                {'order': 10002}],
                        't': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                              'run',
                              {'order': 10002}]},
                    'test_ivstate1': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                salt.utils.odict.OrderedDict([
                                    ('onfail_stop', False),
                                    ('onfail',
                                     [salt.utils.odict.OrderedDict([('cmd', 'test_ivstate0')])])
                                ]),
                                'run',
                                {'order': 10004}]},
                }
            ),
            'test_onfail_integ4': (
                salt.utils.odict.OrderedDict([
                    ('host1',
                     salt.utils.odict.OrderedDict([
                         ('t_|-test_ivstate0_|-echo_|-run', {
                             'result':  False}),
                         ('cmd_|-test_ivstate0_|-echo_|-run', {
                             'result': False}),
                         ('cmd_|-test_ivstate1_|-echo_|-run', {
                             'result': True}),
                     ])),
                ]),
                {
                    'test_ivstate0': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                'run',
                                {'order': 10002}],
                        't': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                              'run',
                              {'order': 10002}]},
                    'test_ivstate1': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                salt.utils.odict.OrderedDict([
                                    ('onfail_stop', False),
                                    ('onfail',
                                     [salt.utils.odict.OrderedDict([('cmd', 'test_ivstate0')])])
                                ]),
                                'run',
                                {'order': 10004}]},
                    'test_ivstate2': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                salt.utils.odict.OrderedDict([
                                    ('onfail_stop', True),
                                    ('onfail',
                                     [salt.utils.odict.OrderedDict([('cmd', 'test_ivstate0')])])
                                ]),
                                'run',
                                {'order': 10004}]},
                }
            ),
            'test_onfail': (
                salt.utils.odict.OrderedDict([
                    ('host1',
                     salt.utils.odict.OrderedDict([
                         ('test_state0', {'result':  False}),
                         ('test_state', {'result': True}),
                     ])),
                ]),
                None
            ),
            'test_onfail_d': (
                salt.utils.odict.OrderedDict([
                    ('host1',
                     salt.utils.odict.OrderedDict([
                         ('test_state0', {'result':  False}),
                         ('test_state', {'result': True}),
                     ])),
                ]),
                {}
            )
        }
        for test, testdata in six.iteritems(test_invalid_true_ht_states):
            data, ht = testdata
            for t_ in [a for a in data['host1']]:
                tdata = data['host1'][t_]
                if '_|-' in t_:
                    t_ = t_.split('_|-')[1]
                tdata['__id__'] = t_
            self.assertFalse(
                salt.utils.state.check_state_result(data, highstate=ht),
                msg='{0} failed'.format(test))

        test_valid_true_ht_states = {
            'test_onfail_integ': (
                salt.utils.odict.OrderedDict([
                    ('host1',
                     salt.utils.odict.OrderedDict([
                         ('cmd_|-test_ivstate0_|-echo_|-run', {
                             'result':  False}),
                         ('cmd_|-test_ivstate1_|-echo_|-run', {
                             'result': True}),
                     ])),
                ]),
                {
                    'test_ivstate0': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                'run',
                                {'order': 10002}]},
                    'test_ivstate1': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                salt.utils.odict.OrderedDict([
                                    ('onfail_stop', False),
                                    ('onfail',
                                     [salt.utils.odict.OrderedDict([('cmd', 'test_ivstate0')])])
                                ]),
                                'run',
                                {'order': 10004}]},
                }
            ),
            'test_onfail_intega3': (
                salt.utils.odict.OrderedDict([
                    ('host1',
                     salt.utils.odict.OrderedDict([
                         ('t_|-test_ivstate0_|-echo_|-run', {
                             'result':  True}),
                         ('cmd_|-test_ivstate0_|-echo_|-run', {
                             'result': False}),
                         ('cmd_|-test_ivstate1_|-echo_|-run', {
                             'result': True}),
                     ])),
                ]),
                {
                    'test_ivstate0': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                'run',
                                {'order': 10002}],
                        't': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                              'run',
                              {'order': 10002}]},
                    'test_ivstate1': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                salt.utils.odict.OrderedDict([
                                    ('onfail_stop', False),
                                    ('onfail',
                                     [salt.utils.odict.OrderedDict([('cmd', 'test_ivstate0')])])
                                ]),
                                'run',
                                {'order': 10004}]},
                }
            ),
            'test_onfail_simple': (
                salt.utils.odict.OrderedDict([
                    ('host1',
                     salt.utils.odict.OrderedDict([
                         ('test_vstate0', {'result':  False}),
                         ('test_vstate1', {'result': True}),
                     ])),
                ]),
                {
                    'test_vstate0': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                'run',
                                {'order': 10002}]},
                    'test_vstate1': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                salt.utils.odict.OrderedDict([
                                    ('onfail_stop', False),
                                    ('onfail',
                                     [salt.utils.odict.OrderedDict([('cmd', 'test_vstate0')])])
                                ]),
                                'run',
                                {'order': 10004}]},
                }
            ),  # order is different
            'test_onfail_simple_rev': (
                salt.utils.odict.OrderedDict([
                    ('host1',
                     salt.utils.odict.OrderedDict([
                         ('test_vstate0', {'result':  False}),
                         ('test_vstate1', {'result': True}),
                     ])),
                ]),
                {
                    'test_vstate0': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                'run',
                                {'order': 10002}]},
                    'test_vstate1': {
                        '__env__': 'base',
                        '__sls__': u'a',
                        'cmd': [salt.utils.odict.OrderedDict([('name', '/bin/true')]),
                                salt.utils.odict.OrderedDict([
                                    ('onfail',
                                     [salt.utils.odict.OrderedDict([('cmd', 'test_vstate0')])])
                                ]),
                                salt.utils.odict.OrderedDict([('onfail_stop', False)]),
                                'run',
                                {'order': 10004}]},
                }
            )
        }
        for test, testdata in six.iteritems(test_valid_true_ht_states):
            data, ht = testdata
            for t_ in [a for a in data['host1']]:
                tdata = data['host1'][t_]
                if '_|-' in t_:
                    t_ = t_.split('_|-')[1]
                tdata['__id__'] = t_
            self.assertTrue(
                salt.utils.state.check_state_result(data, highstate=ht),
                msg='{0} failed'.format(test))
        test_valid_false_state = {'host1': {'test_state': {'result': False}}}
        self.assertFalse(salt.utils.check_state_result(test_valid_false_state))
