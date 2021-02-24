import pytest
import salt.utils.platform

from . import normalize_ret

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_watch_in(state, state_tree):
    """
    test watch_in requisite when there is a success
    """
    sls_contents = """
    return_changes:
      test.succeed_with_changes:
        - watch_in:
          - test: watch_states

    watch_states:
      test.succeed_without_changes
    """
    changes = "test_|-return_changes_|-return_changes_|-succeed_with_changes"
    watch = "test_|-watch_states_|-watch_states_|-succeed_without_changes"
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret[changes]["__run_num__"] == 0
        assert (
            ret[changes]["changes"]["testing"]["new"] == "Something pretended to change"
        )
        assert ret[watch]["__run_num__"] == 2
        assert ret[watch]["comment"] == "Watch statement fired."


def test_watch_in_failure(state, state_tree):
    """
    test watch_in requisite when there is a failure
    """
    sls_contents = """
    return_changes:
      test.fail_with_changes:
        - watch_in:
          - test: watch_states

    watch_states:
      test.succeed_without_changes
    """
    fail = "test_|-return_changes_|-return_changes_|-fail_with_changes"
    watch = "test_|-watch_states_|-watch_states_|-succeed_without_changes"
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret[fail]["result"] is False
        assert (
            ret[watch]["comment"]
            == "One or more requisite failed: requisite.return_changes"
        )


@pytest.mark.slow_test
def test_requisites_watch_any(state, state_tree):
    """
    Call sls file containing several require_in and require.

    Ensure that some of them are failing and that the order is right.
    """
    if salt.utils.platform.is_windows():
        cmd_true = "exit"
        cmd_false = "exit /B 1"
    else:
        cmd_true = "true"
        cmd_false = "false"
    sls_contents = """
    A:
      cmd.wait:
        - name: '{cmd_true}'
        - watch_any:
          - cmd: B
          - cmd: C
          - cmd: D

    B:
      cmd.run:
        - name: '{cmd_true}'

    C:
      cmd.run:
        - name: '{cmd_false}'

    D:
      cmd.run:
        - name: '{cmd_true}'

    E:
      cmd.wait:
        - name: '{cmd_true}'
        - watch_any:
          - cmd: F
          - cmd: G
          - cmd: H

    F:
      cmd.run:
        - name: '{cmd_true}'

    G:
      cmd.run:
        - name: '{cmd_false}'

    H:
      cmd.run:
        - name: '{cmd_false}'
    """.format(
        cmd_true=cmd_true, cmd_false=cmd_false
    )
    expected_result = {
        "cmd_|-A_|-{}_|-wait".format(cmd_true): {
            "__run_num__": 4,
            "comment": 'Command "{}" run'.format(cmd_true),
            "result": True,
            "changes": True,
        },
        "cmd_|-B_|-{}_|-run".format(cmd_true): {
            "__run_num__": 0,
            "comment": 'Command "{}" run'.format(cmd_true),
            "result": True,
            "changes": True,
        },
        "cmd_|-C_|-{}_|-run".format(cmd_false): {
            "__run_num__": 1,
            "comment": 'Command "{}" run'.format(cmd_false),
            "result": False,
            "changes": True,
        },
        "cmd_|-D_|-{}_|-run".format(cmd_true): {
            "__run_num__": 2,
            "comment": 'Command "{}" run'.format(cmd_true),
            "result": True,
            "changes": True,
        },
        "cmd_|-E_|-{}_|-wait".format(cmd_true): {
            "__run_num__": 9,
            "comment": 'Command "{}" run'.format(cmd_true),
            "result": True,
            "changes": True,
        },
        "cmd_|-F_|-{}_|-run".format(cmd_true): {
            "__run_num__": 5,
            "comment": 'Command "{}" run'.format(cmd_true),
            "result": True,
            "changes": True,
        },
        "cmd_|-G_|-{}_|-run".format(cmd_false): {
            "__run_num__": 6,
            "comment": 'Command "{}" run'.format(cmd_false),
            "result": False,
            "changes": True,
        },
        "cmd_|-H_|-{}_|-run".format(cmd_false): {
            "__run_num__": 7,
            "comment": 'Command "{}" run'.format(cmd_false),
            "result": False,
            "changes": True,
        },
    }
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret)
        ret = pytest.helpers.state_return(ret)
        ret.assert_return_non_empty_state_type()
        assert result == expected_result


def test_requisites_watch_any_fail(state, state_tree):
    """
    Call sls file containing several require_in and require.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    A:
      cmd.wait:
        - name: 'true'
        - watch_any:
          - cmd: B
          - cmd: C

    B:
      cmd.run:
        - name: 'false'

    C:
      cmd.run:
        - name: 'false'
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert "One or more requisite failed" in ret["cmd_|-A_|-true_|-wait"]["comment"]


def test_issue_30820_requisite_in_match_by_name(state, state_tree):
    """
    This tests the case where a requisite_in matches by name instead of ID

    See https://github.com/saltstack/salt/issues/30820 for more info
    """
    sls_contents = """
    bar state:
      cmd.wait:
        - name: 'echo bar'

    echo foo:
      cmd.run:
        - watch_in:
          - cmd: 'echo bar'
    """
    bar_state = "cmd_|-bar state_|-echo bar_|-wait"
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert bar_state in ret
        assert ret[bar_state]["comment"] == 'Command "echo bar" run'
