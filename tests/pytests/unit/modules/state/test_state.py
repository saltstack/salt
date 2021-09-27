"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import datetime
import logging
import os

import pytest
import salt.config
import salt.loader
import salt.modules.config as config
import salt.modules.state as state
import salt.state
import salt.utils.args
import salt.utils.files
import salt.utils.hashutils
import salt.utils.json
import salt.utils.odict
import salt.utils.platform
import salt.utils.state
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.utils.event import SaltEvent
from tests.support.mock import MagicMock, Mock, mock_open, patch

log = logging.getLogger(__name__)


class MockState:
    """
    Mock class
    """

    def __init__(self):
        pass

    class State:
        """
        Mock state class
        """

        flag = None

        def __init__(
            self, opts, pillar_override=False, pillar_enc=None, initial_pillar=None
        ):
            pass

        def verify_data(self, data):
            """
            Mock verify_data method
            """
            if self.flag:
                return True
            else:
                return False

        @staticmethod
        def call(data):
            """
            Mock call method
            """
            return list

        @staticmethod
        def call_high(data, orchestration_jid=None):
            """
            Mock call_high method
            """
            return True

        @staticmethod
        def call_template_str(data):
            """
            Mock call_template_str method
            """
            return True

        @staticmethod
        def _mod_init(data):
            """
            Mock _mod_init method
            """
            return True

        def verify_high(self, data):
            """
            Mock verify_high method
            """
            if self.flag:
                return True
            else:
                return -1

        @staticmethod
        def compile_high_data(data):
            """
            Mock compile_high_data
            """
            return [{"__id__": "ABC"}]

        @staticmethod
        def call_chunk(data, data1, data2):
            """
            Mock call_chunk method
            """
            return {"": "ABC"}

        @staticmethod
        def call_chunks(data):
            """
            Mock call_chunks method
            """
            return True

        @staticmethod
        def call_listen(data, ret):
            """
            Mock call_listen method
            """
            return True

        def requisite_in(self, data):  # pylint: disable=unused-argument
            return data, []

    class HighState:
        """
        Mock HighState class
        """

        flag = False
        opts = {"state_top": "", "pillar": {}}

        def __init__(self, opts, pillar_override=None, *args, **kwargs):
            self.building_highstate = salt.utils.odict.OrderedDict
            self.state = MockState.State(opts, pillar_override=pillar_override)

        def render_state(self, sls, saltenv, mods, matches, local=False):
            """
            Mock render_state method
            """
            if self.flag:
                return {}, True
            else:
                return {}, False

        @staticmethod
        def get_top():
            """
            Mock get_top method
            """
            return "_top"

        def verify_tops(self, data):
            """
            Mock verify_tops method
            """
            if self.flag:
                return ["a", "b"]
            else:
                return []

        @staticmethod
        def top_matches(data):
            """
            Mock top_matches method
            """
            return ["a", "b", "c"]

        @staticmethod
        def push_active():
            """
            Mock push_active method
            """
            return True

        @staticmethod
        def compile_highstate():
            """
            Mock compile_highstate method
            """
            return "A"

        @staticmethod
        def compile_state_usage():
            """
            Mock compile_state_usage method
            """
            return "A"

        @staticmethod
        def pop_active():
            """
            Mock pop_active method
            """
            return True

        @staticmethod
        def compile_low_chunks():
            """
            Mock compile_low_chunks method
            """
            return [{"__id__": "ABC", "__sls__": "abc"}]

        def render_highstate(self, data):
            """
            Mock render_highstate method
            """
            if self.flag:
                return ["a", "b"], True
            else:
                return ["a", "b"], False

        @staticmethod
        def call_highstate(
            exclude,
            cache,
            cache_name,
            force=None,
            whitelist=None,
            orchestration_jid=None,
        ):
            """
            Mock call_highstate method
            """
            return True

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass


class MockSerial:
    """
    Mock Class
    """

    @staticmethod
    def load(data):
        """
        Mock load method
        """
        return {"A": "B"}

    @staticmethod
    def dump(data, data1):
        """
        Mock dump method
        """
        return True


class MockTarFile:
    """
    Mock tarfile class
    """

    path = os.sep + "tmp"

    def __init__(self):
        pass

    @staticmethod
    def open(data, data1):
        """
        Mock open method
        """
        return MockTarFile

    @staticmethod
    def getmembers():
        """
        Mock getmembers method
        """
        return [MockTarFile]

    @staticmethod
    def extractall(data):
        """
        Mock extractall method
        """
        return True

    @staticmethod
    def close():
        """
        Mock close method
        """
        return True


