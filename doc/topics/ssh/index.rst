.. _salt-ssh:

========
Salt SSH
========

.. raw:: html
 :file: index.html

Getting Started
===============

Salt SSH is very easy to use, simply set up a basic :ref:`roster <ssh-roster>` file of the
systems to connect to and run ``salt-ssh`` commands in a similar way as
standard ``salt`` commands.

- Salt ssh is considered production ready in version 2014.7.0
- Python is required on the remote system (unless using the ``-r`` option to send raw ssh commands)
- On many systems, the ``salt-ssh`` executable will be in its own package, usually named
  ``salt-ssh``
- The Salt SSH system does not supersede the standard Salt communication
  systems, it simply offers an SSH-based alternative that does not require
  ZeroMQ and a remote agent. Be aware that since all communication with Salt SSH is
  executed via SSH it is substantially slower than standard Salt with ZeroMQ.
- At the moment fileserver operations must be wrapped to ensure that the
  relevant files are delivered with the ``salt-ssh`` commands.
  The state module is an exception, which compiles the state run on the
  master, and in the process finds all the references to ``salt://`` paths and
  copies those files down in the same tarball as the state run.
  However, needed fileserver wrappers are still under development.

Salt SSH Roster
===============

The roster system in Salt allows for remote minions to be easily defined.

.. note::
    See the :ref:`SSH roster docs <ssh-roster>` for more details.

Simply create the roster file, the default location is `/etc/salt/roster`:

.. code-block:: yaml

    web1: 192.168.42.1

This is a very basic roster file where a Salt ID is being assigned to an IP
address. A more elaborate roster can be created:

.. code-block:: yaml

    web1:
      host: 192.168.42.1 # The IP addr or DNS hostname
      user: fred         # Remote executions will be executed as user fred
      passwd: foobarbaz  # The password to use for login, if omitted, keys are used
      sudo: True         # Whether to sudo to root, not enabled by default
    web2:
      host: 192.168.42.2

.. note::
    sudo works only if NOPASSWD is set for user in /etc/sudoers:
    ``fred ALL=(ALL) NOPASSWD: ALL``

Deploy ssh key for salt-ssh
===========================

By default, salt-ssh will generate key pairs for ssh, the default path will be
``/etc/salt/pki/master/ssh/salt-ssh.rsa``. The key generation happens when you run
``salt-ssh`` for the first time.

You can use ssh-copy-id, (the OpenSSH key deployment tool) to deploy keys to your servers.

.. code-block:: bash

   ssh-copy-id -i /etc/salt/pki/master/ssh/salt-ssh.rsa.pub user@server.demo.com

One could also create a simple shell script, named salt-ssh-copy-id.sh as follows:

.. code-block:: bash

   #!/bin/bash
   if [ -z $1 ]; then
      echo $0 user@host.com
      exit 0
   fi
   ssh-copy-id -i /etc/salt/pki/master/ssh/salt-ssh.rsa.pub $1


.. note::
    Be certain to chmod +x salt-ssh-copy-id.sh.

.. code-block:: bash

   ./salt-ssh-copy-id.sh user@server1.host.com
   ./salt-ssh-copy-id.sh user@server2.host.com

Once keys are successfully deployed, salt-ssh can be used to control them.

Alternatively ssh agent forwarding can be used by setting the priv to agent-forwarding.

Calling Salt SSH
================

.. note:: ``salt-ssh`` on RHEL/CentOS 5

    The ``salt-ssh`` command requires at least python 2.6, which is not
    installed by default on RHEL/CentOS 5.  An easy workaround in this
    situation is to use the ``-r`` option to run a raw shell command that
    installs python26:

    .. code-block:: bash

        salt-ssh centos-5-minion -r 'yum -y install epel-release ; yum -y install python26'

.. note:: ``salt-ssh`` on systems with Python 3.x

    Salt, before the 2017.7.0 release, does not support Python 3.x which is the
    default on for example the popular 16.04 LTS release of Ubuntu. An easy
    workaround for this scenario is to use the ``-r`` option similar to the
    example above:

    .. code-block:: bash

        salt-ssh ubuntu-1604-minion -r 'apt update ; apt install -y python-minimal'

The ``salt-ssh`` command can be easily executed in the same way as a salt
command:

.. code-block:: bash

    salt-ssh '*' test.version

Commands with ``salt-ssh`` follow the same syntax as the ``salt`` command.

The standard salt functions are available! The output is the same as ``salt``
and many of the same flags are available. Please see
http://docs.saltstack.com/ref/cli/salt-ssh.html for all of the available
options.

Raw Shell Calls
---------------

By default ``salt-ssh`` runs Salt execution modules on the remote system,
but ``salt-ssh`` can also execute raw shell commands:

.. code-block:: bash

    salt-ssh '*' -r 'ifconfig'

States Via Salt SSH
===================

The Salt State system can also be used with ``salt-ssh``. The state system
abstracts the same interface to the user in ``salt-ssh`` as it does when using
standard ``salt``. The intent is that Salt Formulas defined for standard
``salt`` will work seamlessly with ``salt-ssh`` and vice-versa.

