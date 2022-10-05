"""
Tests for the idem state
"""
import tempfile
from contextlib import contextmanager

import pytest

import salt.state
import salt.utils.idem as idem
import salt.utils.path
import tests.support.sminion

pytestmark = [
    pytest.mark.skipif(not idem.HAS_POP[0], reason=idem.HAS_POP[1]),
]


@contextmanager
def test_state(salt_call_cli):
    with tempfile.NamedTemporaryFile(suffix=".sls", delete=True, mode="w+") as fh:
        sls_succeed_without_changes = """
        state_name:
          test.succeed_without_changes:
            - name: idem_test
            - foo: bar
        """
        fh.write(sls_succeed_without_changes)
        fh.flush()
        ret = salt_call_cli.run(
            "--local", "state.single", "idem.state", sls=fh.name, name="idem_test"
        )

    state_id = "idem_|-idem_test_|-idem_test_|-state"
    parent = ret.data[state_id]
    assert parent["result"] is True, parent["comment"]
    sub_state_ret = parent["sub_state_run"][0]
    assert sub_state_ret["result"] is True
    assert sub_state_ret["name"] == "idem_test"
    assert "Success!" in sub_state_ret["comment"]

    # Format the idem state through the state outputter
    minion_opts = tests.support.sminion.build_minion_opts()
    state_obj = salt.state.State(minion_opts)

    chunk_ret = state_obj.call_chunk(
        {"state": "state", "name": "name", "fun": "fun", "__id__": "__id__"},
        ret.data,
        {},
    )
    # Verify that the sub_state_run looks like a normal salt state
    assert "start_time" in chunk_ret[state_id]
    float(chunk_ret[state_id]["duration"])


def test_bad_state(salt_call_cli):
    bad_sls = "non-existant-file.sls"

    ret = salt_call_cli.run(
        "--local", "state.single", "idem.state", sls=bad_sls, name="idem_bad_test"
    )
    parent = ret.data["idem_|-idem_bad_test_|-idem_bad_test_|-state"]

    assert parent["result"] is False
    assert "SLS ref {} did not resolve to a file".format(bad_sls) == parent["comment"]
    assert not parent["sub_state_run"]
