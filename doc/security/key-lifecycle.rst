.. _security-key-lifecycle:

==================
Key lifecycle
==================

This page describes the supported flows for accepting, rotating, and
revoking Salt keys, including the edge cases that have been reported
as bugs over the years. It complements the operator-facing
:ref:`hardening-salt` checklist.

.. contents::
   :local:
   :depth: 2


Key locations
=============

Master
------

Under :conf_master:`pki_dir` (default ``/etc/salt/pki/master``)::

    master.pem            # master private key
    master.pub            # master public key
    minions/              # accepted minion public keys
    minions_pre/          # unaccepted minion public keys
    minions_rejected/     # explicitly rejected minion public keys
    minions_denied/       # auto-rejected by ID collision

Minion
------

Under :conf_minion:`pki_dir` (default ``/etc/salt/pki/minion``)::

    minion.pem            # minion private key
    minion.pub            # minion public key
    minion_master.pub     # pinned master public key

The minion identifier on the wire is :conf_minion:`id`. **The minion
ID is not the public key**; the operator chooses the ID, and the
master indexes accepted keys by that string.


Accept flow
===========

1. The minion starts and reads its public key from
   ``minion.pem``/``minion.pub``. If the files do not exist they are
   generated.
2. The minion connects to ``ret_port`` (4506) and submits its
   public key with its declared :conf_minion:`id`.
3. The master writes the key into ``minions_pre/<id>`` and emits a
   ``salt/auth`` event with ``act: pend``.
4. The operator runs ``salt-key -a <id>``, which moves
   ``minions_pre/<id>`` to ``minions/<id>``.
5. On the next reauth (within :conf_minion:`auth_timeout` plus
   :conf_minion:`acceptance_wait_time`) the minion is admitted.

The :command:`salt-key` flags are:

* ``-l unaccepted`` — list ``minions_pre``.
* ``-a <id>`` — accept (move ``minions_pre/<id>`` → ``minions/<id>``).
* ``-A`` — accept everything in ``minions_pre/``.
* ``-r <id>`` — reject (move to ``minions_rejected/``).
* ``-d <id>`` — delete from any of the four directories.
* ``-D`` — delete every key.
* ``-f`` — print key fingerprints.

For automation, the equivalents under ``wheel.key.*`` are documented
in :py:mod:`salt.wheel.key`.


Auto-accept (and why to avoid bare ``auto_accept: True``)
=========================================================

Setting :conf_master:`auto_accept` to ``True`` skips the
operator-decision step. **Any** key that reaches port 4506 is
accepted. This is appropriate only on a closed bootstrap network.

For provisioning-time auto-accept, prefer
:conf_master:`autosign_file`: a flat file of minion-ID glob patterns
that are accepted when they connect, with the rest still landing in
``minions_pre/``.

:conf_master:`autosign_grains_dir` extends this to grain-matching
auto-accept, but requires that the minion *send* the named grains in
its initial auth payload (see :conf_minion:`autosign_grains`); a
hostile minion can lie about its grains, so use grain-based autosign
only inside a trusted network.


Reject flow
===========

* ``salt-key -r <id>`` moves the key into ``minions_rejected/<id>``.
* The next reauth attempt from that minion is logged as
  ``Reject: rejected key`` on the master.
* What the minion does next depends on
  :conf_minion:`rejected_retry`.

  * Default ``False`` — the minion logs ``Reject: rejected master
    public key`` and **exits**. Whatever supervises ``salt-minion``
    (``systemd``, ``runit``, ``rc.d``) restarts it; on restart the
    auth attempt repeats and is rejected again. This is a hot-loop
    if the operator does not remove the key from
    ``minions_rejected/``.
  * ``True`` — the minion treats the rejected response identically
    to an unaccepted response: it backs off using
    :conf_minion:`acceptance_wait_time` and retries. The key
    remains in ``minions_rejected/`` until an operator deletes it.

The choice matters: a fleet that bootstraps faster than operators
accept keys is better off with ``rejected_retry: True`` so the
minion does not consume CPU and log volume restarting. A fleet
where rejection is a deliberate quarantine action should leave it
``False`` so the minion stays down.


Denied keys (ID collision)
==========================

When two distinct minions present two distinct public keys for the
same minion ID, only the first is written to ``minions_pre/`` or
``minions/``. Subsequent presentations of a different public key
under the same ID are written to ``minions_denied/<id>``.

The minion-side symptom is the same as a rejection: ``Reject: rejected
master public key`` and the minion is not admitted. The fix is **not**
to accept the denied key on top of the accepted one — that creates an
``id`` conflict the master cannot resolve. The supported repair is:

1. Decide which physical minion *owns* the ID.
2. ``salt-key -d <id>`` to clear both accepted and denied entries.
3. On the *losing* minion, change :conf_minion:`id` and remove its
   ``minion.pem`` / ``minion.pub``.
4. Restart both minions and re-accept under the corrected IDs.


Minion-side key regen
=====================

The supported flow for minion-side key regen is:

