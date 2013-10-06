===========
Node groups
===========

.. glossary::

    Node group
        A predefined group of minions declared in the master configuration file
        :conf_master:`nodegroups` setting as a compound target.

Nodegroups are declared using a compound target specification. The compound
target documentation can be found :doc:`here <compound>`.

The :conf_master:`nodegroups` master config file parameter is used to define
nodegroups. Here's an example nodegroup configuration:

.. code-block:: yaml

    nodegroups:
      group1: 'L@foo.domain.com,bar.domain.com,baz.domain.com or bl*.domain.com'
      group2: 'G@os:Debian and foo.domain.com'

To match a nodegroup on the CLI, use the ``-N`` command-line option:

.. code-block:: bash

    salt -N group1 test.ping

To match in your :term:`top file`, make sure to put ``- match: nodegroup`` on
the line directly following the nodegroup name.

.. code-block:: yaml

    base:
      group1:
        - match: nodegroup
        - webserver
