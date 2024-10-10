import datetime

import pytest


@pytest.fixture(scope="module")
def minion_config_overrides():
    return {"state_max_parallel": 2}


@pytest.mark.skip_on_windows
def test_max_parallel(state, state_tree):
    """
    Ensure the number of running ``parallel`` states can be limited.
    """
    sls_contents = """
        service_a:
          cmd.run:
              - name: sleep 3
              - parallel: True

        service_b:
          cmd.run:
              - name: sleep 3
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
        start_a = datetime.datetime.combine(
            datetime.date.today(),
            datetime.time.fromisoformat(
                ret["cmd_|-service_a_|-sleep 3_|-run"]["start_time"]
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
