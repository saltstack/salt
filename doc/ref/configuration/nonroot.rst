.. _configuration-non-root-user:

======================================================
Running the Salt Master/Minion as an Unprivileged User
======================================================

While the default setup runs the master and minion as the root user, some
may consider it an extra measure of security to run the master as a non-root
user. Keep in mind that doing so does not change the master's capability
to access minions as the user they are running as. Due to this many feel that
running the master as a non-root user does not grant any real security advantage
which is why the master has remained as root by default.

.. note::

    Some of Salt's operations cannot execute correctly when the master is not
    running as root, specifically the pam external auth system, as this system
    needs root access to check authentication.

As of Salt 0.9.10 it is possible to run Salt as a non-root user. This can be
done by setting the :conf_master:`user` parameter in the master configuration
file. and restarting the ``salt-master`` service.

The minion has its own :conf_minion:`user` parameter as well, but running the
minion as an unprivileged user will keep it from making changes to things like
users, installed packages, etc. unless access controls (sudo, etc.) are setup
on the minion to permit the non-root user to make the needed changes.

In order to allow Salt to successfully run as a non-root user, ownership, and
permissions need to be set such that the desired user can read from and write
to the following directories (and their subdirectories, where applicable):

* /etc/salt
* /var/cache/salt
* /var/log/salt
* /var/run/salt

Ownership can be easily changed with ``chown``, like so:

.. code-block:: bash

    # chown -R user /etc/salt /var/cache/salt /var/log/salt /var/run/salt

.. warning::

    Running either the master or minion with the :conf_master:`root_dir`
    parameter specified will affect these paths, as will setting options like
    :conf_master:`pki_dir`, :conf_master:`cachedir`, :conf_master:`log_file`,
    and other options that normally live in the above directories.

.. _nonroot-master-grains:

Grains when the master runs as non-root
=======================================

The master collects a set of grains for its own ``MasterMinion`` at
startup. Several of those grain loaders make root-only system calls
or read root-only files; when ``salt-master`` runs as a non-root
user those calls fail and the loader logs an error (or, on older
releases, raises).

The grains known to be affected:

* :py:func:`mdadm <salt.grains.mdadm>` — reads ``/proc/mdstat``
  *and* invokes ``mdadm`` on each device, which requires
  ``CAP_SYS_ADMIN``. Returns an empty grain when denied.
* :py:func:`smartos <salt.grains.smartos>` — uses ``zoneadm`` /
  ``mdata-get``, both root-only on SmartOS.
* :py:func:`opts.fips_enabled <salt.grains.opts>` — reads
  ``/proc/sys/crypto/fips_enabled``, which is world-readable on
  Linux but not present on every container/jail.
* :py:mod:`salt.grains.disks` — uses ``lsblk`` /
  ``/proc/partitions``; partial output when the user has no read
  access to ``/proc/partitions``.
* :py:mod:`salt.grains.iscsi` — reads
  ``/etc/iscsi/initiatorname.iscsi``, mode ``0600`` root.

The practical implication for a non-root master is:

* These grains are present but empty / partial. Don't write
  master-side targeting expressions or orchestrations that depend on
  these grain *values* being populated when the master is non-root.
* Errors from the grain loaders are logged at ``INFO``; an empty
  ``mdadm`` grain is not necessarily a misconfiguration.
* If you need any of these grains on the master, run those specific
  loaders out-of-band (for example, regenerate via a cron job that
  *does* run as root and writes the values into a static grains
  file), or run the master as root.

This list is **not exhaustive.** Custom grain modules under
``_grains/`` may also call privileged tools. The supported test is
to run ``salt-call --local grains.items`` as the same user the
master will run as; anything that errors or returns empty is a
grain you cannot rely on from the non-root master.

See :ref:`security-threat-model` for what non-root operation does
and does not buy you.
