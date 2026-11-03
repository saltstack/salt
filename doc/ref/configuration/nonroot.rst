.. _configuration-non-root-user:

==========================================
Customizing the Salt Master or Minion user
==========================================

Default behavior since 3006.0 (Linux packages)
==============================================

Starting in **Salt 3006.0**, the Linux rpm and deb packages ship a ``master``
config with :conf_master:`user` set to ``salt``, and the package ``preinst``
creates the ``salt`` system user and group. **The salt-master daemon runs as
the unprivileged** ``salt`` **account out of the box** -- nothing in this
page is required to "enable" non-root operation for the master.

This change was announced in the `3006.0 release notes
<https://docs.saltproject.io/en/latest/topics/releases/3006.0.html>`_
under "Linux Packaging Salt Master Salt User and Group". Releases before
3006.0 (the 3005.x line and earlier) shipped the master with ``#user: root``
and the master ran as ``root`` by default.

The shipped ``minion`` config still has ``#user: root`` (commented) in 3006
and later. The salt-minion daemon runs as ``root`` by default because most
of the minion's work (``pkg``, ``service``, ``user``, ``file`` on system
paths) needs root. Switching the minion to a non-root account is a
customization, covered below.

The macOS and Windows installers are not covered by the 3006.0 packaging
change above; on those platforms the master and minion still run as the
installer-default account.

This page is the consolidated reference for the older "non-root user" and
"unprivileged user" pages, updated for the onedir layout. It is about
**customizing** the runtime account -- changing the username, relocating
directories, running rootless -- not about enabling something that is off by
default.

.. note::

    The ``pam`` external auth on the master requires root to read
    ``/etc/shadow``. The default ``user: salt`` master cannot use ``pam``
    eauth without additional capabilities; use ``auto_signing`` keys, the
    ``file`` eauth backend, or another eauth that does not need root.

When to customize
=================

Reasons to change the shipped defaults:

* You want the master or minion to run under a different account name (e.g.
  ``saltsvc`` rather than ``salt``), or under an existing operator account.
* You need the onedir install root or runtime directories somewhere other
  than ``/opt/saltstack/salt`` and ``/var/{cache,log,run}/salt`` -- for
  example, on a separate volume.
* You are running the minion non-root and need to relocate the directories
  it writes to so the target account can own them.

A non-root master can still publish to minions running as ``root`` and push
arbitrary states to them, so the choice of master account is not a substitute
for transport-level controls, ACLs, and minion-side ``disable_modules``.

Changing the account at install time (onedir packages)
======================================================

The deb and rpm packages create a ``salt`` system user and group during
``preinst``. To create a different account instead, drop overrides into
``/etc/default/salt-setup`` (Debian convention) or
``/etc/sysconfig/salt-minion-setup`` (RPM convention) **before** installing
the packages. The supported variables are:

============================ =================================================
Variable                     Purpose
============================ =================================================
``SALT_HOME``                Account home directory and onedir install root
                             (default ``/opt/saltstack/salt``).
``SALT_USER``                Account name to create / reuse (default ``salt``).
``SALT_GROUP``               Primary group (default ``$SALT_USER``).
``SALT_NAME``                GECOS name (default ``Salt``).
``SALT_SHELL``               Login shell (default ``/usr/sbin/nologin``).
``SALT_EXTRAS_DIR``          Override the ``extras-3.N`` directory used by
                             :ref:`salt-pip <salt-pip-onedir>` so packages
                             installed there survive upgrades. Default is
                             ``$SALT_HOME/extras-3.N``.
============================ =================================================

Drop the file in place *before* installing the package, for example:

.. code-block:: bash

    cat > /etc/default/salt-setup <<'EOF'
    SALT_USER=saltsvc
    SALT_GROUP=saltsvc
    SALT_HOME=/srv/salt-onedir
    SALT_EXTRAS_DIR=/srv/salt-onedir-extras
    EOF
    apt install salt-master salt-minion

The same file is sourced again on upgrade, so ownership of ``$SALT_HOME`` and
``$SALT_EXTRAS_DIR`` is restored to the right account after each ``apt`` or
``dnf`` upgrade.

