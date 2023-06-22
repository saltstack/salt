.. _masterless-quickstart:

==========================
Salt Masterless Quickstart
==========================

.. _`Vagrant`: https://www.vagrantup.com/
.. _`Vagrant salt provisioner`: https://www.vagrantup.com/docs/provisioning/salt.html
.. _`salt-bootstrap`: https://github.com/saltstack/salt-bootstrap

Running a masterless salt-minion lets you use Salt's configuration management
for a single machine without calling out to a Salt master on another machine.

Since the Salt minion contains such extensive functionality it can be useful
to run it standalone. A standalone minion can be used to do a number of
things:

- Stand up a master server via States (Salting a Salt Master)
- Use salt-call commands on a system without connectivity to a master
- Masterless States, run states entirely from files local to the minion


It is also useful for testing out state trees before deploying to a production setup.


Bootstrap Salt Minion
=====================

The `salt-bootstrap`_ script makes bootstrapping a server with Salt simple
for any OS with a Bourne shell:

.. code-block:: bash

    curl -L https://bootstrap.saltstack.com -o bootstrap_salt.sh
    sudo sh bootstrap_salt.sh

Before run the script, it is a good practice to verify the checksum of the downloaded
file. You can verify the checksum with SHA256 by running this command:

.. code-block:: bash

    test $(sha256sum bootstrap_salt.sh | awk '{print $1}') \
       = $(curl -sL https://bootstrap.saltproject.io/sha256 | cat -) \
       && echo "OK" \
       || echo "File does not match checksum"

.. note::

    The previous example is the preferred method because by downloading the script
    you can investigate the contents of the bootstrap script or using it again later.
    Alternatively, if you want to download the bash script and run it immediately,
    use:

    .. code-block:: bash

        curl -L https://bootstrap.saltproject.io | sudo sh -s --

See the `salt-bootstrap`_ documentation for other one liners. When using `Vagrant`_
to test out salt, the `Vagrant salt provisioner`_ will provision the VM for you.

Telling Salt to Run Masterless
==============================

To instruct the minion to not look for a master, the :conf_minion:`file_client`
configuration option needs to be set in the minion configuration file.
By default the :conf_minion:`file_client` is set to ``remote`` so that the
minion gathers file server and pillar data from the salt master.
When setting the :conf_minion:`file_client` option to ``local`` the
minion is configured to not gather this data from the master.

.. code-block:: yaml

    file_client: local

Now the salt minion will not look for a master and will assume that the local
system has all of the file and pillar resources.

Configuration which resided in the
:ref:`master configuration <configuration-salt-master>` (e.g. ``/etc/salt/master``)
should be moved to the :ref:`minion configuration <configuration-salt-minion>`
since the minion does not read the master configuration.

.. note::

    When running Salt in masterless mode, do not run the salt-minion daemon.
    Otherwise, it will attempt to connect to a master and fail. The salt-call
    command stands on its own and does not need the salt-minion daemon.

Create State Tree
=================

Following the successful installation of a salt-minion, the next step is to create
a state tree, which is where the SLS files that comprise the possible states of the
minion are stored.

The following example walks through the steps necessary to create a state tree that
ensures that the server has the Apache webserver installed.

.. note::
    For a complete explanation on Salt States, see the `tutorial
    <https://docs.saltproject.io/en/latest/topics/tutorials/states_pt1.html>`_.

1. Create the ``top.sls`` file:

``/srv/salt/top.sls:``

.. code-block:: yaml

    base:
      '*':
        - webserver

2. Create the webserver state tree:

``/srv/salt/webserver.sls:``

.. code-block:: yaml

    apache:               # ID declaration
      pkg:                # state declaration
        - installed       # function declaration

.. note::

    The apache package has different names on different platforms, for
    instance on Debian/Ubuntu it is apache2, on Fedora/RHEL it is httpd
    and on Arch it is apache

The only thing left is to provision our minion using ``salt-call``.

Salt-call
---------

The salt-call command is used to run remote execution functions locally on a
minion instead of executing them from the master. Normally the salt-call
command checks into the master to retrieve file server and pillar data, but
when running standalone salt-call needs to be instructed to not check the
master for this data:

.. code-block:: bash

    salt-call --local state.apply

The ``--local`` flag tells the salt-minion to look for the state tree in the
local file system and not to contact a Salt Master for instructions.

To provide verbose output, use ``-l debug``:

.. code-block:: bash

    salt-call --local state.apply -l debug

The minion first examines the ``top.sls`` file and determines that it is a part
of the group matched by ``*`` glob and that the ``webserver`` SLS should be applied.

It then examines the ``webserver.sls`` file and finds the ``apache`` state, which
installs the Apache package.

The minion should now have Apache installed, and the next step is to begin
learning how to write :ref:`more complex states<states-tutorial>`.
