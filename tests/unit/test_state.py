# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import os
import tempfile

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)
from tests.support.mixins import AdaptedConfigurationTestCaseMixin

# Import Salt libs
import salt.exceptions
import salt.state
from salt.utils.odict import OrderedDict, DefaultOrderedDict
from salt.utils.decorators import state as statedecorators

try:
    import pytest
except ImportError as err:
    pytest = None


@skipIf(NO_MOCK, NO_MOCK_REASON)
class StateCompilerTestCase(TestCase, AdaptedConfigurationTestCaseMixin):
    '''
    TestCase for the state compiler.
    '''

    def test_format_log_non_ascii_character(self):
        '''
        Tests running a non-ascii character through the state.format_log
        function. See Issue #33605.
        '''
        # There is no return to test against as the format_log
        # function doesn't return anything. However, we do want
        # to make sure that the function doesn't stacktrace when
        # called.
        ret = {'changes': {'Français': {'old': 'something old',
                                         'new': 'something new'}},
               'result': True}
        salt.state.format_log(ret)

    def test_render_error_on_invalid_requisite(self):
        '''
        Test that the state compiler correctly deliver a rendering
        exception when a requisite cannot be resolved
        '''
        with patch('salt.state.State._gather_pillar') as state_patch:
            high_data = {
                'git': OrderedDict([
                    ('pkg', [
                        OrderedDict([
                            ('require', [
                                OrderedDict([
                                    ('file', OrderedDict(
                                        [('test1', 'test')]))])])]),
                        'installed', {'order': 10000}]), ('__sls__', 'issue_35226'), ('__env__', 'base')])}
            minion_opts = self.get_temp_config('minion')
            minion_opts['pillar'] = {'git': OrderedDict([('test1', 'test')])}
            state_obj = salt.state.State(minion_opts)
            with self.assertRaises(salt.exceptions.SaltRenderError):
                state_obj.call_high(high_data)


class HighStateTestCase(TestCase, AdaptedConfigurationTestCaseMixin):
    def setUp(self):
        root_dir = tempfile.mkdtemp(dir=integration.TMP)
        state_tree_dir = os.path.join(root_dir, 'state_tree')
        cache_dir = os.path.join(root_dir, 'cachedir')
        for dpath in (root_dir, state_tree_dir, cache_dir):
            if not os.path.isdir(dpath):
                os.makedirs(dpath)

        overrides = {}
        overrides['root_dir'] = root_dir
        overrides['state_events'] = False
        overrides['id'] = 'match'
        overrides['file_client'] = 'local'
        overrides['file_roots'] = dict(base=[state_tree_dir])
        overrides['cachedir'] = cache_dir
        overrides['test'] = False
        self.config = self.get_temp_config('minion', **overrides)
        self.addCleanup(delattr, self, 'config')
        self.highstate = salt.state.HighState(self.config)
        self.addCleanup(delattr, self, 'highstate')
        self.highstate.push_active()

    def tearDown(self):
        self.highstate.pop_active()

    def test_top_matches_with_list(self):
        top = {'env': {'match': ['state1', 'state2'], 'nomatch': ['state3']}}
        matches = self.highstate.top_matches(top)
        self.assertEqual(matches, {'env': ['state1', 'state2']})

    def test_top_matches_with_string(self):
        top = {'env': {'match': 'state1', 'nomatch': 'state2'}}
        matches = self.highstate.top_matches(top)
        self.assertEqual(matches, {'env': ['state1']})

    def test_matches_whitelist(self):
        matches = {'env': ['state1', 'state2', 'state3']}
        matches = self.highstate.matches_whitelist(matches, ['state2'])
        self.assertEqual(matches, {'env': ['state2']})

    def test_matches_whitelist_with_string(self):
        matches = {'env': ['state1', 'state2', 'state3']}
        matches = self.highstate.matches_whitelist(matches,
                                                   'state2,state3')
        self.assertEqual(matches, {'env': ['state2', 'state3']})

    def test_show_state_usage(self):
        # monkey patch sub methods
        self.highstate.avail = {
            'base': ['state.a', 'state.b', 'state.c']
        }

        def verify_tops(*args, **kwargs):
            return []

        def get_top(*args, **kwargs):
            return None

        def top_matches(*args, **kwargs):
            return {'base': ['state.a', 'state.b']}

        self.highstate.verify_tops = verify_tops
        self.highstate.get_top = get_top
        self.highstate.top_matches = top_matches

        # get compile_state_usage() result
        state_usage_dict = self.highstate.compile_state_usage()

        self.assertEqual(state_usage_dict['base']['count_unused'], 1)
        self.assertEqual(state_usage_dict['base']['count_used'], 2)
        self.assertEqual(state_usage_dict['base']['count_all'], 3)
        self.assertEqual(state_usage_dict['base']['used'], ['state.a', 'state.b'])
        self.assertEqual(state_usage_dict['base']['unused'], ['state.c'])


