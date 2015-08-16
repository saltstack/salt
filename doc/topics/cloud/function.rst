.. _salt-cloud-functions:

===============
Cloud Functions
===============

Cloud functions work much the same way as cloud actions, except that they don't
perform an operation on a specific instance, and so do not need a machine name
to be specified. However, since they perform an operation on a specific cloud
provider, that provider must be specified.

.. code-block:: bash

    $ salt-cloud -f show_image ec2 image=ami-fd20ad94

There are three universal salt-cloud functions that are extremely useful for
gathering information about instances on a provider basis:

* ``list_nodes``: Returns some general information about the instances for the given provider.
* ``list_nodes_full``: Returns all information about the instances for the given provider.
* ``list_nodes_select``: Returns select information about the instances for the given provider.

.. code-block:: bash

    $ salt-cloud -f list_nodes linode
    $ salt-cloud -f list_nodes_full linode
    $ salt-cloud -f list_nodes_select linode

Another useful reference for viewing salt-cloud functions is the
:ref:Salt Cloud Feature Matrix <salt-cloud-feature-matrix>
