"""
Functional tests for cluster AES key rotation under
``cluster_isolated_filesystem: True``.

Regression guard for saltstack/salt#70543: when the rotating master was the
only one that touched ``cluster_pki_dir/.aes`` (isolated filesystems), peers
received the ``rotate_cluster_aes_key`` event but reloaded their own
unchanged local file, leaving every peer with the OLD key.  The fix carries
the new key encrypted per-peer in the event payload so receivers write it to
their own ``.aes`` before reloading.
"""

import asyncio
import ctypes
import hashlib
import multiprocessing
import os
import pathlib
import shutil
import time

import pytest

import salt.crypt
import salt.master
import salt.utils.event
import salt.utils.files
import salt.utils.stringutils
from tests.support.mock import MagicMock, patch

# The rotation protocol uses the OAEP-SHA1/PKCS1v15-SHA1 defaults.  FIPS
# platforms reject SHA1, so skip until the cluster code negotiates a FIPS-safe
# algorithm (same reason test_join_crypto skips).
pytestmark = [pytest.mark.skip_on_fips_enabled_platform]


@pytest.fixture
def isolated_cluster(master_opts, tmp_path):
    """
    Three independent master layouts.  Each has its own ``pki_dir``,
    ``cluster_pki_dir``, and ``cachedir`` — no shared paths.  Peer pub keys
    are copied into each master's ``cluster_pki_dir/peers/<id>.pub`` as the
    join handshake would have done.
    """
    masters = {}
    for mid in ("m1", "m2", "m3"):
        root = tmp_path / mid
        pki = root / "pki"
        cluster_pki = root / "cluster_pki"
        peers = cluster_pki / "peers"
        cache = root / "cache"
        for d in (pki, cluster_pki, peers, cache):
            d.mkdir(parents=True, exist_ok=True)
        opts = master_opts.copy()
        opts["id"] = mid
        opts["pki_dir"] = str(pki)
        opts["cluster_id"] = "test_cluster"
        opts["cluster_pki_dir"] = str(cluster_pki)
        opts["cluster_peers"] = [m for m in ("m1", "m2", "m3") if m != mid]
        opts["cluster_isolated_filesystem"] = True
        opts["cluster_encryption_algorithm"] = "OAEP-SHA1"
        opts["cluster_key_pass"] = None
        opts["cluster_secret"] = None
        opts["key_pass"] = None
        opts["cachedir"] = str(cache)
        opts["sock_dir"] = str(cache)
        masters[mid] = opts
        salt.crypt.write_keys(pki, "master", 2048)

    # Distribute peer pubs.
    for mid, opts in masters.items():
        for peer_id, peer_opts in masters.items():
            if peer_id == mid:
                continue
            src = pathlib.Path(peer_opts["pki_dir"]) / "master.pub"
            dst = pathlib.Path(opts["cluster_pki_dir"]) / "peers" / f"{peer_id}.pub"
            shutil.copyfile(src, dst)
            os.chmod(dst, 0o400)

    # Seed identical cluster_aes to all three (as if the join-reply happened).
    shared = salt.crypt.Crypticle.generate_key_string()
    for opts in masters.values():
        aes_path = pathlib.Path(opts["cluster_pki_dir"]) / ".aes"
        with salt.utils.files.set_umask(0o177):
            aes_path.write_text(shared, encoding="utf-8")
    return masters


def _aes_hash(opts):
    return hashlib.sha256(
        (pathlib.Path(opts["cluster_pki_dir"]) / ".aes").read_bytes()
    ).hexdigest()


def _install_owner_secrets(opts):
    """Populate ``SMaster.secrets['cluster_aes']`` from this master's view."""

    def reload(remove=False):
        path = os.path.join(opts["cluster_pki_dir"], ".aes")
        if remove:
            os.remove(path)
        key = salt.crypt.Crypticle.read_key(path)
        if key:
            return key
        salt.crypt.Crypticle.write_key(path)
        time.sleep(0.05)
        return salt.crypt.Crypticle.read_key(path)

    salt.master.SMaster.secrets["cluster_aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(reload()),
        ),
        "serial": multiprocessing.Value(ctypes.c_longlong, lock=False),
        "reload": reload,
    }


class _CaptureEvent:
    """Minimal event stand-in that captures the fired payload."""

    def __init__(self):
        self.events = []

    def fire_event(self, data, tag=None):
        self.events.append((tag, data))


class _FakeMonitor:
    """Instance with just enough state for EventMonitor's private helpers."""

    def __init__(self, opts):
        self.opts = opts


