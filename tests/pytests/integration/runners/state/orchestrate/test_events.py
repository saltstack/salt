"""
Tests for orchestration events
"""
import concurrent.futures
import functools
import json
import time

import pytest
import salt.utils.jid

pytestmark = [
    pytest.mark.slow_test,
]


def test_state_event(salt_run_cli, salt_cli, salt_minion):
    """
    test to ensure state.event
    runner returns correct data
    """
    # If and when we have tornado 5.0, we can just do io_loop.run_in_executor() ....
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        runner_future = executor.submit(
            functools.partial(
                salt_run_cli.run, "state.event", "salt/job/*/new", count=1
            )
        )

        while not runner_future.done():
            ret = salt_cli.run("--static", "test.ping", minion_tgt=salt_minion.id)
            assert ret.exitcode == 0
            assert ret.json is True

        # Wait for the runner command which should now have data to return to us
        exc = runner_future.exception()
        if exc:
            raise exc
        ret = runner_future.result()
        assert ret.exitcode == 0
        # We have to parse the JSON ourselves since we have regular output mixed with JSON output
        data = None
        for line in ret.stdout.splitlines():
            try:
                _, payload = line.strip().split("\t")
                data = json.loads(payload)
                break
            except ValueError:
                continue
        assert isinstance(data, dict)
        assert salt_minion.id in data["minions"]


def test_jid_in_ret_event(
    salt_run_cli, salt_master, salt_minion, event_listener, base_env_state_tree_root_dir
):
    """
    Test to confirm that the ret event for the orchestration contains the
    jid for the jobs spawned.
    """
    test_state_contents = """
    date:
      cmd.run
    """
    test_orch_contents = """
    date_cmd:
      salt.state:
        - tgt: {minion_id}
        - sls: test-state

    ping_minion:
      salt.function:
        - name: test.ping
        - tgt: {minion_id}

    fileserver.file_list:
      salt.runner

    config.values:
      salt.wheel
    """.format(
        minion_id=salt_minion.id
    )
    with pytest.helpers.temp_file(
        "test-state.sls", test_state_contents, base_env_state_tree_root_dir
    ), pytest.helpers.temp_file(
        "test-orch.sls", test_orch_contents, base_env_state_tree_root_dir
    ):
        start_time = time.time()
        jid = salt.utils.jid.gen_jid(salt_master.config)

        ret = salt_run_cli.run("--jid", jid, "state.orchestrate", "test-orch")
        assert ret.exitcode == 0
        orch_job_data = ret.json
        for step_data in orch_job_data["data"][salt_master.id].values():
            assert "__jid__" in step_data

        expected_event_tag = "salt/run/{}/ret".format(jid)
        event_pattern = (salt_master.id, expected_event_tag)

        matched_events = event_listener.wait_for_events(
            [event_pattern], after_time=start_time, timeout=120
        )
        assert (
            matched_events.found_all_events
        ), "Failed to receive the event with the tag '{}'".format(expected_event_tag)
        for event in matched_events.matches:
            for job_data in event.data["return"]["data"][salt_master.id].values():
                assert "__jid__" in job_data


def test_parallel_orchestrations(
    salt_run_cli, salt_master, salt_minion, event_listener, base_env_state_tree_root_dir
):
    """
    Test to confirm that the parallel state requisite works in orch
    we do this by running 19 test.sleep's of 10 seconds, and a last 10 seconds sleep
    which depends on the previous 19.
    It should take more than 20 seconds and less than 19*10 seconds
    """
    test_orch_contents = """
    {% for count in range(1, 20) %}

    sleep {{ count }}:
        module.run:
            - name: test.sleep
            - length: 10
            - parallel: True

    {% endfor %}

    sleep 21:
        module.run:
            - name: test.sleep
            - length: 10
            - parallel: True
            - require:
                - module: sleep 1
    """
    with pytest.helpers.temp_file(
        "test-orch.sls", test_orch_contents, base_env_state_tree_root_dir
    ):
        start_time = time.time()
        jid = salt.utils.jid.gen_jid(salt_master.config)

        ret = salt_run_cli.run("--jid", jid, "state.orchestrate", "test-orch")
        assert ret.exitcode == 0
        orch_job_data = ret.json
        for step_data in orch_job_data["data"][salt_master.id].values():
            # we expect each duration to be greater than 10s
            assert step_data["duration"] > 10 * 1000

        # Since we started range(1, 20)(19) sleep state steps, and the last state
        # step requires all of those to have finished before it runs, since we are
        # running in parallel, the duration should be more than 20 seconds, and
        # less than 19*10(190) seconds, less then half actually
        duration = time.time() - start_time
        assert duration > 20
        assert duration < 19 * 10 / 2

        expected_event_tag = "salt/run/{}/ret".format(jid)
        event_pattern = (salt_master.id, expected_event_tag)

        matched_events = event_listener.wait_for_events(
            [event_pattern], after_time=start_time, timeout=120
        )
        assert (
            matched_events.found_all_events
        ), "Failed to receive the event with the tag '{}'".format(expected_event_tag)
        for event in matched_events.matches:
            for job_data in event.data["return"]["data"][salt_master.id].values():
                # we expect each duration to be greater than 10s
                assert job_data["duration"] > 10 * 1000

        # Since we started range(1, 20)(19) sleep state steps, and the last state
        # step requires all of those to have finished before it runs, since we are
        # running in parallel, the duration should be more than 20 seconds, and
        # less than 19*10(190) seconds, less then half actually
        duration = time.time() - start_time
        assert duration > 20
        assert duration < 19 * 10 / 2


