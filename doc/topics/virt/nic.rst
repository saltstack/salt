.. _vm-nic-profiles:

================================
Virtual Machine Network Profiles
================================

Salt Virt allows for the network devices created for deployed virtual machines
to be finely configured. The configuration is a simple data structure which is
read from the ``config.option`` function, meaning that the configuration can be
stored in the minion config file, the master config file, or the minion's
pillar.

This configuration option is called ``virt:nic``. By default the ``virt:nic``
option is empty but defaults to a data structure which looks like this:

.. code-block:: yaml

    virt:
      nic:
        default:
          eth0:
            bridge: br0
            model: virtio

.. note::

    The model does not need to be defined, Salt will default to the optimal
    model used by the underlying hypervisor, in the case of kvm this model
    is :strong:`virtio`

This configuration sets up a network profile called default. The default
profile creates a single Ethernet device on the virtual machine that is bridged
to the hypervisor's :strong:`br0` interface. This default setup does not
require setting up the ``virt:nic`` configuration, and is the reason why a
default install only requires setting up the :strong:`br0` bridge device on the
hypervisor.

Define More Profiles
====================

Many environments will require more complex network profiles and may require
more than one profile, this can be easily accomplished:

.. code-block:: yaml

    virt:
      nic:
        dual:
          eth0:
            bridge: service_br
          eth1:
            bridge: storage_br
        single:
          eth0:
            bridge: service_br
        triple:
          eth0:
            bridge: service_br
          eth1:
            bridge: storage_br
          eth2:
            bridge: dmz_br
        all:
          eth0:
            bridge: service_br
          eth1:
            bridge: storage_br
          eth2:
            bridge: dmz_br
          eth3:
            bridge: database_br
        dmz:
          eth0:
            bridge: service_br
          eth1:
            bridge: dmz_br
        database:
          eth0:
            bridge: service_br
          eth1:
            bridge: database_br

This configuration allows for one of six profiles to be selected, allowing
virtual machines to be created which attach to different network depending
on the needs of the deployed vm.
