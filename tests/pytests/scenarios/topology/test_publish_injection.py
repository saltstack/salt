"""
End-to-end integration regression for the master-topology
publish-injection chain.

The attack
----------

An adversary with network reach to ``topology_link_port`` plus knowledge
of any one accepted peer's ``cluster_id`` (an identity string present
on every peer handshake and routinely logged) can inject an arbitrary
``topology/pub`` frame that this master will dispatch to its own local
minions.

The wire chain is:

1. msgpack envelope ``{"enc": "clear", "load": <inner>, "version": 0}``
   reaches :meth:`salt.channel.server.ReqServerChannel.handle_message`;
2. the version gate in ``handle_message`` is bypassed because the
   topology listener overrides ``minimum_auth_version`` to ``0``
   (:mod:`salt.topology.link_manager` ``_open_inbound_listener``);
3. :func:`salt.topology.link_manager._handle_inbound` runs
   :func:`_maybe_lazy_register_inbound`, which writes
   ``_INBOUND[origin]`` from the frame's self-reported
   ``session_generation`` with ``session_aes=None``;
4. :func:`_verify_session` then compares the frame's gen against the
   record it just created and returns True;
5. :func:`_dispatch_pub` consults the router and, on a local match,
   calls :func:`_publish_to_local_minions` -- running the attacker's
   function on this master's minions.

What this test covers that the sibling unit/functional tests do not
--------------------------------------------------------------------

The sibling tests in
``tests/pytests/unit/topology/test_link_manager.py`` and
``tests/pytests/functional/topology/test_link_manager.py`` pin the
invariant at :func:`_handle_inbound` and at its helpers (``_verify_session``
+ ``_maybe_lazy_register_inbound``) directly, which is sufficient to
guard the session-forgery leg of the chain.  This scenario goes one
layer up and exercises the real wire envelope, so a fix that moves
the check into :meth:`ReqServerChannel.handle_message` (e.g. a
tag-scoped ``minimum_auth_version`` carve-out or a tag-scoped
authentication envelope) also satisfies this guard --- and a fix at
``_handle_inbound`` alone that regresses the ``minimum_auth_version=0``
override still gets caught here.
"""

import asyncio
import logging
import pathlib

import pytest

import salt.channel.server
import salt.config
import salt.crypt
import salt.master
import salt.payload
import salt.topology.link_manager as link_manager
import salt.topology.router as router_mod
import salt.utils.stringutils

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
    # Builds a real ReqServerChannel + MasterKeys + Crypticle under the
    # test body; FIPS CI shards need headroom over the 90s project
    # default (RSA 4096 generation + cluster-peer ready gate).
    pytest.mark.timeout(300),
]


log = logging.getLogger(__name__)


def _make_master_opts(tmp_path, topology_link_port):
    """
    Minimal but real master opts sufficient to construct a
    :class:`salt.channel.server.ReqServerChannel` that answers
    ``handle_message`` without a bound ZMQ socket.

    ``ReqServerChannel.__init__`` reads ``sock_dir``, ``cachedir``,
    ``pki_dir``, ``keys.cache_driver`` and instantiates
    :class:`salt.crypt.MasterKeys` (which writes ``master.pem`` /
    ``master.pub`` on first construction).  Mirrors the opts transform
    :func:`salt.topology.link_manager._open_inbound_listener` applies
    to produce the listener channel the attacker's frame actually hits
    in production.
    """
    opts = salt.config.DEFAULT_MASTER_OPTS.copy()

    pki = tmp_path / "pki"
    (pki / "master").mkdir(parents=True, exist_ok=True)
    for sub in ("masters", "masters_pre", "masters_rejected", "masters_denied"):
        (pki / sub).mkdir(parents=True, exist_ok=True)
    (pki / "minions").mkdir(exist_ok=True)
    cachedir = tmp_path / "cache"
    cachedir.mkdir(exist_ok=True)
    sockdir = tmp_path / "sock"
    sockdir.mkdir(exist_ok=True)

    opts.update(
        {
            "interface": "127.0.0.1",
            "pki_dir": str(pki),
            "cluster_pki_dir": str(pki),
            "cachedir": str(cachedir),
            "sock_dir": str(sockdir),
            "id": "topology-victim",
            "__role": "master",
            "transport": "zeromq",
            "ret_port": 44506,
            "master_uri": "tcp://127.0.0.1:44506",
            "topology_enabled": True,
            "topology_link_port": topology_link_port,
            "topology_peers": [],
            "topology_registry_cache_size": 512,
            "topology_registry_cache_key_size": 64,
            "topology_breadcrumb_cache_size": 1024,
            "topology_breadcrumb_cache_key_size": 64,
            "topology_breadcrumb_grace": 2,
            "topology_breadcrumb_max_age": 60,
            "topology_detach_quiesce": 0,
            "cluster_id": "self",
            # Opts that _open_inbound_listener applies when building the
            # topology channel.  Mirrored here so the test exercises the
            # exact channel configuration the attacker's frame hits.
            "minimum_auth_version": 0,
            "cluster_peers": [],
            "worker_pools_enabled": False,
        }
    )
    return opts


