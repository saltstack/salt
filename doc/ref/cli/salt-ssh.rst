.. _cli-salt-ssh:

============
``salt-ssh``
============

Synopsis
========

.. code-block:: bash

    salt-ssh '*' [ options ] sys.doc

    salt-ssh -E '.*' [ options ] sys.doc cmd

Description
===========

Salt SSH allows for salt routines to be executed using only SSH for transport

Options
=======

.. program:: salt-ssh

.. include:: _includes/common-options.rst

.. option:: --hard-crash

   Raise any original exception rather than exiting gracefully. Default: False.

.. option:: -r, --raw, --raw-shell

    Execute a raw shell command.

.. option:: --roster

    Define which roster system to use, this defines if a database backend,
    scanner, or custom roster system is used. Default is the flat file roster.

.. option:: --roster-file

    Define an alternative location for the default roster file location. The
    default roster file is called ``roster`` and is found in the same directory
    as the master config file.

    .. versionadded:: 2014.1.0

.. option:: --refresh, --refresh-cache

    Force a refresh of the master side data cache of the target's data. This
    is needed if a target's grains have been changed and the auto refresh
    timeframe has not been reached.

.. option:: --max-procs

    Set the number of concurrent minions to communicate with. This value
    defines how many processes are opened up at a time to manage connections,
    the more running process the faster communication should be, default
    is 25.

.. option:: --extra-filerefs=EXTRA_FILEREFS

   Pass in extra files to include in the state tarball.

.. option:: --min-extra-modules=MIN_EXTRA_MODS

    One or comma-separated list of extra Python modulesto be included
    into Minimal Salt.

.. option:: --thin-extra-modules=THIN_EXTRA_MODS

   One or comma-separated list of extra Python modulesto  be included
   into Thin Salt.

.. option:: -v, --verbose

   Turn on command verbosity, display jid.

.. option:: -s, --static

   Return the data from minions as a group after they all return.

.. option:: -w, --wipe

   Remove the deployment of the salt files when done executing.

.. option:: -W, --rand-thin-dir

   Select a random temp dir to deploy on the remote system. The dir
   will be cleaned after the execution.

.. option:: -t, --regen-thin, --thin

   Trigger a thin tarball regeneration. This is needed if  custom
   grains/modules/states have been added or updated.

.. option:: --python2-bin=PYTHON2_BIN

   Path to a python2 binary which has salt installed.

.. option:: --python3-bin=PYTHON3_BIN

   Path to a python3 binary which has salt installed.

.. option:: --jid=JID

   Pass a JID to be used instead of generating one.

.. option:: --pre-flight

   Run the ssh_pre_flight script defined in the roster.
   By default this script will only run if the thin dir
   does not exist on the target minion. This option will
   force the script to run regardless of the thin dir
   existing or not.

Authentication Options
----------------------

.. option:: --priv=SSH_PRIV

    Specify the SSH private key file to be used for authentication.

.. option:: --priv-passwd=SSH_PRIV_PASSWD

    Specify the SSH private key file's passphrase if need be.

.. option:: -i, --ignore-host-keys

    By default ssh host keys are honored and connections  will ask for
    approval. Use this option to disable StrictHostKeyChecking.

.. option:: --no-host-keys

    Fully ignores ssh host keys which by default are honored and connections
    would ask for approval. Useful if the host key of a remote server has
    changed and would still error with --ignore-host-keys.

.. option:: --user=SSH_USER

    Set the default user to attempt to use when authenticating.

.. option:: --passwd

    Set the default password to attempt to use when authenticating.

.. option:: --askpass

    Interactively ask for the SSH password with no echo - avoids password
    in process args and stored in history.

.. option:: --key-deploy

   Set this flag to attempt to deploy the authorized ssh key with all
   minions. This combined with --passwd can make initial deployment of keys
   very fast and easy.

.. option:: --identities-only

   Use the only authentication identity files configured in the ssh_config
   files. See IdentitiesOnly flag in man ssh_config.

.. option:: --sudo

   Run command via sudo.

Scan Roster Options
-------------------

.. option:: --scan-ports=SSH_SCAN_PORTS

   Comma-separated list of ports to scan in the scan roster.

.. option:: --scan-timeout=SSH_SCAN_TIMEOUT

   Scanning socket timeout for the scan roster.

.. include:: _includes/logging-options.rst
.. |logfile| replace:: /var/log/salt/ssh
.. |loglevel| replace:: ``warning``

.. include:: _includes/target-selection-ssh.rst

.. include:: _includes/output-options.rst

.. note::
    If using ``--out=json``, you will probably want ``--static`` as well.
    Without the static option, you will get a separate JSON string per minion
    which makes JSON output invalid as a whole.
    This is due to using an iterative outputter. So if you want to feed it
    to a JSON parser, use ``--static`` as well.

See also
========

:manpage:`salt(7)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