class TopFileMergeTestCase(TestCase, AdaptedConfigurationTestCaseMixin):
    '''
    Test various merge strategies for multiple tops files collected from
    multiple environments. Various options correspond to merge strategies
    which can be set by the user with the top_file_merging_strategy config
    option.
    '''
    def setUp(self):
        '''
        Create multiple top files for use in each test. Envs within self.tops
        should be defined in the same order as this ordering will affect
        ordering in merge_tops. The envs in each top file are defined in the
        same order as self.env_order. This is no accident; it was done this way
        in order to produce the proper deterministic results to match the
        tests. Changing anything created in this func will affect the tests, as
        they would affect ordering in states in real life. So, don't change any
        of this unless you know what you're doing. If a test is failing, it is
        likely due to incorrect logic in merge_tops.
        '''
        self.env_order = ['base', 'foo', 'bar', 'baz']
        self.addCleanup(delattr, self, 'env_order')
        self.tops = {
            'base': OrderedDict([
                ('base', OrderedDict([('*', ['base_base'])])),
                ('foo', OrderedDict([('*', ['base_foo'])])),
                ('bar', OrderedDict([('*', ['base_bar'])])),
                ('baz', OrderedDict([('*', ['base_baz'])])),
            ]),
            'foo': OrderedDict([
                ('base', OrderedDict([('*', ['foo_base'])])),
                ('foo', OrderedDict([('*', ['foo_foo'])])),
                ('bar', OrderedDict([('*', ['foo_bar'])])),
                ('baz', OrderedDict([('*', ['foo_baz'])])),
            ]),
            'bar': OrderedDict([
                ('base', OrderedDict([('*', ['bar_base'])])),
                ('foo', OrderedDict([('*', ['bar_foo'])])),
                ('bar', OrderedDict([('*', ['bar_bar'])])),
                ('baz', OrderedDict([('*', ['bar_baz'])])),
            ]),
            # Empty environment
            'baz': OrderedDict()
        }
        self.addCleanup(delattr, self, 'tops')

        # Version without the other envs defined in the base top file
        self.tops_limited_base = copy.deepcopy(self.tops)
        self.tops_limited_base['base'] = OrderedDict([
            ('base', OrderedDict([('*', ['base_base'])])),
        ])
        self.addCleanup(delattr, self, 'tops_limited_base')

    def highstate(self, **opts):
        root_dir = tempfile.mkdtemp(dir=integration.TMP)
        state_tree_dir = os.path.join(root_dir, 'state_tree')
        cache_dir = os.path.join(root_dir, 'cachedir')
        overrides = {}
        overrides['root_dir'] = root_dir
        overrides['state_events'] = False
        overrides['id'] = 'match'
        overrides['file_client'] = 'local'
        overrides['file_roots'] = dict(base=[state_tree_dir])
        overrides['cachedir'] = cache_dir
        overrides['test'] = False
        overrides['default_top'] = 'base'
        overrides.update(opts)
        return salt.state.HighState(self.get_temp_config('minion', **overrides))

    def get_tops(self, tops=None, env_order=None, state_top_saltenv=None):
        '''
        A test helper to emulate salt.state.HighState.get_tops() but just to
        construct an appropriate data structure for top files from multiple
        environments
        '''
        if tops is None:
            tops = self.tops

        if state_top_saltenv:
            append_order = [state_top_saltenv]
        elif env_order:
            append_order = env_order
        else:
            append_order = self.env_order

        ret = DefaultOrderedDict(list)
        for env in append_order:
            item = tops[env]
            if env_order:
                for remove in [x for x in self.env_order if x not in env_order]:
                    # Remove this env from the tops from the tops since this
                    # env is not part of env_order.
                    item.pop(remove)
            ret[env].append(tops[env])
        return ret

    def test_merge_tops_merge(self):
        '''
        Test the default merge strategy for top files, in an instance where the
        base top file contains sections for all envs and the other envs' top
        files are therefore ignored.
        '''
        merged_tops = self.highstate().merge_tops(self.get_tops())

        expected_merge = DefaultOrderedDict(OrderedDict)
        for env in self.env_order:
            expected_merge[env]['*'] = ['base_{0}'.format(env)]

        self.assertEqual(merged_tops, expected_merge)

    def test_merge_tops_merge_limited_base(self):
        '''
        Test the default merge strategy for top files when the base environment
        only defines states for itself.
        '''
        tops = self.get_tops(tops=self.tops_limited_base)
        merged_tops = self.highstate().merge_tops(tops)

        # No baz in the expected results because baz has no top file
        expected_merge = DefaultOrderedDict(OrderedDict)
        for env in self.env_order[:-1]:
            expected_merge[env]['*'] = ['_'.join((env, env))]

        self.assertEqual(merged_tops, expected_merge)

    def test_merge_tops_merge_state_top_saltenv_base(self):
        '''
        Test the 'state_top_saltenv' parameter to load states exclusively from
        the 'base' saltenv, with the default merging strategy. This should
        result in all states from the 'base' top file being in the merged
        result.
        '''
        env = 'base'
        tops = self.get_tops(state_top_saltenv=env)
        merged_tops = self.highstate().merge_tops(tops)

        expected_merge = DefaultOrderedDict(OrderedDict)
        for env2 in self.env_order:
            expected_merge[env2]['*'] = ['_'.join((env, env2))]

        self.assertEqual(merged_tops, expected_merge)

    def test_merge_tops_merge_state_top_saltenv_foo(self):
        '''
        Test the 'state_top_saltenv' parameter to load states exclusively from
        the 'foo' saltenv, with the default merging strategy. This should
        result in just the 'foo' environment's states from the 'foo' top file
        being in the merged result.
        '''
        env = 'foo'
        tops = self.get_tops(state_top_saltenv=env)
        merged_tops = self.highstate().merge_tops(tops)

        expected_merge = DefaultOrderedDict(OrderedDict)
        expected_merge[env]['*'] = ['_'.join((env, env))]

        self.assertEqual(merged_tops, expected_merge)

    def test_merge_tops_merge_all(self):
        '''
        Test the merge_all strategy
        '''
        tops = self.get_tops()
        merged_tops = self.highstate(
            top_file_merging_strategy='merge_all').merge_tops(tops)

        expected_merge = DefaultOrderedDict(OrderedDict)
        for env in self.env_order:
            states = []
            for top_env in self.env_order:
                if top_env in tops[top_env][0]:
                    states.extend(tops[top_env][0][env]['*'])
            expected_merge[env]['*'] = states

        self.assertEqual(merged_tops, expected_merge)

    def test_merge_tops_merge_all_with_env_order(self):
        '''
        Test an altered env_order with the 'merge_all' strategy.
        '''
        env_order = ['bar', 'foo', 'base']
        tops = self.get_tops(env_order=env_order)
        merged_tops = self.highstate(
            top_file_merging_strategy='merge_all',
            env_order=env_order).merge_tops(tops)

        expected_merge = DefaultOrderedDict(OrderedDict)
        for env in [x for x in self.env_order if x in env_order]:
            states = []
            for top_env in env_order:
                states.extend(tops[top_env][0][env]['*'])
            expected_merge[env]['*'] = states

        self.assertEqual(merged_tops, expected_merge)

    def test_merge_tops_merge_all_state_top_saltenv_base(self):
        '''
        Test the 'state_top_saltenv' parameter to load states exclusively from
        the 'base' saltenv, with the 'merge_all' merging strategy. This should
        result in all states from the 'base' top file being in the merged
        result.
        '''
        env = 'base'
        tops = self.get_tops(state_top_saltenv=env)
        merged_tops = self.highstate(
            top_file_merging_strategy='merge_all').merge_tops(tops)

        expected_merge = DefaultOrderedDict(OrderedDict)
        for env2 in self.env_order:
            expected_merge[env2]['*'] = ['_'.join((env, env2))]

        self.assertEqual(merged_tops, expected_merge)

    def test_merge_tops_merge_all_state_top_saltenv_foo(self):
        '''
        Test the 'state_top_saltenv' parameter to load states exclusively from
        the 'foo' saltenv, with the 'merge_all' merging strategy. This should
        result in all the states from the 'foo' top file being in the merged
        result.
        '''
        env = 'foo'
        tops = self.get_tops(state_top_saltenv=env)
        merged_tops = self.highstate(
            top_file_merging_strategy='merge_all').merge_tops(tops)

        expected_merge = DefaultOrderedDict(OrderedDict)
        for env2 in self.env_order:
            expected_merge[env2]['*'] = ['_'.join((env, env2))]

        self.assertEqual(merged_tops, expected_merge)

    def test_merge_tops_same_with_default_top(self):
        '''
        Test to see if the top file that corresponds to the requested env is
        the one that is used by the state system. Also test the 'default_top'
        option for env 'baz', which has no top file and should pull its states
        from the 'foo' top file.
        '''
        merged_tops = self.highstate(
            top_file_merging_strategy='same',
            default_top='foo').merge_tops(self.get_tops())

        expected_merge = DefaultOrderedDict(OrderedDict)
        for env in self.env_order[:-1]:
            expected_merge[env]['*'] = ['_'.join((env, env))]
        # The 'baz' env should be using the foo top file because baz lacks a
        # top file, and default_top has been seet to 'foo'
        expected_merge['baz']['*'] = ['foo_baz']

        self.assertEqual(merged_tops, expected_merge)

    def test_merge_tops_same_without_default_top(self):
        '''
        Test to see if the top file that corresponds to the requested env is
        the one that is used by the state system. default_top will not be set
        (falling back to 'base'), so the 'baz' environment should pull its
        states from the 'base' top file.
        '''
        merged_tops = self.highstate(
            top_file_merging_strategy='same').merge_tops(self.get_tops())

        expected_merge = DefaultOrderedDict(OrderedDict)
        for env in self.env_order[:-1]:
            expected_merge[env]['*'] = ['_'.join((env, env))]
        # The 'baz' env should be using the foo top file because baz lacks a
        # top file, and default_top == 'base'
        expected_merge['baz']['*'] = ['base_baz']

        self.assertEqual(merged_tops, expected_merge)

    def test_merge_tops_same_limited_base_without_default_top(self):
        '''
        Test to see if the top file that corresponds to the requested env is
        the one that is used by the state system. default_top will not be set
        (falling back to 'base'), and since we are using a limited base top
        file, the 'baz' environment should not appear in the merged tops.
        '''
        tops = self.get_tops(tops=self.tops_limited_base)
        merged_tops = \
            self.highstate(top_file_merging_strategy='same').merge_tops(tops)

        expected_merge = DefaultOrderedDict(OrderedDict)
        for env in self.env_order[:-1]:
            expected_merge[env]['*'] = ['_'.join((env, env))]

        self.assertEqual(merged_tops, expected_merge)

    def test_merge_tops_same_state_top_saltenv_base(self):
        '''
        Test the 'state_top_saltenv' parameter to load states exclusively from
        the 'base' saltenv, with the 'same' merging strategy. This should
        result in just the 'base' environment's states from the 'base' top file
        being in the merged result.
        '''
        env = 'base'
        tops = self.get_tops(state_top_saltenv=env)
        merged_tops = self.highstate(
            top_file_merging_strategy='same').merge_tops(tops)

        expected_merge = DefaultOrderedDict(OrderedDict)
        expected_merge[env]['*'] = ['_'.join((env, env))]

        self.assertEqual(merged_tops, expected_merge)

    def test_merge_tops_same_state_top_saltenv_foo(self):
        '''
        Test the 'state_top_saltenv' parameter to load states exclusively from
        the 'foo' saltenv, with the 'same' merging strategy. This should
        result in just the 'foo' environment's states from the 'foo' top file
        being in the merged result.
        '''
        env = 'foo'
        tops = self.get_tops(state_top_saltenv=env)
        merged_tops = self.highstate(
            top_file_merging_strategy='same').merge_tops(tops)

        expected_merge = DefaultOrderedDict(OrderedDict)
        expected_merge[env]['*'] = ['_'.join((env, env))]

        self.assertEqual(merged_tops, expected_merge)

    def test_merge_tops_same_state_top_saltenv_baz(self):
        '''
        Test the 'state_top_saltenv' parameter to load states exclusively from
        the 'baz' saltenv, with the 'same' merging strategy. This should
        result in an empty dictionary since this environment has not top file.
        '''
        tops = self.get_tops(state_top_saltenv='baz')
        merged_tops = self.highstate(
            top_file_merging_strategy='same').merge_tops(tops)

        expected_merge = DefaultOrderedDict(OrderedDict)

        self.assertEqual(merged_tops, expected_merge)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(pytest is None, 'PyTest is missing')