@pytest.fixture
def configure_loader_modules(salt_minion_factory):
    utils = salt.loader.utils(
        salt_minion_factory.config.copy(),
        whitelist=["state", "args", "systemd", "path", "platform"],
    )
    with patch("salt.modules.state.salt.state", MockState()):
        yield {
            state: {
                "__opts__": {
                    "cachedir": "/D",
                    "saltenv": None,
                    "sock_dir": "/var/run/salt/master",
                    "transport": "zeromq",
                    "__cli": "salt",
                },
                "__utils__": utils,
                "__salt__": {
                    "config.get": config.get,
                    "config.option": MagicMock(return_value=""),
                },
            },
            config: {"__opts__": {}, "__pillar__": {}},
        }


def test_running():
    """
    Test of checking i fthe state function is already running
    """
    assert state.running(True) == []

    mock = MagicMock(
        side_effect=[
            [{"fun": "state.running", "pid": "4126", "jid": "20150325123407204096"}],
            [],
        ]
    )
    with patch.dict(state.__salt__, {"saltutil.is_running": mock}):
        assert state.running() == [
            'The function "state.running"'
            " is running as PID 4126 and "
            "was started at 2015, Mar 25 12:34:07."
            "204096 with jid 20150325123407204096"
        ]

        assert state.running() == []


def test_low():
    """
    Test of executing a single low data call
    """
    with patch.object(state, "_check_queue", side_effect=[False, None, None]):
        assert not state.low({"state": "pkg", "fun": "installed", "name": "vi"})

        MockState.State.flag = False
        assert state.low({"state": "pkg", "fun": "installed", "name": "vi"}) == list

        MockState.State.flag = True
        assert state.low({"state": "pkg", "fun": "installed", "name": "vi"})


def test_high():
    """
    Test for checking the state system
    """
    with patch.object(state, "_check_queue", side_effect=[False, None]):
        assert not state.high({"vim": {"pkg": ["installed"]}})

        with patch.object(
            salt.utils.state, "get_sls_opts", return_value={"test": True}
        ):
            assert state.high({"vim": {"pkg": ["installed"]}})


def test_template():
    """
    Test of executing the information
    stored in a template file on the minion
    """
    with patch.object(state, "_check_queue", side_effect=[False, None, None]):
        assert not state.template("/home/salt/salt.sls")

        MockState.HighState.flag = True
        assert state.template("/home/salt/salt.sls")

        MockState.HighState.flag = False
        assert state.template("/home/salt/salt.sls")


def test_template_str():
    """
    Test for Executing the information
    stored in a string from an sls template
    """
    with patch.object(state, "_check_queue", side_effect=[False, None]):
        assert not state.template_str("Template String")

        assert state.template_str("Template String")


def test_apply_():
    """
    Test to apply states
    """
    with patch.object(state, "sls", return_value=True):
        assert state.apply_(True)

    with patch.object(state, "highstate", return_value=True):
        assert state.apply_(None)


def test_test():
    """
    Test to apply states in test mode
    """
    with patch.dict(state.__opts__, {"test": False}):
        with patch.object(state, "sls", return_value=True) as mock:
            assert state.test(True)
            mock.assert_called_once_with(True, test=True)
            assert state.__opts__["test"] is False

        with patch.object(state, "highstate", return_value=True) as mock:
            assert state.test(None)
            mock.assert_called_once_with(test=True)
            assert state.__opts__["test"] is False


def test_list_disabled():
    """
    Test to list disabled states
    """
    mock = MagicMock(return_value=["A", "B", "C"])
    with patch.dict(state.__salt__, {"grains.get": mock}):
        assert state.list_disabled() == ["A", "B", "C"]


def test_enable():
    """
    Test to Enable state function or sls run
    """
    mock = MagicMock(return_value=["A", "B"])
    with patch.dict(state.__salt__, {"grains.get": mock}):
        mock = MagicMock(return_value=[])
        with patch.dict(state.__salt__, {"grains.setval": mock}):
            mock = MagicMock(return_value=[])
            with patch.dict(state.__salt__, {"saltutil.refresh_modules": mock}):
                assert state.enable("A") == {
                    "msg": "Info: A state enabled.",
                    "res": True,
                }

                assert state.enable("Z") == {
                    "msg": "Info: Z state already " "enabled.",
                    "res": True,
                }


def test_disable():
    """
    Test to disable state run
    """
    mock = MagicMock(return_value=["C", "D"])
    with patch.dict(state.__salt__, {"grains.get": mock}):
        mock = MagicMock(return_value=[])
        with patch.dict(state.__salt__, {"grains.setval": mock}):
            mock = MagicMock(return_value=[])
            with patch.dict(state.__salt__, {"saltutil.refresh_modules": mock}):
                assert state.disable("C") == {
                    "msg": "Info: C state " "already disabled.",
                    "res": True,
                }

                assert state.disable("Z") == {
                    "msg": "Info: Z state " "disabled.",
                    "res": True,
                }