def test_rotation_propagates_to_isolated_peers(isolated_cluster):
    """
    When the owner rotates the cluster AES key under
    ``cluster_isolated_filesystem: True``, peers must install the new key on
    their local ``.aes`` after receiving the ``rotate_cluster_aes_key`` event.
    """
    m1 = isolated_cluster["m1"]
    _install_owner_secrets(m1)

    pre = {mid: _aes_hash(opts) for mid, opts in isolated_cluster.items()}
    assert len(set(pre.values())) == 1, "seed should be identical"

    event = _CaptureEvent()
    salt.master.SMaster.rotate_cluster_secret(m1, event=event, owner=True)

    assert len(event.events) == 1
    tag, payload = event.events[0]
    assert tag == "rotate_cluster_aes_key"
    assert payload["rotate_cluster_aes_key"] is True
    assert set(payload["peers"].keys()) == {"m2", "m3"}

    for mid in ("m2", "m3"):
        monitor = _FakeMonitor(isolated_cluster[mid])
        salt.master.EventMonitor._install_rotated_cluster_aes(monitor, payload)

    post = {mid: _aes_hash(opts) for mid, opts in isolated_cluster.items()}
    assert (
        len(set(post.values())) == 1
    ), f"peers did not converge after rotation: {post}"
    assert post["m1"] != pre["m1"], "owner should have a new key"


def test_rotation_payload_missing_peers_is_tolerated(isolated_cluster):
    """
    Backwards-compat guard: a receiver on the new code must not crash when a
    rotating peer sends a legacy payload without a ``peers`` key (e.g. during
    a rolling upgrade).  Behaviour matches the historical reload-only path.
    """
    monitor = _FakeMonitor(isolated_cluster["m2"])
    # Must not raise.
    salt.master.EventMonitor._install_rotated_cluster_aes(
        monitor, {"rotate_cluster_aes_key": True}
    )


def test_rotation_payload_missing_self_entry_is_tolerated(isolated_cluster):
    """
    A payload that carries ``peers`` but omits this receiver's own entry (bad
    rotator misconfig) must log and skip, not crash.
    """
    monitor = _FakeMonitor(isolated_cluster["m2"])
    salt.master.EventMonitor._install_rotated_cluster_aes(
        monitor,
        {"rotate_cluster_aes_key": True, "peers": {"m3": b"not-for-me"}},
    )


def test_rotate_peer_payload_skips_missing_peer_pubs(isolated_cluster, caplog):
    """
    ``_build_rotate_peer_payload`` must not raise when a peer's pub key is
    missing from ``cluster_pki_dir/peers`` — it logs and skips so a quorum of
    peers can still rotate.
    """
    import logging

    m1 = isolated_cluster["m1"]
    _install_owner_secrets(m1)

    # Delete m3's pub from m1's view.
    (pathlib.Path(m1["cluster_pki_dir"]) / "peers" / "m3.pub").unlink()

    with caplog.at_level(logging.WARNING, logger="salt.master"):
        payload = salt.master.SMaster._build_rotate_peer_payload(m1)

    assert set(payload.keys()) == {"m2"}
    assert any(
        "peer pub key" in record.message and "m3.pub" in record.message
        for record in caplog.records
    )


def test_handle_event_rotate_tag_installs_new_key(isolated_cluster):
    """
    Guards the ``EventMonitor.handle_event`` dispatch wiring: a received
    ``rotate_cluster_aes_key`` event must flow through
    ``_install_rotated_cluster_aes`` AND trigger the local reload via
    ``SMaster.rotate_cluster_secret(owner=False)``.

    Issue #70543 is primarily about the payload shape, but the dispatcher
    is the single-point-of-failure that routes the payload to the
    installer -- a future refactor that drops either call without
    updating the other will silently reintroduce the split-brain this
    PR fixes.
    """
    m1 = isolated_cluster["m1"]
    _install_owner_secrets(m1)

    # Owner builds a real payload to feed into the dispatcher so the
    # test exercises the actual ciphertext shape the receiver sees.
    event = _CaptureEvent()
    salt.master.SMaster.rotate_cluster_secret(m1, event=event, owner=True)
    _, payload = event.events[0]
    payload["__peer_id"] = "m1"

    m2 = isolated_cluster["m2"]
    monitor = salt.master.EventMonitor(m2, ipc_publisher=MagicMock())
    package = salt.utils.event.SaltEvent.pack("rotate_cluster_aes_key", payload)

    install_calls = []
    reload_calls = []
    original_install = salt.master.EventMonitor._install_rotated_cluster_aes

    def spy_install(self, data):
        install_calls.append(dict(data))
        return original_install(self, data)

    def spy_rotate(opts, owner=False, publisher=None, **_kwargs):
        reload_calls.append({"id": opts["id"], "owner": owner})

    with patch.object(
        salt.master.EventMonitor,
        "_install_rotated_cluster_aes",
        spy_install,
    ), patch.object(
        salt.master.SMaster, "rotate_cluster_secret", staticmethod(spy_rotate)
    ):
        asyncio.run(monitor.handle_event(package))

    assert (
        len(install_calls) == 1
    ), "handle_event must call _install_rotated_cluster_aes"
    assert install_calls[0]["rotate_cluster_aes_key"] is True
    assert "peers" in install_calls[0], "dispatcher must pass through the peers payload"
    assert reload_calls == [
        {"id": "m2", "owner": False}
    ], "handle_event must call rotate_cluster_secret with owner=False after install"
    # Receiver's local .aes should now match the new owner key.
    post_m2 = _aes_hash(m2)
    post_m1 = _aes_hash(m1)
    assert post_m2 == post_m1


