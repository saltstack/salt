import pytest

from . import normalize_ret

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_requisites_onfail_any(state, state_tree):
    """
    Call sls file containing several require_in and require.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    a:
      cmd.run:
        - name: exit 0

    b:
      cmd.run:
        - name: exit 1

    c:
      cmd.run:
        - name: exit 0

    d:
      cmd.run:
        - name: echo itworked
        - onfail_any:
          - cmd: a
          - cmd: b
          - cmd: c

    e:
      cmd.run:
        - name: exit 0

    f:
      cmd.run:
        - name: exit 0

    g:
      cmd.run:
        - name: exit 0

    h:
      cmd.run:
        - name: echo itworked
        - onfail_any:
          - cmd: e
          - cmd: f
          - cmd: g
    """
    expected_result = {
        "cmd_|-a_|-exit 0_|-run": {
            "__run_num__": 0,
            "changes": True,
            "comment": 'Command "exit 0" run',
            "result": True,
        },
        "cmd_|-b_|-exit 1_|-run": {
            "__run_num__": 1,
            "changes": True,
            "comment": 'Command "exit 1" run',
            "result": False,
        },
        "cmd_|-c_|-exit 0_|-run": {
            "__run_num__": 2,
            "changes": True,
            "comment": 'Command "exit 0" run',
            "result": True,
        },
        "cmd_|-d_|-echo itworked_|-run": {
            "__run_num__": 3,
            "changes": True,
            "comment": 'Command "echo itworked" run',
            "result": True,
        },
        "cmd_|-e_|-exit 0_|-run": {
            "__run_num__": 4,
            "changes": True,
            "comment": 'Command "exit 0" run',
            "result": True,
        },
        "cmd_|-f_|-exit 0_|-run": {
            "__run_num__": 5,
            "changes": True,
            "comment": 'Command "exit 0" run',
            "result": True,
        },
        "cmd_|-g_|-exit 0_|-run": {
            "__run_num__": 6,
            "changes": True,
            "comment": 'Command "exit 0" run',
            "result": True,
        },
        "cmd_|-h_|-echo itworked_|-run": {
            "__run_num__": 7,
            "changes": False,
            "comment": "State was not run because onfail req did not change",
            "result": True,
        },
    }
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_result


def test_requisites_onfail_all(state, state_tree):
    """
    Call sls file containing several onfail-all

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    a:
      cmd.run:
        - name: exit 0

    b:
      cmd.run:
        - name: exit 0

    c:
      cmd.run:
        - name: exit 0

    d:
      cmd.run:
        - name: exit 1

    e:
      cmd.run:
        - name: exit 1

    f:
      cmd.run:
        - name: exit 1

    reqs not met:
      cmd.run:
        - name: echo itdidntonfail
        - onfail_all:
          - cmd: a
          - cmd: e

    reqs also not met:
      cmd.run:
        - name: echo italsodidnonfail
        - onfail_all:
          - cmd: a
          - cmd: b
          - cmd: c

    reqs met:
      cmd.run:
        - name: echo itonfailed
        - onfail_all:
          - cmd: d
          - cmd: e
          - cmd: f

    reqs also met:
      cmd.run:
        - name: echo itonfailed
        - onfail_all:
          - cmd: d
        - require:
          - cmd: a
    """
    expected_result = {
        "cmd_|-a_|-exit 0_|-run": {
            "__run_num__": 0,
            "changes": True,
            "comment": 'Command "exit 0" run',
            "result": True,
        },
        "cmd_|-b_|-exit 0_|-run": {
            "__run_num__": 1,
            "changes": True,
            "comment": 'Command "exit 0" run',
            "result": True,
        },
        "cmd_|-c_|-exit 0_|-run": {
            "__run_num__": 2,
            "changes": True,
            "comment": 'Command "exit 0" run',
            "result": True,
        },
        "cmd_|-d_|-exit 1_|-run": {
            "__run_num__": 3,
            "changes": True,
            "comment": 'Command "exit 1" run',
            "result": False,
        },
        "cmd_|-e_|-exit 1_|-run": {
            "__run_num__": 4,
            "changes": True,
            "comment": 'Command "exit 1" run',
            "result": False,
        },
        "cmd_|-f_|-exit 1_|-run": {
            "__run_num__": 5,
            "changes": True,
            "comment": 'Command "exit 1" run',
            "result": False,
        },
        "cmd_|-reqs also met_|-echo itonfailed_|-run": {
            "__run_num__": 9,
            "changes": True,
            "comment": 'Command "echo itonfailed" run',
            "result": True,
        },
        "cmd_|-reqs also not met_|-echo italsodidnonfail_|-run": {
            "__run_num__": 7,
            "changes": False,
            "comment": "State was not run because onfail req did not change",
            "result": True,
        },
        "cmd_|-reqs met_|-echo itonfailed_|-run": {
            "__run_num__": 8,
            "changes": True,
            "comment": 'Command "echo itonfailed" run',
            "result": True,
        },
        "cmd_|-reqs not met_|-echo itdidntonfail_|-run": {
            "__run_num__": 6,
            "changes": False,
            "comment": "State was not run because onfail req did not change",
            "result": True,
        },
    }
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_result