Changing the account on an existing install
===========================================

If the packages are already installed under the default ``salt`` user and
you want to move the master, the minion, or both to a different account,
set the runtime user in the daemon configs and re-own the runtime paths.

#. In the master config (overrides the shipped ``user: salt``):

   .. code-block:: yaml

       user: saltsvc

#. In the minion config (to switch the minion away from the default
   ``root``):

   .. code-block:: yaml

       user: saltsvc

#. Re-own the directories the daemon needs to read and write:

   .. code-block:: bash

       chown -R saltsvc:saltsvc \
           /etc/salt \
           /var/cache/salt \
           /var/log/salt \
           /var/run/salt \
           /opt/saltstack/salt

   ``/opt/saltstack/salt`` ownership matters because :ref:`salt-pip
   <salt-pip-onedir>` needs to write into the ``extras-3.N`` directory under
   the onedir root.

#. Restart the daemons:

   .. code-block:: bash

       systemctl restart salt-master salt-minion

Relocating runtime directories
==============================

If ``$SALT_HOME`` alone is not enough -- for example, the account has no
write access to ``/var/cache``, ``/var/log``, or ``/var/run`` -- change the
runtime directories explicitly. The simplest option is :conf_master:`root_dir`:

.. code-block:: yaml

    # /etc/salt/master.d/rootless.conf
    user: saltsvc
    root_dir: /srv/salt-runtime

With ``root_dir`` set, every other relative path (:conf_master:`pki_dir`,
:conf_master:`cachedir`, :conf_master:`sock_dir`, :conf_master:`log_file`,
``pidfile``) is rooted under that directory. Pre-create the tree:

.. code-block:: bash

    install -d -o saltsvc -g saltsvc \
        /srv/salt-runtime/etc/salt \
        /srv/salt-runtime/var/cache/salt \
        /srv/salt-runtime/var/log/salt \
        /srv/salt-runtime/var/run/salt

To override individual directories instead, set them explicitly:

.. code-block:: yaml

    user: saltsvc
    pki_dir: /srv/salt-runtime/pki
    cachedir: /srv/salt-runtime/cache
    sock_dir: /srv/salt-runtime/sock
    log_file: /srv/salt-runtime/log/salt-master
    pidfile: /srv/salt-runtime/run/salt-master.pid

The same keys exist on the minion (:conf_minion:`pki_dir`,
:conf_minion:`cachedir`, :conf_minion:`sock_dir`, :conf_minion:`log_file`,
:conf_minion:`pidfile`).

.. warning::

    Setting ``root_dir`` shifts *all* relative paths, including the path
    written to ``pidfile``. systemd unit files reference the default pid path;
    if you set ``root_dir``, update the unit's ``PIDFile=`` directive (use a
    drop-in under ``/etc/systemd/system/salt-master.service.d/``) to match.

systemd unit overrides
======================

The shipped ``salt-master.service`` and ``salt-minion.service`` units have no
``User=`` directive, so systemd starts each daemon as ``root`` and the daemon
drops privileges to the account named in :conf_master:`user` /
:conf_minion:`user` before serving requests. That is how the default
``user: salt`` master ends up running as ``salt`` without any systemd
customization.

If you want systemd itself to start the daemon as a different account
(no in-process drop), add a drop-in:

.. code-block:: ini

    # /etc/systemd/system/salt-master.service.d/user.conf
    [Service]
    User=saltsvc
    Group=saltsvc

Then ``systemctl daemon-reload && systemctl restart salt-master``. Note that
in this mode the daemon must already have read/write access to its runtime
directories at start time -- the in-process ``verify_env`` chown step assumes
the daemon began as ``root``.

The shipped ``salt-minion.service`` already sets ``KillMode=process`` so an
upgrade that triggers ``systemctl try-restart`` does not signal child state
runs.

Verifying the install
=====================

The quickest end-to-end check that the configured account is in effect:

.. code-block:: bash

    sudo -u saltsvc salt-call --local test.ping
    sudo -u saltsvc salt-call --local grains.item user

The ``user`` grain should return the non-root account.
