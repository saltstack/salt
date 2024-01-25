import pytest

from . import normalize_ret

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.core_test,
]


def test_requisites_onchanges_any(state, state_tree):
    """
    Call sls file containing several require_in and require.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    changing_state:
      cmd.run:
        - name: echo "Changed!"

    another_changing_state:
      cmd.run:
        - name: echo "Changed!"

    non_changing_state:
      test.succeed_without_changes:
        - comment: non_changing_state not changed

    another_non_changing_state:
      test.succeed_without_changes:
        - comment: another_non_changing_state not changed

    # Should succeed since at least one will have changes
    test_one_changing_states:
      cmd.run:
        - name: echo "Success!"
        - onchanges_any:
          - cmd: changing_state
          - cmd: another_changing_state
          - test: non_changing_state
          - test: another_non_changing_state

    test_two_non_changing_states:
      cmd.run:
        - name: echo "Should not run"
        - onchanges_any:
          - test: non_changing_state
          - test: another_non_changing_state
    """
    expected_result = {
        'cmd_|-another_changing_state_|-echo "Changed!"_|-run': {
            "__run_num__": 1,
            "changes": True,
            "comment": 'Command "echo "Changed!"" run',
            "result": True,
        },
        'cmd_|-changing_state_|-echo "Changed!"_|-run': {
            "__run_num__": 0,
            "changes": True,
            "comment": 'Command "echo "Changed!"" run',
            "result": True,
        },
        'cmd_|-test_one_changing_states_|-echo "Success!"_|-run': {
            "__run_num__": 4,
            "changes": True,
            "comment": 'Command "echo "Success!"" run',
            "result": True,
        },
        'cmd_|-test_two_non_changing_states_|-echo "Should not run"_|-run': {
            "__run_num__": 5,
            "changes": False,
            "comment": "State was not run because none of the onchanges reqs changed",
            "result": True,
        },
        "test_|-another_non_changing_state_|-another_non_changing_state_|-succeed_without_changes": {
            "__run_num__": 3,
            "changes": False,
            "comment": "another_non_changing_state not changed",
            "result": True,
        },
        "test_|-non_changing_state_|-non_changing_state_|-succeed_without_changes": {
            "__run_num__": 2,
            "changes": False,
            "comment": "non_changing_state not changed",
            "result": True,
        },
    }
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_result


def test_onchanges_requisite(state, state_tree):
    """
    Tests a simple state using the onchanges requisite
    """
    sls_contents = """
    changing_state:
      cmd.run:
        - name: echo "Changed!"

    non_changing_state:
      test.succeed_without_changes:
        - comment: non_changing_state not changed

    test_changing_state:
      cmd.run:
        - name: echo "Success!"
        - onchanges:
          - cmd: changing_state

    test_non_changing_state:
      cmd.run:
        - name: echo "Should not run"
        - onchanges:
          - test: non_changing_state
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert (
            ret['cmd_|-test_changing_state_|-echo "Success!"_|-run'].comment
            == 'Command "echo "Success!"" run'
        )
        assert (
            ret['cmd_|-test_non_changing_state_|-echo "Should not run"_|-run'].comment
            == "State was not run because none of the onchanges reqs changed"
        )


def test_onchanges_requisite_multiple(state, state_tree):
    """
    Tests a simple state using the onchanges requisite
    """
    sls_contents = """
    changing_state:
      cmd.run:
        - name: echo "Changed!"

    another_changing_state:
      cmd.run:
        - name: echo "Changed!"

    non_changing_state:
      test.succeed_without_changes:
        - comment: non_changing_state not changed

    another_non_changing_state:
      test.succeed_without_changes:
        - comment: another_non_changing_state not changed

    test_two_changing_states:
      cmd.run:
        - name: echo "Success!"
        - onchanges:
          - cmd: changing_state
          - cmd: another_changing_state

    test_two_non_changing_states:
      cmd.run:
        - name: echo "Should not run"
        - onchanges:
          - test: non_changing_state
          - test: another_non_changing_state

    test_one_changing_state:
      cmd.run:
        - name: echo "Success!"
        - onchanges:
          - cmd: changing_state
          - test: non_changing_state
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert (
            ret['cmd_|-test_two_changing_states_|-echo "Success!"_|-run'].comment
            == 'Command "echo "Success!"" run'
        )

        assert (
            ret[
                'cmd_|-test_two_non_changing_states_|-echo "Should not run"_|-run'
            ].comment
            == "State was not run because none of the onchanges reqs changed"
        )

        assert (
            ret['cmd_|-test_one_changing_state_|-echo "Success!"_|-run'].comment
            == 'Command "echo "Success!"" run'
        )


def test_onchanges_in_requisite(state, state_tree):
    """
    Tests a simple state using the onchanges_in requisite
    """
    sls_contents = """
    changing_state:
      cmd.run:
        - name: echo "Changed!"
        - onchanges_in:
          - cmd: test_changes_expected

    non_changing_state:
      test.succeed_without_changes:
        - comment: non_changing_state not changed
        - onchanges_in:
          - cmd: test_changes_not_expected

    test_changes_expected:
      cmd.run:
        - name: echo "Success!"

    test_changes_not_expected:
      cmd.run:
        - name: echo "Should not run"
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert (
            ret['cmd_|-test_changes_expected_|-echo "Success!"_|-run'].comment
            == 'Command "echo "Success!"" run'
        )

        assert (
            ret['cmd_|-test_changes_not_expected_|-echo "Should not run"_|-run'].comment
            == "State was not run because none of the onchanges reqs changed"
        )


def test_onchanges_requisite_no_state_module(state, state_tree):
    """
    Tests a simple state using the onchanges requisite without state modules
    """
    sls_contents = """
    changing_state:
      cmd.run:
        - name: echo "Changed!"

    non_changing_state:
      test.succeed_without_changes:
        - comment: non_changing_state not changed

    test_changing_state:
      cmd.run:
        - name: echo "Success!"
        - onchanges:
          - changing_state

    test_non_changing_state:
      cmd.run:
        - name: echo "Should not run"
        - onchanges:
          - non_changing_state
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert (
            ret['cmd_|-test_changing_state_|-echo "Success!"_|-run'].comment
            == 'Command "echo "Success!"" run'
        )


def test_onchanges_requisite_with_duration(state, state_tree):
    """
    Tests a simple state using the onchanges requisite
    the state will not run but results will include duration
    """
    sls_contents = """
    changing_state:
      cmd.run:
        - name: echo "Changed!"

    non_changing_state:
      test.succeed_without_changes:
        - comment: non_changing_state not changed

    test_changing_state:
      cmd.run:
        - name: echo "Success!"
        - onchanges:
          - cmd: changing_state

    test_non_changing_state:
      cmd.run:
        - name: echo "Should not run"
        - onchanges:
          - test: non_changing_state
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert (
            "duration"
            in ret['cmd_|-test_non_changing_state_|-echo "Should not run"_|-run']
        )


def test_onchanges_any_recursive_error_issues_50811(state, state_tree):
    """
    test that onchanges_any does not causes a recursive error
    """
    sls_contents = """
    command-test:
      cmd.run:
        - name: ls
        - onchanges_any:
          - file: /tmp/an-unfollowed-file
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
    assert ret["command-test"].result is False