The standard Salt States walkthroughs function by simply replacing ``salt``
commands with ``salt-ssh``.

Targeting with Salt SSH
=======================

Due to the fact that the targeting approach differs in salt-ssh, only glob
and regex targets are supported as of this writing, the remaining target
systems still need to be implemented.

.. note::
    By default, Grains are settable through ``salt-ssh``. By
    default, these grains will *not* be persisted across reboots.

    See the "thin_dir" setting in :ref:`Roster documentation <ssh-roster>`
    for more details.

Configuring Salt SSH
====================

Salt SSH takes its configuration from a master configuration file. Normally, this
file is in ``/etc/salt/master``. If one wishes to use a customized configuration file,
the ``-c`` option to Salt SSH facilitates passing in a directory to look inside for a
configuration file named ``master``.

Minion Config
-------------

.. versionadded:: 2015.5.1

Minion config options can be defined globally using the master configuration
option ``ssh_minion_opts``. It can also be defined on a per-minion basis with
the ``minion_opts`` entry in the roster.

Running Salt SSH as non-root user
=================================

By default, Salt read all the configuration from /etc/salt/. If you are running
Salt SSH with a regular user you have to modify some paths or you will get
"Permission denied" messages. You have to modify two parameters: ``pki_dir``
and ``cachedir``. Those should point to a full path writable for the user.

It's recommended not to modify /etc/salt for this purpose. Create a private copy
of /etc/salt for the user and run the command with ``-c /new/config/path``.

Define CLI Options with Saltfile
================================

If you are commonly passing in CLI options to ``salt-ssh``, you can create
a ``Saltfile`` to automatically use these options. This is common if you're
managing several different salt projects on the same server.

So you can ``cd`` into a directory that has a ``Saltfile`` with the following
YAML contents:

.. code-block:: yaml

    salt-ssh:
      config_dir: path/to/config/dir
      ssh_log_file: salt-ssh.log
      ssh_max_procs: 30
      ssh_wipe: True

Instead of having to call
``salt-ssh --config-dir=path/to/config/dir --max-procs=30 --wipe \* test.version`` you
can call ``salt-ssh \* test.version``.

Boolean-style options should be specified in their YAML representation.

.. note::

   The option keys specified must match the destination attributes for the
   options specified in the parser
   :py:class:`salt.utils.parsers.SaltSSHOptionParser`.  For example, in the
   case of the ``--wipe`` command line option, its ``dest`` is configured to
   be ``ssh_wipe`` and thus this is what should be configured in the
   ``Saltfile``.  Using the names of flags for this option, being ``wipe:
   True`` or ``w: True``, will not work.

.. note::

    For the `Saltfile` to be automatically detected it needs to be named
    `Saltfile` with a capital `S` and be readable by the user running
    salt-ssh.

At last you can create ``~/.salt/Saltfile`` and ``salt-ssh``
will automatically load it by default.

Advanced options with salt-ssh
==============================

Salt's ability to allow users to have custom grains and custom modules
is also applicable to using salt-ssh. This is done through first packing
the custom grains into the thin tarball before it is deployed on the system.

For this to happen, the ``config`` file must be explicit enough to indicate
where the custom grains are located on the machine like so:

.. code-block:: yaml

    file_client: local
    file_roots:
      base:
        - /home/user/.salt
        - /home/user/.salt/_states
        - /home/user/.salt/_grains
    module_dirs:
      - /home/user/.salt
    pillar_roots:
      base:
        - /home/user/.salt/_pillar
    root_dir: /tmp/.salt-root

It's better to be explicit rather than implicit in this situation. This will
allow urls all under `salt://` to be resolved such as `salt://_grains/custom_grain.py`.

One can confirm this action by executing a properly setup salt-ssh minion with
`salt-ssh minion grains.items`. During this process, a `saltutil.sync_all` is
ran to discover the thin tarball and then consumed. Output similar to this
indicates a successful sync with custom grains.

.. code-block:: yaml

    local:
        ----------
        ...
        executors:
        grains:
            - grains.custom_grain
        log_handlers:
        ...

This is especially important when using a custom `file_roots` that differ from
`/etc/salt/`.

.. note::

    Please see https://docs.saltstack.com/en/latest/topics/grains/ for more
    information on grains and custom grains.


Debugging salt-ssh
==================

One common approach for debugging ``salt-ssh`` is to simply use the tarball that salt
ships to the remote machine and call ``salt-call`` directly.

To determine the location of ``salt-call``, simply run ``salt-ssh`` with the ``-ltrace``
flag and look for a line containing the string, ``SALT_ARGV``. This contains the ``salt-call``
command that ``salt-ssh`` attempted to execute.

It is recommended that one modify this command a bit by removing the ``-l quiet``,
``--metadata`` and ``--output json`` to get a better idea of what's going on the target system.

.. toctree::

    roster