def test_clear_cache():
    """
    Test to clear out cached state file
    """
    mock = MagicMock(return_value=["A.cache.p", "B.cache.p", "C"])
    with patch.object(os, "listdir", mock):
        mock = MagicMock(return_value=True)
        with patch.object(os.path, "isfile", mock):
            mock = MagicMock(return_value=True)
            with patch.object(os, "remove", mock):
                assert state.clear_cache() == ["A.cache.p", "B.cache.p"]


def test_single():
    """
    Test to execute single state function
    """
    ret = {"pkg_|-name=vim_|-name=vim_|-installed": list}
    mock = MagicMock(side_effect=["A", None, None, None, None])
    with patch.object(state, "_check_queue", mock):
        assert state.single("pkg.installed", " name=vim") == "A"

        assert state.single("pk", "name=vim") == "Invalid function passed"

        with patch.dict(state.__opts__, {"test": "install"}):
            mock = MagicMock(return_value={"test": ""})
            with patch.object(salt.utils.state, "get_sls_opts", mock):
                mock = MagicMock(return_value=True)
                with patch.object(salt.utils.args, "test_mode", mock):
                    pytest.raises(
                        SaltInvocationError,
                        state.single,
                        "pkg.installed",
                        "name=vim",
                        pillar="A",
                    )

                    MockState.State.flag = True
                    assert state.single("pkg.installed", "name=vim")

                    MockState.State.flag = False
                    assert state.single("pkg.installed", "name=vim") == ret


def test_show_top():
    """
    Test to return the top data that the minion will use for a highstate
    """
    mock = MagicMock(side_effect=["A", None, None])
    with patch.object(state, "_check_queue", mock):
        assert state.show_top() == "A"

        MockState.HighState.flag = True
        assert state.show_top() == ["a", "b"]

        MockState.HighState.flag = False
        assert state.show_top() == ["a", "b", "c"]


def test_run_request():
    """
    Test to Execute the pending state request
    """
    mock = MagicMock(
        side_effect=[{}, {"name": "A"}, {"name": {"mods": "A", "kwargs": {}}}]
    )
    with patch.object(state, "check_request", mock):
        assert state.run_request("A") == {}

        assert state.run_request("A") == {}

        mock = MagicMock(return_value=["True"])
        with patch.object(state, "apply_", mock):
            mock = MagicMock(return_value="")
            with patch.object(os, "remove", mock):
                assert state.run_request("name") == ["True"]


def test_show_highstate():
    """
    Test to retrieve the highstate data from the salt master
    """
    mock = MagicMock(side_effect=["A", None, None])
    with patch.object(state, "_check_queue", mock):
        assert state.show_highstate() == "A"

        pytest.raises(SaltInvocationError, state.show_highstate, pillar="A")

        assert state.show_highstate() == "A"


def test_show_lowstate():
    """
    Test to list out the low data that will be applied to this minion
    """
    mock = MagicMock(side_effect=["A", None])
    with patch.object(state, "_check_queue", mock):
        pytest.raises(AssertionError, state.show_lowstate)

        assert state.show_lowstate()


def test_show_state_usage():
    """
    Test to list out the state usage that will be applied to this minion
    """

    mock = MagicMock(side_effect=["A", None, None])
    with patch.object(state, "_check_queue", mock):
        assert state.show_state_usage() == "A"

        pytest.raises(SaltInvocationError, state.show_state_usage, pillar="A")

        assert state.show_state_usage() == "A"


def test_show_states():
    """
    Test to display the low data from a specific sls
    """
    mock = MagicMock(side_effect=["A", None])
    with patch.object(state, "_check_queue", mock):

        assert state.show_low_sls("foo") == "A"
        assert state.show_states("foo") == ["abc"]


def test_show_states_missing_sls():
    """
    Test state.show_states when a sls file defined
    in a top.sls file is missing
    """
    msg = ["No matching sls found for 'cloud' in evn 'base'"]
    chunks_mock = MagicMock(side_effect=[msg])
    mock = MagicMock(side_effect=["A", None])
    with patch.object(state, "_check_queue", mock), patch(
        "salt.state.HighState.compile_low_chunks", chunks_mock
    ):
        assert state.show_low_sls("foo") == "A"
        assert state.show_states("foo") == [msg[0]]


