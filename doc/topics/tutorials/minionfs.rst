.. _tutorial-minionfs:

============================
MinionFS Backend Walkthrough
============================

Propagating Files
=================

.. versionadded:: 2014.1.0

Sometimes, one might need to propagate files that are generated on a minion.
Salt already has a feature to send files from a minion to the master.

Enabling File Propagation
=========================

To enable propagation, the :conf_master:`file_recv` option needs to be set to ``True``.

.. code-block:: yaml

    file_recv: True

These changes require a restart of the master, then new requests for the
``salt://minion-id/`` protocol will send files that are pushed by ``cp.push``
from ``minion-id`` to the master.

.. code-block:: bash

    salt 'minion-id' cp.push /path/to/the/file

This command will store the file, including its full path, under
:conf_master:`cachedir` ``/master/minions/minion-id/files``. With the default
:conf_master:`cachedir` the example file above would be stored as
`/var/cache/salt/master/minions/minion-id/files/path/to/the/file`.

.. note::

    This walkthrough assumes basic knowledge of Salt and :mod:`cp.push
    <salt.modules.cp.push>`. To get up to speed, check out the
    :doc:`walkthrough </topics/tutorials/walkthrough>`.

MinionFS Backend
================

Since it is not a good idea to expose the whole :conf_master:`cachedir`, MinionFS
should be used to send these files to other minions.

Simple Configuration
====================

To use the minionfs backend only two configuration changes are required on the
master. The :conf_master:`fileserver_backend` option needs to contain a value of
``minion`` and :conf_master:`file_recv` needs to be set to true:

.. code-block:: yaml

    fileserver_backend:
      - roots
      - minion

    file_recv: True

These changes require a restart of the master, then new requests for the
``salt://minion-id/`` protocol will send files that are pushed by ``cp.push``
from ``minion-id`` to the master.

.. note::

    All of the files that are pushed to the master are going to be available to
    all of the minions. If this is not what you want, please remove ``minion``
    from :conf_master:`fileserver_backend` in the master config file.

.. note::

    Having directories with the same name as your minions in the root
    that can be accessed like ``salt://minion-id/`` might cause confusion.

Commandline Example
===================

Lets assume that we are going to generate SSH keys on a minion called
``minion-source`` and put the public part in ``~/.ssh/authorized_keys`` of root
user of a minion called ``minion-destination``.

First, lets make sure that ``/root/.ssh`` exists and has the right permissions:

.. code-block:: bash

    [root@salt-master file]# salt '*' file.mkdir dir_path=/root/.ssh user=root group=root mode=700
    minion-source:
        None
    minion-destination:
        None

We create an RSA key pair without a passphrase [*]_:

.. code-block:: bash

    [root@salt-master file]# salt 'minion-source' cmd.run 'ssh-keygen -N "" -f /root/.ssh/id_rsa'
    minion-source:
        Generating public/private rsa key pair.
        Your identification has been saved in /root/.ssh/id_rsa.
        Your public key has been saved in /root/.ssh/id_rsa.pub.
        The key fingerprint is:
        9b:cd:1c:b9:c2:93:8e:ad:a3:52:a0:8b:0a:cc:d4:9b root@minion-source
        The key's randomart image is:
        +--[ RSA 2048]----+
        |                 |
        |                 |
        |                 |
        |  o        .     |
        | o o    S o      |
        |=   +  . B o     |
        |o+ E    B =      |
        |+ .   .+ o       |
        |o  ...ooo        |
        +-----------------+

and we send the public part to the master to be available to all minions:

.. code-block:: bash

    [root@salt-master file]# salt 'minion-source' cp.push /root/.ssh/id_rsa.pub
    minion-source:
        True

now it can be seen by everyone:

.. code-block:: bash

    [root@salt-master file]# salt 'minion-destination' cp.list_master_dirs
    minion-destination:
        - .
        - etc
        - minion-source/root
        - minion-source/root/.ssh

Lets copy that as the only authorized key to ``minion-destination``:

.. code-block:: bash

    [root@salt-master file]# salt 'minion-destination' cp.get_file salt://minion-source/root/.ssh/id_rsa.pub /root/.ssh/authorized_keys
    minion-destination:
        /root/.ssh/authorized_keys

Or we can use a more elegant and salty way to add an SSH key:

.. code-block:: bash

    [root@salt-master file]# salt 'minion-destination' ssh.set_auth_key_from_file user=root source=salt://minion-source/root/.ssh/id_rsa.pub
    minion-destination:
        new




.. [*] Yes, that was the actual key on my server, but the server is already destroyed.
