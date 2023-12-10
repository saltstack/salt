"""
Test utility methods that the idem module and state share
"""
from contextlib import contextmanager

import pytest

import salt.utils.idem as idem
import salt.utils.path
from tests.support.case import TestCase

HAS_IDEM = not salt.utils.path.which("idem")


@pytest.mark.skipif(not idem.HAS_POP[0], reason=str(idem.HAS_POP[1]))
@contextmanager
class TestIdem(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hub = idem.hub()

    def test_loop(self):
        assert hasattr(self.hub.pop, "Loop")

    def test_subs(self):
        for sub in ("acct", "config", "idem", "exec", "states"):
            with self.subTest(sub=sub):
                assert hasattr(self.hub, sub)

    @pytest.mark.skipif(not HAS_IDEM, reason="idem is not installed")
    def test_idem_ex(self):
        assert hasattr(self.hub.idem, "ex")

    @pytest.mark.skipif(not HAS_IDEM, reason="idem is not installed")
    def test_idem_state_apply(self):
        assert hasattr(self.hub.idem.state, "apply")

    @pytest.mark.skipif(not HAS_IDEM, reason="idem is not installed")
    def test_idem_exec(self):
        # self.hub.exec.test.ping() causes a pylint error because of "exec" in the namespace
        assert getattr(self.hub, "exec").test.ping()

    @pytest.mark.skipif(not HAS_IDEM, reason="idem is not installed")
    def test_idem_state(self):
        ret = self.hub.states.test.succeed_without_changes({}, "test_state")
        assert ret["result"] is True

    def test_config(self):
        assert self.hub.OPT.acct
        assert self.hub.OPT.idem