def test_sls_id():
    """
    Test to call a single ID from the
    named module(s) and handle all requisites
    """
    mock = MagicMock(side_effect=["A", None, None, None])
    with patch.object(state, "_check_queue", mock):
        assert state.sls_id("apache", "http") == "A"

        with patch.dict(state.__opts__, {"test": "A"}):
            mock = MagicMock(return_value={"test": True, "saltenv": None})
            with patch.object(salt.utils.state, "get_sls_opts", mock):
                mock = MagicMock(return_value=True)
                with patch.object(salt.utils.args, "test_mode", mock):
                    MockState.State.flag = True
                    MockState.HighState.flag = True
                    assert state.sls_id("apache", "http") == 2

                    MockState.State.flag = False
                    assert state.sls_id("ABC", "http") == {"": "ABC"}
                    pytest.raises(SaltInvocationError, state.sls_id, "DEF", "http")


def test_show_low_sls():
    """
    Test to display the low data from a specific sls
    """
    mock = MagicMock(side_effect=["A", None, None])
    with patch.object(state, "_check_queue", mock):
        assert state.show_low_sls("foo") == "A"

        with patch.dict(state.__opts__, {"test": "A"}):
            mock = MagicMock(return_value={"test": True, "saltenv": None})
            with patch.object(salt.utils.state, "get_sls_opts", mock):
                MockState.State.flag = True
                MockState.HighState.flag = True
                assert state.show_low_sls("foo") == 2

                MockState.State.flag = False
                assert state.show_low_sls("foo") == [{"__id__": "ABC"}]


def test_show_sls():
    """
    Test to display the state data from a specific sls
    """
    mock = MagicMock(side_effect=["A", None, None, None])
    with patch.object(state, "_check_queue", mock):
        assert state.show_sls("foo") == "A"

        with patch.dict(state.__opts__, {"test": "A"}):
            mock = MagicMock(return_value={"test": True, "saltenv": None})
            with patch.object(salt.utils.state, "get_sls_opts", mock):
                mock = MagicMock(return_value=True)
                with patch.object(salt.utils.args, "test_mode", mock):
                    pytest.raises(
                        SaltInvocationError, state.show_sls, "foo", pillar="A"
                    )

                    MockState.State.flag = True
                    assert state.show_sls("foo") == 2

                    MockState.State.flag = False
                    assert state.show_sls("foo") == ["a", "b"]


def test_sls_exists():
    """
    Test of sls_exists
    """
    test_state = {}
    test_missing_state = []

    mock = MagicMock(return_value=test_state)
    with patch.object(state, "show_sls", mock):
        assert state.sls_exists("state_name")
    mock = MagicMock(return_value=test_missing_state)
    with patch.object(state, "show_sls", mock):
        assert not state.sls_exists("missing_state")


def test_id_exists():
    """
    Test of id_exists
    """
    test_state = [
        {
            "key1": "value1",
            "name": "value1",
            "state": "file",
            "fun": "test",
            "__env__": "base",
            "__sls__": "test-sls",
            "order": 10000,
            "__id__": "state_id1",
        },
        {
            "key2": "value2",
            "name": "value2",
            "state": "file",
            "fun": "directory",
            "__env__": "base",
            "__sls__": "test-sls",
            "order": 10001,
            "__id__": "state_id2",
        },
    ]
    mock = MagicMock(return_value=test_state)
    with patch.object(state, "show_low_sls", mock):
        assert state.id_exists("state_id1,state_id2", "test-sls")
        assert not state.id_exists("invalid", "state_name")


def test_top():
    """
    Test to execute a specific top file
    """
    ret = ["Pillar failed to render with the following messages:", "E"]
    mock = MagicMock(side_effect=["A", None, None, None])
    with patch.object(state, "_check_queue", mock):
        assert state.top("reverse_top.sls") == "A"

        mock = MagicMock(side_effect=[["E"], None, None])
        with patch.object(state, "_get_pillar_errors", mock):
            with patch.dict(state.__pillar__, {"_errors": ["E"]}):
                assert state.top("reverse_top.sls") == ret

            with patch.dict(state.__opts__, {"test": "A"}):
                mock = MagicMock(return_value={"test": True})
                with patch.object(salt.utils.state, "get_sls_opts", mock):
                    mock = MagicMock(return_value=True)
                    with patch.object(salt.utils.args, "test_mode", mock):
                        pytest.raises(
                            SaltInvocationError,
                            state.top,
                            "reverse_top.sls",
                            pillar="A",
                        )

                        mock = MagicMock(return_value="salt://reverse_top.sls")
                        with patch.object(os.path, "join", mock):
                            mock = MagicMock(return_value=True)
                            with patch.object(state, "_set_retcode", mock):
                                assert state.top(
                                    "reverse_top.sls " "exclude=exclude.sls"
                                )