.. code-block:: shell

   # On the minion:
   salt-call saltutil.regen_keys
   systemctl stop salt-minion

   # On the master:
   salt-key -d <minion-id>

   # On the minion:
   systemctl start salt-minion

   # On the master, after the new key shows in `salt-key -L`:
   salt-key -a <minion-id>

.. important::

    ``saltutil.regen_keys`` only *deletes* the existing key files
    under :conf_minion:`pki_dir`. New keys are generated the next
    time the minion process starts, not in the running process. You
    **must** restart the minion afterwards or the next auth request
    will still use the old (now-deleted) key handle from memory.

The release-note guidance to ``rm /etc/salt/pki/minion/minion.{pem,pub}
&& systemctl restart salt-minion`` is equivalent and is the recommended
manual fallback when ``saltutil.regen_keys`` cannot run (for example,
the minion is unreachable from the master).


Master-side key rotation
========================

Rotating the master key invalidates the pinned ``minion_master.pub``
on every minion. The supported procedure is:

.. code-block:: shell

   # On the master:
   systemctl stop salt-master
   rm <pki_dir>/master.pem <pki_dir>/master.pub
   systemctl start salt-master

   # On every minion:
   systemctl stop salt-minion
   rm <pki_dir>/minion_master.pub
   systemctl start salt-minion

The minion ``rm`` step is mandatory. With :conf_minion:`master_finger`
unset the minion will accept whatever ``master.pub`` the master next
serves; with :conf_minion:`master_finger` set, you must update the
fingerprint there as well or the minion will refuse the new master
key and exit.

For larger fleets where a single sweep is impractical, see the
:py:mod:`salt.runners.manage` ``key.rotate`` documentation.


Minion-ID grain changes wipe keys
=================================

Changing the value of :conf_minion:`id` (or letting the default
``socket.getfqdn()``-derived ID change underneath the minion — for
example, the host's resolver starts returning a different hostname)
makes the minion present a *new* ``(id, pubkey)`` tuple to the master.
The old key remains on the master under the *old* ID. The new key
lands in ``minions_pre/`` under the *new* ID.

Practical implications:

* The minion is no longer reachable under the old ID until the
  operator deletes it with ``salt-key -d <old-id>``.
* If :conf_minion:`id` is recomputed at process start from
  ``socket.getfqdn()`` and the FQDN flaps, the minion will repeatedly
  produce new accepted-key requests. **Pin** :conf_minion:`id` to an
  explicit string in the minion config in any environment where
  hostname or DNS is not stable.
* On the master, no automatic cleanup happens. Old keys persist
  under the previous ID until removed.


Recovering a lost minion key
============================

If the minion's ``minion.pem`` is lost (host reinstall without
preserving ``/etc/salt/pki/minion``, decommission then reuse, ...):

1. On the master, delete the old accepted key:
   ``salt-key -d <id>``.
2. Start the new minion. It will generate a fresh keypair and land
   in ``minions_pre/<id>``.
3. **Verify the new fingerprint out of band** with
   ``salt-call --local key.finger``. The master operator should
   match that against ``salt-key -F <id>`` before accepting.
4. Accept on the master: ``salt-key -a <id>``.

Skipping step 1 produces an ID collision; the new key lands in
``minions_denied/`` instead. Skipping step 3 means the master
operator is accepting an untrusted key by ID alone — an attacker
who can race the legitimate minion at boot can poison this flow.


Message signing options
=======================

Two pairs of options govern message signing on top of the key
exchange:

* :conf_master:`sign_pub_messages` / corresponding minion-side
  verification — the **master** signs every event-bus message
  published to minions; minions verify with the pinned master
  public key.
* :conf_master:`require_minion_sign_messages` (master-side) and
  :conf_minion:`sign_pub_messages` (minion-side) —
  the **minion** signs every message it publishes; the master
  rejects unsigned messages when ``require_minion_sign_messages``
  is True and drops invalid signatures when
  :conf_master:`drop_messages_signature_fail` is True.

Note the option names overlap. :conf_minion:`sign_pub_messages`
on the **minion** turns on minion-side signing; the same-named
master option turns on master-side signing. A misconfiguration
where the minion config has ``sign_pub_messages: True`` but the
master has ``require_minion_sign_messages: False`` is silently
asymmetric — the minion signs, the master ignores the signature.

For a defence-in-depth deployment enable all three:

.. code-block:: yaml

    # /etc/salt/master
    sign_pub_messages: True
    require_minion_sign_messages: True
    drop_messages_signature_fail: True

.. code-block:: yaml

    # /etc/salt/minion
    sign_pub_messages: True

This pins the master → minion and minion → master event channels to
the public-key pair the operator already accepted.


Related tests
=============

The accept / reject / denied / regen flows are exercised by the
existing test suite under
``tests/pytests/unit/transport/`` and
``tests/pytests/integration/cli/test_salt_key.py``. These tests
pin the behaviour described here; this page is the operator-facing
narrative, the tests are the contract.
