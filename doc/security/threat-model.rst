.. _security-threat-model:

==============================
Salt security and threat model
==============================

This page is for the person who has to run Salt in production and
needs a straight answer about what the software actually protects.
It covers what Salt guarantees, what it doesn't, and where you
have to pick up the slack.

.. important::

    Everything here describes the code as it ships today. If you
    need to report a vulnerability, see :ref:`disclosure`. For
    current advisories, see
    :ref:`saltstack_security_announcements`.

.. contents::
   :local:
   :depth: 2


Trust boundaries
================

Salt has four places where trust crosses between parts of the
system. Everything else on this page comes back to one of them.

1. **Minion → master.** Minions send auth requests, job returns,
   mine data, and events. The master knows a minion by its public
   key.
2. **Master → minion.** The master sends jobs and pillar data.
   The minion knows the master by its public key — pinned on
   first contact.
3. **Outside user → master.** Somebody wants the master to do
   something on their behalf. They either log in as a local OS
   user (publisher ACL) or they come in through an external auth
   driver — PAM, LDAP, REST, whatever — via :ref:`eauth
   <acl-eauth>`.
4. **Master → external source.** The master pulls data from
   outside systems: rendered pillar, file_server contents,
   returner storage, SDB secrets. Here Salt is a client, and the
   external system decides what it's allowed to read.


Minion ↔ master cryptographic channel
=====================================

What's on the wire
------------------

The master listens on two ports.

* **4506** (:conf_master:`ret_port`) is request/reply. Auth
  handshakes, job returns, mine pushes, salt-call publish
  requests, file_server reads — anything a minion needs to ask
  the master for.
* **4505** (:conf_master:`publish_port`) is pub/sub. The master
  publishes jobs here, and each minion filters by target and
  acts on what applies to it.

Transport doesn't change the trust model. ZeroMQ is the default;
you can switch to the TCP transport. Either way, every payload is
wrapped in an AES-encrypted, RSA-signed envelope. The envelope is
what authenticates the two ends to each other.

The transports do differ in framing:

* **tcp** prepends a 4-byte big-endian length to the msgpack
  payload (``salt/transport/frame.py``).
* **zeromq** uses native 0MQ frames.

The :conf_master:`ssl` option wraps the TCP transport socket in
TLS if you turn it on. **ZeroMQ does not support this option.**
The AES envelope is there either way.

First-time key exchange
-----------------------

The first time a minion connects, it hands the master a public
key. The master drops that key into one of four directories:

* ``<pki_dir>/minions_pre/`` — waiting for you to decide.
* ``<pki_dir>/minions/`` — accepted. Jobs reach these minions.
* ``<pki_dir>/minions_rejected/`` — refused. The master will not
  authenticate this key.
* ``<pki_dir>/minions_denied/`` — a different key is already
  accepted for this minion ID, and this new one doesn't match
  it.

You decide which pile a key ends up in with :command:`salt-key`
or the ``wheel.key`` runner. **The master does not auto-accept
keys** — :conf_master:`auto_accept` defaults to ``False``. Setting
it to ``True`` removes that decision, and is **not safe** on any
network where something hostile can reach port 4506: anything
that completes the handshake gets in. If you really need
auto-accept, use :conf_master:`autosign_file` to narrow it to a
list of minion IDs you're expecting.

What you actually get from the handshake
----------------------------------------

Once a minion is accepted, two things hold:

* When a job shows up on the minion's pub channel, it really was
  sent by the master this minion is paired with. The minion
  holds the master's pinned public key in
  ``<pki_dir>/minion_master.pub`` and checks the signature on
  every pub message when :conf_minion:`sign_pub_messages` is
  enabled on the minion side. The master signs by default —
  :conf_master:`sign_pub_messages` is ``True`` out of the box on
  the master.
* When a return arrives at the master labeled as coming from
  minion **M**, it really was produced by whoever holds the
  private key the master accepted for **M**.

What you don't get
------------------

