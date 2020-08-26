"""
Tests for the idem state
"""
import tempfile
from contextlib import contextmanager

import pytest
import salt.utils.idem as idem
import salt.utils.path

pytestmark = pytest.mark.skipif(not idem.HAS_POP[0], reason=idem.HAS_POP[1])


@pytest.mark.skipif(not salt.utils.path.which("idem"), reason="idem is not installed")
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

    parent = ret.json["idem_|-idem_test_|-idem_test_|-state"]
    assert parent["result"] is True, parent["comment"]
    sub_state_ret = parent["sub_state_run"][0]
    assert sub_state_ret["result"] is True
    assert sub_state_ret["name"] == "idem_test"
    assert "Success!" in sub_state_ret["comment"]


def test_bad_state(salt_call_cli):
    bad_sls = "non-existant-file.sls"

    ret = salt_call_cli.run(
        "--local", "state.single", "idem.state", sls=bad_sls, name="idem_bad_test"
    )
    parent = ret.json["idem_|-idem_bad_test_|-idem_bad_test_|-state"]

    assert parent["result"] is False
    assert "SLS ref {} did not resolve to a file".format(bad_sls) == parent["comment"]
    assert not parent["sub_state_run"]