def test_highstate():
    """
    Test to retrieve the state data from the
    salt master for the minion and execute it
    """
    arg = "whitelist=sls1.sls"
    mock = MagicMock(side_effect=[True, False, False, False])
    with patch.object(state, "_disabled", mock):
        assert state.highstate("whitelist=sls1.sls") == {
            "comment": "Disabled",
            "name": "Salt highstate run is disabled. "
            "To re-enable, run state.enable highstate",
            "result": "False",
        }

        mock = MagicMock(side_effect=["A", None, None])
        with patch.object(state, "_check_queue", mock):
            assert state.highstate("whitelist=sls1.sls") == "A"

            with patch.dict(state.__opts__, {"test": "A"}):
                mock = MagicMock(return_value={"test": True})
                with patch.object(salt.utils.state, "get_sls_opts", mock):
                    pytest.raises(
                        SaltInvocationError,
                        state.highstate,
                        "whitelist=sls1.sls",
                        pillar="A",
                    )

                    mock = MagicMock(return_value="A")
                    with patch.object(state, "_filter_running", mock):
                        mock = MagicMock(return_value=True)
                        with patch.object(state, "_filter_running", mock):
                            mock = MagicMock(return_value=True)
                            with patch.object(salt.payload, "Serial", mock):
                                with patch.object(os.path, "join", mock):
                                    with patch.object(state, "_set" "_retcode", mock):
                                        assert state.highstate(arg)


def test_clear_request():
    """
    Test to clear out the state execution request without executing it
    """
    mock = MagicMock(return_value=True)
    with patch.object(salt.payload, "Serial", mock):
        mock = MagicMock(side_effect=[False, True, True])
        with patch.object(os.path, "isfile", mock):
            assert state.clear_request("A")

            mock = MagicMock(return_value=True)
            with patch.object(os, "remove", mock):
                assert state.clear_request()

            mock = MagicMock(return_value={})
            with patch.object(state, "check_request", mock):
                assert not state.clear_request("A")


def test_check_request():
    """
    Test to return the state request information
    """
    with patch("salt.modules.state.salt.payload", MockSerial):
        mock = MagicMock(side_effect=[True, True, False])
        with patch.object(os.path, "isfile", mock):
            with patch("salt.utils.files.fopen", mock_open(b"")):
                assert state.check_request() == {"A": "B"}

            with patch("salt.utils.files.fopen", mock_open("")):
                assert state.check_request("A") == "B"

            assert state.check_request() == {}


def test_request():
    """
    Test to request the local admin execute a state run
    """
    mock = MagicMock(return_value=True)
    with patch.object(state, "apply_", mock):
        mock = MagicMock(return_value=True)
        with patch.object(os.path, "join", mock):
            mock = MagicMock(return_value={"test_run": "", "mods": "", "kwargs": ""})
            with patch.object(state, "check_request", mock):
                mock = MagicMock(return_value=True)
                with patch.object(os, "umask", mock):
                    with patch.object(salt.utils.platform, "is_windows", mock):
                        with patch.dict(state.__salt__, {"cmd.run": mock}):
                            with patch("salt.utils.files.fopen", mock_open()):
                                mock = MagicMock(return_value=True)
                                with patch.object(os, "umask", mock):
                                    assert state.request("A")


