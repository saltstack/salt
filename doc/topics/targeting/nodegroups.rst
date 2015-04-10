.. _targeting-nodegroups:

===========
Node groups
===========

Nodegroups are declared using a compound target specification. The compound
target documentation can be found :doc:`here <compound>`.

The :conf_master:`nodegroups` master config file parameter is used to define
nodegroups. Here's an example nodegroup configuration within
``/etc/salt/master``:

.. code-block:: yaml

    nodegroups:
      group1: 'L@foo.domain.com,bar.domain.com,baz.domain.com or bl*.domain.com'
      group2: 'G@os:Debian and foo.domain.com'
      group3: 'G@os:Debian and N@group1'

.. note::

    The ``L`` within group1 is matching a list of minions, while the ``G`` in
    group2 is matching specific grains. See the :doc:`compound matchers
    <compound>` documentation for more details.

.. note::

    Nodgroups can reference other nodegroups as seen in ``group3``.  Ensure
    that you do not have circular references.  Circular references will be
    detected and cause partial expansion with a logged error message.

To match a nodegroup on the CLI, use the ``-N`` command-line option:

.. code-block:: bash

    salt -N group1 test.ping

To match a nodegroup in your :term:`top file`, make sure to put ``- match:
nodegroup`` on the line directly following the nodegroup name.

.. code-block:: yaml

    base:
      group1:
        - match: nodegroup
        - webserver

.. note::

    When adding or modifying nodegroups to a master configuration file, the master must be restarted
    for those changes to be fully recognized.

    A limited amount of functionality, such as targeting with -N from the command-line may be
    available without a restart.
