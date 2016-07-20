.. _salt-cloud-map:

==============
Cloud Map File
==============

A number of options exist when creating virtual machines. They can be managed
directly from profiles and the command line execution, or a more complex map
file can be created. The map file allows for a number of virtual machines to
be created and associated with specific profiles. The map file is designed to
be run once to create these more complex scenarios using salt-cloud.

Map files have a simple format, specify a profile and then a list of virtual
machines to make from said profile:

.. code-block:: yaml

    fedora_small:
      - web1
      - web2
      - web3
    fedora_high:
      - redis1
      - redis2
      - redis3
    cent_high:
      - riak1
      - riak2
      - riak3

This map file can then be called to roll out all of these virtual machines. Map
files are called from the salt-cloud command with the -m option:

.. code-block:: bash

    $ salt-cloud -m /path/to/mapfile

Remember, that as with direct profile provisioning the -P option can be passed
to create the virtual machines in parallel:

.. code-block:: bash

    $ salt-cloud -m /path/to/mapfile -P

.. note::

    Due to limitations in the GoGrid API, instances cannot be provisioned in parallel
    with the GoGrid driver. Map files will work with GoGrid, but the ``-P``
    argument should not be used on maps referencing GoGrid instances.

A map file can also be enforced to represent the total state of a cloud
deployment by using the ``--hard`` option. When using the hard option any vms
that exist but are not specified in the map file will be destroyed:

.. code-block:: bash

    $ salt-cloud -m /path/to/mapfile -P -H

Be careful with this argument, it is very dangerous! In fact, it is so
dangerous that in order to use it, you must explicitly enable it in the main
configuration file.

.. code-block:: yaml

    enable_hard_maps: True

A map file can include grains and minion configuration options:

.. code-block:: yaml

    fedora_small:
      - web1:
          minion:
            log_level: debug
          grains:
            cheese: tasty
            omelet: du fromage
      - web2:
          minion:
            log_level: warn
          grains:
            cheese: more tasty
            omelet: with peppers

A map file may also be used with the various query options:

.. code-block:: bash

    $ salt-cloud -m /path/to/mapfile -Q
    {'ec2': {'web1': {'id': 'i-e6aqfegb',
                         'image': None,
                         'private_ips': [],
                         'public_ips': [],
                         'size': None,
                         'state': 0}},
             'web2': {'Absent'}}

...or with the delete option:

.. code-block:: bash

    $ salt-cloud -m /path/to/mapfile -d
    The following virtual machines are set to be destroyed:
      web1
      web2

    Proceed? [N/y]

.. warning:: Specifying Nodes with Maps on the Command Line
    Specifying the name of a node or nodes with the maps options on the command
    line is *not* supported. This is especially important to remember when
    using ``--destroy`` with maps; ``salt-cloud`` will ignore any arguments
    passed in which are not directly relevant to the map file. *When using
    ``--destroy`` with a map, every node in the map file will be deleted!*
    Maps don't provide any useful information for destroying individual nodes,
    and should not be used to destroy a subset of a map.


Setting up New Salt Masters
===========================

Bootstrapping a new master in the map is as simple as:

.. code-block:: yaml

    fedora_small:
      - web1:
          make_master: True
      - web2
      - web3

Notice that **ALL** bootstrapped minions from the map will answer to the newly
created salt-master.

To make any of the bootstrapped minions answer to the bootstrapping salt-master
as opposed to the newly created salt-master, as an example:

.. code-block:: yaml

    fedora_small:
      - web1:
          make_master: True
          minion:
            master: <the local master ip address>
            local_master: True
      - web2
      - web3


The above says the minion running on the newly created salt-master responds to
the local master, ie, the master used to bootstrap these VMs.

Another example:

.. code-block:: yaml

    fedora_small:
      - web1:
          make_master: True
      - web2
      - web3:
          minion:
            master: <the local master ip address>
            local_master: True

The above example makes the ``web3`` minion answer to the local master, not the
newly created master.