def test_sls():
    """
    Test to execute a set list of state files from an environment
    """
    arg = "core,edit.vim dev"
    ret = ["Pillar failed to render with the following messages:", "E", "1"]
    with patch.object(state, "running", return_value=True):
        with patch.dict(state.__context__, {"retcode": 1}):
            assert state.sls("core,edit.vim dev") is True

    with patch.object(
        state, "_wait", side_effect=[True, True, True, True, True, True]
    ), patch.object(state, "_disabled", side_effect=[["A"], [], [], [], [], []]):
        with patch.dict(state.__context__, {"retcode": 1}):
            assert state.sls("core,edit.vim dev", None, None, True) == ["A"]

        with patch.object(
            state,
            "_get_pillar_errors",
            side_effect=[["E", "1"], None, None, None, None],
        ):
            with patch.dict(state.__context__, {"retcode": 5}), patch.dict(
                state.__pillar__, {"_errors": ["E", "1"]}
            ):
                assert state.sls("core,edit.vim dev", None, None, True) == ret

            with patch.dict(state.__opts__, {"test": None}), patch.object(
                salt.utils.state,
                "get_sls_opts",
                return_value={"test": "", "saltenv": None},
            ), patch.object(salt.utils.args, "test_mode", return_value=True):
                pytest.raises(
                    SaltInvocationError,
                    state.sls,
                    "core,edit.vim dev",
                    None,
                    None,
                    True,
                    pillar="A",
                )
                with patch.object(os.path, "join", return_value="/D/cache.cache.p"):
                    with patch.object(os.path, "isfile", return_value=True), patch(
                        "salt.utils.files.fopen", mock_open(b"")
                    ):
                        assert state.sls(arg, None, None, True, cache=True)

                    MockState.HighState.flag = True
                    assert state.sls("core,edit" ".vim dev", None, None, True)

                    MockState.HighState.flag = False
                    with patch.object(
                        state, "_filter_" "running", return_value=True
                    ), patch.object(os.path, "join", return_value=True), patch.object(
                        os, "umask", return_value=True
                    ), patch.object(
                        salt.utils.platform, "is_windows", return_value=False
                    ), patch.object(
                        state, "_set_retcode", return_value=True
                    ), patch.dict(
                        state.__opts__, {"test": True}
                    ), patch(
                        "salt.utils.files.fopen", mock_open()
                    ):
                        assert state.sls("core,edit" ".vim dev", None, None, True)


def test_get_test_value():
    """
    Test _get_test_value when opts contains different values
    """
    test_arg = "test"
    with patch.dict(state.__opts__, {test_arg: True}):
        assert state._get_test_value(
            test=None
        ), "Failure when {} is True in __opts__".format(test_arg)

    with patch.dict(config.__pillar__, {test_arg: "blah"}):
        assert not state._get_test_value(
            test=None
        ), "Failure when {} is blah in __opts__".format(test_arg)

    with patch.dict(config.__pillar__, {test_arg: "true"}):
        assert not state._get_test_value(
            test=None
        ), "Failure when {} is true in __opts__".format(test_arg)

    with patch.dict(config.__opts__, {test_arg: False}):
        assert not state._get_test_value(
            test=None
        ), "Failure when {} is False in __opts__".format(test_arg)

    with patch.dict(config.__opts__, {}):
        assert not state._get_test_value(
            test=None
        ), "Failure when {} does not exist in __opts__".format(test_arg)

    with patch.dict(config.__pillar__, {test_arg: None}):
        assert (
            state._get_test_value(test=None) is None
        ), "Failure when {} is None in __opts__".format(test_arg)

    with patch.dict(config.__pillar__, {test_arg: True}):
        assert state._get_test_value(
            test=None
        ), "Failure when {} is True in __pillar__".format(test_arg)

    with patch.dict(config.__pillar__, {"master": {test_arg: True}}):
        assert state._get_test_value(
            test=None
        ), "Failure when {} is True in master __pillar__".format(test_arg)

    with patch.dict(config.__pillar__, {"master": {test_arg: False}}):
        with patch.dict(config.__pillar__, {test_arg: True}):
            assert state._get_test_value(
                test=None
            ), "Failure when {} is False in master __pillar__ and True in pillar".format(
                test_arg
            )

    with patch.dict(config.__pillar__, {"master": {test_arg: True}}):
        with patch.dict(config.__pillar__, {test_arg: False}):
            assert not state._get_test_value(
                test=None
            ), "Failure when {} is True in master __pillar__ and False in pillar".format(
                test_arg
            )

    with patch.dict(state.__opts__, {"test": False}):
        assert not state._get_test_value(
            test=None
        ), "Failure when {} is False in __opts__".format(test_arg)

    with patch.dict(state.__opts__, {"test": False}):
        with patch.dict(config.__pillar__, {"master": {test_arg: True}}):
            assert state._get_test_value(
                test=None
            ), "Failure when {} is False in __opts__".format(test_arg)

    with patch.dict(state.__opts__, {}):
        assert state._get_test_value(test=True), "Failure when test is True as arg"