class StateReturnsTestCase(TestCase):
    '''
    TestCase for code handling state returns.
    '''

    def test_state_output_check_changes_is_dict(self):
        '''
        Test that changes key contains a dictionary.
        :return:
        '''
        data = {'changes': []}
        out = statedecorators.OutputUnifier('content_check')(lambda: data)()
        assert "'Changes' should be a dictionary" in out['comment']
        assert not out['result']

    def test_state_output_check_return_is_dict(self):
        '''
        Test for the entire return is a dictionary
        :return:
        '''
        data = ['whatever']
        out = statedecorators.OutputUnifier('content_check')(lambda: data)()
        assert 'Malformed state return. Data must be a dictionary type' in out['comment']
        assert not out['result']

    def test_state_output_check_return_has_nrc(self):
        '''
        Test for name/result/comment keys are inside the return.
        :return:
        '''
        data = {'arbitrary': 'data', 'changes': {}}
        out = statedecorators.OutputUnifier('content_check')(lambda: data)()
        assert ' The following keys were not present in the state return: name, result, comment' in out['comment']
        assert not out['result']

    def test_state_output_unifier_comment_is_not_list(self):
        '''
        Test for output is unified so the comment is converted to a multi-line string
        :return:
        '''
        data = {'comment': ['data', 'in', 'the', 'list'], 'changes': {}, 'name': None, 'result': 'fantastic!'}
        expected = {'comment': 'data\nin\nthe\nlist', 'changes': {}, 'name': None, 'result': True}
        assert statedecorators.OutputUnifier('unify')(lambda: data)() == expected

        data = {'comment': ['data', 'in', 'the', 'list'], 'changes': {}, 'name': None, 'result': None}
        expected = 'data\nin\nthe\nlist'
        assert statedecorators.OutputUnifier('unify')(lambda: data)()['comment'] == expected

    def test_state_output_unifier_result_converted_to_true(self):
        '''
        Test for output is unified so the result is converted to True
        :return:
        '''
        data = {'comment': ['data', 'in', 'the', 'list'], 'changes': {}, 'name': None, 'result': 'Fantastic'}
        assert statedecorators.OutputUnifier('unify')(lambda: data)()['result'] is True

    def test_state_output_unifier_result_converted_to_false(self):
        '''
        Test for output is unified so the result is converted to False
        :return:
        '''
        data = {'comment': ['data', 'in', 'the', 'list'], 'changes': {}, 'name': None, 'result': ''}
        assert statedecorators.OutputUnifier('unify')(lambda: data)()['result'] is False


