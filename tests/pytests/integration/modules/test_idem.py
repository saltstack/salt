"""
Integration tests for the idem execution module
"""
from contextlib import contextmanager

import pytest

import salt.utils.idem as idem
import salt.utils.path

pytestmark = [
    pytest.mark.skipif(not idem.HAS_POP[0], reason=idem.HAS_POP[1]),
]


@pytest.mark.skipif(not salt.utils.path.which("idem"), reason="idem is not installed")
@contextmanager
def test_exec(salt_call_cli):
    ret = salt_call_cli.run("--local", "idem.exec", "test.ping")
    assert ret.data is True
