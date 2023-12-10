import pytest

pytestmark = [
    pytest.mark.slow_test,
]


def test_orchestrate_output(salt_run_cli, salt_minion, salt_master):
    """
    Ensure the orchestrate runner outputs useful state data.

    In Issue #31330, the output only contains ['outputter:', '    highstate'],
    and not the full stateful return. This tests ensures we don't regress in that
    manner again.

    Also test against some sample "good" output that would be included in a correct
    orchestrate run.
    """
    bad_out = ["outputter:", "    highstate"]
    good_out = [
        "    Function: salt.state",
        "      Result: True",
        "Succeeded: 1 (changed=1)",
        "Failed:    0",
        "Total states run:     1",
    ]
    sls_contents = """
    call_sleep_state:
      salt.state:
        - tgt: {}
        - sls: simple-ping
    """.format(
        salt_minion.id
    )
    simple_ping_sls = """
    simple-ping:
      module.run:
        - name: test.ping
    """
    with salt_master.state_tree.base.temp_file(
        "orch-test.sls", sls_contents
    ), salt_master.state_tree.base.temp_file("simple-ping.sls", simple_ping_sls):
        ret = salt_run_cli.run("--out=highstate", "state.orchestrate", "orch-test")
        assert ret.returncode == 0
        ret_output = ret.stdout.splitlines()

        # First, check that we don't have the "bad" output that was displaying in
        # Issue #31330 where only the highstate outputter was listed
        assert bad_out != ret_output
        assert len(ret_output) > 2

        # Now test that some expected good sample output is present in the return.
        for item in good_out:
            assert item in ret_output


def test_orchestrate_state_output_with_salt_function(
    salt_run_cli, salt_minion, salt_master
):
    """
    Ensure that orchestration produces the correct output with salt.function.

    A salt execution module function does not return highstate data, so we
    should not try to recursively output it as such.
    The outlier to this rule is state.apply, but that is handled by the salt.state.

    See https://github.com/saltstack/salt/issues/60029 for more detail.
    """
    sls_contents = """
    arg_clean_test:
      salt.function:
        - name: test.arg_clean
        - arg:
          - B flat major
          - has 2 flats
        - tgt: {minion_id}

    ping_test:
      salt.function:
        - name: test.ping
        - tgt: {minion_id}
    """.format(
        minion_id=salt_minion.id
    )
    with salt_master.state_tree.base.temp_file("orch-function-test.sls", sls_contents):
        ret = salt_run_cli.run(
            "--out=highstate", "state.orchestrate", "orch-function-test"
        )
        assert ret.returncode == 0
        ret_output = [line.strip() for line in ret.stdout.splitlines()]

        assert "args:" in ret_output
        assert "- B flat major" in ret_output
        assert "- has 2 flats" in ret_output
        assert "True" in ret_output


def test_orchestrate_nested(salt_run_cli, salt_minion, salt_master, tmp_path):
    """
    test salt-run state.orchestrate and failhard with nested orchestration
    """
    testfile = tmp_path / "ewu-2016-12-13"
    inner_sls = """
    cmd.run:
      salt.function:
        - tgt: {}
        - arg:
          - {}
        - failhard: True
    """.format(
        salt_minion.id, pytest.helpers.shell_test_false()
    )
    outer_sls = """
    state.orchestrate:
      salt.runner:
        - mods: nested.inner
        - failhard: True

    cmd.run:
      salt.function:
        - tgt: {}
        - arg:
          - touch {}
    """.format(
        salt_minion.id, testfile
    )

    with salt_master.state_tree.base.temp_file(
        "nested/inner.sls", inner_sls
    ), salt_master.state_tree.base.temp_file("nested/outer.sls", outer_sls):
        ret = salt_run_cli.run("state.orchestrate", "nested.outer")
        assert ret.returncode != 0
        assert testfile.exists() is False