* **A minion ID is not an identity.** It's a string the minion
  picks for itself. If a second key shows up claiming an ID
  that's already accepted, that second key goes to
  ``minions_denied/`` — it doesn't take over the first one, but
  the ID itself doesn't tell you much about which host is really
  which.
* **No replay protection on the pub channel.** The signature
  (:conf_master:`sign_pub_messages`) proves the master sent a
  message. It does not say *when* — there's no timestamp.
  Someone who can record signed traffic and re-inject it later
  can replay it. Signing stops forgery, not replay.
* **Keys are identities, not hosts.** Two different keys on one
  host are two different minions as far as the master is
  concerned. The master doesn't check source IPs against
  anything.


What publisher ACL and eauth are for
====================================

Once someone reaches the master, the master decides what they
get to run. There are two systems for this, depending on who
"someone" is:

* :ref:`publisher-acl` covers local OS users on the master host.
  Being able to read the master's IPC socket as yourself is how
  you authenticate.
* :ref:`acl-eauth` covers everyone else — remote users coming
  through PAM, LDAP, REST, or whatever backend you've pointed
  salt-api at.

Both use the same :ref:`matcher language <acl>`.

What the ACLs cover
-------------------

* **Modules and functions.** "User X can run ``cmd.run``" or
  "User X can run anything under ``state.*``."
* **Target minions.** "User X can target ``web*``" — same
  matcher Salt uses for ``salt -G os:RedHat``.
* **Argument shapes.** "User X can run ``cmd.run`` only when the
  first argument matches ``^ls``."

What the ACLs don't cover
-------------------------

* If a user can run ``cmd.run``, they have a shell on the
  minion. That's what ``cmd.run`` is.
* If a user can call ``pillar.items`` on a minion, they can read
  whatever pillar that minion sees — including values you
  encrypted at rest, because decryption happens on the master
  before the pillar is shipped.
* If a user has ``@runner`` access, they can call the
  ``salt.cmd`` runner. ``salt.cmd`` runs Salt execution modules
  on the **master host**, as the master process user — root by
  default. So ``salt-run salt.cmd cmd.run ...`` is a shell on
  the master.
* ``state.orchestrate`` from an authorized user runs whatever
  SLS they name. Nothing in the ACL stops them from naming a
  bad one.

Keep the mental model straight: **publisher_acl and eauth decide
who gets to kick off what. They are not a sandbox around what the
kicked-off code can do.** If you need real isolation, use
dedicated minions or ``salt-ssh`` targets — not finer-grained ACL
entries on a shared minion.

Things that have surprised operators
------------------------------------

* :conf_master:`publisher_acl_blacklist` is checked *before*
  :conf_master:`publisher_acl`. Blacklist wins.
* :conf_master:`permissive_acl` is subtle. With
  ``permissive_acl: False`` (the default), a ``*`` entry only
  applies to users who don't match any named entry. With
  ``permissive_acl: True``, a ``*`` entry applies to **every**
  user, on top of whatever else they match.
* ``@runner`` and ``@wheel`` are not globs. A ``*`` entry
  doesn't grant them. You have to spell out ``@runner`` (or
  ``@wheel``, or something tighter like ``@runner_modname``).
* Argument restrictions check each positional arg as a regex
  against ``str(arg)``. A ``None`` in the args list means
  "anything goes in this slot." Only the slots you name are
  checked — extra trailing args pass straight through.


Pillar and encrypted secrets
============================

Pillar is where Salt expects secrets to live. It's rendered on
the master and shipped to the minion inside the encrypted
channel.

Encrypting pillar at rest
-------------------------

Salt ships two renderers that decrypt secrets at render time:

* :py:mod:`gpg <salt.renderers.gpg>` uses gnupg on the master.
  The master needs the private key in its gpg homedir. The
  ciphertext stays in the pillar SLS.
* :py:mod:`nacl <salt.renderers.nacl>` uses libsodium / PyNaCl.
  The master holds the private key. The ciphertext stays in the
  pillar SLS.

In both cases the **master process has to hold the unwrapping
key**. What encryption buys you here is protection of the SLS
file at rest — in the filesystem, or in source control. It does
not protect the master process itself.

