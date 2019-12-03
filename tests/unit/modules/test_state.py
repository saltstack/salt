# -*- coding: utf-8 -*-
'''
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import os
import shutil
import tempfile
import textwrap
import time

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.paths import TMP, TMP_CONF_DIR
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    Mock,
    MagicMock,
    patch,
    mock_open,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.config
import salt.loader
import salt.state
import salt.utils.args
import salt.utils.files
import salt.utils.json
import salt.utils.hashutils
import salt.utils.odict
import salt.utils.platform
import salt.utils.state
import salt.modules.state as state
from salt.exceptions import CommandExecutionError, SaltInvocationError
import salt.modules.config as config
from salt.ext import six


class MockState(object):
    '''
        Mock class
    '''
    def __init__(self):
        pass

    class State(object):
        '''
            Mock state class
        '''
        flag = None

        def __init__(self,
                     opts,
                     pillar_override=False,
                     pillar_enc=None,
                     initial_pillar=None):
            pass

        def verify_data(self, data):
            '''
                Mock verify_data method
            '''
            data = data
            if self.flag:
                return True
            else:
                return False

        @staticmethod
        def call(data):
            '''
                Mock call method
            '''
            data = data
            return list

        @staticmethod
        def call_high(data, orchestration_jid=None):
            '''
                Mock call_high method
            '''
            data = data
            return True

        @staticmethod
        def call_template_str(data):
            '''
                Mock call_template_str method
            '''
            data = data
            return True

        @staticmethod
        def _mod_init(data):
            '''
                Mock _mod_init method
            '''
            data = data
            return True

        def verify_high(self, data):
            '''
                Mock verify_high method
            '''
            data = data
            if self.flag:
                return True
            else:
                return -1

        @staticmethod
        def compile_high_data(data):
            '''
                Mock compile_high_data
            '''
            data = data
            return [{"__id__": "ABC"}]

        @staticmethod
        def call_chunk(data, data1, data2):
            '''
                Mock call_chunk method
            '''
            data = data
            data1 = data1
            data2 = data2
            return {'': 'ABC'}

        @staticmethod
        def call_chunks(data):
            '''
                Mock call_chunks method
            '''
            data = data
            return True

        @staticmethod
        def call_listen(data, ret):
            '''
                Mock call_listen method
            '''
            data = data
            ret = ret
            return True

        def requisite_in(self, data):  # pylint: disable=unused-argument
            return data, []

    class HighState(object):
        '''
            Mock HighState class
        '''
        flag = False
        opts = {'state_top': '',
                'pillar': {}}

        def __init__(self, opts, pillar_override=None, *args, **kwargs):
            self.building_highstate = salt.utils.odict.OrderedDict
            self.state = MockState.State(opts,
                                         pillar_override=pillar_override)

        def render_state(self, sls, saltenv, mods, matches, local=False):
            '''
                Mock render_state method
            '''
            sls = sls
            saltenv = saltenv
            mods = mods
            matches = matches
            local = local
            if self.flag:
                return {}, True
            else:
                return {}, False

        @staticmethod
        def get_top():
            '''
                Mock get_top method
            '''
            return "_top"

        def verify_tops(self, data):
            '''
                Mock verify_tops method
            '''
            data = data
            if self.flag:
                return ["a", "b"]
            else:
                return []

        @staticmethod
        def top_matches(data):
            '''
                Mock top_matches method
            '''
            data = data
            return ["a", "b", "c"]

        @staticmethod
        def push_active():
            '''
                Mock push_active method
            '''
            return True

        @staticmethod
        def compile_highstate():
            '''
                Mock compile_highstate method
            '''
            return "A"

        @staticmethod
        def compile_state_usage():
            '''
                Mock compile_state_usage method
            '''
            return "A"

        @staticmethod
        def pop_active():
            '''
                Mock pop_active method
            '''
            return True

        @staticmethod
        def compile_low_chunks():
            '''
                Mock compile_low_chunks method
            '''
            return [{"__id__": "ABC", "__sls__": "abc"}]

        def render_highstate(self, data):
            '''
                Mock render_highstate method
            '''
            data = data
            if self.flag:
                return ["a", "b"], True
            else:
                return ["a", "b"], False

        @staticmethod
        def call_highstate(exclude, cache, cache_name, force=None,
                           whitelist=None, orchestration_jid=None):
            '''
                Mock call_highstate method
            '''
            exclude = exclude
            cache = cache
            cache_name = cache_name
            force = force
            whitelist = whitelist
            return True


class MockSerial(object):
    '''
        Mock Class
    '''
    def __init__(self):
        pass

    class Serial(object):
        '''
            Mock Serial class
        '''
        def __init__(self, data):
            data = data

        @staticmethod
        def load(data):
            '''
                Mock load method
            '''
            data = data
            return {"A": "B"}

        @staticmethod
        def dump(data, data1):
            '''
                Mock dump method
            '''
            data = data
            data1 = data1
            return True


class MockTarFile(object):
    '''
        Mock tarfile class
    '''
    path = os.sep + "tmp"

    def __init__(self):
        pass

    @staticmethod
    def open(data, data1):
        '''
            Mock open method
        '''
        data = data
        data1 = data1
        return MockTarFile

    @staticmethod
    def getmembers():
        '''
            Mock getmembers method
        '''
        return [MockTarFile]

    @staticmethod
    def extractall(data):
        '''
            Mock extractall method
        '''
        data = data
        return True

    @staticmethod
    def close():
        '''
            Mock close method
        '''
        return True


@skipIf(NO_MOCK, NO_MOCK_REASON)
class StateTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Test case for salt.modules.state
    '''

    def setup_loader_modules(self):
        utils = salt.loader.utils(
            salt.config.DEFAULT_MINION_OPTS.copy(),
            whitelist=['state', 'args', 'systemd', 'path', 'platform']
        )
        utils.keys()
        patcher = patch('salt.modules.state.salt.state', MockState())
        patcher.start()
        self.addCleanup(patcher.stop)
        return {
            state: {
                '__opts__': {
                    'cachedir': '/D',
                    'saltenv': None,
                    '__cli': 'salt',
                },
                '__utils__': utils,
                '__salt__': {
                    'config.get': config.get,
                    'config.option': MagicMock(return_value=''),
                }
            },
            config: {
                '__opts__': {},
                '__pillar__': {},
            },

        }

    def test_running(self):
        '''
            Test of checking i fthe state function is already running
        '''
        self.assertEqual(state.running(True), [])

        mock = MagicMock(side_effect=[[{"fun": "state.running", "pid": "4126",
                                        "jid": "20150325123407204096"}], []])
        with patch.dict(state.__salt__,
                        {'saltutil.is_running': mock}
                        ):
            self.assertListEqual(state.running(),
                                 ['The function "state.running"'
                                  ' is running as PID 4126 and '
                                  'was started at 2015, Mar 25 12:34:07.'
                                  '204096 with jid 20150325123407204096'])

            self.assertListEqual(state.running(), [])

    def test_low(self):
        '''
            Test of executing a single low data call
        '''
        mock = MagicMock(side_effect=[False, None, None])
        with patch.object(state, '_check_queue', mock):
            self.assertFalse(state.low({"state": "pkg", "fun": "installed",
                                        "name": "vi"}))

            MockState.State.flag = False
            self.assertEqual(state.low({"state": "pkg", "fun": "installed",
                                        "name": "vi"}), list)

            MockState.State.flag = True
            self.assertTrue(state.low({"state": "pkg", "fun": "installed",
                                       "name": "vi"}))

    def test_high(self):
        '''
            Test for checking the state system
        '''
        mock = MagicMock(side_effect=[False, None])
        with patch.object(state, '_check_queue', mock):
            self.assertFalse(state.high({"vim": {"pkg": ["installed"]}}))

            mock = MagicMock(return_value={"test": True})
            with patch.object(salt.utils.state, 'get_sls_opts', mock):
                self.assertTrue(state.high({"vim": {"pkg": ["installed"]}}))

    def test_template(self):
        '''
            Test of executing the information
            stored in a template file on the minion
        '''
        mock = MagicMock(side_effect=[False, None, None])
        with patch.object(state, '_check_queue', mock):
            self.assertFalse(state.template('/home/salt/salt.sls'))

            MockState.HighState.flag = True
            self.assertTrue(state.template('/home/salt/salt.sls'))

            MockState.HighState.flag = False
            self.assertTrue(state.template('/home/salt/salt.sls'))

    def test_template_str(self):
        '''
            Test for Executing the information
            stored in a string from an sls template
        '''
        mock = MagicMock(side_effect=[False, None])
        with patch.object(state, '_check_queue', mock):
            self.assertFalse(state.template_str('Template String'))

            self.assertTrue(state.template_str('Template String'))

    def test_apply_(self):
        '''
            Test to apply states
        '''
        mock = MagicMock(return_value=True)
        with patch.object(state, 'sls', mock):
            self.assertTrue(state.apply_(True))

        with patch.object(state, 'highstate', mock):
            self.assertTrue(state.apply_(None))

    def test_list_disabled(self):
        '''
            Test to list disabled states
        '''
        mock = MagicMock(return_value=["A", "B", "C"])
        with patch.dict(state.__salt__, {'grains.get': mock}):
            self.assertListEqual(state.list_disabled(), ["A", "B", "C"])

    def test_enable(self):
        '''
            Test to Enable state function or sls run
        '''
        mock = MagicMock(return_value=["A", "B"])
        with patch.dict(state.__salt__, {'grains.get': mock}):
            mock = MagicMock(return_value=[])
            with patch.dict(state.__salt__, {'grains.setval': mock}):
                mock = MagicMock(return_value=[])
                with patch.dict(state.__salt__, {'saltutil.refresh_modules':
                                                 mock}):
                    self.assertDictEqual(state.enable("A"),
                                         {'msg': 'Info: A state enabled.',
                                          'res': True})

                    self.assertDictEqual(state.enable("Z"),
                                         {'msg': 'Info: Z state already '
                                          'enabled.', 'res': True})

    def test_disable(self):
        '''
            Test to disable state run
        '''
        mock = MagicMock(return_value=["C", "D"])
        with patch.dict(state.__salt__, {'grains.get': mock}):
            mock = MagicMock(return_value=[])
            with patch.dict(state.__salt__, {'grains.setval': mock}):
                mock = MagicMock(return_value=[])
                with patch.dict(state.__salt__, {'saltutil.refresh_modules':
                                                 mock}):
                    self.assertDictEqual(state.disable("C"),
                                         {'msg': 'Info: C state '
                                          'already disabled.',
                                          'res': True})

                    self.assertDictEqual(state.disable("Z"),
                                         {'msg': 'Info: Z state '
                                          'disabled.', 'res': True})

    def test_clear_cache(self):
        '''
            Test to clear out cached state file
        '''
        mock = MagicMock(return_value=["A.cache.p", "B.cache.p", "C"])
        with patch.object(os, 'listdir', mock):
            mock = MagicMock(return_value=True)
            with patch.object(os.path, 'isfile', mock):
                mock = MagicMock(return_value=True)
                with patch.object(os, 'remove', mock):
                    self.assertEqual(state.clear_cache(),
                                     ['A.cache.p',
                                      'B.cache.p'])

    def test_single(self):
        '''
            Test to execute single state function
        '''
        ret = {'pkg_|-name=vim_|-name=vim_|-installed': list}
        mock = MagicMock(side_effect=["A", None, None, None, None])
        with patch.object(state, '_check_queue', mock):
            self.assertEqual(state.single("pkg.installed",
                                          " name=vim"), "A")

            self.assertEqual(state.single("pk", "name=vim"),
                             "Invalid function passed")

            with patch.dict(state.__opts__, {"test": "install"}):
                mock = MagicMock(return_value={"test": ""})
                with patch.object(salt.utils.state, 'get_sls_opts', mock):
                    mock = MagicMock(return_value=True)
                    with patch.object(salt.utils.args, 'test_mode', mock):
                        self.assertRaises(SaltInvocationError,
                                          state.single,
                                          "pkg.installed",
                                          "name=vim",
                                          pillar="A")

                        MockState.State.flag = True
                        self.assertTrue(state.single("pkg.installed",
                                                     "name=vim"))

                        MockState.State.flag = False
                        self.assertDictEqual(state.single("pkg.installed",
                                                          "name=vim"), ret)

    def test_show_top(self):
        '''
            Test to return the top data that the minion will use for a highstate
        '''
        mock = MagicMock(side_effect=["A", None, None])
        with patch.object(state, '_check_queue', mock):
            self.assertEqual(state.show_top(), "A")

            MockState.HighState.flag = True
            self.assertListEqual(state.show_top(), ['a', 'b'])

            MockState.HighState.flag = False
            self.assertListEqual(state.show_top(), ['a', 'b', 'c'])

    def test_run_request(self):
        '''
            Test to Execute the pending state request
        '''
        mock = MagicMock(side_effect=[{},
                                      {"name": "A"},
                                      {"name": {'mods': "A",
                                                'kwargs': {}}}])
        with patch.object(state, 'check_request', mock):
            self.assertDictEqual(state.run_request("A"), {})

            self.assertDictEqual(state.run_request("A"), {})

            mock = MagicMock(return_value=["True"])
            with patch.object(state, 'apply_', mock):
                mock = MagicMock(return_value="")
                with patch.object(os, 'remove', mock):
                    self.assertListEqual(state.run_request("name"),
                                         ["True"])

    def test_show_highstate(self):
        '''
            Test to retrieve the highstate data from the salt master
        '''
        mock = MagicMock(side_effect=["A", None, None])
        with patch.object(state, '_check_queue', mock):
            self.assertEqual(state.show_highstate(), "A")

            self.assertRaises(SaltInvocationError,
                              state.show_highstate,
                              pillar="A")

            self.assertEqual(state.show_highstate(), "A")

    def test_show_lowstate(self):
        '''
            Test to list out the low data that will be applied to this minion
        '''
        mock = MagicMock(side_effect=["A", None])
        with patch.object(state, '_check_queue', mock):
            self.assertRaises(AssertionError, state.show_lowstate)

            self.assertTrue(state.show_lowstate())

    def test_show_state_usage(self):
        '''
            Test to list out the state usage that will be applied to this minion
        '''

        mock = MagicMock(side_effect=["A", None, None])
        with patch.object(state, '_check_queue', mock):
            self.assertEqual(state.show_state_usage(), "A")

            self.assertRaises(SaltInvocationError,
                              state.show_state_usage,
                              pillar="A")

            self.assertEqual(state.show_state_usage(), "A")

    def test_show_states(self):
        '''
            Test to display the low data from a specific sls
        '''
        mock = MagicMock(side_effect=["A", None])
        with patch.object(state, '_check_queue', mock):

            self.assertEqual(state.show_low_sls("foo"), "A")
            self.assertListEqual(state.show_states("foo"), ['abc'])

    def test_show_states_missing_sls(self):
        '''
        Test state.show_states when a sls file defined
        in a top.sls file is missing
        '''
        msg = ["No matching sls found for 'cloud' in evn 'base'"]
        chunks_mock = MagicMock(side_effect=[msg])
        mock = MagicMock(side_effect=["A", None])
        with patch.object(state, '_check_queue', mock),\
            patch('salt.state.HighState.compile_low_chunks', chunks_mock):
            self.assertEqual(state.show_low_sls("foo"), "A")
            self.assertListEqual(state.show_states("foo"), [msg[0]])

    def test_sls_id(self):
        '''
            Test to call a single ID from the
            named module(s) and handle all requisites
        '''
        mock = MagicMock(side_effect=["A", None, None, None])
        with patch.object(state, '_check_queue', mock):
            self.assertEqual(state.sls_id("apache", "http"), "A")

            with patch.dict(state.__opts__, {"test": "A"}):
                mock = MagicMock(
                    return_value={'test': True,
                                  'saltenv': None}
                )
                with patch.object(salt.utils.state, 'get_sls_opts', mock):
                    mock = MagicMock(return_value=True)
                    with patch.object(salt.utils.args, 'test_mode', mock):
                        MockState.State.flag = True
                        MockState.HighState.flag = True
                        self.assertEqual(state.sls_id("apache", "http"), 2)

                        MockState.State.flag = False
                        self.assertDictEqual(state.sls_id("ABC", "http"),
                                             {'': 'ABC'})
                        self.assertRaises(SaltInvocationError,
                                          state.sls_id,
                                          "DEF", "http")

    def test_show_low_sls(self):
        '''
            Test to display the low data from a specific sls
        '''
        mock = MagicMock(side_effect=["A", None, None])
        with patch.object(state, '_check_queue', mock):
            self.assertEqual(state.show_low_sls("foo"), "A")

            with patch.dict(state.__opts__, {"test": "A"}):
                mock = MagicMock(
                    return_value={'test': True,
                                  'saltenv': None}
                )
                with patch.object(salt.utils.state, 'get_sls_opts', mock):
                    MockState.State.flag = True
                    MockState.HighState.flag = True
                    self.assertEqual(state.show_low_sls("foo"), 2)

                    MockState.State.flag = False
                    self.assertListEqual(state.show_low_sls("foo"),
                                         [{'__id__': 'ABC'}])

    def test_show_sls(self):
        '''
            Test to display the state data from a specific sls
        '''
        mock = MagicMock(side_effect=["A", None, None, None])
        with patch.object(state, '_check_queue', mock):
            self.assertEqual(state.show_sls("foo"), "A")

            with patch.dict(state.__opts__, {"test": "A"}):
                mock = MagicMock(
                    return_value={'test': True,
                                  'saltenv': None}
                )
                with patch.object(salt.utils.state, 'get_sls_opts', mock):
                    mock = MagicMock(return_value=True)
                    with patch.object(salt.utils.args, 'test_mode', mock):
                        self.assertRaises(SaltInvocationError,
                                          state.show_sls,
                                          "foo",
                                          pillar="A")

                        MockState.State.flag = True
                        self.assertEqual(state.show_sls("foo"), 2)

                        MockState.State.flag = False
                        self.assertListEqual(state.show_sls("foo"),
                                             ['a', 'b'])

    def test_sls_exists(self):
        '''
            Test of sls_exists
        '''
        test_state = {}
        test_missing_state = []

        mock = MagicMock(return_value=test_state)
        with patch.object(state, 'show_sls', mock):
            self.assertTrue(state.sls_exists("state_name"))
        mock = MagicMock(return_value=test_missing_state)
        with patch.object(state, 'show_sls', mock):
            self.assertFalse(state.sls_exists("missing_state"))

    def test_id_exists(self):
        '''
            Test of id_exists
        '''
        test_state = [{
                        "key1": "value1",
                        "name": "value1",
                        "state": "file",
                        "fun": "test",
                        "__env__": "base",
                        "__sls__": "test-sls",
                        "order": 10000,
                        "__id__": "state_id1"
                    },
                    {
                        "key2": "value2",
                        "name": "value2",
                        "state": "file",
                        "fun": "directory",
                        "__env__": "base",
                        "__sls__": "test-sls",
                        "order": 10001,
                        "__id__": "state_id2"
                    }]
        mock = MagicMock(return_value=test_state)
        with patch.object(state, 'show_low_sls', mock):
            self.assertTrue(state.id_exists("state_id1,state_id2", "test-sls"))
            self.assertFalse(state.id_exists("invalid", "state_name"))

    def test_top(self):
        '''
            Test to execute a specific top file
        '''
        ret = ['Pillar failed to render with the following messages:', 'E']
        mock = MagicMock(side_effect=["A", None, None, None])
        with patch.object(state, '_check_queue', mock):
            self.assertEqual(state.top("reverse_top.sls"), "A")

            mock = MagicMock(side_effect=[['E'], None, None])
            with patch.object(state, '_get_pillar_errors', mock):
                with patch.dict(state.__pillar__, {"_errors": ['E']}):
                    self.assertListEqual(state.top("reverse_top.sls"), ret)

                with patch.dict(state.__opts__, {"test": "A"}):
                    mock = MagicMock(return_value={'test': True})
                    with patch.object(salt.utils.state, 'get_sls_opts', mock):
                        mock = MagicMock(return_value=True)
                        with patch.object(salt.utils.args, 'test_mode', mock):
                            self.assertRaises(SaltInvocationError,
                                              state.top,
                                              "reverse_top.sls",
                                              pillar="A")

                            mock = MagicMock(
                                             return_value
                                             =
                                             'salt://reverse_top.sls')
                            with patch.object(os.path, 'join', mock):
                                mock = MagicMock(return_value=True)
                                with patch.object(state, '_set_retcode',
                                                  mock):
                                    self.assertTrue(
                                                    state.
                                                    top("reverse_top.sls "
                                                        "exclude=exclude.sls"))

    def test_highstate(self):
        '''
            Test to retrieve the state data from the
            salt master for the minion and execute it
        '''
        arg = "whitelist=sls1.sls"
        mock = MagicMock(side_effect=[True, False, False, False])
        with patch.object(state, '_disabled', mock):
            self.assertDictEqual(state.highstate("whitelist=sls1.sls"),
                                 {'comment': 'Disabled',
                                  'name': 'Salt highstate run is disabled. '
                                  'To re-enable, run state.enable highstate',
                                  'result': 'False'})

            mock = MagicMock(side_effect=["A", None, None])
            with patch.object(state, '_check_queue', mock):
                self.assertEqual(state.highstate("whitelist=sls1.sls"), "A")

                with patch.dict(state.__opts__, {"test": "A"}):
                    mock = MagicMock(return_value={'test': True})
                    with patch.object(salt.utils.state, 'get_sls_opts', mock):
                        self.assertRaises(SaltInvocationError,
                                          state.highstate,
                                          "whitelist=sls1.sls",
                                          pillar="A")

                        mock = MagicMock(return_value="A")
                        with patch.object(state, '_filter_running',
                                          mock):
                            mock = MagicMock(return_value=True)
                            with patch.object(state, '_filter_running',
                                              mock):
                                mock = MagicMock(return_value=True)
                                with patch.object(salt.payload, 'Serial',
                                                  mock):
                                    with patch.object(os.path,
                                                      'join', mock):
                                        with patch.object(
                                                          state,
                                                          '_set'
                                                          '_retcode',
                                                          mock):
                                            self.assertTrue(state.
                                                            highstate
                                                            (arg))

    def test_clear_request(self):
        '''
            Test to clear out the state execution request without executing it
        '''
        mock = MagicMock(return_value=True)
        with patch.object(salt.payload, 'Serial', mock):
            mock = MagicMock(side_effect=[False, True, True])
            with patch.object(os.path, 'isfile', mock):
                self.assertTrue(state.clear_request("A"))

                mock = MagicMock(return_value=True)
                with patch.object(os, 'remove', mock):
                    self.assertTrue(state.clear_request())

                mock = MagicMock(return_value={})
                with patch.object(state, 'check_request', mock):
                    self.assertFalse(state.clear_request("A"))

    def test_check_request(self):
        '''
            Test to return the state request information
        '''
        with patch('salt.modules.state.salt.payload', MockSerial):
            mock = MagicMock(side_effect=[True, True, False])
            with patch.object(os.path, 'isfile', mock):
                with patch('salt.utils.files.fopen', mock_open()):
                    self.assertDictEqual(state.check_request(), {'A': 'B'})

                with patch('salt.utils.files.fopen', mock_open()):
                    self.assertEqual(state.check_request("A"), 'B')

                self.assertDictEqual(state.check_request(), {})

    def test_request(self):
        '''
            Test to request the local admin execute a state run
        '''
        mock = MagicMock(return_value=True)
        with patch.object(state, 'apply_', mock):
            mock = MagicMock(return_value=True)
            with patch.object(os.path, 'join', mock):
                mock = MagicMock(return_value=
                                 {"test_run": "",
                                  "mods": "",
                                  "kwargs": ""})
                with patch.object(state, 'check_request', mock):
                    mock = MagicMock(return_value=True)
                    with patch.object(os, 'umask', mock):
                        with patch.object(salt.utils.platform, 'is_windows', mock):
                            with patch.dict(state.__salt__, {'cmd.run': mock}):
                                with patch('salt.utils.files.fopen', mock_open()):
                                    mock = MagicMock(return_value=True)
                                    with patch.object(os, 'umask', mock):
                                        self.assertTrue(state.request("A"))

    def test_sls(self):
        '''
            Test to execute a set list of state files from an environment
        '''
        arg = "core,edit.vim dev"
        ret = ['Pillar failed to render with the following messages:', 'E', '1']
        mock = MagicMock(return_value=True)
        with patch.object(state, 'running', mock):
            with patch.dict(state.__context__, {"retcode": 1}):
                self.assertEqual(state.sls("core,edit.vim dev"), True)

        mock = MagicMock(side_effect=[True, True, True, True, True, True])
        with patch.object(state, '_wait', mock):
            mock = MagicMock(side_effect=[["A"], [], [], [], [], []])
            with patch.object(state, '_disabled', mock):
                with patch.dict(state.__context__, {"retcode": 1}):
                    self.assertEqual(
                                     state.sls("core,edit.vim dev",
                                               None,
                                               None,
                                               True),
                                     ["A"])

                mock = MagicMock(side_effect=[['E', '1'], None, None, None, None])
                with patch.object(state, '_get_pillar_errors', mock):
                    with patch.dict(state.__context__, {"retcode": 5}):
                        with patch.dict(state.__pillar__, {"_errors": ['E', '1']}):
                            self.assertListEqual(state.sls("core,edit.vim dev",
                                                           None,
                                                           None,
                                                           True), ret)

                    with patch.dict(state.__opts__, {"test": None}):
                        mock = MagicMock(return_value={"test": "",
                                                       "saltenv": None})
                        with patch.object(salt.utils.state, 'get_sls_opts', mock):
                            mock = MagicMock(return_value=True)
                            with patch.object(salt.utils.args,
                                              'test_mode',
                                              mock):
                                self.assertRaises(
                                                  SaltInvocationError,
                                                  state.sls,
                                                  "core,edit.vim dev",
                                                  None,
                                                  None,
                                                  True,
                                                  pillar="A")

                                mock = MagicMock(return_value="/D/cache.cache.p")
                                with patch.object(os.path,
                                                  'join',
                                                  mock):
                                    mock = MagicMock(return_value=True)
                                    with patch.object(os.path,
                                                      'isfile',
                                                      mock):
                                        with patch(
                                                   'salt.utils.files.fopen',
                                                   mock_open(b'')):
                                            self.assertTrue(
                                                            state.sls(arg,
                                                                      None,
                                                                      None,
                                                                      True,
                                                                      cache
                                                                      =True
                                                                      )
                                                            )

                                    MockState.HighState.flag = True
                                    self.assertTrue(state.sls("core,edit"
                                                              ".vim dev",
                                                              None,
                                                              None,
                                                              True)
                                                    )

                                    MockState.HighState.flag = False
                                    mock = MagicMock(return_value=True)
                                    with patch.object(state,
                                                      '_filter_'
                                                      'running',
                                                      mock):
                                        self.sub_test_sls()

    def test_get_test_value(self):
        '''
        Test _get_test_value when opts contains different values
        '''
        test_arg = 'test'
        with patch.dict(state.__opts__, {test_arg: True}):
            self.assertTrue(state._get_test_value(test=None),
                            msg='Failure when {0} is True in __opts__'.format(test_arg))

        with patch.dict(config.__pillar__, {test_arg: 'blah'}):
            self.assertFalse(state._get_test_value(test=None),
                            msg='Failure when {0} is blah in __opts__'.format(test_arg))

        with patch.dict(config.__pillar__, {test_arg: 'true'}):
            self.assertFalse(state._get_test_value(test=None),
                            msg='Failure when {0} is true in __opts__'.format(test_arg))

        with patch.dict(config.__opts__, {test_arg: False}):
            self.assertFalse(state._get_test_value(test=None),
                            msg='Failure when {0} is False in __opts__'.format(test_arg))

        with patch.dict(config.__opts__, {}):
            self.assertFalse(state._get_test_value(test=None),
                            msg='Failure when {0} does not exist in __opts__'.format(test_arg))

        with patch.dict(config.__pillar__, {test_arg: None}):
            self.assertEqual(state._get_test_value(test=None), None,
                            msg='Failure when {0} is None in __opts__'.format(test_arg))

        with patch.dict(config.__pillar__, {test_arg: True}):
            self.assertTrue(state._get_test_value(test=None),
                            msg='Failure when {0} is True in __pillar__'.format(test_arg))

        with patch.dict(config.__pillar__, {'master': {test_arg: True}}):
            self.assertTrue(state._get_test_value(test=None),
                            msg='Failure when {0} is True in master __pillar__'.format(test_arg))

        with patch.dict(config.__pillar__, {'master': {test_arg: False}}):
            with patch.dict(config.__pillar__, {test_arg: True}):
                self.assertTrue(state._get_test_value(test=None),
                                msg='Failure when {0} is False in master __pillar__ and True in pillar'.format(test_arg))

        with patch.dict(config.__pillar__, {'master': {test_arg: True}}):
            with patch.dict(config.__pillar__, {test_arg: False}):
                self.assertFalse(state._get_test_value(test=None),
                                 msg='Failure when {0} is True in master __pillar__ and False in pillar'.format(test_arg))

        with patch.dict(state.__opts__, {'test': False}):
            self.assertFalse(state._get_test_value(test=None),
                             msg='Failure when {0} is False in __opts__'.format(test_arg))

        with patch.dict(state.__opts__, {'test': False}):
            with patch.dict(config.__pillar__, {'master': {test_arg: True}}):
                self.assertTrue(state._get_test_value(test=None),
                                msg='Failure when {0} is False in __opts__'.format(test_arg))

        with patch.dict(state.__opts__, {}):
            self.assertTrue(state._get_test_value(test=True),
                            msg='Failure when test is True as arg')

    def sub_test_sls(self):
        '''
            Sub function of test_sls
        '''
        mock = MagicMock(return_value=True)
        with patch.object(os.path, 'join', mock):
            with patch.object(os, 'umask', mock):
                mock = MagicMock(return_value=False)
                with patch.object(salt.utils.platform, 'is_windows', mock):
                    mock = MagicMock(return_value=True)
                    with patch.object(os, 'umask', mock):
                        with patch.object(state, '_set_retcode', mock):
                            with patch.dict(state.__opts__,
                                            {"test": True}):
                                with patch('salt.utils.files.fopen', mock_open()):
                                    self.assertTrue(state.sls("core,edit"
                                                              ".vim dev",
                                                              None,
                                                              None,
                                                              True))

    def test_sls_sync(self):
        '''
        Test test.sls with the sync argument

        We're only mocking the sync functions we expect to sync. If any other
        sync functions are run then they will raise a KeyError, which we want
        as it will tell us that we are syncing things we shouldn't.
        '''
        mock_empty_list = MagicMock(return_value=[])
        with patch.object(state, 'running', mock_empty_list), \
                patch.object(state, '_disabled', mock_empty_list), \
                patch.object(state, '_get_pillar_errors', mock_empty_list):

            sync_mocks = {
                'saltutil.sync_modules': Mock(),
                'saltutil.sync_states': Mock(),
            }
            with patch.dict(state.__salt__, sync_mocks):
                state.sls('foo', sync_mods='modules,states')

            for key in sync_mocks:
                call_count = sync_mocks[key].call_count
                expected = 1
                assert call_count == expected, \
                    '{0} called {1} time(s) (expected: {2})'.format(
                        key, call_count, expected
                    )

            # Test syncing all
            sync_mocks = {'saltutil.sync_all': Mock()}
            with patch.dict(state.__salt__, sync_mocks):
                state.sls('foo', sync_mods='all')

            for key in sync_mocks:
                call_count = sync_mocks[key].call_count
                expected = 1
                assert call_count == expected, \
                    '{0} called {1} time(s) (expected: {2})'.format(
                        key, call_count, expected
                    )

            # sync_mods=True should be interpreted as sync_mods=all
            sync_mocks = {'saltutil.sync_all': Mock()}
            with patch.dict(state.__salt__, sync_mocks):
                state.sls('foo', sync_mods=True)

            for key in sync_mocks:
                call_count = sync_mocks[key].call_count
                expected = 1
                assert call_count == expected, \
                    '{0} called {1} time(s) (expected: {2})'.format(
                        key, call_count, expected
                    )

            # Test syncing all when "all" is passed along with module types.
            # This tests that we *only* run a sync_all and avoid unnecessary
            # extra syncing.
            sync_mocks = {'saltutil.sync_all': Mock()}
            with patch.dict(state.__salt__, sync_mocks):
                state.sls('foo', sync_mods='modules,all')

            for key in sync_mocks:
                call_count = sync_mocks[key].call_count
                expected = 1
                assert call_count == expected, \
                    '{0} called {1} time(s) (expected: {2})'.format(
                        key, call_count, expected
                    )

    def test_pkg(self):
        '''
            Test to execute a packaged state run
        '''
        tar_file = os.sep + os.path.join('tmp', 'state_pkg.tgz')
        mock = MagicMock(side_effect=[False, True, True, True, True, True,
            True, True, True, True, True])
        mock_json_loads_true = MagicMock(return_value=[True])
        mock_json_loads_dictlist = MagicMock(return_value=[{"test": ""}])
        with patch.object(os.path, 'isfile', mock), \
                patch('salt.modules.state.tarfile', MockTarFile), \
                patch.object(salt.utils, 'json', mock_json_loads_dictlist):
            self.assertEqual(state.pkg(tar_file, "", "md5"), {})

            mock = MagicMock(side_effect=[False, 0, 0, 0, 0])
            with patch.object(salt.utils.hashutils, 'get_hash', mock):
                # Verify hash
                self.assertDictEqual(state.pkg(tar_file, "", "md5"), {})

                # Verify file outside intended root
                self.assertDictEqual(state.pkg(tar_file, 0, "md5"), {})

                MockTarFile.path = ""
                with patch('salt.utils.files.fopen', mock_open()), \
                        patch.object(salt.utils.json, 'loads', mock_json_loads_true):
                    self.assertEqual(state.pkg(tar_file, 0, "md5"), True)

                MockTarFile.path = ""
                if six.PY2:
                    with patch('salt.utils.files.fopen', mock_open()), \
                            patch.dict(state.__utils__, {'state.check_result': MagicMock(return_value=True)}):
                        self.assertTrue(state.pkg(tar_file, 0, "md5"))
                else:
                    with patch('salt.utils.files.fopen', mock_open()):
                        self.assertTrue(state.pkg(tar_file, 0, "md5"))

    def test_lock_saltenv(self):
        '''
        Tests lock_saltenv in each function which accepts saltenv on the CLI
        '''
        lock_msg = 'lock_saltenv is enabled, saltenv cannot be changed'
        empty_list_mock = MagicMock(return_value=[])
        with patch.dict(state.__opts__, {'lock_saltenv': True}), \
                patch.dict(state.__salt__, {'grains.get': empty_list_mock}), \
                patch.object(state, 'running', empty_list_mock):

            # Test high
            with self.assertRaisesRegex(CommandExecutionError, lock_msg):
                state.high(
                    [{"vim": {"pkg": ["installed"]}}], saltenv='base')

            # Test template
            with self.assertRaisesRegex(CommandExecutionError, lock_msg):
                state.template('foo', saltenv='base')

            # Test template_str
            with self.assertRaisesRegex(CommandExecutionError, lock_msg):
                state.template_str('foo', saltenv='base')

            # Test apply_ with SLS
            with self.assertRaisesRegex(CommandExecutionError, lock_msg):
                state.apply_('foo', saltenv='base')

            # Test apply_ with Highstate
            with self.assertRaisesRegex(CommandExecutionError, lock_msg):
                state.apply_(saltenv='base')

            # Test highstate
            with self.assertRaisesRegex(CommandExecutionError, lock_msg):
                state.highstate(saltenv='base')

            # Test sls
            with self.assertRaisesRegex(CommandExecutionError, lock_msg):
                state.sls('foo', saltenv='base')

            # Test top
            with self.assertRaisesRegex(CommandExecutionError, lock_msg):
                state.top('foo.sls', saltenv='base')

            # Test show_highstate
            with self.assertRaisesRegex(CommandExecutionError, lock_msg):
                state.show_highstate(saltenv='base')

            # Test show_lowstate
            with self.assertRaisesRegex(CommandExecutionError, lock_msg):
                state.show_lowstate(saltenv='base')

            # Test sls_id
            with self.assertRaisesRegex(CommandExecutionError, lock_msg):
                state.sls_id('foo', 'bar', saltenv='base')

            # Test show_low_sls
            with self.assertRaisesRegex(CommandExecutionError, lock_msg):
                state.show_low_sls('foo', saltenv='base')

            # Test show_sls
            with self.assertRaisesRegex(CommandExecutionError, lock_msg):
                state.show_sls('foo', saltenv='base')

            # Test show_top
            with self.assertRaisesRegex(CommandExecutionError, lock_msg):
                state.show_top(saltenv='base')

            # Test single
            with self.assertRaisesRegex(CommandExecutionError, lock_msg):
                state.single('foo.bar', name='baz', saltenv='base')

            # Test pkg
            with self.assertRaisesRegex(CommandExecutionError, lock_msg):
                state.pkg(
                    '/tmp/salt_state.tgz',
                    '760a9353810e36f6d81416366fc426dc',
                    'md5',
                    saltenv='base')

    def test_get_pillar_errors_CC(self):
        '''
        Test _get_pillar_errors function.
        CC: External clean, Internal clean
        :return:
        '''
        for int_pillar, ext_pillar in [({'foo': 'bar'}, {'fred': 'baz'}),
                                       ({'foo': 'bar'}, None),
                                       ({}, {'fred': 'baz'})]:
            with patch('salt.modules.state.__pillar__', int_pillar):
                for opts, res in [({'force': True}, None),
                                  ({'force': False}, None),
                                  ({}, None)]:
                    assert res == state._get_pillar_errors(kwargs=opts, pillar=ext_pillar)

    def test_get_pillar_errors_EC(self):
        '''
        Test _get_pillar_errors function.
        EC: External erroneous, Internal clean
        :return:
        '''
        errors = ['failure', 'everywhere']
        for int_pillar, ext_pillar in [({'foo': 'bar'}, {'fred': 'baz', '_errors': errors}),
                                       ({}, {'fred': 'baz', '_errors': errors})]:
            with patch('salt.modules.state.__pillar__', int_pillar):
                for opts, res in [({'force': True}, None),
                                  ({'force': False}, errors),
                                  ({}, errors)]:
                    assert res == state._get_pillar_errors(kwargs=opts, pillar=ext_pillar)

    def test_get_pillar_errors_EE(self):
        '''
        Test _get_pillar_errors function.
        CC: External erroneous, Internal erroneous
        :return:
        '''
        errors = ['failure', 'everywhere']
        for int_pillar, ext_pillar in [({'foo': 'bar', '_errors': errors}, {'fred': 'baz', '_errors': errors})]:
            with patch('salt.modules.state.__pillar__', int_pillar):
                for opts, res in [({'force': True}, None),
                                  ({'force': False}, errors),
                                  ({}, errors)]:
                    assert res == state._get_pillar_errors(kwargs=opts, pillar=ext_pillar)

    def test_get_pillar_errors_CE(self):
        '''
        Test _get_pillar_errors function.
        CC: External clean, Internal erroneous
        :return:
        '''
        errors = ['failure', 'everywhere']
        for int_pillar, ext_pillar in [({'foo': 'bar', '_errors': errors}, {'fred': 'baz'}),
                                       ({'foo': 'bar', '_errors': errors}, None)]:
            with patch('salt.modules.state.__pillar__', int_pillar):
                for opts, res in [({'force': True}, None),
                                  ({'force': False}, errors),
                                  ({}, errors)]:
                    assert res == state._get_pillar_errors(kwargs=opts, pillar=ext_pillar)


class TopFileMergingCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {
            state: {
                '__opts__': salt.config.minion_config(
                    os.path.join(TMP_CONF_DIR, 'minion')
                ),
                '__salt__': {
                    'saltutil.is_running': MagicMock(return_value=[]),
                },
            },
        }

    def setUp(self):
        self.cachedir = tempfile.mkdtemp(dir=TMP)
        self.fileserver_root = tempfile.mkdtemp(dir=TMP)
        self.addCleanup(shutil.rmtree, self.cachedir, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.fileserver_root, ignore_errors=True)

        self.saltenvs = ['base', 'foo', 'bar', 'baz']
        self.saltenv_roots = {
            x: os.path.join(self.fileserver_root, x)
            for x in ('base', 'foo', 'bar', 'baz')
        }
        self.base_top_file = os.path.join(self.saltenv_roots['base'], 'top.sls')
        self.dunder_opts = salt.utils.yaml.safe_load(
            textwrap.dedent('''\
                file_client: local
                default_top: base

                file_roots:
                  base:
                    - {base}
                  foo:
                    - {foo}
                  bar:
                    - {bar}
                  baz:
                    - {baz}
                '''.format(**self.saltenv_roots)
            )
        )
        self.dunder_opts['env_order'] = self.saltenvs

        # Write top files for all but the "baz" environment
        for saltenv in self.saltenv_roots:
            os.makedirs(self.saltenv_roots[saltenv])
            if saltenv == 'baz':
                continue
            top_file = os.path.join(self.saltenv_roots[saltenv], 'top.sls')
            with salt.utils.files.fopen(top_file, 'w') as fp_:
                # Add a section for every environment to each top file, with
                # the SLS target prefixed with the current saltenv.
                for env_name in self.saltenvs:
                    fp_.write(textwrap.dedent('''\
                        {env_name}:
                          '*':
                            - {saltenv}_{env_name}
                        '''.format(env_name=env_name, saltenv=saltenv)))

    def tearDown(self):
        time.sleep(1)
        os.remove(self.base_top_file)

    def show_top(self, **kwargs):
        local_opts = copy.deepcopy(self.dunder_opts)
        local_opts.update(kwargs)
        with patch.dict(state.__opts__, local_opts), \
                patch.object(salt.state.State, '_gather_pillar',
                             MagicMock(return_value={})):
            ret = state.show_top()
            # Lazy way of converting ordered dicts to regular dicts. We don't
            # care about dict ordering for these tests.
            return salt.utils.json.loads(salt.utils.json.dumps(ret))

    def use_limited_base_top_file(self):
        '''
        Overwrites the base top file so that it only contains sections for its
        own saltenv.
        '''
        with salt.utils.files.fopen(self.base_top_file, 'w') as fp_:
            fp_.write(textwrap.dedent('''\
                base:
                  '*':
                    - base_base
                '''))
        time.sleep(1)

    def test_merge_strategy_merge(self):
        '''
        Base overrides everything
        '''
        ret = self.show_top(top_file_merging_strategy='merge')
        assert ret == {
            'base': ['base_base'],
            'foo': ['base_foo'],
            'bar': ['base_bar'],
            'baz': ['base_baz'],
        }, ret

    def test_merge_strategy_merge_limited_base(self):
        '''
        Test with a "base" top file containing only a "base" section. The "baz"
        saltenv should not be in the return data because that env doesn't have
        its own top file and there will be no "baz" section in the "base" env's
        top file.

        Next, append a "baz" section to the rewritten top file and we should
        get results for that saltenv in the return data.
        '''
        self.use_limited_base_top_file()
        ret = self.show_top(top_file_merging_strategy='merge')
        assert ret == {
            'base': ['base_base'],
            'foo': ['foo_foo'],
            'bar': ['bar_bar'],
        }, ret

        # Add a "baz" section
        with salt.utils.files.fopen(self.base_top_file, 'a') as fp_:
            fp_.write(textwrap.dedent('''\
                baz:
                  '*':
                    - base_baz
                '''))

        ret = self.show_top(top_file_merging_strategy='merge')
        assert ret == {
            'base': ['base_base'],
            'foo': ['foo_foo'],
            'bar': ['bar_bar'],
            'baz': ['base_baz'],
        }, ret

    def test_merge_strategy_merge_state_top_saltenv_base(self):
        '''
        This tests with state_top_saltenv=base, which should pull states *only*
        from the base saltenv.
        '''
        ret = self.show_top(
            top_file_merging_strategy='merge',
            state_top_saltenv='base')
        assert ret == {
            'base': ['base_base'],
            'foo': ['base_foo'],
            'bar': ['base_bar'],
            'baz': ['base_baz'],
        }, ret

    def test_merge_strategy_merge_state_top_saltenv_foo(self):
        '''
        This tests with state_top_saltenv=foo, which should pull states *only*
        from the foo saltenv. Since that top file is only authoritative for
        its own saltenv, *only* the foo saltenv's matches from the foo top file
        should be in the return data.
        '''
        ret = self.show_top(
            top_file_merging_strategy='merge',
            state_top_saltenv='foo')
        assert ret == {'foo': ['foo_foo']}, ret

    def test_merge_strategy_merge_all(self):
        '''
        Include everything in every top file
        '''
        ret = self.show_top(top_file_merging_strategy='merge_all')
        assert ret == {
            'base': ['base_base', 'foo_base', 'bar_base'],
            'foo': ['base_foo', 'foo_foo', 'bar_foo'],
            'bar': ['base_bar', 'foo_bar', 'bar_bar'],
            'baz': ['base_baz', 'foo_baz', 'bar_baz'],
        }, ret

    def test_merge_strategy_merge_all_alternate_env_order(self):
        '''
        Use an alternate env_order. This should change the order in which the
        SLS targets appear in the result.
        '''
        ret = self.show_top(
            top_file_merging_strategy='merge_all',
            env_order=['bar', 'foo', 'base'])
        assert ret == {
            'base': ['bar_base', 'foo_base', 'base_base'],
            'foo': ['bar_foo', 'foo_foo', 'base_foo'],
            'bar': ['bar_bar', 'foo_bar', 'base_bar'],
            'baz': ['bar_baz', 'foo_baz', 'base_baz'],
        }, ret

    def test_merge_strategy_merge_all_state_top_saltenv_base(self):
        '''
        This tests with state_top_saltenv=base, which should pull states *only*
        from the base saltenv. Since we are using the "merge_all" strategy, all
        the states from that top file should be in the return data.
        '''
        ret = self.show_top(
            top_file_merging_strategy='merge_all',
            state_top_saltenv='base')
        assert ret == {
            'base': ['base_base'],
            'foo': ['base_foo'],
            'bar': ['base_bar'],
            'baz': ['base_baz'],
        }, ret

    def test_merge_strategy_merge_all_state_top_saltenv_foo(self):
        '''
        This tests with state_top_saltenv=foo, which should pull states *only*
        from the foo saltenv. Since we are using the "merge_all" strategy, all
        the states from that top file should be in the return data.
        '''
        ret = self.show_top(
            top_file_merging_strategy='merge_all',
            state_top_saltenv='foo')
        assert ret == {
            'base': ['foo_base'],
            'foo': ['foo_foo'],
            'bar': ['foo_bar'],
            'baz': ['foo_baz'],
        }, ret

    def test_merge_strategy_same(self):
        '''
        Each env should get its SLS targets from its own top file, with the
        "baz" env pulling from "base" since default_top=base and there is no
        top file in the "baz" saltenv.
        '''
        ret = self.show_top(top_file_merging_strategy='same')
        assert ret == {
            'base': ['base_base'],
            'foo': ['foo_foo'],
            'bar': ['bar_bar'],
            'baz': ['base_baz'],
        }, ret

    def test_merge_strategy_same_limited_base(self):
        '''
        Each env should get its SLS targets from its own top file, with the
        "baz" env pulling from "base" since default_top=base and there is no
        top file in the "baz" saltenv.
        '''
        self.use_limited_base_top_file()
        ret = self.show_top(top_file_merging_strategy='same')
        assert ret == {
            'base': ['base_base'],
            'foo': ['foo_foo'],
            'bar': ['bar_bar'],
        }, ret

    def test_merge_strategy_same_default_top_foo(self):
        '''
        Each env should get its SLS targets from its own top file, with the
        "baz" env pulling from "foo" since default_top=foo and there is no top
        file in the "baz" saltenv.
        '''
        ret = self.show_top(
            top_file_merging_strategy='same',
            default_top='foo')
        assert ret == {
            'base': ['base_base'],
            'foo': ['foo_foo'],
            'bar': ['bar_bar'],
            'baz': ['foo_baz'],
        }, ret

    def test_merge_strategy_same_state_top_saltenv_base(self):
        '''
        Test the state_top_saltenv parameter to load states exclusively from
        the base saltenv, with the "same" merging strategy. This should
        result in just the base environment's states from the base top file
        being in the merged result.
        '''
        ret = self.show_top(
            top_file_merging_strategy='same',
            state_top_saltenv='base')
        assert ret == {'base': ['base_base']}, ret

    def test_merge_strategy_same_state_top_saltenv_foo(self):
        '''
        Test the state_top_saltenv parameter to load states exclusively from
        the foo saltenv, with the "same" merging strategy. This should
        result in just the foo environment's states from the foo top file
        being in the merged result.
        '''
        ret = self.show_top(
            top_file_merging_strategy='same',
            state_top_saltenv='foo')
        assert ret == {'foo': ['foo_foo']}, ret

    def test_merge_strategy_same_state_top_saltenv_baz(self):
        '''
        Test the state_top_saltenv parameter to load states exclusively from
        the baz saltenv, with the "same" merging strategy. This should
        result in an empty dictionary since there is no top file in that
        environment.
        '''
        ret = self.show_top(
            top_file_merging_strategy='same',
            state_top_saltenv='baz')
        assert ret == {}, ret
