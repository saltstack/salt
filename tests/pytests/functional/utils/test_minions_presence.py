"""
Functional tests for id-based presence in
:py:meth:`salt.utils.minions.CkMinions.connected_ids`.

Issue #58592: minions that connect from an address other than the ones in
their grains (NAT, internet-facing minions, ...) are never matched by the
grains-IP comparison and therefore never show up in ``manage.present``.

When ``presence_id_tracking`` is enabled the master records a "last seen"
timestamp per authenticated minion id in the ``presence`` cache bank, and
``connected_ids`` unions the ids with a fresh record into the result.

These tests use a real on-disk cache, real accepted-key files and, for the
IP-matching path, a real listening TCP socket.
"""

import pathlib
import socket
import time

import pytest

import salt.cache
import salt.utils.minions
import salt.utils.network

pytestmark = [
    pytest.mark.windows_whitelisted,
]

PRESENCE_BANK = "presence"
TTL = 60
# RFC 5737 TEST-NET-3: never a real address of this host
NAT_GRAINS = {"ipv4": ["203.0.113.10"], "ipv6": []}


@pytest.fixture
def opts(master_opts, tmp_path):
    opts = master_opts.copy()
    pki_dir = tmp_path / "pki"
    for name in ("minions", "minions_pre", "minions_rejected", "minions_denied"):
        (pki_dir / name).mkdir(parents=True)
    opts.update(
        {
            "pki_dir": str(pki_dir),
            "cachedir": str(tmp_path / "cache"),
            "minion_data_cache": True,
            "detect_remote_minions": False,
            "presence_id_tracking": True,
            "presence_id_ttl": TTL,
            # nothing in this test touches the real publisher
            "publish_port": 1,
        }
    )
    return opts


@pytest.fixture
def cache(opts):
    return salt.cache.Cache(opts)


@pytest.fixture
def accept(opts):
    def _accept(*ids):
        for id_ in ids:
            (pathlib.Path(opts["pki_dir"]) / "minions" / id_).write_text(
                "fake-public-key"
            )

    return _accept


def _seen(cache, id_, age=0):
    cache.store(PRESENCE_BANK, id_, {"ts": time.time() - age})


def _natted(cache, id_):
    """
    Simulate a NAT'd minion: its cached grains do not contain the address the
    master sees it connecting from.
    """
    cache.store("grains", id_, NAT_GRAINS)


def test_fresh_presence_record_is_connected(opts, cache, accept):
    accept("nat-minion")
    _natted(cache, "nat-minion")
    _seen(cache, "nat-minion")
    ckminions = salt.utils.minions.CkMinions(opts)
    assert ckminions.connected_ids() == {"nat-minion"}


def test_option_off_ignores_presence_records(opts, cache, accept):
    """
    With the default configuration nothing changes: presence records are
    not consulted.
    """
    opts["presence_id_tracking"] = False
    accept("nat-minion")
    _natted(cache, "nat-minion")
    _seen(cache, "nat-minion")
    ckminions = salt.utils.minions.CkMinions(opts)
    assert ckminions.connected_ids() == set()


def test_stale_presence_record_is_not_connected(opts, cache, accept):
    accept("nat-minion")
    _natted(cache, "nat-minion")
    _seen(cache, "nat-minion", age=TTL + 30)
    ckminions = salt.utils.minions.CkMinions(opts)
    assert ckminions.connected_ids() == set()


def test_presence_record_for_unaccepted_minion_is_ignored(opts, cache, accept):
    """
    A deleted/rejected/never-accepted key must not show up as present even
    if a (still fresh) record exists for it.
    """
    accept("accepted-minion")
    _seen(cache, "accepted-minion")
    _seen(cache, "deleted-minion")
    ckminions = salt.utils.minions.CkMinions(opts)
    assert ckminions.connected_ids() == {"accepted-minion"}


def test_presence_does_not_depend_on_minion_data_cache(opts, cache, accept):
    opts["minion_data_cache"] = False
    accept("nat-minion")
    _seen(cache, "nat-minion")
    ckminions = salt.utils.minions.CkMinions(opts)
    assert ckminions.connected_ids() == {"nat-minion"}


def test_presence_respects_subset(opts, cache, accept):
    accept("minion-a", "minion-b")
    _seen(cache, "minion-a")
    _seen(cache, "minion-b")
    ckminions = salt.utils.minions.CkMinions(opts)
    assert ckminions.connected_ids(subset=["minion-b"]) == {"minion-b"}


def test_presence_show_ip_has_no_address(opts, cache, accept):
    accept("nat-minion")
    _seen(cache, "nat-minion")
    ckminions = salt.utils.minions.CkMinions(opts)
    assert dict(ckminions.connected_ids(show_ip=True)) == {"nat-minion": None}


def test_malformed_presence_record_is_ignored(opts, cache, accept):
    accept("nat-minion")
    cache.store(PRESENCE_BANK, "nat-minion", "garbage")
    ckminions = salt.utils.minions.CkMinions(opts)
    assert ckminions.connected_ids() == set()


@pytest.fixture
def listening_port():
    """
    A real listening socket with one established connection so the TCP
    table the master inspects contains a peer for it.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    client = socket.create_connection(server.getsockname())
    conn, _ = server.accept()
    try:
        yield server.getsockname()[1]
    finally:
        conn.close()
        client.close()
        server.close()


def test_ip_match_still_works_and_is_not_duplicated(
    opts, cache, accept, listening_port
):
    """
    The grains-IP path is unchanged, and a minion found by both paths is
    reported once, with its address.
    """
    addrs = salt.utils.network.ip_addrs(include_loopback=False)
    if not addrs:
        pytest.skip("No non-loopback address available to match against")
    local_ip = addrs[0]
    opts["publish_port"] = listening_port
    accept("lan-minion")
    cache.store("grains", "lan-minion", {"ipv4": [local_ip], "ipv6": []})
    _seen(cache, "lan-minion")
    ckminions = salt.utils.minions.CkMinions(opts)
    assert ckminions.connected_ids() == {"lan-minion"}
    assert dict(ckminions.connected_ids(show_ip=True)) == {"lan-minion": local_ip}
