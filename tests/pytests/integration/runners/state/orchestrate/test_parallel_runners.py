"""
Orchestrate ``salt.parallel_runners`` against real runner returns.

``test.sleep`` returns a boolean. That is the reproduction from #70742 / #66022:
the state must keep the loader context in its worker threads and must not
assume every runner return is a dictionary.
"""

import pytest

pytest.importorskip("zmq")

pytestmark = [
    pytest.mark.slow_test,
]


def test_parallel_runners_test_sleep(salt_run_cli, salt_master):
    """Run ``test.sleep`` twice under ``salt.parallel_runners``."""
    sls_contents = """
parallel-state:
  salt.parallel_runners:
    - runners:
        my_runner_1:
          - name: test.sleep
          - kwarg:
              s_time: 0.1
        my_runner_2:
          - name: test.sleep
          - kwarg:
              s_time: 0.1
"""
    with salt_master.state_tree.base.temp_file("test_parallel.sls", sls_contents):
        ret = salt_run_cli.run("state.orchestrate", "test_parallel")

    assert ret.returncode == 0, (ret.returncode, ret.stdout, ret.stderr)
    assert "All runner functions executed successfully." in ret.stdout
    assert "my_runner_1" in ret.stdout
    assert "my_runner_2" in ret.stdout
    assert "not subscriptable" not in ret.stdout
    assert "has no attribute 'get'" not in ret.stdout
