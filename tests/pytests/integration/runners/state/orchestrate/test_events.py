"""
Tests for orchestration events
"""

import concurrent.futures
import functools
import json
import logging
import time

import attr
import pytest
from saltfactories.utils import random_string

import salt.utils.jid
import salt.utils.platform
import salt.utils.pycrypto

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class TestMasterAccount:
    username = attr.ib()
    password = attr.ib()
    _delete_account = attr.ib(init=False, repr=False, default=False)

    @username.default
    def _default_username(self):
        return random_string("account-", uppercase=False)

    @password.default
    def _default_password(self):
        return random_string("pwd-", size=8)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture(scope="session")
def salt_auth_account_m_factory():
    return TestMasterAccount(username="saltdev-auth-m")


@pytest.fixture(scope="module")
def salt_auth_account_m(salt_auth_account_m_factory):
    with salt_auth_account_m_factory as account:
        yield account


@pytest.fixture(scope="module")
def runner_master_config(salt_auth_account_m):
    return {
        "external_auth": {
            "pam": {salt_auth_account_m.username: [{"*": [".*"]}, "@runner", "@wheel"]}
        }
    }


@pytest.fixture(scope="module")
def runner_salt_master(salt_factories, runner_master_config):
    factory = salt_factories.salt_master_daemon(
        "runner-master", defaults=runner_master_config
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def runner_salt_run_cli(runner_salt_master):
    return runner_salt_master.salt_run_cli()


@pytest.fixture(scope="module")
def runner_salt_call_cli(runner_salt_minion):
    return runner_salt_minion.salt_call_cli()


@pytest.fixture(scope="module")
def runner_add_user(runner_salt_run_cli, salt_auth_account_m):
    ## create user on master to use
    ret = runner_salt_run_cli.run("salt.cmd", "user.add", salt_auth_account_m.username)
    assert ret.returncode == 0

    yield

    ## remove user on master
    ret = runner_salt_run_cli.run(
        "salt.cmd", "user.delete", salt_auth_account_m.username
    )
    assert ret.returncode == 0


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
            assert ret.returncode == 0
            assert ret.data is True

        # Wait for the runner command which should now have data to return to us
        exc = runner_future.exception()
        if exc:
            raise exc
        ret = runner_future.result()
        assert ret.returncode == 0
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


def test_jid_in_ret_event(salt_run_cli, salt_master, salt_minion, event_listener):
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
    with salt_master.state_tree.base.temp_file(
        "test-state.sls", test_state_contents
    ), salt_master.state_tree.base.temp_file("test-orch.sls", test_orch_contents):
        start_time = time.time()
        jid = salt.utils.jid.gen_jid(salt_master.config)

        ret = salt_run_cli.run("--jid", jid, "state.orchestrate", "test-orch")
        assert ret.returncode == 0
        orch_job_data = ret.data
        for step_data in orch_job_data["data"][salt_master.id].values():
            assert "__jid__" in step_data

        expected_event_tag = f"salt/run/{jid}/ret"
        event_pattern = (salt_master.id, expected_event_tag)

        matched_events = event_listener.wait_for_events(
            [event_pattern], after_time=start_time, timeout=120
        )
        assert (
            matched_events.found_all_events
        ), f"Failed to receive the event with the tag '{expected_event_tag}'"
        for event in matched_events.matches:
            for job_data in event.data["return"]["data"][salt_master.id].values():
                assert "__jid__" in job_data


# This test is flaky on FreeBSD
@pytest.mark.skip_on_freebsd
@pytest.mark.slow_test
@pytest.mark.skip_on_spawning_platform(
    reason="The '__low__' global is not populated on spawning platforms"
)
def test_parallel_orchestrations(
    salt_run_cli, salt_master, salt_minion, event_listener
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
    with salt_master.state_tree.base.temp_file("test-orch.sls", test_orch_contents):
        start_time = time.time()
        jid = salt.utils.jid.gen_jid(salt_master.config)

        ret = salt_run_cli.run("--jid", jid, "state.orchestrate", "test-orch")
        assert ret.returncode == 0
        orch_job_data = ret.data
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

        expected_event_tag = f"salt/run/{jid}/ret"
        event_pattern = (salt_master.id, expected_event_tag)

        matched_events = event_listener.wait_for_events(
            [event_pattern], after_time=start_time, timeout=120
        )
        assert (
            matched_events.found_all_events
        ), f"Failed to receive the event with the tag '{expected_event_tag}'"
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


def test_orchestration_soft_kill(salt_run_cli, salt_master):
    sls_contents = """
    stage_one:
        test.succeed_without_changes

    stage_two:
        test.fail_without_changes
    """
    with salt_master.state_tree.base.temp_file("test-orch.sls", sls_contents):
        jid = salt.utils.jid.gen_jid(salt_master.config)

        # Without soft kill, the orchestration will fail because stage_two is set to fail
        ret = salt_run_cli.run("--jid", jid, "state.orchestrate", "test-orch")
        assert ret.returncode == 1
        for state_data in ret.data["data"][salt_master.id].values():
            if state_data["__id__"] == "stage_two":
                assert state_data["result"] is False
            else:
                assert state_data["result"] is True

        # With soft kill set, 'stage_two' will not run, thus, the orchestration will not fail
        # and 'stage_two' will not be present in the returned data
        jid = salt.utils.jid.gen_jid(salt_master.config)
        ret = salt_run_cli.run("state.soft_kill", jid, "stage_two")
        assert ret.returncode == 0
        ret = salt_run_cli.run("--jid", jid, "state.orchestrate", "test-orch")
        assert ret.returncode == 0
        for state_data in ret.data["data"][salt_master.id].values():
            if state_data["__id__"] == "stage_two":
                pytest.fail("'stage_two' was present in the ochestration return data")
            else:
                assert state_data["result"] is True


def test_orchestration_with_pillar_dot_items(salt_run_cli, salt_master):
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
    with salt_master.state_tree.base.temp_file(
        "test-orch.sls", main_sls_contents
    ), salt_master.state_tree.base.temp_file(
        "one.sls", one_sls_contents
    ), salt_master.state_tree.base.temp_file(
        "two.sls", two_sls_contents
    ), salt_master.state_tree.base.temp_file(
        "three.sls", three_sls_contents
    ):
        jid = salt.utils.jid.gen_jid(salt_master.config)

        ret = salt_run_cli.run("--jid", jid, "state.orchestrate", "test-orch")
        assert ret.returncode == 0
        for state_data in ret.data["data"][salt_master.id].values():
            # Each state should be successful
            assert state_data["result"] is True


def test_orchestration_onchanges_and_prereq(
    salt_run_cli, salt_master, salt_minion, tmp_path
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

    with salt_master.state_tree.base.temp_file(
        "test-orch.sls", sls_contents
    ), salt_master.state_tree.base.temp_file("orch-req-test.sls", req_sls_contents):
        jid1 = salt.utils.jid.gen_jid(salt_master.config)

        # Run in test mode, will describe what changes would occur
        ret = salt_run_cli.run(
            "--jid", jid1, "state.orchestrate", "test-orch", test=True
        )
        assert ret.returncode == 0
        ret1 = ret.data

        # Now run without test mode to actually create the file
        ret = salt_run_cli.run("state.orchestrate", "test-orch")
        assert ret.returncode == 0

        # Run again in test mode. Since there were no changes, the requisites should not fire.
        jid2 = salt.utils.jid.gen_jid(salt_master.config)
        ret = salt_run_cli.run(
            "--jid", jid2, "state.orchestrate", "test-orch", test=True
        )
        assert ret.returncode == 0
        ret2 = ret.data

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


@pytest.mark.slow_test
@pytest.mark.skip_if_not_root
@pytest.mark.skip_on_windows
@pytest.mark.skip_on_darwin
@pytest.mark.timeout_unless_on_windows(120)
def test_unknown_in_runner_event(
    runner_salt_run_cli,
    runner_salt_master,
    salt_minion,
    salt_auth_account_m,
    runner_add_user,
    event_listener,
):
    """
    Test to confirm that the ret event for the orchestration contains the
    jid for the jobs spawned.
    """
    file_roots_base_dir = runner_salt_master.config["file_roots"]["base"][0]
    test_top_file_contents = """
    base:
      '{minion_id}':
        - {file_roots}
    """.format(
        minion_id=salt_minion.id, file_roots=file_roots_base_dir
    )
    test_init_state_contents = """
    always-passes-with-any-kwarg:
      test.nop:
        - name: foo
        - something: else
        - foo: bar
    always-passes:
      test.succeed_without_changes:
        - name: foo
    always-changes-and-succeeds:
      test.succeed_with_changes:
        - name: foo
    {{slspath}}:
      test.nop
    """
    test_orch_contents = """
    test_highstate:
      salt.state:
        - tgt: {minion_id}
        - highstate: True
    test_runner_metasyntetic:
      salt.runner:
        - name: test.metasyntactic
        - locality: us
    """.format(
        minion_id=salt_minion.id
    )
    with runner_salt_master.state_tree.base.temp_file(
        "top.sls", test_top_file_contents
    ), runner_salt_master.state_tree.base.temp_file(
        "init.sls", test_init_state_contents
    ), runner_salt_master.state_tree.base.temp_file(
        "orch.sls", test_orch_contents
    ):
        ret = runner_salt_run_cli.run(
            "salt.cmd", "shadow.gen_password", salt_auth_account_m.password
        )
        assert ret.returncode == 0

        gen_pwd = ret.stdout
        ret = runner_salt_run_cli.run(
            "salt.cmd", "shadow.set_password", salt_auth_account_m.username, gen_pwd
        )
        assert ret.returncode == 0

        jid = salt.utils.jid.gen_jid(runner_salt_master.config)
        start_time = time.time()

        ret = runner_salt_run_cli.run(
            "--jid",
            jid,
            "-a",
            "pam",
            "--username",
            salt_auth_account_m.username,
            "--password",
            salt_auth_account_m.password,
            "state.orchestrate",
            "orch",
        )
        assert not ret.stdout.startswith("Authentication failure")

        expected_new_event_tag = "salt/run/*/new"
        event_pattern = (runner_salt_master.id, expected_new_event_tag)
        found_events = event_listener.get_events([event_pattern], after_time=start_time)

        for event in found_events:
            if event.data["fun"] == "runner.test.metasyntactic":
                assert event.data["user"] == salt_auth_account_m.username

        expected_ret_event_tag = "salt/run/*/ret"
        event_pattern = (runner_salt_master.id, expected_ret_event_tag)
        found_events = event_listener.get_events([event_pattern], after_time=start_time)

        for event in found_events:
            if event.data["fun"] == "runner.test.metasyntactic":
                assert event.data["user"] == salt_auth_account_m.username
