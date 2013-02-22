===============
Cloud Functions
===============

Cloud functions work much the same way as cloud actions, except that they don't
perform an operation on a specific instance, and so do not need a machine name
to be specified. However, since they perform an operation on a specific cloud
provider, that provider must be specified.

.. code-block:: bash

    $ salt-cloud -f aws show_image image=ami-fd20ad94

