=============================
Virtual Machine Disk Profiles
=============================

Salt Virt allows for the disks created for deployed virtual machines
to be finely configured. The configuration is a simple data structure which is
read from the ``config.option`` function, meaning that the configuration can be
stored in the minion config file, the master config file, or the minion's
pillar.

This configuration option is called ``virt.disk``. The default ``virt.disk``
data structure looks like this:

.. code-block:: yaml

    virt.disk:
      default:
        - system:
          size: 8192
	  format: qcow2
          model: virtio

.. note::

    The format and model does not need to be defined, Salt will
    default to the optimal format used by the underlying hypervisor,
    in the case of kvm this it is :strong:`qcow2` and
    :strong:`virtio`.

This configuration sets up a disk profile called default. The default
profile creates a single system disk on the virtual machine.

Define More Profiles
====================

Many environments will require more complex disk profiles and may require
more than one profile, this can be easily accomplished:

.. code-block:: yaml

    virt.disk:
      default:
        - system:
            size: 8192
      database:
        - system:
            size: 8192
        - data:
            size: 30720
      web:
        - system:
            size: 1024
        - logs:
            size: 5120

This configuration allows for one of three profiles to be selected,
allowing virtual machines to be created with different storage needs
of the deployed vm.
