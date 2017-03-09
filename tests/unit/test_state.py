# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import copy
import os
import sys
import tempfile

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch

# Import Salt libs
import salt.state
import salt.config
import salt.exceptions
from salt.utils.odict import OrderedDict, DefaultOrderedDict


@skipIf(NO_MOCK, NO_MOCK_REASON)
class StateCompilerTestCase(TestCase):
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
        ret = {'changes': {u'Français': {'old': 'something old',
                                         'new': 'something new'}},
               'result': True}
        salt.state.format_log(ret)

    @skipIf(sys.version_info < (2, 7), 'Context manager in assertEquals only available in > Py2.7')
    @patch('salt.state.State._gather_pillar')
    def test_render_error_on_invalid_requisite(self, state_patch):
        '''
        Test that the state compiler correctly deliver a rendering
        exception when a requisite cannot be resolved
        '''
        high_data = {'git': OrderedDict([('pkg', [OrderedDict([('require', [OrderedDict([('file', OrderedDict([('test1', 'test')]))])])]), 'installed', {'order': 10000}]), ('__sls__', u'issue_35226'), ('__env__', 'base')])}
        minion_opts = salt.config.minion_config(os.path.join(integration.TMP_CONF_DIR, 'minion'))
        minion_opts['pillar'] = {'git': OrderedDict([('test1', 'test')])}
        state_obj = salt.state.State(minion_opts)
        with self.assertRaises(salt.exceptions.SaltRenderError):
            state_obj.call_high(high_data)


class HighStateTestCase(TestCase):
    def setUp(self):
        self.root_dir = tempfile.mkdtemp(dir=integration.TMP)
        self.state_tree_dir = os.path.join(self.root_dir, 'state_tree')
        self.cache_dir = os.path.join(self.root_dir, 'cachedir')
        if not os.path.isdir(self.root_dir):
            os.makedirs(self.root_dir)

        if not os.path.isdir(self.state_tree_dir):
            os.makedirs(self.state_tree_dir)

        if not os.path.isdir(self.cache_dir):
            os.makedirs(self.cache_dir)
        self.config = salt.config.minion_config(None)
        self.config['root_dir'] = self.root_dir
        self.config['state_events'] = False
        self.config['id'] = 'match'
        self.config['file_client'] = 'local'
        self.config['file_roots'] = dict(base=[self.state_tree_dir])
        self.config['cachedir'] = self.cache_dir
        self.config['test'] = False
        self.highstate = salt.state.HighState(self.config)
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


class TopFileMergeTestCase(TestCase):
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

        # Version without the other envs defined in the base top file
        self.tops_limited_base = copy.deepcopy(self.tops)
        self.tops_limited_base['base'] = OrderedDict([
            ('base', OrderedDict([('*', ['base_base'])])),
        ])

    @staticmethod
    def highstate(**opts):
        config = salt.config.minion_config(None)
        root_dir = tempfile.mkdtemp(dir=integration.TMP)
        state_tree_dir = os.path.join(root_dir, 'state_tree')
        cache_dir = os.path.join(root_dir, 'cachedir')
        config['root_dir'] = root_dir
        config['state_events'] = False
        config['id'] = 'match'
        config['file_client'] = 'local'
        config['file_roots'] = dict(base=[state_tree_dir])
        config['cachedir'] = cache_dir
        config['test'] = False
        config['default_top'] = 'base'
        config.update(opts)
        return salt.state.HighState(config)

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