@pytest.fixture
def _reset_master_secrets():
    """
    :class:`salt.channel.server.ReqServerChannel.__init__` consults
    :data:`salt.master.SMaster.secrets["aes"]`.  Seed it for the test
    and restore on teardown so a left-over key never bleeds into a
    sibling test's master.
    """
    import ctypes
    import multiprocessing

    had_before = "aes" in salt.master.SMaster.secrets
    if not had_before:
        salt.master.SMaster.secrets["aes"] = {
            "secret": multiprocessing.Array(
                ctypes.c_char,
                salt.utils.stringutils.to_bytes(
                    salt.crypt.Crypticle.generate_key_string()
                ),
            ),
            "serial": multiprocessing.Value(ctypes.c_longlong, lock=False),
        }
    yield
    if not had_before:
        salt.master.SMaster.secrets.pop("aes", None)


@pytest.fixture
def clean_link_manager(monkeypatch):
    link_manager._reset_module_state()  # pylint: disable=protected-access
    monkeypatch.setattr(router_mod, "_ROUTER", None)
    yield
    try:
        asyncio.new_event_loop().run_until_complete(link_manager.stop())
    except Exception:  # pylint: disable=broad-except
        pass
    link_manager._reset_module_state()  # pylint: disable=protected-access


class _CapturingRouter:
    """
    Router stub that would unconditionally request a local publish on
    ``forward_publish``.  The test's assertion target is that this
    router is never consulted and -- as a stronger guard --
    :func:`_publish_to_local_minions` is never invoked.
    """

    def __init__(self):
        self.forward_publish_calls = []

    def forward_publish(self, load, inbound_link):
        self.forward_publish_calls.append((load, inbound_link))
        return [], True  # (links, local_match=True)


def test_wire_envelope_forged_pub_blocked(
    tmp_path, _reset_master_secrets, clean_link_manager, monkeypatch, caplog
):
    """
    A version=0 cleartext msgpack envelope sent over the wire to the
    topology listener must not reach :func:`_publish_to_local_minions`.

    This is the integration-level sibling of the unit tests in
    ``tests/pytests/unit/topology/test_link_manager.py``
    (``test_handle_inbound_rejects_forged_pub_*``) and the functional
    tests in ``tests/pytests/functional/topology/test_link_manager.py``
    (``test_handle_inbound_forged_pub_*``).  The three layers cover the
    same end invariant at descending slices of the stack: unit tests
    pin the helpers, functional tests pin the dispatcher, this test
    pins the full channel ``handle_message`` path --- i.e. what the
    real ZMQ layer calls after msgpack decoding the envelope.
    """
    # Pick a free port for the topology listener opt -- we never bind
    # it (ReqServerChannel.__init__ takes just the opts dict; the
    # bind happens in ``post_fork`` which we deliberately skip so the
    # test drives ``handle_message`` directly).
    import socket as _socket

    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        topology_link_port = sock.getsockname()[1]

    opts = _make_master_opts(tmp_path, topology_link_port)

    # Spy on the final sink.  Must be installed BEFORE
    # ``link_manager.start`` so the module-level ref the dispatcher
    # resolves against is the spy.
    local_calls = []

    async def _spy_publish(load, matched=None):
        local_calls.append(load)

    monkeypatch.setattr(link_manager, "_publish_to_local_minions", _spy_publish)

    loop = asyncio.new_event_loop()
    channel = None
    try:
        # Bring up the real link_manager module (router + dispatch table
        # + _OPTS wired).  The listener bind may fail in this reduced
        # test opts -- that is OK; we drive ``handle_message`` directly
        # on a channel object constructed below.
        loop.run_until_complete(link_manager.start(opts, loop))
        monkeypatch.setattr(router_mod, "_ROUTER", _CapturingRouter())

        # Pre-stage the attacker's precondition: ``masters/east.pub``
        # on disk.  No in-process ``_INBOUND[east]`` -- the frame
        # itself must not be sufficient to establish one.
        accepted = pathlib.Path(opts["pki_dir"]) / "masters" / "east.pub"
        accepted.parent.mkdir(parents=True, exist_ok=True)
        accepted.write_bytes(
            b"-----BEGIN PUBLIC KEY-----\nstub\n-----END PUBLIC KEY-----\n"
        )
        assert (
            "east" not in link_manager._INBOUND  # pylint: disable=protected-access
        ), "test precondition: no prior inbound session for east"

        # Build the real ReqServerChannel using the exact opts transform
        # :func:`_open_inbound_listener` applies.  Skip ``post_fork`` so
        # no socket is bound; ``handle_message`` is callable on the
        # channel object directly.
        channel_opts = dict(opts)
        channel_opts["ret_port"] = opts["topology_link_port"]
        channel = salt.channel.server.ReqServerChannel.factory(channel_opts)
        channel.payload_handler = (
            link_manager._handle_inbound_channel  # pylint: disable=protected-access
        )

        # Construct the exact wire-level envelope an attacker would
        # emit: version=0 cleartext, no AES, forged origin.
        forged_inner = {
            "tag": "topology/pub",
            "origin_cluster_id": "east",
            "session_generation": 424242,  # attacker-chosen
            "load": {
                "jid": "20260101000000000000",
                "tgt": "C@self and *",
                "tgt_type": "compound",
                "fun": "cmd.run",
                "arg": ["id"],
            },
        }
        envelope = {"enc": "clear", "load": forged_inner, "version": 0}

        # Sanity: the envelope must survive the salt.payload msgpack
        # round-trip so the test's envelope matches what the ZMQ layer
        # would deserialize from an attacker's byte stream.
        roundtripped = salt.payload.loads(salt.payload.dumps(envelope))
        assert roundtripped == envelope

        with caplog.at_level(logging.WARNING):
            reply = loop.run_until_complete(channel.handle_message(envelope))

        # Any of three post-fix behaviours satisfies the invariant:
        #   * ``"bad load"``  -- rejected at the version gate
        #     (``minimum_auth_version`` raised back to >= 3 or scoped
        #     out for non-handshake tags)
        #   * ``({}, {"fun": "send_clear"})`` -- dropped at
        #     ``_handle_inbound_channel`` after ``_verify_session`` fails
        #   * some other serializable "dropped" reply shape
        # The chain-failure invariant is the same for all three: the
        # local-publish sink must not have been reached.
        assert local_calls == [], (
            "Full wire-path publish injection succeeded: "
            f"_publish_to_local_minions invoked with {local_calls!r}; "
            f"handle_message reply was {reply!r}"
        )
    finally:
        try:
            if channel is not None:
                channel.close()
        except Exception:  # pylint: disable=broad-except
            pass
        try:
            loop.run_until_complete(link_manager.stop())
        except Exception:  # pylint: disable=broad-except
            pass
        loop.close()


