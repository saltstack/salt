from time import time

import pytest

from salt.utils import bundle
from salt.utils.bundle import PlayGround

pytestmark = [
    pytest.mark.skipif(not bundle.HAS_BUNDLE, reason="Docker"),
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="Windows does not support local masters!"),
]


GRACE_PERIOD = 6


def test_ping_speed():
    with PlayGround() as play_ground:
        mn = play_ground["master"]
        start_time = time()
        output, status = mn.run("salt '*' test.ping")
        assert "True" in output
        assert status == 0
        run_time = time() - start_time
    cut_time = 25
    assert run_time - GRACE_PERIOD < cut_time


state_file = """
test1:
  cmd.run:
    - name: "echo 'This is a test!'"

test2:
  pkg.removed:
    - name: nano

test3:
   pkg.installed:
    - name: nano

test4:
  user.present:
    - name: test

test5:
  user.absent:
    - name: test

test6:
  file.managed:
    - name: /tmp/test

test7:
  file.absent:
    - name: /tmp/test
"""


# def test_state_speed():
#     with LocalSalt(state_files={"state": state_file}) as local_salt:
#         mn = local_salt.master_minion()
