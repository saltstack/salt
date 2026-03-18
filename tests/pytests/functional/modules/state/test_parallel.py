import datetime

import pytest

import salt.utils.platform

SLEEP = salt.utils.platform.is_windows() and "timeout /t" or "sleep"


@pytest.fixture(scope="module")
def minion_config_overrides():
    return {"state_max_parallel": 2}


def test_max_parallel(state, state_tree):
    """
    Ensure the number of running ``parallel`` states can be limited.
    """
    sls_contents = f"""
        service_a:
          cmd.run:
              - name: {SLEEP} 3
              - parallel: True

        service_b:
          cmd.run:
              - name: {SLEEP} 3
              - parallel: True

        service_c:
          cmd.run:
              - name: 'true'
              - parallel: True
    """

    with pytest.helpers.temp_file("state_max_parallel.sls", sls_contents, state_tree):
        ret = state.sls(
            "state_max_parallel",
            __pub_jid="1",  # Because these run in parallel we need a fake JID)
        )
        assert not ret.failed
        assert all(single.result is True for single in ret)
        start_a = datetime.datetime.combine(
            datetime.date.today(),
            datetime.time.fromisoformat(
                ret[f"cmd_|-service_a_|-{SLEEP} 3_|-run"]["start_time"]
            ),
        )
        start_c = datetime.datetime.combine(
            datetime.date.today(),
            datetime.time.fromisoformat(
                ret["cmd_|-service_c_|-true_|-run"]["start_time"]
            ),
        )
        start_diff = start_c - start_a
        # c needs to wait for a or b to finish
        assert start_diff > datetime.timedelta(seconds=3)


def test_max_parallel_in_requisites(state, state_tree):
    """
    Ensure the number of running ``parallel`` states is respected
    when a state is started implicitly during a requisite check.
    """
    sls_contents = f"""
        service_a1:
          cmd.run:
              - name: {SLEEP} 2
              - parallel: True

        service_a2:
          cmd.run:
              - name: {SLEEP} 2
              - parallel: True

        service_c:
          cmd.run:
              - name: 'true'
              - parallel: True
              - require:
                - service_b

        service_b:
          cmd.run:
              - name: {SLEEP} 2
              - parallel: True
    """

    with pytest.helpers.temp_file("state_max_parallel_2.sls", sls_contents, state_tree):
        ret = state.sls(
            "state_max_parallel_2",
            __pub_jid="1",  # Because these run in parallel we need a fake JID)
        )
        assert not ret.failed
        assert all(single.result is True for single in ret)
        start_a1 = datetime.datetime.combine(
            datetime.date.today(),
            datetime.time.fromisoformat(
                ret[f"cmd_|-service_a1_|-{SLEEP} 2_|-run"]["start_time"]
            ),
        )
        start_c = datetime.datetime.combine(
            datetime.date.today(),
            datetime.time.fromisoformat(
                ret["cmd_|-service_c_|-true_|-run"]["start_time"]
            ),
        )
        start_diff = start_c - start_a1
        # c needs to wait for b, b needs to wait for a1 or a2 to finish
        assert start_diff > datetime.timedelta(seconds=4)
