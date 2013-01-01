============================================
Running the Salt Master as Unprivileged User
============================================

While the default setup runs the Salt Master as the root user, it is generally
wise to run servers as an unprivileged user. In Salt 0.9.10 the management
of the running user was greatly improved, the only change needed is to alter
the option ``user`` in the master configuration file and all salt system
components will be updated to function under the new user when the master
is started.

.. note::
    If running a version older that 0.9.10 then a number of files need to be
    owned by the user intended to run the master:

    .. code-block:: bash

        # chown -R <user> /var/cache/salt
        # chown -R <user> /var/log/salt
        # chown -R <user> /etc/salt/pki

.. note::
    When running as a non-root account, Salt Master will warn about being
    unable to use `dmidecode` and as a result grains output might not be
    accurate.


Configuration Example
---------------------

Here is an configuration example for running Salt Master as a non-root
account named `salt`. The account is configured using `/srv/salt` as home
folder.

To simplify file permissions configuration, all files are stored
inside user's home folder.

The following folder layout is used::

    /srv/salt       - Base folder to store all files used by Salt Master.
    /srv/salt/pki   - Public and private keys storage.
    /srv/salt/base  - Store states, files, modules ... etc.
                      This is the base folder for Salt file server.
    /srv/salt/cache - Cacke folder for internal usage.
    /srv/salt/sock  - Socket files for internal usage.
    /srv/salt/log   - Store logs files.

Make sure only `salt` account has read (and write) access to `/srv/salt/pki`
folder::

    sudo chmod 600 /srv/salt/pki

The `top.sls` file is located in `/srv/salt/base/top.sls`. Custom grains
and modules are located in `/srv/salt/base/_grains` and
'/srv/salt/base/_modules', respectively.

This is the configuration for the above layout::

    #
    # Configuration for running salt-master as non-root.
    #
    user: salt

    root_dir: /srv/salt/
    pki_dir: /pki
    cachedir: /cache/
    sock_dir: /sock/

    log_file: /log/master
    key_logfile: /log/key

    file_roots:
      base:
        - /srv/salt/base
