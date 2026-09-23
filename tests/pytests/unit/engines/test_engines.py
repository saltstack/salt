import pytest

import salt.engines
from tests.support.mock import MagicMock, patch


@pytest.fixture
def kwargs():
    opts = {"__role": "minion"}
    name = "foobar"
    fun = f"{name}.start"
    config = funcs = runners = proxy = {}
    return dict(
        opts=opts,
        name=name,
        fun=fun,
        config=config,
        funcs=funcs,
        runners=runners,
        proxy=proxy,
    )


def test_engine_module_name(kwargs):
    engine = salt.engines.Engine(**kwargs)
    assert engine.name == kwargs["name"]


def test_engine_title_set(kwargs):
    engine = salt.engines.Engine(**kwargs)
    with patch("salt.utils.process.appendproctitle", MagicMock()) as mm:
        engine.run()
    mm.assert_called_with(kwargs["name"])


def test_ensure_master_uri_resolves_for_minion(kwargs):
    # #57952: a minion engine's opts snapshot is taken before the minion has
    # resolved master_uri, so the engine resolves it in its own process before
    # __salt__ (e.g. pillar.data) touches the transport.
    engine = salt.engines.Engine(**kwargs)
    engine.opts = {"__role": "minion", "file_client": "remote"}
    with patch(
        "salt.minion.resolve_dns",
        return_value={"master_uri": "tcp://1.2.3.4:4506", "master_ip": "1.2.3.4"},
    ) as resolve:
        engine._ensure_master_uri()
    resolve.assert_called_once()
    assert engine.opts["master_uri"] == "tcp://1.2.3.4:4506"


def test_ensure_master_uri_skips_master_role(kwargs):
    engine = salt.engines.Engine(**kwargs)
    engine.opts = {"__role": "master"}
    with patch("salt.minion.resolve_dns") as resolve:
        engine._ensure_master_uri()
    resolve.assert_not_called()
    assert "master_uri" not in engine.opts


def test_ensure_master_uri_skips_when_already_present(kwargs):
    engine = salt.engines.Engine(**kwargs)
    engine.opts = {"__role": "minion", "master_uri": "tcp://existing:4506"}
    with patch("salt.minion.resolve_dns") as resolve:
        engine._ensure_master_uri()
    resolve.assert_not_called()
    assert engine.opts["master_uri"] == "tcp://existing:4506"


def test_ensure_master_uri_skips_masterless(kwargs):
    engine = salt.engines.Engine(**kwargs)
    engine.opts = {"__role": "minion", "file_client": "local"}
    with patch("salt.minion.resolve_dns") as resolve:
        engine._ensure_master_uri()
    resolve.assert_not_called()
    assert "master_uri" not in engine.opts


def test_ensure_master_uri_is_non_fatal(kwargs):
    # A resolution failure (failover/list master, or an unresolvable master at
    # boot for a transport-less engine) must not prevent the engine starting.
    engine = salt.engines.Engine(**kwargs)
    engine.opts = {"__role": "minion", "file_client": "remote"}
    with patch("salt.minion.resolve_dns", side_effect=Exception("boom")):
        engine._ensure_master_uri()  # must not raise
    assert "master_uri" not in engine.opts