class StateFormatSlotsTestCase(TestCase, AdaptedConfigurationTestCaseMixin):
    '''
    TestCase for code handling slots
    '''
    def setUp(self):
        with patch('salt.state.State._gather_pillar'):
            minion_opts = self.get_temp_config('minion')
            self.state_obj = salt.state.State(minion_opts)

    def test_format_slots_no_slots(self):
        '''
        Test the format slots keeps data without slots untouched.
        '''
        cdata = {
                'args': [
                    'arg',
                ],
                'kwargs': {
                    'key': 'val',
                }
        }
        self.state_obj.format_slots(cdata)
        self.assertEqual(cdata, {'args': ['arg'], 'kwargs': {'key': 'val'}})

    def test_format_slots_arg(self):
        '''
        Test the format slots is calling a slot specified in args with corresponding arguments.
        '''
        cdata = {
                'args': [
                    '__slot__:salt:mod.fun(fun_arg, fun_key=fun_val)',
                ],
                'kwargs': {
                    'key': 'val',
                }
        }
        mock = MagicMock(return_value='fun_return')
        with patch.dict(self.state_obj.functions, {'mod.fun': mock}):
            self.state_obj.format_slots(cdata)
        mock.assert_called_once_with('fun_arg', fun_key='fun_val')
        self.assertEqual(cdata, {'args': ['fun_return'], 'kwargs': {'key': 'val'}})

    def test_format_slots_kwarg(self):
        '''
        Test the format slots is calling a slot specified in kwargs with corresponding arguments.
        '''
        cdata = {
            'args': [
                'arg',
            ],
            'kwargs': {
                'key': '__slot__:salt:mod.fun(fun_arg, fun_key=fun_val)',
            }
        }
        mock = MagicMock(return_value='fun_return')
        with patch.dict(self.state_obj.functions, {'mod.fun': mock}):
            self.state_obj.format_slots(cdata)
        mock.assert_called_once_with('fun_arg', fun_key='fun_val')
        self.assertEqual(cdata, {'args': ['arg'], 'kwargs': {'key': 'fun_return'}})

    def test_format_slots_multi(self):
        '''
        Test the format slots is calling all slots with corresponding arguments when multiple slots
        specified.
        '''
        cdata = {
            'args': [
                '__slot__:salt:test_mod.fun_a(a_arg, a_key=a_kwarg)',
                '__slot__:salt:test_mod.fun_b(b_arg, b_key=b_kwarg)',
            ],
            'kwargs': {
                'kw_key_1': '__slot__:salt:test_mod.fun_c(c_arg, c_key=c_kwarg)',
                'kw_key_2': '__slot__:salt:test_mod.fun_d(d_arg, d_key=d_kwarg)',
            }
        }
        mock_a = MagicMock(return_value='fun_a_return')
        mock_b = MagicMock(return_value='fun_b_return')
        mock_c = MagicMock(return_value='fun_c_return')
        mock_d = MagicMock(return_value='fun_d_return')
        with patch.dict(self.state_obj.functions, {'test_mod.fun_a': mock_a,
                                                   'test_mod.fun_b': mock_b,
                                                   'test_mod.fun_c': mock_c,
                                                   'test_mod.fun_d': mock_d}):
            self.state_obj.format_slots(cdata)
        mock_a.assert_called_once_with('a_arg', a_key='a_kwarg')
        mock_b.assert_called_once_with('b_arg', b_key='b_kwarg')
        mock_c.assert_called_once_with('c_arg', c_key='c_kwarg')
        mock_d.assert_called_once_with('d_arg', d_key='d_kwarg')
        self.assertEqual(cdata, {'args': ['fun_a_return',
                                          'fun_b_return'],
                                 'kwargs': {'kw_key_1': 'fun_c_return',
                                            'kw_key_2': 'fun_d_return'}})

    def test_format_slots_malformed(self):
        '''
        Test the format slots keeps malformed slots untouched.
        '''
        sls_data = {
            'args': [
                '__slot__:NOT_SUPPORTED:not.called()',
                '__slot__:salt:not.called(',
                '__slot__:salt:',
                '__slot__:salt',
                '__slot__:',
                '__slot__',
            ],
            'kwargs': {
                'key3': '__slot__:NOT_SUPPORTED:not.called()',
                'key4': '__slot__:salt:not.called(',
                'key5': '__slot__:salt:',
                'key6': '__slot__:salt',
                'key7': '__slot__:',
                'key8': '__slot__',
            }
        }
        cdata = sls_data.copy()
        mock = MagicMock(return_value='return')
        with patch.dict(self.state_obj.functions, {'not.called': mock}):
            self.state_obj.format_slots(cdata)
        mock.assert_not_called()
        self.assertEqual(cdata, sls_data)
