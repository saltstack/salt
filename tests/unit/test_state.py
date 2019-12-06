# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil
import tempfile

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.runtests import RUNTIME_VARS

# Import Salt libs
import salt.exceptions
import salt.state
from salt.utils.odict import OrderedDict
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
        root_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.state_tree_dir = os.path.join(root_dir, 'state_tree')
        cache_dir = os.path.join(root_dir, 'cachedir')
        for dpath in (root_dir, self.state_tree_dir, cache_dir):
            if not os.path.isdir(dpath):
                os.makedirs(dpath)

        overrides = {}
        overrides['root_dir'] = root_dir
        overrides['state_events'] = False
        overrides['id'] = 'match'
        overrides['file_client'] = 'local'
        overrides['file_roots'] = dict(base=[self.state_tree_dir])
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

    def test_find_sls_ids_with_exclude(self):
        '''
        See https://github.com/saltstack/salt/issues/47182
        '''
        sls_dir = 'issue-47182'
        shutil.copytree(
            os.path.join(RUNTIME_VARS.BASE_FILES, sls_dir),
            os.path.join(self.state_tree_dir, sls_dir)
        )
        shutil.move(
            os.path.join(self.state_tree_dir, sls_dir, 'top.sls'),
            self.state_tree_dir
        )
        # Manually compile the high data. We don't have to worry about all of
        # the normal error checking we do here since we know that all the SLS
        # files exist and there is no whitelist/blacklist being used.
        top = self.highstate.get_top()  # pylint: disable=assignment-from-none
        matches = self.highstate.top_matches(top)
        high, _ = self.highstate.render_highstate(matches)
        ret = salt.state.find_sls_ids('issue-47182.stateA.newer', high)
        self.assertEqual(ret, [('somestuff', 'cmd')])


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

    def test_format_slots_dict_arg(self):
        '''
        Test the format slots is calling a slot specified in dict arg.
        '''
        cdata = {
                'args': [
                    {'subarg': '__slot__:salt:mod.fun(fun_arg, fun_key=fun_val)'},
                ],
                'kwargs': {
                    'key': 'val',
                }
        }
        mock = MagicMock(return_value='fun_return')
        with patch.dict(self.state_obj.functions, {'mod.fun': mock}):
            self.state_obj.format_slots(cdata)
        mock.assert_called_once_with('fun_arg', fun_key='fun_val')
        self.assertEqual(cdata, {'args': [{'subarg': 'fun_return'}], 'kwargs': {'key': 'val'}})

    def test_format_slots_listdict_arg(self):
        '''
        Test the format slots is calling a slot specified in list containing a dict.
        '''
        cdata = {
                'args': [[
                    {'subarg': '__slot__:salt:mod.fun(fun_arg, fun_key=fun_val)'},
                ]],
                'kwargs': {
                    'key': 'val',
                }
        }
        mock = MagicMock(return_value='fun_return')
        with patch.dict(self.state_obj.functions, {'mod.fun': mock}):
            self.state_obj.format_slots(cdata)
        mock.assert_called_once_with('fun_arg', fun_key='fun_val')
        self.assertEqual(cdata, {'args': [[{'subarg': 'fun_return'}]], 'kwargs': {'key': 'val'}})

    def test_format_slots_liststr_arg(self):
        '''
        Test the format slots is calling a slot specified in list containing a dict.
        '''
        cdata = {
                'args': [[
                    '__slot__:salt:mod.fun(fun_arg, fun_key=fun_val)',
                ]],
                'kwargs': {
                    'key': 'val',
                }
        }
        mock = MagicMock(return_value='fun_return')
        with patch.dict(self.state_obj.functions, {'mod.fun': mock}):
            self.state_obj.format_slots(cdata)
        mock.assert_called_once_with('fun_arg', fun_key='fun_val')
        self.assertEqual(cdata, {'args': [['fun_return']], 'kwargs': {'key': 'val'}})

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

    def test_slot_traverse_dict(self):
        '''
        Test the slot parsing of dict response.
        '''
        cdata = {
            'args': [
                'arg',
            ],
            'kwargs': {
                'key': '__slot__:salt:mod.fun(fun_arg, fun_key=fun_val).key1',
            }
        }
        return_data = {'key1': 'value1'}
        mock = MagicMock(return_value=return_data)
        with patch.dict(self.state_obj.functions, {'mod.fun': mock}):
            self.state_obj.format_slots(cdata)
        mock.assert_called_once_with('fun_arg', fun_key='fun_val')
        self.assertEqual(cdata, {'args': ['arg'], 'kwargs': {'key': 'value1'}})

    def test_slot_append(self):
        '''
        Test the slot parsing of dict response.
        '''
        cdata = {
            'args': [
                'arg',
            ],
            'kwargs': {
                'key': '__slot__:salt:mod.fun(fun_arg, fun_key=fun_val).key1 ~ thing~',
            }
        }
        return_data = {'key1': 'value1'}
        mock = MagicMock(return_value=return_data)
        with patch.dict(self.state_obj.functions, {'mod.fun': mock}):
            self.state_obj.format_slots(cdata)
        mock.assert_called_once_with('fun_arg', fun_key='fun_val')
        self.assertEqual(cdata, {'args': ['arg'], 'kwargs': {'key': 'value1thing~'}})