def test_orchestration_soft_kill(
    salt_run_cli, salt_master, base_env_state_tree_root_dir
):
    sls_contents = """
    stage_one:
        test.succeed_without_changes

    stage_two:
        test.fail_without_changes
    """
    with pytest.helpers.temp_file(
        "test-orch.sls", sls_contents, base_env_state_tree_root_dir
    ):
        jid = salt.utils.jid.gen_jid(salt_master.config)

        # Without soft kill, the orchestration will fail because stage_two is set to fail
        ret = salt_run_cli.run("--jid", jid, "state.orchestrate", "test-orch")
        assert ret.exitcode == 1
        for state_data in ret.json["data"][salt_master.id].values():
            if state_data["__id__"] == "stage_two":
                assert state_data["result"] is False
            else:
                assert state_data["result"] is True

        # With soft kill set, 'stage_two' will not run, thus, the orchestration will not fail
        # and 'stage_two' will not be present in the returned data
        jid = salt.utils.jid.gen_jid(salt_master.config)
        ret = salt_run_cli.run("state.soft_kill", jid, "stage_two")
        assert ret.exitcode == 0
        ret = salt_run_cli.run("--jid", jid, "state.orchestrate", "test-orch")
        assert ret.exitcode == 0
        for state_data in ret.json["data"][salt_master.id].values():
            if state_data["__id__"] == "stage_two":
                pytest.fail("'stage_two' was present in the ochestration return data")
            else:
                assert state_data["result"] is True


def test_orchestration_with_pillar_dot_items(
    salt_run_cli, salt_master, base_env_state_tree_root_dir
):
    """
    Test to confirm when using a state file that includes other state file, if
    one of those state files includes pillar related functions that will not
    be pulling from the pillar cache that all the state files are available and
    the file_roots has been preserved.  See issues #48277 and #46986.
    """
    main_sls_contents = """
    include:
      - one
      - two
      - three
    """
    one_sls_contents = """
    {%- set foo = salt['saltutil.runner']('pillar.show_pillar') %}
    placeholder_one:
      test.succeed_without_changes
    """
    two_sls_contents = """
    placeholder_two:
      test.succeed_without_changes
    """
    three_sls_contents = """
    placeholder_three:
      test.succeed_without_changes
    """
    with pytest.helpers.temp_file(
        "test-orch.sls", main_sls_contents, base_env_state_tree_root_dir
    ), pytest.helpers.temp_file(
        "one.sls", one_sls_contents, base_env_state_tree_root_dir
    ), pytest.helpers.temp_file(
        "two.sls", two_sls_contents, base_env_state_tree_root_dir
    ), pytest.helpers.temp_file(
        "three.sls", three_sls_contents, base_env_state_tree_root_dir
    ):
        jid = salt.utils.jid.gen_jid(salt_master.config)

        ret = salt_run_cli.run("--jid", jid, "state.orchestrate", "test-orch")
        assert ret.exitcode == 0
        for state_data in ret.json["data"][salt_master.id].values():
            # Each state should be successful
            assert state_data["result"] is True


def test_orchestration_onchanges_and_prereq(
    salt_run_cli, salt_master, salt_minion, base_env_state_tree_root_dir, tmp_path
):
    sls_contents = """
    manage_a_file:
      salt.state:
        - tgt: {minion_id}
        - sls:
          - orch-req-test

    do_onchanges:
      salt.function:
        - tgt: {minion_id}
        - name: test.ping
        - onchanges:
          - salt: manage_a_file

    do_prereq:
      salt.function:
        - tgt: {minion_id}
        - name: test.ping
        - prereq:
          - salt: manage_a_file
    """.format(
        minion_id=salt_minion.id
    )

    orch_test_file = tmp_path / "orch-test-file"
    req_sls_contents = """
    {}:
      file.managed:
        - contents: 'Hello World!'
    """.format(
        orch_test_file
    )

    with pytest.helpers.temp_file(
        "test-orch.sls", sls_contents, base_env_state_tree_root_dir
    ), pytest.helpers.temp_file(
        "orch-req-test.sls", req_sls_contents, base_env_state_tree_root_dir
    ):
        jid1 = salt.utils.jid.gen_jid(salt_master.config)

        # Run in test mode, will describe what changes would occur
        ret = salt_run_cli.run(
            "--jid", jid1, "state.orchestrate", "test-orch", test=True
        )
        assert ret.exitcode == 0
        ret1 = ret.json

        # Now run without test mode to actually create the file
        ret = salt_run_cli.run("state.orchestrate", "test-orch")
        assert ret.exitcode == 0

        # Run again in test mode. Since there were no changes, the requisites should not fire.
        jid2 = salt.utils.jid.gen_jid(salt_master.config)
        ret = salt_run_cli.run(
            "--jid", jid2, "state.orchestrate", "test-orch", test=True
        )
        assert ret.exitcode == 0
        ret2 = ret.json

        # The first time through, all three states should have a None result
        for state_data in ret1["data"][salt_master.id].values():
            assert state_data["result"] is None
            if state_data.get("__id__") == "manage_a_file":
                # The file.managed state should have shown changes in the test mode
                # return data.
                assert state_data["changes"]

        # While the second time through, they should all have a True result.
        for state_data in ret2["data"][salt_master.id].values():
            assert state_data["result"] is True
            if state_data.get("__id__") == "manage_a_file":
                # After the file was created, running again in test mode should have
                # shown no changes.
                assert not state_data["changes"]
