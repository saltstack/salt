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

Three Phase-5 gaps were closed as follow-ups so the ``C@west``
scenario below drives end-to-end:

* :meth:`salt.master.ClearFuncs.publish` now has a forward-only
  pass that permits publishes through on empty local-match when
  ``topology_enabled`` is set AND the target contains ``C@``
  scopes naming non-local clusters.  Pre-fix the "Master could
  not resolve minions for target" short-circuit dropped a
  ``-C 'C@west'`` publish on east before
  ``MasterPubServerChannel.publish_payload`` could invoke
  :func:`salt.topology.router.on_publish`.
* :func:`salt.topology.link_manager._dispatch_pub` now acts on
  ``forward_publish``'s ``local_match`` return by publishing the
  stripped-scope load through
  :class:`salt.channel.server.PubServerChannel` so west dispatches
  the forwarded publish to its own minions.
* :meth:`salt.utils.minions.CkMinions._check_cluster_minions`
  now sources the local ``cluster_id`` via
  :func:`salt.config.topology.load_topology_config` when
  ``opts["cluster_id"]`` is unset.  A topology-enabled solo
  master cannot set ``opts["cluster_id"]`` (3008.x preflight
  requires ``cluster_peers``), so the previous read-from-opts
  path returned empty for every ``C@`` clause on solo masters.
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


def test_scenario_cli_c_at_local_publish_round_trip(
    two_cluster_fixture,
    attach_minion,
):
    """
    Drive ``salt -C 'C@east' test.ping`` on east with the real
    ``salt`` CLI.  Exercises Fix 3 end-to-end: on a topology-
    enabled solo master, ``opts["cluster_id"]`` is unset but the
    C@ compound matcher must still resolve east as the local
    cluster via ``topology.conf``.

    Pre-fix this returned "Master could not resolve minions for
    target C@east" because ``_check_cluster_minions`` only
    consulted ``opts["cluster_id"]``.
    """
    east, _west = two_cluster_fixture

    east.ensure_identity_key()
    minion = attach_minion(east, minion_id="web-local")
    assert minion.is_running()

    salt_cli = east.masters[0].salt_cli(timeout=120)
    ret = salt_cli.run("--compound", "test.ping", minion_tgt="C@east")

    assert ret.returncode == 0, (
        f"salt CLI exited {ret.returncode}; stdout={ret.stdout!r} "
        f"stderr={ret.stderr!r}"
    )
    assert isinstance(ret.data, dict), (
        f"expected a dict of minion returns, got {ret.data!r} "
        f"(stdout={ret.stdout!r})"
    )
    assert (
        "web-local" in ret.data
    ), f"web-local missing from CLI return data={ret.data!r}"
    assert (
        ret.data["web-local"] is True
    ), f"web-local returned {ret.data['web-local']!r}; expected True"


def test_scenario_cli_c_at_peer_publish_round_trip_with_peered_topology(
    two_cluster_fixture,
    attach_minion,
):
    """
    Drive ``salt -C 'C@west' test.ping`` on east with the real
    ``salt`` CLI against a topology-peered east+west pair.
    Exercises all three Phase-5 follow-up fixes end-to-end:

    * Fix 1: ``ClearFuncs.publish`` lets the publish through on
      empty local-match (east has no C@west minions locally) so
      ``MasterPubServerChannel.publish_payload`` reaches
      :func:`salt.topology.router.on_publish`.
    * Fix 2: :func:`salt.topology.link_manager._dispatch_pub` acts
      on ``forward_publish``'s ``local_match=True`` on west and
      publishes the stripped-scope load to west's own minions.
    * Fix 3: :meth:`CkMinions._check_cluster_minions` on west
      resolves west as the local cluster via
      :func:`salt.config.topology.load_topology_config` when
      ``opts["cluster_id"]`` is unset on a solo master.

    Verifications:

    * CLI exits 0 and reports ``web-west: True`` --- the publish
      made it from east over the topology link to west and west
      forwarded the local return back.
    """
    east, west = two_cluster_fixture

    east.ensure_identity_key()
    west.ensure_identity_key()
    east.accept_peer(west)
    west.accept_peer(east)
    east.config_peer(west)
    west.config_peer(east)

    # The running masters loaded ``topology.conf`` at startup with an
    # empty peers list (the fixture writes it to disk before
    # ``factory.started()``).  ``config_peer`` just updated the file;
    # restart both masters so :func:`salt.topology.link_manager.start`
    # picks up the new peer and brings up the east<->west outbound
    # links the C@west publish needs.
    east.restart()
    west.restart()

    # Attach the target minion to WEST, not east.  The C@west
    # scope must forward the publish to west and have west fan it
    # out to this minion.
    minion = attach_minion(west, minion_id="web-west")
    assert minion.is_running()

    # Wait for the east<->west topology handshake to attach the peer
    # on both sides before the CLI fires -- Windows CI occasionally
    # saw an empty-stdout timeout here because the publish daemon
    # had not yet registered its ``_INBOUND[west]`` entry when the
    # publish arrived, so the forwarded ``topology/pub`` never left
    # east.  ``salt-run topology.peers`` returns a list of
    # ``{"cluster_id": ..., "state": ...}`` dicts; the handshake has
    # completed when the peer's state is ``"attached"``.
    import time as _time

    def _peer_attached(cluster, peer_cluster_id):
        run_cli = cluster.masters[0].salt_run_cli(timeout=30)
        ret = run_cli.run("topology.peers")
        if ret.returncode != 0 or not isinstance(ret.data, list):
            return False
        for entry in ret.data:
            if (
                entry.get("cluster_id") == peer_cluster_id
                and entry.get("state") == "attached"
            ):
                return True
        return False

    deadline = _time.monotonic() + 60
    while _time.monotonic() < deadline:
        if _peer_attached(east, west.cluster_id) and _peer_attached(
            west, east.cluster_id
        ):
            break
        _time.sleep(1)
    else:
        pytest.fail(
            "east<->west topology handshake did not attach within 60s "
            "after restart; CLI publish would have no outbound link"
        )

    salt_cli = east.masters[0].salt_cli(timeout=120)
    ret = salt_cli.run("--compound", "test.ping", minion_tgt="C@west")

    assert ret.returncode == 0, (
        f"salt CLI exited {ret.returncode}; stdout={ret.stdout!r} "
        f"stderr={ret.stderr!r}"
    )
    assert isinstance(ret.data, dict), (
        f"expected a dict of minion returns, got {ret.data!r} "
        f"(stdout={ret.stdout!r})"
    )
    assert "web-west" in ret.data, (
        f"web-west missing from CLI return data={ret.data!r} " f"stdout={ret.stdout!r}"
    )
    assert (
        ret.data["web-west"] is True
    ), f"web-west returned {ret.data['web-west']!r}; expected True"
