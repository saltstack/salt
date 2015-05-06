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
`targets`. The `targets` is a list of target systems and attributes about how
to connect to said systems. The only requirement for a roster module in Salt
is to return the `targets` data structure.

Targets Data
------------

The information which can be stored in a roster `target` is the following:

.. code-block:: yaml

    <Salt ID>:       # The id to reference the target system with
        host:        # The IP address or DNS name of the remote host
        user:        # The user to log in as
        passwd:      # The password to log in with

        # Optional parameters
        port:        # The target system's ssh port number
        sudo:        # Boolean to run command via sudo
        priv:        # File path to ssh private key, defaults to salt-ssh.rsa
        timeout:     # Number of seconds to wait for response when establishing
                     # an SSH connection
        timeout:     # Number of seconds to wait for response
        minion_opts: # Dictionary of minion opts
