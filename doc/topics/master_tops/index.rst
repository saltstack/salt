==================
Master Tops System
==================

In 0.10.4 the `external_nodes` system was upgraded to allow for modular
subsystems to be used to generate the top file data for a highstate run on
the master.

The old `external_nodes` option was deprecated after 0.10.4 and was
completely removed in 2014.1.5.

The master tops system contains a number of subsystems that
are loaded via the Salt loader interfaces like modules, states, returners,
runners, etc.

Using the `master_tops` option is simple:

.. code-block:: yaml

    master_tops:
      ext_nodes: cobbler-external-nodes

for :doc:`Cobbler <../../ref/tops/all/salt.tops.cobbler>` or:

.. code-block:: yaml

    master_tops:
      reclass:
        inventory_base_uri: /etc/reclass
        classes_uri: roles

for :doc:`Reclass <../../ref/tops/all/salt.tops.reclass_adapter>`.
