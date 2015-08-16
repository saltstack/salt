Salt Cloud basic usage
======================

Salt Cloud needs, at least, one configured
:ref:`Provider <cloud-provider-specifics>`
and :doc:`Profile <profiles>` to be functional.

Creating a VM
-------------

To create a VM with salt cloud, use command:

.. code-block:: bash

    salt-cloud -p <profile> name_of_vm

Assuming there is a profile configured as following:

.. code-block:: bash

    fedora_rackspace:
        provider: my-rackspace-config
        image: Fedora 17
        size: 256 server
        script: bootstrap-salt

Then, the command to create new VM named ``fedora_http_01`` is:

.. code-block:: bash

    salt-cloud -p fedora_rackspace fedora_http_01

Destroying a VM
---------------

To destroy a created-by-salt-cloud VM, use command:

.. code-block:: bash

    salt-cloud -d name_of_vm

For example, to delete the VM created on above example, use:

.. code-block:: bash

    salt-cloud -d fedora_http_01
