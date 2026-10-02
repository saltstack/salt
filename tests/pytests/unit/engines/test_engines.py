import logging
import os
import threading
import time

import pytest

import salt.config
import salt.engines
import salt.minion
import salt.utils.files
from salt.utils.optsdict import OptsDict
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


@pytest.fixture
def minion_pki(tmp_path):
    """
    A pki_dir that already holds the minion's key pair, as it does on every
    start after the first one.
    """
    pki = tmp_path / "pki"
    pki.mkdir()
    for name in ("minion.pem", "minion.pub"):
        with salt.utils.files.fopen(str(pki / name), "w") as fh:
            fh.write("key\n")
    return str(pki)


def test_engine_module_name(kwargs):
    engine = salt.engines.Engine(**kwargs)
    assert engine.name == kwargs["name"]


def test_engine_title_set(kwargs):
    engine = salt.engines.Engine(**kwargs)
    with patch("salt.utils.process.appendproctitle", MagicMock()) as mm:
        engine.run()
    mm.assert_called_with(kwargs["name"])


def test_ensure_master_uri_resolves_for_minion(kwargs, minion_pki):
    # #57952: a minion engine's opts snapshot is taken before the minion has
    # resolved master_uri, so the engine resolves it in its own process before
    # __salt__ (e.g. pillar.data) touches the transport.
    engine = salt.engines.Engine(**kwargs)
    engine.opts = {"__role": "minion", "file_client": "remote", "pki_dir": minion_pki}
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


def test_ensure_master_uri_is_non_fatal(kwargs, minion_pki):
    # A resolution failure (failover/list master, or an unresolvable master at
    # boot for a transport-less engine) must not prevent the engine starting.
    engine = salt.engines.Engine(**kwargs)
    engine.opts = {"__role": "minion", "file_client": "remote", "pki_dir": minion_pki}
    with patch("salt.minion.resolve_dns", side_effect=Exception("boom")):
        engine._ensure_master_uri()  # must not raise
    assert "master_uri" not in engine.opts


@pytest.mark.parametrize("master_type", ["failover", "distributed"])
def test_ensure_master_uri_skips_list_master_57952(kwargs, master_type):
    # A failover/distributed minion keeps ``master`` as a list in the opts its
    # engines are forked with. resolve_dns raises SaltSystemExit (a SystemExit,
    # not an Exception) for a list, so it must not be called at all, otherwise
    # the engine process dies and the process manager keeps restarting it.
    engine = salt.engines.Engine(**kwargs)
    engine.opts = dict(
        salt.config.DEFAULT_MINION_OPTS,
        __role="minion",
        master=["m1.example.com", "m2.example.com"],
        master_type=master_type,
    )
    with patch("salt.minion.resolve_dns", wraps=salt.minion.resolve_dns) as resolve:
        engine._ensure_master_uri()  # must not raise SystemExit
    resolve.assert_not_called()
    assert "master_uri" not in engine.opts


def test_ensure_master_uri_survives_salt_system_exit_57952(kwargs, minion_pki):
    # resolve_dns exits with SaltSystemExit (code 42) for an empty master;
    # that must be contained like any other resolution failure.
    engine = salt.engines.Engine(**kwargs)
    engine.opts = dict(
        salt.config.DEFAULT_MINION_OPTS,
        __role="minion",
        master="",
        pki_dir=minion_pki,
    )
    engine._ensure_master_uri()  # must not raise SystemExit
    assert "master_uri" not in engine.opts


def test_ensure_master_uri_resolves_optsdict_57952(kwargs, minion_pki):
    # On 3008.x the minion hands its engines an OptsDict (copy-on-write child
    # of the minion manager's opts). Resolve with the real resolve_dns, only
    # stubbing the network lookup, to prove the opts copy and update work on it.
    parent = OptsDict.from_dict(
        dict(
            salt.config.DEFAULT_MINION_OPTS,
            __role="minion",
            master="salt",
            pki_dir=minion_pki,
        )
    )
    engine = salt.engines.Engine(**kwargs)
    engine.opts = OptsDict.from_parent(parent, name="minion_manager:salt")
    with patch("salt.utils.network.dns_check", return_value="192.0.2.10"):
        engine._ensure_master_uri()
    assert engine.opts["master_ip"] == "192.0.2.10"
    assert engine.opts["master_uri"] == "tcp://192.0.2.10:4506"
    assert "master_uri" not in parent


def _run_engine_capturing_opts(engine):
    seen = {}

    def start(**kwargs):
        seen["master_uri"] = engine.opts.get("master_uri")

    with patch("salt.loader.utils", MagicMock(return_value={})), patch(
        "salt.loader.engines", MagicMock(return_value={"foobar.start": start})
    ), patch("salt.utils.process.appendproctitle", MagicMock()):
        engine.run()
    return seen


def test_engine_run_resolves_master_uri_before_engine_starts_57952(kwargs, minion_pki):
    # Production path: Engine.run() with the opts a minion forks its engines
    # with (no master_uri yet). The engine's start function, and so every
    # __salt__ call it makes, must already see master_uri.
    engine = salt.engines.Engine(**kwargs)
    engine.opts = dict(
        salt.config.DEFAULT_MINION_OPTS,
        __role="minion",
        master="salt",
        pki_dir=minion_pki,
    )
    with patch("salt.utils.network.dns_check", return_value="192.0.2.10"):
        seen = _run_engine_capturing_opts(engine)
    assert seen == {"master_uri": "tcp://192.0.2.10:4506"}