def test_orchestrate_with_mine(salt_run_cli, salt_minion, salt_master):
    """
    test salt-run state.orchestrate with mine.get call in sls
    """
    sls_contents = (
        """
    {% set minion = '"""
        + salt_minion.id
        + """' %}
    {% set mine = salt.saltutil.runner('mine.get', tgt=minion, fun='test.ping') %}

    {% if mine %}
    test.ping:
      salt.function:
        - tgt: "{{ minion }}"
    {% endif %}
    """
    )
    ret = salt_run_cli.run("mine.update", salt_minion.id)
    assert ret.returncode == 0

    with salt_master.state_tree.base.temp_file("orch/mine.sls", sls_contents):
        ret = salt_run_cli.run("state.orchestrate", "orch.mine")
        assert ret.returncode == 0
        assert ret.data
        assert ret.data["data"][salt_master.id]
        for state_data in ret.data["data"][salt_master.id].values():
            assert state_data["changes"]["ret"]
            assert state_data["changes"]["ret"][salt_minion.id] is True


def test_orchestrate_state_and_function_failure(salt_run_cli, salt_master, salt_minion):
    """
    Ensure that returns from failed minions are in the changes dict where
    they belong, so they can be programmatically analyzed.

    See https://github.com/saltstack/salt/issues/43204
    """
    init_sls = """
    Step01:
      salt.state:
        - tgt: {minion_id}
        - sls:
          - orch.issue43204.fail_with_changes

    Step02:
      salt.function:
        - name: runtests_helpers.nonzero_retcode_return_false
        - tgt: {minion_id}
        - fail_function: runtests_helpers.fail_function
    """.format(
        minion_id=salt_minion.id
    )
    fail_sls = """
    test fail with changes:
      test.fail_with_changes
    """
    with salt_master.state_tree.base.temp_file(
        "orch/issue43204/init.sls", init_sls
    ), salt_master.state_tree.base.temp_file(
        "orch/issue43204/fail_with_changes.sls", fail_sls
    ):
        ret = salt_run_cli.run("saltutil.sync_modules")
        assert ret.returncode == 0

        ret = salt_run_cli.run("state.orchestrate", "orch.issue43204")
        assert ret.returncode != 0

    # Drill down to the changes dict
    data = ret.data["data"][salt_master.id]
    state_ret = data["salt_|-Step01_|-Step01_|-state"]["changes"]
    func_ret = data[
        "salt_|-Step02_|-runtests_helpers.nonzero_retcode_return_false_|-function"
    ]["changes"]

    # Remove duration and start time from the results, since they would
    # vary with each run and that would make it impossible to test.
    for item in ("duration", "start_time"):
        state_ret["ret"][salt_minion.id][
            "test_|-test fail with changes_|-test fail with changes_|-fail_with_changes"
        ].pop(item)

    expected = {
        "out": "highstate",
        "ret": {
            salt_minion.id: {
                "test_|-test fail with changes_|-test fail with changes_|-fail_with_changes": {
                    "__id__": "test fail with changes",
                    "__run_num__": 0,
                    "__sls__": "orch.issue43204.fail_with_changes",
                    "changes": {
                        "testing": {
                            "new": "Something pretended to change",
                            "old": "Unchanged",
                        }
                    },
                    "comment": "Failure!",
                    "name": "test fail with changes",
                    "result": False,
                }
            }
        },
    }
    assert state_ret == expected
    assert func_ret == {"ret": {salt_minion.id: False}}


def test_orchestrate_salt_function_return_false_failure(
    salt_run_cli, salt_minion, salt_master
):
    """
    Ensure that functions that only return False in the return
    are flagged as failed when run as orchestrations.

    See https://github.com/saltstack/salt/issues/30367
    """
    sls_contents = """
    deploy_check:
      salt.function:
        - name: test.false
        - tgt: {}
    """.format(
        salt_minion.id
    )
    with salt_master.state_tree.base.temp_file("orch/issue30367.sls", sls_contents):
        ret = salt_run_cli.run("saltutil.sync_modules")
        assert ret.returncode == 0

        ret = salt_run_cli.run("state.orchestrate", "orch.issue30367")
        assert ret.returncode != 0

    # Drill down to the changes dict
    data = ret.data["data"][salt_master.id]
    state_result = data["salt_|-deploy_check_|-test.false_|-function"]["result"]
    func_ret = data["salt_|-deploy_check_|-test.false_|-function"]["changes"]

    assert state_result is False
    assert func_ret == {"ret": {salt_minion.id: False}}


