.. _configuration-non-root-user:

==========================================
Running the Salt Master or Minion non-root
==========================================

The Salt onedir packages run as ``root`` by default. This page is the
consolidated reference for the older "non-root user" and "unprivileged user"
pages, updated for the onedir layout shipped from 3006 onward.

Why run non-root
================

Running ``salt-master`` as a non-root account narrows blast radius if the
master process is exploited, and is required by some operator policies. Note
that a non-root master can still publish to minions running as ``root`` and
push arbitrary states to them, so non-root on the master is not a substitute
for transport-level controls, ACLs, and minion-side ``disable_modules``.

The minion has its own :conf_minion:`user` parameter. Running the minion as a
non-root user is supported but the minion can then only manage what that user
can change. ``pkg``, ``service``, ``user``, and similar modules will fail
unless the account has the appropriate ``sudo`` rules or capabilities.

.. note::

    The ``pam`` external auth on the master requires root to read
    ``/etc/shadow``. Use ``auto_signing`` keys, ``file`` eauth, or a different
    eauth backend if the master is non-root.

Choosing the account at install time (onedir packages)
======================================================

The deb and rpm packages create a ``salt`` system user and group during
``preinst``. The defaults and overrides are read from
``/etc/default/salt-setup`` (Debian convention) or
``/etc/sysconfig/salt-minion-setup`` (RPM convention) before the user is
created. The supported variables are:

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

Switching an existing install to a non-root user
================================================

If the packages are already installed under the default ``salt`` user, set
the runtime user in the daemon configs and chown the runtime paths.

#. In the master config:

   .. code-block:: yaml

       user: saltsvc

#. In the minion config (if running the minion non-root too):

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

The shipped systemd units run as ``root``. To run as a different user without
forking through ``su``, add a drop-in:

.. code-block:: ini

    # /etc/systemd/system/salt-master.service.d/user.conf
    [Service]
    User=saltsvc
    Group=saltsvc

Then ``systemctl daemon-reload && systemctl restart salt-master``.

The ``[Service]`` section already sets ``KillMode=process`` so an upgrade
that triggers ``systemctl try-restart`` does not signal child state runs.

Verifying the install
=====================

After switching user, the quickest end-to-end check is:

.. code-block:: bash

    sudo -u saltsvc salt-call --local test.ping
    sudo -u saltsvc salt-call --local grains.item user

The ``user`` grain should return the non-root account.