def test_engine_run_master_engine_untouched_57952(kwargs):
    # Inverse: a master's engines must not be given a master_uri.
    engine = salt.engines.Engine(**kwargs)
    engine.opts = dict(salt.config.DEFAULT_MASTER_OPTS, __role="master")
    with patch("salt.utils.network.dns_check") as dns_check:
        seen = _run_engine_capturing_opts(engine)
    dns_check.assert_not_called()
    assert seen == {"master_uri": None}


def test_engine_run_failover_minion_engine_starts_57952(kwargs):
    # A failover minion's engine (list master) must still start; it is left
    # without master_uri, as before #57952 was fixed.
    engine = salt.engines.Engine(**kwargs)
    engine.opts = dict(
        salt.config.DEFAULT_MINION_OPTS,
        __role="minion",
        master=["m1.example.com", "m2.example.com"],
        master_type="failover",
    )
    seen = _run_engine_capturing_opts(engine)
    assert seen == {"master_uri": None}


def test_ensure_master_uri_waits_for_minion_keys_57952(kwargs, tmp_path):
    # On a first start the engine runs before the minion has created its key
    # pair. master_uri must only be set once both key files exist, so nothing
    # in the engine can reach AsyncAuth.get_keys while the minion is still
    # generating keys (which would leave the two with different keys).
    pki = tmp_path / "pki"
    pki.mkdir()
    key_files = [str(pki / name) for name in ("minion.pem", "minion.pub")]

    def minion_writes_keys():
        time.sleep(0.6)
        for path in key_files:
            with salt.utils.files.fopen(path, "w") as fh:
                fh.write("key\n")

    engine = salt.engines.Engine(**kwargs)
    engine.opts = {"__role": "minion", "file_client": "remote", "pki_dir": str(pki)}
    writer = threading.Thread(target=minion_writes_keys)
    writer.start()
    try:
        with patch.object(salt.engines, "MINION_KEY_WAIT_TIMEOUT", 10), patch(
            "salt.minion.resolve_dns",
            return_value={"master_uri": "tcp://1.2.3.4:4506", "master_ip": "1.2.3.4"},
        ):
            engine._ensure_master_uri()
        # Checked before joining the writer: if the engine had not waited, it
        # would have returned (with master_uri set) before the keys existed.
        keys_present_on_return = all(os.path.exists(path) for path in key_files)
    finally:
        writer.join()
    assert keys_present_on_return
    assert engine.opts["master_uri"] == "tcp://1.2.3.4:4506"


def test_ensure_master_uri_skipped_when_minion_keys_never_appear_57952(
    kwargs, tmp_path, caplog
):
    # Inverse: if the minion never creates its keys within the wait, the engine
    # must not set master_uri (so nothing in it can generate keys); it starts as
    # it did before #57952 was fixed and says why.
    pki = tmp_path / "pki"
    pki.mkdir()
    engine = salt.engines.Engine(**kwargs)
    engine.opts = {"__role": "minion", "file_client": "remote", "pki_dir": str(pki)}
    with patch.object(salt.engines, "MINION_KEY_WAIT_TIMEOUT", 0.2), patch(
        "salt.minion.resolve_dns",
        return_value={"master_uri": "tcp://1.2.3.4:4506", "master_ip": "1.2.3.4"},
    ), caplog.at_level(logging.WARNING, logger="salt.engines"):
        engine._ensure_master_uri()
    assert "master_uri" not in engine.opts
    assert "master_ip" not in engine.opts
    assert "did not appear" in caplog.text


def test_ensure_master_uri_no_key_wait_when_master_unresolvable_57952(kwargs, tmp_path):
    # The minion resolves the master before it creates its keys, so when the
    # master does not resolve there are no keys coming. The engine must give up
    # straight away instead of sitting out the key wait.
    pki = tmp_path / "pki"
    pki.mkdir()
    engine = salt.engines.Engine(**kwargs)
    engine.opts = {"__role": "minion", "file_client": "remote", "pki_dir": str(pki)}
    with patch.object(salt.engines, "MINION_KEY_WAIT_TIMEOUT", 30), patch(
        "salt.minion.resolve_dns", side_effect=Exception("unresolvable")
    ), patch.object(engine, "_wait_for_minion_keys") as wait:
        engine._ensure_master_uri()
    wait.assert_not_called()
    assert "master_uri" not in engine.opts


@pytest.mark.parametrize(
    "present,expected",
    [
        ((), False),
        (("minion.pem",), False),
        (("minion.pub",), False),
        (("minion.pem", "minion.pub"), True),
    ],
)
def test_wait_for_minion_keys_needs_both_files_57952(
    kwargs, tmp_path, present, expected
):
    # The minion writes minion.pem and then minion.pub; only both together mean
    # the pair is complete. minion.pem alone is a minion mid-write.
    pki = tmp_path / "pki"
    pki.mkdir()
    for name in present:
        with salt.utils.files.fopen(str(pki / name), "w") as fh:
            fh.write("key\n")
    engine = salt.engines.Engine(**kwargs)
    engine.opts = {"__role": "minion", "pki_dir": str(pki)}
    with patch.object(salt.engines, "MINION_KEY_WAIT_TIMEOUT", 0.2):
        assert engine._wait_for_minion_keys() is expected
