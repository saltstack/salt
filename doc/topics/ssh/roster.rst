.. _ssh-roster:

============
Salt Rosters
============

Salt rosters are pluggable systems added in Salt 0.17.0 to facilitate the
``salt-ssh`` system.
The roster system was created because ``salt-ssh`` needs a means to
identify which systems need to be targeted for execution.

.. seealso:: :ref:`all-salt.roster`

.. note::
    The Roster System is not needed or used in standard Salt because the
    master does not need to be initially aware of target systems, since the
    Salt Minion checks itself into the master.

Since the roster system is pluggable, it can be easily augmented to attach to
any existing systems to gather information about what servers are presently
available and should be attached to by ``salt-ssh``. By default the roster
file is located at /etc/salt/roster.

How Rosters Work
================

The roster system compiles a data structure internally referred to as
``targets``. The ``targets`` is a list of target systems and attributes about how
to connect to said systems. The only requirement for a roster module in Salt
is to return the ``targets`` data structure.

Targets Data
------------

The information which can be stored in a roster ``target`` is the following:

.. code-block:: yaml

    <Salt ID>:       # The id to reference the target system with
        host:        # The IP address or DNS name of the remote host
        user:        # The user to log in as
        passwd:      # The password to log in with

        # Optional parameters
        port:        # The target system's ssh port number
        sudo:        # Boolean to run command via sudo
        sudo_user:   # Str: Set this to execute Salt as a sudo user other than root.
                     # This user must be in the same system group as the remote user
                     # that is used to login and is specified above. Alternatively,
                     # the user must be a super-user.
        tty:         # Boolean: Set this option to True if sudo is also set to
                     # True and requiretty is also set on the target system
        priv:        # File path to ssh private key, defaults to salt-ssh.rsa
                     # The priv can also be set to agent-forwarding to not specify
                     # a key, but use ssh agent forwarding
        priv_passwd: # Passphrase for ssh private key
        timeout:     # Number of seconds to wait for response when establishing
                     # an SSH connection
        minion_opts: # Dictionary of minion opts
        thin_dir:    # The target system's storage directory for Salt
                     # components. Defaults to /tmp/salt-<hash>.
        cmd_umask:   # umask to enforce for the salt-call command. Should be in
                     # octal (so for 0o077 in YAML you would do 0077, or 63)
        ssh_pre_flight: # Path to a script that will run before all other salt-ssh
                        # commands. Will only run the first time when the thin dir
                        # does not exist, unless --pre-flight is passed to salt-ssh
                        # command or ssh_run_pre_flight is set to true in the config
                        # Added in Sodium Release.
        set_path:    # Set the path environment variable, to ensure the expected python
                     # binary is in the salt-ssh path, when running the command.
                     # Example: '$PATH:/usr/local/bin/'. Added in Sodium Release.


.. _ssh_pre_flight:

ssh_pre_flight
--------------

A Salt-SSH roster option `ssh_pre_flight` was added in the Sodium release. This enables
you to run a script before Salt-SSH tries to run any commands. You can set this option
in the roster for a specific minion or use the `roster_defaults` to set it for all minions.
This script will only run if the thin dir is not currently on the minion. This means it will
only run on the first run of salt-ssh or if you have recently wiped out your thin dir. If
you want to intentionally run the script again you have a couple of options:

* Wipe out your thin dir by using the -w salt-ssh arg.
* Set ssh_run_pre_flight to True in the config
* Run salt-ssh with the --pre-flight arg.

.. _roster_defaults:

Target Defaults
---------------

The `roster_defaults` dictionary in the master config is used to set the
default login variables for minions in the roster so that the same arguments do
not need to be passed with commandline arguments.

.. code-block:: yaml

    roster_defaults:
      user: daniel
      sudo: True
      priv: /root/.ssh/id_rsa
      tty: True

thin_dir
--------

Salt needs to upload a standalone environment to the target system, and this
defaults to /tmp/salt-<hash>. This directory will be cleaned up per normal
systems operation.

If you need a persistent Salt environment, for instance to set persistent grains,
this value will need to be changed.