def test_onfail_requisite(state, state_tree):
    """
    Tests a simple state using the onfail requisite
    """
    sls_contents = """
    failing_state:
      cmd.run:
        - name: asdf

    non_failing_state:
      cmd.run:
        - name: echo "Non-failing state"

    test_failing_state:
      cmd.run:
        - name: echo "Success!"
        - onfail:
          - cmd: failing_state

    test_non_failing_state:
      cmd.run:
        - name: echo "Should not run"
        - onfail:
          - cmd: non_failing_state
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert (
            ret['cmd_|-test_failing_state_|-echo "Success!"_|-run'].comment
            == 'Command "echo "Success!"" run'
        )

        assert (
            ret['cmd_|-test_non_failing_state_|-echo "Should not run"_|-run'].comment
            == "State was not run because onfail req did not change"
        )


def test_multiple_onfail_requisite(state, state_tree):
    """
    test to ensure state is run even if only one
    of the onfails fails. This is a test for the issue:
    https://github.com/saltstack/salt/issues/22370
    """
    sls_contents = """
    a:
      cmd.run:
        - name: exit 0

    b:
      cmd.run:
        - name: exit 1

    c:
      cmd.run:
        - name: echo itworked
        - onfail:
          - cmd: a
          - cmd: b
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret["cmd_|-c_|-echo itworked_|-run"].changes["retcode"] == 0
        assert ret["cmd_|-c_|-echo itworked_|-run"].changes["stdout"] == "itworked"


def test_onfail_in_requisite(state, state_tree):
    """
    Tests a simple state using the onfail_in requisite
    """
    sls_contents = """
    failing_state:
      cmd.run:
        - name: asdf
        - onfail_in:
          - cmd: test_failing_state

    non_failing_state:
      cmd.run:
        - name: echo "Non-failing state"
        - onfail_in:
          - cmd: test_non_failing_state

    test_failing_state:
      cmd.run:
        - name: echo "Success!"

    test_non_failing_state:
      cmd.run:
        - name: echo "Should not run"
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert (
            ret['cmd_|-test_failing_state_|-echo "Success!"_|-run'].comment
            == 'Command "echo "Success!"" run'
        )
        assert (
            ret['cmd_|-test_non_failing_state_|-echo "Should not run"_|-run'].comment
            == "State was not run because onfail req did not change"
        )


def test_onfail_requisite_no_state_module(state, state_tree):
    """
    Tests a simple state using the onfail requisite
    """
    sls_contents = """
    failing_state:
      cmd.run:
        - name: asdf

    non_failing_state:
      cmd.run:
        - name: echo "Non-failing state"

    test_failing_state:
      cmd.run:
        - name: echo "Success!"
        - onfail:
          - failing_state

    test_non_failing_state:
      cmd.run:
        - name: echo "Should not run"
        - onfail:
          - non_failing_state
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert (
            ret['cmd_|-test_failing_state_|-echo "Success!"_|-run'].comment
            == 'Command "echo "Success!"" run'
        )
        assert (
            ret['cmd_|-test_non_failing_state_|-echo "Should not run"_|-run'].comment
            == "State was not run because onfail req did not change"
        )


