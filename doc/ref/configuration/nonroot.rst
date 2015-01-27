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

The minion has it's own :conf_minion:`user` parameter as well, but running the
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