def test_sls_sync(subtests):
    """
    Test test.sls with the sync argument

    We're only mocking the sync functions we expect to sync. If any other
    sync functions are run then they will raise a KeyError, which we want
    as it will tell us that we are syncing things we shouldn't.
    """
    expected_err_msg = "{} called {} time(s) (expected: {})"
    mock_empty_list = MagicMock(return_value=[])
    with patch.object(state, "running", mock_empty_list), patch.object(
        state, "_disabled", mock_empty_list
    ), patch.object(state, "_get_pillar_errors", mock_empty_list):

        with subtests.test("sync_mods=modules,states"):
            sync_mocks = {
                "saltutil.sync_modules": Mock(),
                "saltutil.sync_states": Mock(),
            }
            if salt.utils.platform.is_windows():
                sync_mocks["cmd.run"] = Mock()
            with patch.dict(state.__salt__, sync_mocks):
                state.sls("foo", sync_mods="modules,states")

            for key in sync_mocks:
                call_count = sync_mocks[key].call_count
                expected = 1
                assert call_count == expected, expected_err_msg.format(
                    key, call_count, expected
                )

        with subtests.test("sync_mods=all"):
            # Test syncing all
            sync_mocks = {"saltutil.sync_all": Mock()}
            if salt.utils.platform.is_windows():
                sync_mocks["cmd.run"] = Mock()
            with patch.dict(state.__salt__, sync_mocks):
                state.sls("foo", sync_mods="all")

            for key in sync_mocks:
                call_count = sync_mocks[key].call_count
                expected = 1
                assert call_count == expected, expected_err_msg.format(
                    key, call_count, expected
                )

        with subtests.test("sync_mods=True"):
            # sync_mods=True should be interpreted as sync_mods=all
            sync_mocks = {"saltutil.sync_all": Mock()}
            if salt.utils.platform.is_windows():
                sync_mocks["cmd.run"] = Mock()
            with patch.dict(state.__salt__, sync_mocks):
                state.sls("foo", sync_mods=True)

            for key in sync_mocks:
                call_count = sync_mocks[key].call_count
                expected = 1
                assert call_count == expected, expected_err_msg.format(
                    key, call_count, expected
                )

        with subtests.test("sync_mods=modules,all"):
            # Test syncing all when "all" is passed along with module types.
            # This tests that we *only* run a sync_all and avoid unnecessary
            # extra syncing.
            sync_mocks = {"saltutil.sync_all": Mock()}
            if salt.utils.platform.is_windows():
                sync_mocks["cmd.run"] = Mock()
            with patch.dict(state.__salt__, sync_mocks):
                state.sls("foo", sync_mods="modules,all")

            for key in sync_mocks:
                call_count = sync_mocks[key].call_count
                expected = 1
                assert call_count == expected, expected_err_msg.format(
                    key, call_count, expected
                )


def test_pkg():
    """
    Test to execute a packaged state run
    """
    tar_file = os.sep + os.path.join("tmp", "state_pkg.tgz")
    mock = MagicMock(
        side_effect=[False, True, True, True, True, True, True, True, True, True, True]
    )
    mock_json_loads_true = MagicMock(return_value=[True])
    mock_json_loads_dictlist = MagicMock(return_value=[{"test": ""}])
    with patch.object(os.path, "isfile", mock), patch(
        "salt.modules.state.tarfile", MockTarFile
    ), patch.object(salt.utils, "json", mock_json_loads_dictlist):
        assert state.pkg(tar_file, "", "md5") == {}

        mock = MagicMock(side_effect=[False, 0, 0, 0, 0])
        with patch.object(salt.utils.hashutils, "get_hash", mock):
            # Verify hash
            assert state.pkg(tar_file, "", "md5") == {}

            # Verify file outside intended root
            assert state.pkg(tar_file, 0, "md5") == {}

            MockTarFile.path = ""
            with patch("salt.utils.files.fopen", mock_open()), patch.object(
                salt.utils.json, "loads", mock_json_loads_true
            ), patch.object(state, "_format_cached_grains", MagicMock()):
                assert state.pkg(tar_file, 0, "md5") is True
                state._format_cached_grains.assert_called_once()

            MockTarFile.path = ""
            with patch("salt.utils.files.fopen", mock_open()):
                assert state.pkg(tar_file, 0, "md5")


def test_lock_saltenv():
    """
    Tests lock_saltenv in each function which accepts saltenv on the CLI
    """
    lock_msg = "lock_saltenv is enabled, saltenv cannot be changed"
    empty_list_mock = MagicMock(return_value=[])
    with patch.dict(state.__opts__, {"lock_saltenv": True}), patch.dict(
        state.__salt__, {"grains.get": empty_list_mock}
    ), patch.object(state, "running", empty_list_mock):

        # Test high
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.high([{"vim": {"pkg": ["installed"]}}], saltenv="base")

        # Test template
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.template("foo", saltenv="base")

        # Test template_str
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.template_str("foo", saltenv="base")

        # Test apply_ with SLS
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.apply_("foo", saltenv="base")

        # Test apply_ with Highstate
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.apply_(saltenv="base")

        # Test "test" with SLS
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.test("foo", saltenv="base")

        # Test "test" with Highstate
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.test(saltenv="base")

        # Test highstate
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.highstate(saltenv="base")

        # Test sls
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.sls("foo", saltenv="base")

        # Test top
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.top("foo.sls", saltenv="base")

        # Test show_highstate
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.show_highstate(saltenv="base")

        # Test show_lowstate
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.show_lowstate(saltenv="base")

        # Test sls_id
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.sls_id("foo", "bar", saltenv="base")

        # Test show_low_sls
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.show_low_sls("foo", saltenv="base")

        # Test show_sls
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.show_sls("foo", saltenv="base")

        # Test show_top
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.show_top(saltenv="base")

        # Test single
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.single("foo.bar", name="baz", saltenv="base")

        # Test pkg
        with pytest.raises(CommandExecutionError, match=lock_msg):
            state.pkg(
                "/tmp/salt_state.tgz",
                "760a9353810e36f6d81416366fc426dc",
                "md5",
                saltenv="base",
            )