def test_orchestrate_target_exists(salt_run_cli, salt_minion, salt_master):
    """
    test orchestration when target exists while using multiple states
    """
    sls_contents = """
    core:
      salt.state:
        - tgt: '{minion_id}*'
        - sls:
          - core

    test-state:
      salt.state:
        - tgt: '{minion_id}*'
        - sls:
          - orch.target-test

    cmd.run:
      salt.function:
        - tgt: '{minion_id}*'
        - arg:
          - echo test
    """.format(
        minion_id=salt_minion.id
    )
    target_test_sls = """
    always_true:
      test.succeed_without_changes
    """
    with salt_master.state_tree.base.temp_file(
        "orch/target-exists.sls", sls_contents
    ), salt_master.state_tree.base.temp_file(
        "orch/target-test.sls", target_test_sls
    ), salt_master.state_tree.base.temp_file(
        "core.sls", target_test_sls
    ):
        ret = salt_run_cli.run("state.orchestrate", "orch.target-exists")
        assert ret.returncode == 0
        assert ret.data

    data = ret.data["data"][salt_master.id]
    to_check = {"core", "test-state", "cmd.run"}
    for state_data in data.values():
        if state_data["name"] == "core":
            to_check.remove("core")
            assert state_data["result"] is True
        if state_data["name"] == "test-state":
            assert state_data["result"] is True
            to_check.remove("test-state")
        if state_data["name"] == "cmd.run":
            assert state_data["changes"] == {
                "ret": {salt_minion.id: "test"},
            }
            to_check.remove("cmd.run")

    assert not to_check


def test_orchestrate_target_does_not_exist(salt_run_cli, salt_minion, salt_master):
    """
    test orchestration when target does not exist while using multiple states
    """
    sls_contents = """
    core:
      salt.state:
        - tgt: 'does-not-exist*'
        - sls:
          - core

    test-state:
      salt.state:
        - tgt: '{minion_id}*'
        - sls:
          - orch.target-test

    cmd.run:
      salt.function:
        - tgt: '{minion_id}*'
        - arg:
          - echo test
    """.format(
        minion_id=salt_minion.id
    )
    target_test_sls = """
    always_true:
      test.succeed_without_changes
    """
    with salt_master.state_tree.base.temp_file(
        "orch/target-does-not-exist.sls", sls_contents
    ), salt_master.state_tree.base.temp_file(
        "orch/target-test.sls", target_test_sls
    ), salt_master.state_tree.base.temp_file(
        "core.sls", target_test_sls
    ):
        ret = salt_run_cli.run("state.orchestrate", "orch.target-does-not-exist")
        assert ret.returncode != 0
        assert ret.data

    data = ret.data["data"][salt_master.id]
    to_check = {"core", "test-state", "cmd.run"}
    for state_data in data.values():
        if state_data["name"] == "core":
            to_check.remove("core")
            assert state_data["result"] is False
            assert state_data["comment"] == "No minions returned"
        if state_data["name"] == "test-state":
            assert state_data["result"] is True
            to_check.remove("test-state")
        if state_data["name"] == "cmd.run":
            assert state_data["changes"] == {
                "ret": {salt_minion.id: "test"},
            }
            to_check.remove("cmd.run")

    assert not to_check


