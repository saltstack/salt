==================
Master Tops System
==================

In 0.10.4 the `external_nodes` system was upgraded to allow for modular
subsystems to be used to generate the top file data for a :ref:`highstate
<running-highstate>` run on the master.

The old `external_nodes` option has been removed.
The master tops system contains a number of subsystems that
are loaded via the Salt loader interfaces like modules, states, returners,
runners, etc.

Using the new `master_tops` option is simple:

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

.. code-block:: yaml

    master_tops:
      varstack: /path/to/the/config/file/varstack.yaml

for :doc:`Varstack <../../ref/tops/all/salt.tops.varstack>`.

It's also possible to create custom master_tops modules. These modules must go
in a subdirectory called `tops` in the `extension_modules` directory.
The `extension_modules` directory is not defined by default (the
default `/srv/salt/_modules` will NOT work as of this release)

Custom tops modules are written like any other execution module, see the source
for the two modules above for examples of fully functional ones. Below is
a degenerate example:

/etc/salt/master:

.. code-block:: yaml

   extension_modules: /srv/salt/modules
   master_tops:
     customtop: True

/srv/salt/modules/tops/customtop.py:

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
