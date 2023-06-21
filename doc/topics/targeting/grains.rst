.. _targeting-grains:

======================
Targeting using Grains
======================

Grain data can be used when targeting minions.

For example, the following matches all CentOS minions:

.. code-block:: bash

    salt -G 'os:CentOS' test.version

Match all minions with 64-bit CPUs, and return number of CPU cores for each
matching minion:

.. code-block:: bash

    salt -G 'cpuarch:x86_64' grains.item num_cpus

Additionally, globs can be used in grain matches, and grains that are nested in
a dictionary can be matched by adding a colon for each level that is traversed.
For example, the following will match hosts that have a grain called
``ec2_tags``, which itself is a dictionary with a key named ``environment``,
which has a value that contains the word ``production``:

.. code-block:: bash

    salt -G 'ec2_tags:environment:*production*'

.. important::
  See :ref:`Is Targeting using Grain Data Secure? <faq-grain-security>` for
  important security information.
