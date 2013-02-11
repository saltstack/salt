================================
Miscellaneous Salt Cloud Options
================================

This page describes various miscellaneous options available in Salt Cloud

Delete SSH Keys
===============

When Salt Cloud deploys an instance, the SSH pub key for the instance is added
to the known_hosts file for the user that ran the salt-cloud command. When an
instance is deployed, a cloud provider generally recycles the IP address for
the instance.  When Salt Cloud attempts to deploy an instance using a recycled
IP address that has previously been accessed from the same machine, the old key
in the known_hosts file will cause a conflict.

In order to mitigate this issue, Salt Cloud can be configured to remove old
keys from the known_hosts file when destroying the node. In order to do this,
the following line needs to be added to the main cloud configuration file:

.. code-block:: yaml

    delete_sshkeys: True

