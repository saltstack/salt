==================
Master Tops System
==================

In 0.10.4 the `external_nodes` system was upgraded to allow for modular
subsystems to be used to generate the top file data for a highstate run on
the master.

The old `external_nodes` option still works, but will be removed in the
future in favor of the new `master_tops` option which uses the modular
system instead. The master tops system contains a number of subsystems that
are loaded via the Salt loader interfaces like modules, states, returners,
runners, etc.

Using the new `master_tops` option is simple:

.. code-block:: yaml

    master_tops:
      ext_nodes: cobbler-external-nodes
