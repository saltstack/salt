import pytest

from . import normalize_ret

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.core_test,
]


def test_requisites_full_sls_prereq(state, state_tree):
    """
    Test the sls special command in requisites
    """
    full_sls_contents = """
    B:
      cmd.run:
        - name: echo B
    C:
      cmd.run:
        - name: echo C
    """
    sls_contents = """
    include:
      - fullsls
    A:
      cmd.run:
        - name: echo A
        - prereq:
          - sls: fullsls
    """
    expected_result = {
        "cmd_|-A_|-echo A_|-run": {
            "__run_num__": 0,
            "comment": 'Command "echo A" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-B_|-echo B_|-run": {
            "__run_num__": 1,
            "comment": 'Command "echo B" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-C_|-echo C_|-run": {
            "__run_num__": 2,
            "comment": 'Command "echo C" run',
            "result": True,
            "changes": True,
        },
    }
    with pytest.helpers.temp_file(
        "requisite.sls", sls_contents, state_tree
    ), pytest.helpers.temp_file("fullsls.sls", full_sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_result


def test_requisites_prereq_simple_ordering_and_errors_1(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    # B --+
    #     |
    # C <-+ ----+
    #           |
    # A <-------+

    # runs after C
    A:
      cmd.run:
        - name: echo A third
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C

    # runs before C
    B:
      cmd.run:
        - name: echo B first
        # will test C and be applied only if C changes,
        # and then will run before C
        - prereq:
          - cmd: C
    C:
      cmd.run:
        - name: echo C second

    # will fail
    I:
      test.fail_without_changes:
        - name: echo I
    J:
      test.fail_without_changes:
        - name: echo J
    """
    expected_result = {
        "cmd_|-A_|-echo A third_|-run": {
            "__run_num__": 2,
            "comment": 'Command "echo A third" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-B_|-echo B first_|-run": {
            "__run_num__": 0,
            "comment": 'Command "echo B first" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-C_|-echo C second_|-run": {
            "__run_num__": 1,
            "comment": 'Command "echo C second" run',
            "result": True,
            "changes": True,
        },
        "test_|-I_|-echo I_|-fail_without_changes": {
            "__run_num__": 3,
            "comment": "Failure!",
            "result": False,
            "changes": False,
        },
        "test_|-J_|-echo J_|-fail_without_changes": {
            "__run_num__": 4,
            "comment": "Failure!",
            "result": False,
            "changes": False,
        },
    }
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_result


def test_requisites_prereq_simple_ordering_and_errors_2(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    # same test, but not using lists in yaml syntax
    sls_contents = """
    # B --+
    #     |
    # C <-+ ----+
    #           |
    # A <-------+

    # runs after C
    A:
      cmd.run:
        - name: echo A third
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
           cmd: C

    # runs before C
    B:
      cmd.run:
        - name: echo B first
        # will test C and be applied only if C changes,
        # and then will run before C
        - prereq:
            cmd: C
    C:
      cmd.run:
        - name: echo C second
    """
    errmsg = (
        "The prereq statement in state 'B' in SLS 'requisite' needs to be formed as a"
        " list"
    )
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret.failed
        assert ret.errors == [errmsg]


def test_requisites_prereq_simple_ordering_and_errors_3(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    # B --+
    #     |
    # C <-+ ----+
    #           |
    # A <-------+

    # runs after C
    A:
      cmd.run:
        - name: echo A third
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - C

    # runs before C
    B:
      cmd.run:
        - name: echo B first
        # will test C and be applied only if C changes,
        # and then will run before C
        - prereq:
          - C
    C:
      cmd.run:
        - name: echo C second

    # will fail
    I:
      test.fail_without_changes:
        - name: echo I
        """
    expected_result = {
        "cmd_|-A_|-echo A third_|-run": {
            "__run_num__": 2,
            "comment": 'Command "echo A third" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-B_|-echo B first_|-run": {
            "__run_num__": 0,
            "comment": 'Command "echo B first" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-C_|-echo C second_|-run": {
            "__run_num__": 1,
            "comment": 'Command "echo C second" run',
            "result": True,
            "changes": True,
        },
        "test_|-I_|-echo I_|-fail_without_changes": {
            "__run_num__": 3,
            "comment": "Failure!",
            "result": False,
            "changes": False,
        },
    }

    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_result


def test_requisites_prereq_simple_ordering_and_errors_4(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that the order is right.
    """
    sls_contents = """
    # Theory:
    #
    # C <--+ <--+ <-+ <-+
    #      |    |   |   |
    # A ---+    |   |   |
    #           |   |   |
    # B --------+   |   |
    #               |   |
    # D-------------+   |
    #                   |
    # E-----------------+

    # runs after C
    A:
      cmd.run:
        - name: echo A
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C

    B:
      cmd.run:
        - name: echo B

    # runs before D and B
    C:
      cmd.run:
        - name: echo C
        # will test D and be applied only if D changes,
        # and then will run before D. Same for B
        - prereq:
          - cmd: B
          - cmd: D

    D:
      cmd.run:
        - name: echo D

    E:
      cmd.run:
        - name: echo E
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C
    """
    expected_result = {
        "cmd_|-A_|-echo A_|-run": {
            "__run_num__": 1,
            "comment": 'Command "echo A" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-B_|-echo B_|-run": {
            "__run_num__": 2,
            "comment": 'Command "echo B" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-C_|-echo C_|-run": {
            "__run_num__": 0,
            "comment": 'Command "echo C" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-D_|-echo D_|-run": {
            "__run_num__": 3,
            "comment": 'Command "echo D" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-E_|-echo E_|-run": {
            "__run_num__": 4,
            "comment": 'Command "echo E" run',
            "result": True,
            "changes": True,
        },
    }

    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_result


def test_requisites_prereq_simple_ordering_and_errors_5(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    # A --+
    #     |
    # B <-+ ----+
    #           |
    # C <-------+

    # runs before A and/or B
    A:
      cmd.run:
        - name: echo A first
        # is running in test mode before B/C
        - prereq:
          - cmd: B
          - cmd: C

    # always has to run
    B:
      cmd.run:
        - name: echo B second

    # never has to run
    C:
      cmd.wait:
        - name: echo C third
    """
    expected_result = {
        "cmd_|-A_|-echo A first_|-run": {
            "__run_num__": 0,
            "comment": 'Command "echo A first" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-B_|-echo B second_|-run": {
            "__run_num__": 1,
            "comment": 'Command "echo B second" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-C_|-echo C third_|-wait": {
            "__run_num__": 2,
            "comment": "",
            "result": True,
            "changes": False,
        },
    }

    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_result


def test_requisites_prereq_simple_ordering_and_errors_6(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    # issue #8211
    #             expected rank
    #
    # D --+ -------+    1
    #              |
    # B --+        |    2
    #     |        |
    # C <-+ --+    |    3
    #         |    |
    # A <-----+ <--+    4
    #
    #             resulting rank
    # D --+
    #     |
    # A <-+ <==+
    #          |
    # B --+    +--> unrespected A prereq_in C (FAILURE)
    #     |    |
    # C <-+ ===+

    # runs after C
    A:
      cmd.run:
        - name: echo A fourth
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C

    # runs before C
    B:
      cmd.run:
        - name: echo B first
        # will test C and be applied only if C changes,
        # and then will run before C
        - prereq:
          - cmd: C

    C:
      cmd.run:
        - name: echo C second
        # replacing A prereq_in C by theses lines
        # changes nothing actually
        #- prereq:
        #  - cmd: A

    # Removing D, A gets executed after C
    # as described in (A prereq_in C)
    # runs before A
    D:
      cmd.run:
        - name: echo D third
        # will test A and be applied only if A changes,
        # and then will run before A
        - prereq:
          - cmd: A
    """
    expected_result = {
        "cmd_|-A_|-echo A fourth_|-run": {
            "__run_num__": 3,
            "comment": 'Command "echo A fourth" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-B_|-echo B first_|-run": {
            "__run_num__": 1,
            "comment": 'Command "echo B first" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-C_|-echo C second_|-run": {
            "__run_num__": 2,
            "comment": 'Command "echo C second" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-D_|-echo D third_|-run": {
            "__run_num__": 0,
            "comment": 'Command "echo D third" run',
            "result": True,
            "changes": True,
        },
    }

    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_result


def test_requisites_prereq_simple_ordering_and_errors_7(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    # will fail with 'Cannot extend ID Z (...) not part of the high state.'
    # and not "Referenced state does not exist for requisite" like in yaml list syntax
    I:
      cmd.run:
        - name: echo I
        - prereq:
          - cmd: Z
    """
    errmsg = (
        "Referenced state does not exist for requisite "
        "[prereq: (cmd: Z)] in state "
        "[echo I] in SLS [requisite]"
    )
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret.failed
        assert ret.errors == [errmsg]


def test_requisites_prereq_simple_ordering_and_errors_8(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    A:
      cmd.run:
        - name: echo A

    B:
      cmd.run:
        - name: echo B
        - prereq:
          - foobar: A
    """
    errmsg = (
        "Referenced state does not exist for requisite "
        "[prereq: (foobar: A)] in state "
        "[echo B] in SLS [requisite]"
    )
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret.failed
        assert ret.errors == [errmsg]


def test_requisites_prereq_simple_ordering_and_errors_9(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    A:
      cmd.run:
        - name: echo A

    B:
      cmd.run:
        - name: echo B
        - prereq:
          - foobar: C
    """
    errmsg = (
        "Referenced state does not exist for requisite "
        "[prereq: (foobar: C)] in state "
        "[echo B] in SLS [requisite]"
    )
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret.failed
        assert ret.errors == [errmsg]


def test_requisites_prereq_simple_ordering_and_errors_10(state, state_tree):
    """
    Call sls file containing several prereq.

    Ensure a recursive requisite error occurs.
    """
    sls_contents = """
    A:
      cmd.run:
        - name: echo A
        - prereq:
          - cmd: B
    B:
      cmd.run:
        - name: echo B
        - prereq:
          - cmd: A
    """
    errmsg = (
        "Recursive requisites were found: "
        "({'SLS': 'requisite', 'ID': 'B', 'NAME': 'echo B'}, "
        "'prereq', {'SLS': 'requisite', 'ID': 'A', 'NAME': 'echo A'}), "
        "({'SLS': 'requisite', 'ID': 'A', 'NAME': 'echo A'}, "
        "'prereq', {'SLS': 'requisite', 'ID': 'B', 'NAME': 'echo B'})"
    )
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret.failed
        assert ret.errors == [errmsg]


def test_requisites_prereq_in_simple_ordering_and_errors(state, state_tree):
    """
    Call sls file containing several prereq_in.

    Ensure a recursive requisite error occurs.
    """
    sls_contents = """
    A:
      cmd.run:
        - name: echo A
        - prereq_in:
          - cmd: B
    B:
      cmd.run:
        - name: echo B
        - prereq_in:
          - cmd: A
    """
    errmsg = (
        "Recursive requisites were found: "
        "({'SLS': 'requisite', 'ID': 'B', 'NAME': 'echo B'}, "
        "'prereq', {'SLS': 'requisite', 'ID': 'A', 'NAME': 'echo A'}), "
        "({'SLS': 'requisite', 'ID': 'A', 'NAME': 'echo A'}, "
        "'prereq', {'SLS': 'requisite', 'ID': 'B', 'NAME': 'echo B'})"
    )
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret.failed
        assert ret.errors == [errmsg]


def test_infinite_recursion_sls_prereq(state, state_tree):
    sls_contents = """
    include:
      - requisite2
    A:
      test.succeed_without_changes:
        - name: A
        - prereq:
          - sls: requisite2
    """
    sls_2_contents = """
    B:
      test.succeed_without_changes:
        - name: B
    """
    with pytest.helpers.temp_file(
        "requisite.sls", sls_contents, state_tree
    ), pytest.helpers.temp_file("requisite2.sls", sls_2_contents, state_tree):
        ret = state.sls("requisite")
        for state_return in ret:
            assert state_return.result is True


def test_infinite_recursion_prereq(state, state_tree):
    sls_contents = """
    A:
      test.nop:
        - prereq:
          - test: B
    B:
      test.nop:
        - require:
          - name: non-existant
    C:
      test.nop:
        - require:
          - test: B
    """

    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        for state_return in ret:
            assert state_return.result is False


def test_infinite_recursion_prereq2(state, state_tree):
    sls_contents = """
    A:
      test.nop:
        - prereq:
          - test: B
    B:
      test.nop:
        - require:
          - test: D
    C:
      test.nop:
        - require:
          - test: B
    D:
      test.nop: []
    """

    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        for state_return in ret:
            assert state_return.result is True


def test_requisites_prereq_fail_in_prereq(state, state_tree):
    sls_contents = """
    State A:
      test.configurable_test_state:
        - result: True
        - changes: True
        - name: fail

    State B:
      test.configurable_test_state:
        - changes: True
        - result: False
        - prereq:
          - test: State A

    State C:
      test.nop:
        - onchanges:
          - test: State A
    """

    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret["test_|-State A_|-fail_|-configurable_test_state"].result is None
        assert (
            ret["test_|-State A_|-fail_|-configurable_test_state"].full_return[
                "changes"
            ]
            == {}
        )

        assert not ret["test_|-State B_|-State B_|-configurable_test_state"].result

        assert ret["test_|-State C_|-State C_|-nop"].result
        assert not ret["test_|-State C_|-State C_|-nop"].full_return["__state_ran__"]
        assert (
            ret["test_|-State C_|-State C_|-nop"].full_return["comment"]
            == "State was not run because none of the onchanges reqs changed"
        )
