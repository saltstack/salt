"""
Functional tests for the cryptographic primitives the cluster peer
join / discover protocol relies on.

The join handshake in :mod:`salt.channel.server` boils down to::

    # peer B wants to join peer A's cluster
    token  = A.gen_token()                                # random 32 chars
    blob   = A.pub.encrypt(token.encode() + cluster_secret.encode())
    aesblob = A.pub.encrypt(token.encode() + aes_key)
    sig    = B.master_key.sign(packed_payload)

    # peer A receives, decrypts with its own master_rsa, strips token,
    # verifies signature with B's master_pub.

These tests exercise that round-trip against real on-disk keys produced
by :class:`salt.crypt.MasterKeys` so we know the join path stays wired
up correctly when primitive implementations (algorithms, paddings)
change.
"""

import random
import string

import pytest

import salt.crypt
import salt.payload

# The cluster join protocol uses the default RSA OAEP/PKCS1v15 SHA1 algorithms.
# On FIPS-enabled platforms, salt.crypt._enforce_fips rejects SHA1, so these
# tests cannot exercise the protocol until salt/channel/server.py negotiates a
# FIPS-safe algorithm (e.g. OAEP-SHA224 / PKCS1v15-SHA256) for cluster joins.
pytestmark = [pytest.mark.skip_on_fips_enabled_platform]


@pytest.fixture
def cluster_pki_dir(tmp_path):
    path = tmp_path / "cluster_pki"
    path.mkdir()
    (path / "peers").mkdir()
    return path


def _cluster_opts(master_opts, pki_dir, master_id, cluster_pki_dir):
    opts = master_opts.copy()
    opts["id"] = master_id
    opts["pki_dir"] = str(pki_dir)
    opts["cluster_id"] = "master_cluster"
    opts["cluster_pki_dir"] = str(cluster_pki_dir)
    opts["cluster_peers"] = []
    opts["cluster_key_pass"] = None
    opts["cluster_secret"] = None
    opts["key_pass"] = None
    opts["master_sign_pubkey"] = False
    return opts


def _gen_token():
    return "".join(random.choices(string.ascii_letters + string.digits, k=32))


def _build_peer(master_opts, tmp_path, cluster_pki_dir, master_id):
    pki_dir = tmp_path / master_id
    pki_dir.mkdir()
    opts = _cluster_opts(master_opts, pki_dir, master_id, cluster_pki_dir)
    keys = salt.crypt.MasterKeys(opts)
    return opts, keys


def test_join_secret_round_trip(master_opts, tmp_path, cluster_pki_dir):
    """
    Peer B can encrypt ``token + cluster_secret`` under peer A's public
    key, and peer A decrypts with its own private key and recovers the
    original bytes.
    """
    _, keys_a = _build_peer(master_opts, tmp_path, cluster_pki_dir, "127.0.0.1")

    token = _gen_token()
    cluster_secret = "super-secret-cluster-password"

    peer_a_pub_path = cluster_pki_dir / "peers" / "127.0.0.1.pub"
    peer_a_pub = salt.crypt.PublicKey.from_file(peer_a_pub_path)

    blob = peer_a_pub.encrypt(token.encode() + cluster_secret.encode())

    recovered = (
        salt.crypt.PrivateKey.from_file(keys_a.master_rsa_path).decrypt(blob).decode()
    )

    assert recovered.startswith(token)
    assert recovered[len(token) :] == cluster_secret


def test_join_aes_key_round_trip(master_opts, tmp_path, cluster_pki_dir):
    """
    The shared AES session key is handed off the same way the secret
    is: ``token + aes_key`` encrypted under the target peer's pub.
    Peer A recovering the AES blob must get the original bytes back
    exactly, with no text decoding in the middle -- the AES key is raw
    binary.
    """
    _, keys_a = _build_peer(master_opts, tmp_path, cluster_pki_dir, "127.0.0.1")

    token = _gen_token()
    aes_key = salt.crypt.Crypticle.generate_key_string().encode()

    peer_a_pub = salt.crypt.PublicKey.from_file(
        cluster_pki_dir / "peers" / "127.0.0.1.pub"
    )

    blob = peer_a_pub.encrypt(token.encode() + aes_key)

    recovered = salt.crypt.PrivateKey.from_file(keys_a.master_rsa_path).decrypt(blob)

    assert recovered.startswith(token.encode())
    assert recovered[len(token) :] == aes_key


def test_join_signature_verifies_across_peers(master_opts, tmp_path, cluster_pki_dir):
    """
    Peer B signs the packed join payload with its own master private
    key. Peer A verifies the signature using peer B's pub key from the
    shared ``peers/`` directory.
    """
    _, keys_b = _build_peer(master_opts, tmp_path, cluster_pki_dir, "127.0.0.2")
    _build_peer(master_opts, tmp_path, cluster_pki_dir, "127.0.0.1")

    payload = salt.payload.package(
        {
            "peer_id": "127.0.0.2",
            "token": _gen_token(),
            "pub": (cluster_pki_dir / "peers" / "127.0.0.2.pub").read_text(
                encoding="utf-8"
            ),
        }
    )
    sig = salt.crypt.PrivateKey.from_file(keys_b.master_rsa_path).sign(payload)

    peer_b_pub = salt.crypt.PublicKey.from_file(
        cluster_pki_dir / "peers" / "127.0.0.2.pub"
    )
    assert peer_b_pub.verify(payload, sig) is True


def test_join_signature_rejects_tampered_payload(
    master_opts, tmp_path, cluster_pki_dir
):
    """
    Any modification of the signed payload between peers must be
    detected -- otherwise an attacker could replace the pub key inside
    a legitimate join frame.
    """
    _, keys_b = _build_peer(master_opts, tmp_path, cluster_pki_dir, "127.0.0.2")

    payload = salt.payload.package({"peer_id": "127.0.0.2", "token": "abc"})
    sig = salt.crypt.PrivateKey.from_file(keys_b.master_rsa_path).sign(payload)

    tampered = payload + b"\x00"
    peer_b_pub = salt.crypt.PublicKey.from_file(
        cluster_pki_dir / "peers" / "127.0.0.2.pub"
    )
    assert peer_b_pub.verify(tampered, sig) is False


def test_join_signature_rejects_wrong_signer(master_opts, tmp_path, cluster_pki_dir):
    """
    A payload signed by peer C must NOT verify when the receiver looks
    up the claimed sender (peer B) in ``peers/`` -- the join handshake
    leans on this so an authorised peer cannot impersonate another.
    """
    _build_peer(master_opts, tmp_path, cluster_pki_dir, "127.0.0.2")
    _, keys_c = _build_peer(master_opts, tmp_path, cluster_pki_dir, "127.0.0.3")

    payload = salt.payload.package({"peer_id": "127.0.0.2", "token": "abc"})
    sig = salt.crypt.PrivateKey.from_file(keys_c.master_rsa_path).sign(payload)

    peer_b_pub = salt.crypt.PublicKey.from_file(
        cluster_pki_dir / "peers" / "127.0.0.2.pub"
    )
    assert peer_b_pub.verify(payload, sig) is False
