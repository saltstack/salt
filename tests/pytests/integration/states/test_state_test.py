import logging

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
