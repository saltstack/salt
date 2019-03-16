.. _salt-cloud-actions:

=============
Cloud Actions
=============

Once a VM has been created, there are a number of actions that can be performed
on it. The "reboot" action can be used across all providers, but all other
actions are specific to the cloud provider. In order to perform an action, you
may specify it from the command line, including the name(s) of the VM to
perform the action on:

.. code-block:: bash

    $ salt-cloud -a reboot vm_name
    $ salt-cloud -a reboot vm1 vm2 vm2

Or you may specify a map which includes all VMs to perform the action on:

.. code-block:: bash

    $ salt-cloud -a reboot -m /path/to/mapfile

The following is an example list of actions currently supported by ``salt-cloud``:

.. code-block:: yaml

    all providers:
        - reboot
    ec2:
        - start
        - stop
    joyent:
        - stop
    linode:
        - start
        - stop

Another useful reference for viewing more ``salt-cloud`` actions is the
:ref:`Salt Cloud Feature Matrix <salt-cloud-feature-matrix>`.
