import json
import logging
from textwrap import dedent

import pytest

log = logging.getLogger(__name__)


def test_issue_62590(salt_master, salt_minion, salt_cli):

    statepy = """
    # _states/test2.py
    import logging
    log = logging.getLogger(__name__)

    def call_another(name, m_name, **kwargs):
        ret = __states__[m_name](name, **kwargs)
        log.info(f'{__opts__["test"]}: {ret}')
        return ret
    """
    statesls = """
    run indirect:
      test2.call_another:
        - m_name: test.succeed_with_changes

    run prereq:
      test2.call_another:
        - m_name: test.succeed_with_changes

    nop:
      test.nop:
        - prereq:
          - run prereq
    """
    with salt_master.state_tree.base.temp_file(
        "_states/test2.py", statepy
    ), salt_master.state_tree.base.temp_file("test_62590.sls", statesls):
        ret = salt_cli.run("saltutil.sync_all", minion_tgt=salt_minion.id)
        assert ret.returncode == 0
        ret = salt_cli.run("state.apply", "test_62590", minion_tgt=salt_minion.id)
        assert ret.returncode == 0
        assert "Success!" == ret.data["test_|-nop_|-nop_|-nop"]["comment"]


def test_failing_sls(salt_master, salt_minion, salt_cli, caplog):
    """
    Test when running state.sls and the state fails.
    When the master stores the job and attempts to send
    an event a KeyError was previously being logged.
    This test ensures we do not log an error when
    attempting to send an event about a failing state.
    """
    statesls = """
    test_state:
      test.fail_without_changes:
        - name: "bla"
    """
    with salt_master.state_tree.base.temp_file("test_failure.sls", statesls):
        ret = salt_cli.run("state.sls", "test_failure", minion_tgt=salt_minion.id)
        for message in caplog.messages:
            assert "Event iteration failed with" not in message


def test_failing_sls_compound(salt_master, salt_minion, salt_cli, caplog):
    """
    Test when running state.sls in a compound command and the state fails.
    When the master stores the job and attempts to send
    an event a KeyError was previously being logged.
    This test ensures we do not log an error when
    attempting to send an event about a failing state.
    """
    statesls = """
    test_state:
      test.fail_without_changes:
        - name: "bla"
    """
    with salt_master.state_tree.base.temp_file("test_failure.sls", statesls):
        ret = salt_cli.run(
            "state.sls,cmd.run", "test_failure,ls", minion_tgt=salt_minion.id
        )
        for message in caplog.messages:
            assert "Event iteration failed with" not in message


@pytest.fixture
def _foobar_state(tmp_path, salt_master, salt_call_cli):
    chaos_mod = dedent(
        f"""
        def foobar_d(name):
            __salt__["state.single"]("file.managed", {json.dumps(str(tmp_path / 'foobar'))}, replace=False, test=True)
            return {{"name": name, "result": True, "comment": "foobar_d file mod", "changes": {{}}}}
        """
    )
    with salt_master.state_tree.base.temp_file("_states/issue_68281.py", chaos_mod):
        ret = salt_call_cli.run("saltutil.sync_states")
        assert ret.returncode == 0
        assert "states.issue_68281" in ret.data
        yield

    ret = salt_call_cli.run("saltutil.sync_states")
    assert ret.returncode == 0


@pytest.mark.usefixtures("_foobar_state")
def test_issue_68281(tmp_path, salt_master, salt_call_cli):
    """
    Ensure instantiating another state module loader during
    a state run does not confuse the loader/break test mode handling.
    """
    sls = f"""
    file:
      file.managed:
        - name: {json.dumps(str(tmp_path / 'ca.crt'))}
        - contents: dummy

    foobar-file:
      issue_68281.foobar_d

    kube-api-service:
      test.nop:
        - prereq:
          - file: test-download

    test-download:
      file.managed:
        - name: {json.dumps(str(tmp_path / 'foo'))}
        - source: salt://cheese
        - makedirs: true
        - replace: true
        - mode: '0755'
    """
    with salt_master.state_tree.base.temp_file("test_68281.sls", sls):
        ret = salt_call_cli.run("state.apply", "test_68281")
        assert ret.returncode == 0
        assert ret.data[f"file_|-test-download_|-{tmp_path}/foo_|-managed"]["changes"]
