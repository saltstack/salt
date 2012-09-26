==============
Cloud Map File
==============

A number of options exist when creating virtual machines. They can be managed
directly from profiles and the command line execution, or a more complex map
file can be created. The map file allows for a number of virtual machines to
be created and associated with specific profiles.

Map files have a simple format, specify a profile and then a list of virtual
machines to make from said profile:

.. code-block:: yaml

    fedora_small:
        - web1
        - web2
        - web3
        - web3
        - web4
        - web5
    fedora_high:
        - redis1
        - redis2
        - redis3
    cent_high:
        - riak1
        - riak2
        - riak3
        - riak4
        - riak5

This map file can then be called to roll out all of these virtual machines. Map
files are called from the salt-cloud command with the -m option:

.. code-block:: bash

    $ salt-cloud -m /path/to/mapfile

Remember, that as with direct profile provisioning the -P option can be passed
to create the virtual machines in parallel:

.. code-block:: bash

    $ salt-cloud -m /path/to/mapfile -P

A map file can also be enforced to represent the total state of a cloud
deployment by using the ``--hard`` option. When using the hard option any vms
that exist but are not specified in the map file will be destroyed:

.. code-block:: bash

    $ salt-cloud -m /path/to/mapfile -P -H

A map file can include grains:

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