def test_orchestrate_retcode(salt_run_cli, salt_master):
    """
    Test orchestration with nonzero retcode set in __context__
    """
    sls_contents = """
    test_runner_success:
      salt.runner:
        - name: runtests_helpers.success

    test_runner_failure:
      salt.runner:
        - name: runtests_helpers.failure

    test_wheel_success:
      salt.wheel:
        - name: runtests_helpers.success

    test_wheel_failure:
      salt.wheel:
        - name: runtests_helpers.failure
    """
    with salt_master.state_tree.base.temp_file("orch/retcode.sls", sls_contents):
        ret = salt_run_cli.run("saltutil.sync_runners")
        assert ret.returncode == 0
        ret = salt_run_cli.run("saltutil.sync_wheel")
        assert ret.returncode == 0

        ret = salt_run_cli.run("state.orchestrate", "orch.retcode")
        assert ret.returncode != 0
        assert ret.data

    data = ret.data["data"][salt_master.id]
    to_check = {
        "test_runner_success",
        "test_runner_failure",
        "test_wheel_failure",
        "test_wheel_success",
    }

    for state_data in data.values():
        name = state_data["__id__"]
        to_check.remove(name)
        if name in ("test_runner_success", "test_wheel_success"):
            assert state_data["result"] is True
        if name in ("test_runner_failure", "test_wheel_failure"):
            assert state_data["result"] is False

    assert not to_check


def test_orchestrate_batch_with_failhard_error(
    salt_run_cli, salt_master, salt_minion, tmp_path
):
    """
    test orchestration properly stops with failhard and batch.
    """
    testfile = tmp_path / "test-file"
    sls_contents = """
    call_fail_state:
      salt.state:
        - tgt: {}
        - batch: 1
        - failhard: True
        - sls: fail
    """.format(
        salt_minion.id
    )
    fail_sls = """
    {}:
      file.managed:
        - source: salt://hnlcfsdjhkzkdhynclarkhmcls
    """.format(
        testfile
    )
    with salt_master.state_tree.base.temp_file(
        "orch/batch.sls", sls_contents
    ), salt_master.state_tree.base.temp_file("fail.sls", fail_sls):
        ret = salt_run_cli.run("state.orchestrate", "orch.batch")
        assert ret.returncode != 0

    data = ret.data["data"][salt_master.id]
    result = data["salt_|-call_fail_state_|-call_fail_state_|-state"]["result"]
    changes = data["salt_|-call_fail_state_|-call_fail_state_|-state"]["changes"]

    assert result is False
    # The execution should stop after first error, so return dict should contain only one minion
    assert len(changes["ret"]) == 1


def _check_skip(grains):
    if grains["os"] == "Fedora":
        return True
    if grains["os"] == "VMware Photon OS" and grains["osmajorrelease"] == 4:
        return True
    if grains["os"] == "Ubuntu" and grains["osmajorrelease"] in (20, 22):
        return True
    return False


@pytest.mark.skip_initial_gh_actions_failure(skip=_check_skip)
def test_orchestrate_subset(
    salt_run_cli,
    salt_master,
    salt_minion,
    salt_sub_minion,
):
    """
    test orchestration state using subset
    """
    sls_contents = """
    test subset:
      salt.state:
        - tgt: '*minion*'
        - subset: 1
        - sls: test
    """
    test_sls = """
    test state:
      test.succeed_without_changes:
        - name: test
    """
    with salt_master.state_tree.base.temp_file(
        "orch/subset.sls", sls_contents
    ), salt_master.state_tree.base.temp_file("test.sls", test_sls):
        ret = salt_run_cli.run("state.orchestrate", "orch.subset", _timeout=60)
        assert ret.returncode == 0

    for state_data in ret.data["data"][salt_master.id].values():
        # Should only run in one of the minions
        comment = state_data["comment"]
        if salt_minion.id in comment:
            assert salt_sub_minion.id not in comment
        elif salt_sub_minion.id in comment:
            assert salt_minion.id not in comment
        else:
            pytest.fail(
                "None of the targeted minions({}) show up in comment: '{}'".format(
                    ", ".join([salt_minion.id, salt_sub_minion.id]), comment
                )
            )