def test_onfail_requisite_with_duration(state, state_tree):
    """
    Tests a simple state using the onfail requisite
    """
    sls_contents = """
    failing_state:
      cmd.run:
        - name: asdf

    non_failing_state:
      cmd.run:
        - name: echo "Non-failing state"

    test_failing_state:
      cmd.run:
        - name: echo "Success!"
        - onfail:
          - cmd: failing_state

    test_non_failing_state:
      cmd.run:
        - name: echo "Should not run"
        - onfail:
          - cmd: non_failing_state
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert (
            "duration"
            in ret['cmd_|-test_non_failing_state_|-echo "Should not run"_|-run']
        )


def test_multiple_onfail_requisite_with_required(state, state_tree):
    """
    test to ensure multiple states are run
    when specified as onfails for a single state.
    This is a test for the issue:
    https://github.com/saltstack/salt/issues/46552
    """
    sls_contents = """
    a:
      cmd.run:
        - name: exit 1

    pass:
      cmd.run:
        - name: exit 0

    b:
      cmd.run:
        - name: echo b
        - onfail:
          - cmd: a

    c:
      cmd.run:
        - name: echo c
        - onfail:
          - cmd: a
        - require:
          - cmd: b

    d:
      cmd.run:
        - name: echo d
        - onfail:
          - cmd: a
        - require:
          - cmd: c

    e:
      cmd.run:
        - name: echo e
        - onfail:
          - cmd: pass
        - require:
          - cmd: c

    f:
      cmd.run:
        - name: echo f
        - onfail:
          - cmd: pass
        - onchanges:
          - cmd: b
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")

        assert ret["cmd_|-b_|-echo b_|-run"].changes["retcode"] == 0
        assert ret["cmd_|-c_|-echo c_|-run"].changes["retcode"] == 0
        assert ret["cmd_|-d_|-echo d_|-run"].changes["retcode"] == 0
        assert ret["cmd_|-b_|-echo b_|-run"].changes["stdout"] == "b"
        assert ret["cmd_|-c_|-echo c_|-run"].changes["stdout"] == "c"
        assert ret["cmd_|-d_|-echo d_|-run"].changes["stdout"] == "d"
        assert (
            ret["cmd_|-e_|-echo e_|-run"].comment
            == "State was not run because onfail req did not change"
        )
        assert (
            ret["cmd_|-f_|-echo f_|-run"].comment
            == "State was not run because onfail req did not change"
        )


def test_multiple_onfail_requisite_with_required_no_run(state, state_tree):
    """
    test to ensure multiple states are not run
    when specified as onfails for a single state
    which fails.
    This is a test for the issue:
    https://github.com/saltstack/salt/issues/46552
    """
    sls_contents = """
    a:
      cmd.run:
        - name: exit 0

    b:
      cmd.run:
        - name: echo b
        - onfail:
          - cmd: a

    c:
      cmd.run:
        - name: echo c
        - onfail:
          - cmd: a
        - require:
          - cmd: b

    d:
      cmd.run:
        - name: echo d
        - onfail:
          - cmd: a
        - require:
          - cmd: c
    """
    expected = "State was not run because onfail req did not change"
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret["cmd_|-b_|-echo b_|-run"].comment == expected
        assert ret["cmd_|-c_|-echo c_|-run"].comment == expected
        assert ret["cmd_|-d_|-echo d_|-run"].comment == expected
