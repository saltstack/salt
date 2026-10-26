"""
Full-CLI end-to-end scenario for the master-topology feature.

Prior scenarios under ``tests/pytests/scenarios/topology`` fake the
:class:`salt.channel.client.AsyncReqChannel` at the link layer
because the shared harness's placeholder ``master_identity.pub``
could not pass real ``topology/_master_auth`` crypto.  The real-CLI
scenario here closes that gap:

* :meth:`tests.support.topology.cluster.TopologyCluster.ensure_identity_key`
  generates a real :class:`salt.crypt.MasterIdentityKey` keypair on
  disk (``<pki_dir>/master/master_identity.{pub,pem}``).
* :meth:`tests.support.topology.cluster.TopologyCluster.accept_peer`
  copies that real pub into the peer's
  ``<pki_dir>/masters/<cluster_id>.pub`` --- same byte-shape
  ``salt-key -a <cluster_id> --master`` would write in production.
* The real ``salt`` CLI drives the publish via the running east
  master process, which exercises:

  * :meth:`salt.master.ClearFuncs.publish` ->
    :meth:`salt.utils.minions.CkMinions.check_minions`
  * :meth:`salt.channel.server.MasterPubServerChannel.publish_payload`
    -> :func:`salt.topology.router.on_publish`
  * east's local return path from the attached minion

Phase-5 gaps surfaced while writing this scenario, held back as
RFC follow-ups:

* :meth:`salt.master.ClearFuncs.publish` short-circuits with
  ``Master could not resolve minions for target`` when the local
  compound match is empty, before ``_send_pub`` reaches
  :func:`salt.topology.router.on_publish`.  Blocks a
  ``-C 'C@west'`` publish on east because east is not west and
  the local compound returns zero minions.
* :func:`salt.topology.link_manager._dispatch_pub` returns
  ``forward_publish``'s ``(links, local_match)`` without hooking
  the local-match side into the receiving master's publish
  pipeline, so west never actually publishes to its own minions
  even if the forwarded publish arrives.
* The master-side :meth:`salt.utils.minions.CkMinions._check_cluster_minions`
  reads ``opts["cluster_id"]``, which can only be set on a
  3008.x master cluster (preflight check in
  :meth:`salt.master.Master._pre_flight` requires
  ``cluster_peers`` whenever ``cluster_id`` is truthy).  A
  single-master topology cannot express "my cluster_id is east"
  through ``opts`` today --- the topology ``cluster_id`` lives
  in ``topology.conf`` and the master-side compound matcher does
  not consult it.

Those three gaps mean this scenario deliberately targets ``'*'``
instead of ``-C 'C@east'`` --- the glob matcher does not depend
on ``opts["cluster_id"]`` and the publish flows through
``publish_payload`` -> ``on_publish`` identically.
"""

import logging

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scenario --- real CLI publish round-trip through topology-enabled master
# ---------------------------------------------------------------------------


def test_scenario_cli_glob_publish_round_trip_with_peered_topology(
    two_cluster_fixture,
    attach_minion,
):
    """
    Drive ``salt '*' test.ping`` on east with the real ``salt`` CLI
    against a topology-enabled east master whose west peer has
    been accepted using a real :class:`salt.crypt.MasterIdentityKey`.

    Verifications:

    * The CLI exits 0 and reports ``web-01: True`` --- so the
      end-to-end chain through
      :meth:`salt.master.ClearFuncs.publish`,
      :meth:`salt.channel.server.MasterPubServerChannel.publish_payload`
      -> :func:`salt.topology.router.on_publish`, and east's
      local minion return path is exercised.
    * East has west's real ``master_identity.pub`` on disk under
      ``<east_pki_dir>/masters/west.pub`` and the bytes start
      with the standard PEM header ``-----BEGIN PUBLIC KEY-----``,
      proving the harness extension actually wrote real crypto
      instead of the placeholder blob the prior scenarios used.
      The symmetric fact holds for west.
    * Both masters have generated their own on-disk
      ``master_identity.{pub,pem}`` under ``<pki_dir>/master/``,
      so a ``topology/_master_auth`` handshake from either side
      would present a valid identity.
    """
    east, west = two_cluster_fixture

    # Generate real master-identity keypairs for both sides.
    east.ensure_identity_key()
    west.ensure_identity_key()

    # Bidirectional peer acceptance using the REAL pub keys.
    east.accept_peer(west)
    west.accept_peer(east)

    # Bidirectional config-level peering in each side's
    # ``topology.conf``.  The running master processes already
    # loaded their topology config at start, so this new entry
    # takes effect at the next ``link_manager.start`` call ---
    # not re-exercised here but part of the on-disk end-state.
    east.config_peer(west)
    west.config_peer(east)

    # Harness-level sanity: identity keys are real RSA PEMs.
    east_pub_path, east_priv_path = east.identity_key_paths()
    west_pub_path, west_priv_path = west.identity_key_paths()
    assert east_pub_path.is_file()
    assert east_priv_path.is_file()
    assert west_pub_path.is_file()
    assert west_priv_path.is_file()

    # Both masters now have the peer's real ``master_identity.pub``
    # on disk under ``masters/<peer>.pub``, with the standard
    # PEM header (not the placeholder sentinel bytes).
    east_peer_pub = east.masters_pki_dir / f"{west.cluster_id}.pub"
    west_peer_pub = west.masters_pki_dir / f"{east.cluster_id}.pub"
    assert east_peer_pub.is_file()
    assert west_peer_pub.is_file()
    assert east_peer_pub.read_bytes().startswith(
        b"-----BEGIN PUBLIC KEY-----"
    ), "accept_peer must write a real RSA-formatted PEM, not placeholder bytes"
    assert west_peer_pub.read_bytes().startswith(b"-----BEGIN PUBLIC KEY-----")
    # And the bytes copied over match the generating cluster's
    # on-disk pub exactly --- no in-memory re-encoding drift.
    assert east_peer_pub.read_bytes() == west_pub_path.read_bytes()
    assert west_peer_pub.read_bytes() == east_pub_path.read_bytes()

    # One minion attached to east's publish channel.
    minion = attach_minion(east, minion_id="web-01")
    assert minion.is_running()

    # Drive the real salt CLI on east.  Target ``'*'`` matches
    # every locally-known minion through the glob matcher ---
    # independent of the master-side ``opts["cluster_id"]`` that
    # would be needed for a ``-C 'C@east'`` compound match.
    salt_cli = east.masters[0].salt_cli(timeout=120)
    ret = salt_cli.run("test.ping", minion_tgt="*")

    assert ret.returncode == 0, (
        f"salt CLI exited {ret.returncode}; stdout={ret.stdout!r} "
        f"stderr={ret.stderr!r}"
    )
    assert isinstance(ret.data, dict), (
        f"expected a dict of minion returns, got {ret.data!r} "
        f"(stdout={ret.stdout!r})"
    )
    assert "web-01" in ret.data, f"web-01 missing from CLI return data={ret.data!r}"
    assert (
        ret.data["web-01"] is True
    ), f"web-01 returned {ret.data['web-01']!r}; expected True"