def test_get_pillar_errors_CC():
    """
    Test _get_pillar_errors function.
    CC: External clean, Internal clean
    :return:
    """
    for int_pillar, ext_pillar in [
        ({"foo": "bar"}, {"fred": "baz"}),
        ({"foo": "bar"}, None),
        ({}, {"fred": "baz"}),
    ]:
        with patch("salt.modules.state.__pillar__", int_pillar):
            for opts, res in [
                ({"force": True}, None),
                ({"force": False}, None),
                ({}, None),
            ]:
                assert res == state._get_pillar_errors(kwargs=opts, pillar=ext_pillar)


def test_get_pillar_errors_EC():
    """
    Test _get_pillar_errors function.
    EC: External erroneous, Internal clean
    :return:
    """
    errors = ["failure", "everywhere"]
    for int_pillar, ext_pillar in [
        ({"foo": "bar"}, {"fred": "baz", "_errors": errors}),
        ({}, {"fred": "baz", "_errors": errors}),
    ]:
        with patch("salt.modules.state.__pillar__", int_pillar):
            for opts, res in [
                ({"force": True}, None),
                ({"force": False}, errors),
                ({}, errors),
            ]:
                assert res == state._get_pillar_errors(kwargs=opts, pillar=ext_pillar)


def test_get_pillar_errors_EE():
    """
    Test _get_pillar_errors function.
    CC: External erroneous, Internal erroneous
    :return:
    """
    errors = ["failure", "everywhere"]
    for int_pillar, ext_pillar in [
        ({"foo": "bar", "_errors": errors}, {"fred": "baz", "_errors": errors})
    ]:
        with patch("salt.modules.state.__pillar__", int_pillar):
            for opts, res in [
                ({"force": True}, None),
                ({"force": False}, errors),
                ({}, errors),
            ]:
                assert res == state._get_pillar_errors(kwargs=opts, pillar=ext_pillar)


def test_get_pillar_errors_CE():
    """
    Test _get_pillar_errors function.
    CC: External clean, Internal erroneous
    :return:
    """
    errors = ["failure", "everywhere"]
    for int_pillar, ext_pillar in [
        ({"foo": "bar", "_errors": errors}, {"fred": "baz"}),
        ({"foo": "bar", "_errors": errors}, None),
    ]:
        with patch("salt.modules.state.__pillar__", int_pillar):
            for opts, res in [
                ({"force": True}, None),
                ({"force": False}, errors),
                ({}, errors),
            ]:
                assert res == state._get_pillar_errors(kwargs=opts, pillar=ext_pillar)


def test_event():
    """
    test state.event runner
    """
    event_returns = {
        "data": {
            "body": b'{"text": "Hello World"}',
            "_stamp": "2021-01-08T00:12:32.320928",
        },
        "tag": "salt/engines/hook/test",
    }

    _expected = '"body": "{\\"text\\": \\"Hello World\\"}"'
    with patch.object(SaltEvent, "get_event", return_value=event_returns):
        print_cli_mock = MagicMock()
        with patch.object(salt.utils.stringutils, "print_cli", print_cli_mock):
            found = False
            state.event(count=1)
            for x in print_cli_mock.mock_calls:
                if _expected in x.args[0]:
                    found = True
            assert found is True

    now = datetime.datetime.now().isoformat()
    event_returns = {
        "data": {"date": now, "_stamp": "2021-01-08T00:12:32.320928"},
        "tag": "a_event_tag",
    }

    _expected = '"date": "{}"'.format(now)
    with patch.object(SaltEvent, "get_event", return_value=event_returns):
        print_cli_mock = MagicMock()
        with patch.object(salt.utils.stringutils, "print_cli", print_cli_mock):
            found = False
            state.event(count=1)
            for x in print_cli_mock.mock_calls:
                if _expected in x.args[0]:
                    found = True
            assert found is True