def test_handle_event_rotate_tag_requires_peer_id(isolated_cluster):
    """
    The dispatcher must guard on ``__peer_id`` -- a locally-fired event
    (no cluster peer attribution) must NOT trigger an install, otherwise
    a stray local event bus message would rewrite the local ``.aes``.
    """
    m2 = isolated_cluster["m2"]
    monitor = salt.master.EventMonitor(m2, ipc_publisher=MagicMock())

    # Payload with NO __peer_id.
    payload = {"rotate_cluster_aes_key": True, "peers": {"m2": b"garbage"}}
    package = salt.utils.event.SaltEvent.pack("rotate_cluster_aes_key", payload)

    install_calls = []

    def spy_install(self, data):
        install_calls.append(data)

    with patch.object(
        salt.master.EventMonitor,
        "_install_rotated_cluster_aes",
        spy_install,
    ), patch.object(
        salt.master.SMaster, "rotate_cluster_secret", staticmethod(lambda *a, **k: None)
    ):
        asyncio.run(monitor.handle_event(package))

    assert install_calls == [], (
        "handle_event must ignore rotate_cluster_aes_key events that lack a "
        "__peer_id attribution"
    )


def test_multiple_independent_rotators_still_converge(isolated_cluster):
    """
    Reporter noted (secondary observation on #70543) that each master
    has its own private ``cachedir/.dfn`` under
    ``cluster_isolated_filesystem: True``, so two masters can each
    independently decide to rotate on their own schedule.

    This test drives TWO successive rotations initiated from different
    masters (m1 then m2) and verifies the cluster still converges to a
    single AES key after each rotation.  A permanent split would be the
    #70543 symptom; this test asserts the fix survives the
    independent-rotator case the reporter observed in production.
    """
    seed = _aes_hash(isolated_cluster["m1"])

    # Rotation #1: owner is m1.
    _install_owner_secrets(isolated_cluster["m1"])
    event = _CaptureEvent()
    salt.master.SMaster.rotate_cluster_secret(
        isolated_cluster["m1"], event=event, owner=True
    )
    _, payload = event.events[0]
    for mid in ("m2", "m3"):
        monitor = _FakeMonitor(isolated_cluster[mid])
        salt.master.EventMonitor._install_rotated_cluster_aes(monitor, payload)
    after_first = {mid: _aes_hash(opts) for mid, opts in isolated_cluster.items()}
    assert len(set(after_first.values())) == 1
    assert after_first["m1"] != seed

    # Clear ``SMaster.secrets`` so the next owner's ``rotate_cluster_secret``
    # populates its own view (mirrors a fresh master process picking up the
    # file after a restart).  Then rotate from m2.
    salt.master.SMaster.secrets.pop("cluster_aes", None)
    _install_owner_secrets(isolated_cluster["m2"])
    event = _CaptureEvent()
    salt.master.SMaster.rotate_cluster_secret(
        isolated_cluster["m2"], event=event, owner=True
    )
    _, payload = event.events[0]
    assert set(payload["peers"].keys()) == {"m1", "m3"}
    for mid in ("m1", "m3"):
        monitor = _FakeMonitor(isolated_cluster[mid])
        salt.master.EventMonitor._install_rotated_cluster_aes(monitor, payload)
    after_second = {mid: _aes_hash(opts) for mid, opts in isolated_cluster.items()}
    assert (
        len(set(after_second.values())) == 1
    ), f"independent rotator from m2 left the cluster split: {after_second}"
    assert (
        after_second["m1"] != after_first["m1"]
    ), "second rotation should advance the key"


def test_handle_key_rotate_removes_publish_session_dropfile(
    isolated_cluster, monkeypatch, tmp_path
):
    """
    Regression for the secondary bug in #70543: the ``publish_session`` branch
    of ``Maintenance.handle_key_rotate`` created ``.dfn`` to pick a leader but
    never removed it on success, so the first branch of the next maintenance
    tick saw the stale dropfile and rotated AGAIN (double rotation).
    """
    m1 = isolated_cluster["m1"].copy()
    m1["publish_session"] = 1
    m1["user"] = None

    # Age the .aes past publish_session so the branch triggers.
    aes_path = pathlib.Path(m1["cluster_pki_dir"]) / ".aes"
    old = time.time() - 3600
    os.utime(aes_path, (old, old))

    # Stub the SMaster rotate call: this test only cares about dfn hygiene.
    rotated = {"count": 0}

    def fake_rotate(*args, **kwargs):
        rotated["count"] += 1

    monkeypatch.setattr(
        salt.master.SMaster, "rotate_cluster_secret", staticmethod(fake_rotate)
    )

    # Instantiate the Maintenance class without running __init__ (avoids all
    # the heavy sub-process plumbing); just set the attributes we use.
    maint = salt.master.Maintenance.__new__(salt.master.Maintenance)
    maint.opts = m1
    maint.event = None
    maint.ipc_publisher = None

    maint.handle_key_rotate(int(time.time()), drop_file_wait=0)

    assert rotated["count"] == 1
    dfn = pathlib.Path(m1["cachedir"]) / ".dfn"
    assert (
        not dfn.exists()
    ), f".dfn should be removed after rotation; left behind at {dfn}"
