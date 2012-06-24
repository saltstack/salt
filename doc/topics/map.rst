==============
Cloud Map File
==============

A number of options exist when creating virtual machines. They can be managed
directly from profiles and the command line execution, or a more complex map
file can be created. The map file allows for a number fo virtual machines to
be created and associated with specific profiles.

Map files have a simple format, specify a profile and then a list of virtual
machines to make from said profile:

.. code-block:: yaml

    fedora_smal:
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
      - riak1
      - riak1
      - riak1
      - riak1

This map file can then be called to roll out all of these virtual machines. Map
files are called from the salt-cloud command with the -m option:

.. code-block:: bash

    $ salt-cloud -m /path/to/mapfile

Remember, that as with direct profile provisioning the -P option can be passed
to create the virtual machines in parallel:

.. code-block:: bash

    $ salt-cloud -m /path/to/mapfile -P