def test_wire_envelope_forged_pub_does_not_pollute_inbound(
    tmp_path, _reset_master_secrets, clean_link_manager, monkeypatch
):
    """
    Side-effect integration: a single wire-level forged frame must not
    leave ``_INBOUND[east]`` populated with the attacker-chosen
    ``session_generation``.  Pre-fix the lazy-register runs before
    ``_verify_session`` and writes the attacker's gen -- subsequent
    replays and legitimate peer collisions then see a poisoned record.
    """
    import socket as _socket

    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        topology_link_port = sock.getsockname()[1]

    opts = _make_master_opts(tmp_path, topology_link_port)

    loop = asyncio.new_event_loop()
    channel = None
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        monkeypatch.setattr(router_mod, "_ROUTER", _CapturingRouter())

        accepted = pathlib.Path(opts["pki_dir"]) / "masters" / "east.pub"
        accepted.parent.mkdir(parents=True, exist_ok=True)
        accepted.write_bytes(
            b"-----BEGIN PUBLIC KEY-----\nstub\n-----END PUBLIC KEY-----\n"
        )

        channel_opts = dict(opts)
        channel_opts["ret_port"] = opts["topology_link_port"]
        channel = salt.channel.server.ReqServerChannel.factory(channel_opts)
        channel.payload_handler = (
            link_manager._handle_inbound_channel  # pylint: disable=protected-access
        )

        forged = {
            "tag": "topology/pub",
            "origin_cluster_id": "east",
            "session_generation": 919191,
            "load": {"jid": "20260101000000000001"},
        }
        loop.run_until_complete(
            channel.handle_message({"enc": "clear", "load": forged, "version": 0})
        )
        inbound = link_manager._INBOUND.get("east")  # pylint: disable=protected-access
        if inbound is not None:
            assert getattr(inbound, "session_generation", None) != 919191, (
                "wire-level forged frame installed attacker-chosen "
                "session_generation in _INBOUND -- subsequent replays "
                "with the same gen would pass _verify_session"
            )
    finally:
        try:
            if channel is not None:
                channel.close()
        except Exception:  # pylint: disable=broad-except
            pass
        try:
            loop.run_until_complete(link_manager.stop())
        except Exception:  # pylint: disable=broad-except
            pass
        loop.close()
