.. _master-tops-system:

==================
Master Tops System
==================

In 0.10.4 the `external_nodes` system was upgraded to allow for modular
subsystems to be used to generate the top file data for a :ref:`highstate
<running-highstate>` run on the master.

The old `external_nodes` option has been removed. The master tops system
provides a pluggable and extendable replacement for it, allowing for multiple
different subsystems to provide top file data.

Using the new `master_tops` option is simple:

.. code-block:: yaml

    master_tops:
      ext_nodes: cobbler-external-nodes

for :mod:`Cobbler <salt.tops.cobbler>` or:

.. code-block:: yaml

    master_tops:
      reclass:
        inventory_base_uri: /etc/reclass
        classes_uri: roles

for :mod:`Reclass <salt.tops.reclass_adapter>`.

.. code-block:: yaml

    master_tops:
      varstack: /path/to/the/config/file/varstack.yaml

for :mod:`Varstack <salt.tops.varstack>`.

It's also possible to create custom master_tops modules. Simply place them into
``salt://_tops`` in the Salt fileserver and use the
:py:func:`saltutil.sync_tops <salt.runners.saltutil.sync_tops>` runner to sync
them. If this runner function is not available, they can manually be placed
into ``extmods/tops``, relative to the master cachedir (in most cases the full
path will be ``/var/cache/salt/master/extmods/tops``).

Custom tops modules are written like any other execution module, see the source
for the two modules above for examples of fully functional ones. Below is a
bare-bones example:

**/etc/salt/master:**

.. code-block:: yaml

   master_tops:
     customtop: True

**customtop.py:** (custom master_tops module)

.. code-block:: python

    import logging
    import sys
    # Define the module's virtual name
    __virtualname__ = 'customtop'

    log = logging.getLogger(__name__)


    def __virtual__():
        return __virtualname__


    def top(**kwargs):
        log.debug('Calling top in customtop')
        return {'base': ['test']}

`salt minion state.show_top` should then display something like:

.. code-block:: bash

   $ salt minion state.show_top

   minion
       ----------
       base:
         - test

.. note::
    If a master_tops module returns :ref:`top file <states-top>` data for a
    given minion, it will be added to the states configured in the top file. It
    will *not* replace it altogether. The Nitrogen release adds additional
    functionality allowing a minion to treat master_tops as the single source
    of truth, irrespective of the top file.