What encrypted pillar does **not** do
-------------------------------------

* It does not stop a user with ``pillar.items`` on the target
  minion from reading the cleartext. The master decrypts before
  shipping; the minion sees plaintext.
* It does not help if the master itself is compromised. The
  master has the unwrap key and the decrypted value in memory
  at the same time.


External data sources
=====================

* :ref:`file_server <file-server>` is read by the master. With
  ``gitfs`` the git remote authenticates the master; with
  ``s3fs`` the S3 bucket policy authenticates the master. Same
  pattern for the other backends.
* ``ext_pillar`` runs inside the master process. Each backend
  documents its own failure modes.
* Returners can run on the minion (``--return``) or on the
  master (:conf_master:`master_job_cache`). Credentials for
  whichever returner you use live in the config file. Keeping
  that config file protected is on you.
* :ref:`SDB <sdb>` is a generic name-lookup layer. Whichever
  backend you point it at — Vault, consul, env, and so on — is
  what actually authenticates.

The common thread: Salt is the client. The external system
enforces its own access policy, and Salt just forwards
credentials.


What's on disk matters
======================

The wire protocol isn't usually where incidents start. The
filesystem is.

On the master host
------------------

* ``<pki_dir>/master.pem`` is the master's private key. Anyone
  who can read this file **is** the master, and stays the master
  across reboots.
* With :conf_master:`minion_data_cache` on, the master keeps the
  last rendered pillar for each minion in its ``pillar`` cache
  bank. If someone can read that cache, they can read every
  secret you've ever shipped.
* ``<cachedir>/jobs/`` holds job results — including stdout from
  every command. Anybody who can read the directory can read
  what minions returned.
* **Running the master as a non-root user doesn't by itself
  shrink the blast radius.** The master still has whatever
  authority it needs to publish to all your minions. What
  matters is who can talk to the master's IPC socket, not what
  UID the master process runs as. See
  :ref:`configuration-non-root-user` for the supported way to
  run under a dedicated user.

On the minion host
------------------

* ``<pki_dir>/minion.pem`` is the minion's private key. Whoever
  holds it can return data to the master as this minion ID.
* ``<pki_dir>/minion_master.pub`` is the master public key the
  minion pinned on first contact. Replace this file and the
  minion quietly starts following a different master — nothing
  else gates the swap.
* ``<cachedir>/extmods/`` is where the minion keeps custom
  modules the master shipped down. Anything you drop in there
  runs the next time the minion starts a job.


Onedir and dependency CVEs
==========================

Since Salt 3005, the default packaging is "onedir": a bundled
Python interpreter plus a frozen set of Python dependencies, all
under ``/opt/saltstack/salt`` (or the platform equivalent). The
distro's ``python`` and the distro package manager aren't
involved at runtime.

That changes how you patch:

* **A distro security update to** ``python3-*`` **does not patch
  the Salt onedir.** The onedir carries its own copy of every
  Python library it links against — ``cryptography``,
  ``requests``, ``pyzmq``, ``tornado``, ``msgpack``,
  ``urllib3``, ``certifi``, and so on. When a CVE lands against
  one of those, you get the fix by upgrading Salt itself.
* Each release's notes under ``doc/topics/releases/`` list the
  bundled-dependency upgrades for that release.
* The supported way to keep the onedir current is to install the
  next Salt release. Dropping newer wheels into ``site-packages``
  inside the onedir tree isn't supported.
* If you need to pick your own dependency versions — say because
  you're on a strict CVE-response SLA — you can install Salt
  from wheel (``pip install salt``) instead of using the onedir.
  You give up the curated test matrix and the ``salt-master`` /
  ``salt-minion`` systemd units that the package ships.

Why it works this way: the onedir decision was made so every
Salt install runs the same Python on every host. The security
trade-off is that you have to treat the onedir as a separate
patching domain from the host OS.


Related reading
===============

* :ref:`hardening-salt` — operator checklist.
* :ref:`disclosure` — how to report a vulnerability.
* :ref:`publisher-acl` and :ref:`acl-eauth` — the ACL systems in
  detail.
