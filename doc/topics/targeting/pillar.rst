.. _targeting-pillar:

======================
Targeting using Pillar
======================

Pillar data can be used when targeting minions. This allows for ultimate
control and flexibility when targeting minions.

.. note::

    To start using Pillar targeting it is required to make a Pillar
    data cache on Salt Master for each Minion via following commands:
    ``salt '*' saltutil.refresh_pillar`` or ``salt '*' saltutil.sync_all``.
    Also Pillar data cache will be populated during the
    :ref:`highstate <running-highstate>` run. Once Pillar data changes, you
    must refresh the cache by running above commands for this targeting
    method to work correctly.

Example:

.. code-block:: bash

    salt -I 'somekey:specialvalue' test.version

Like with :ref:`Grains <targeting-grains>`, it is possible to use globbing
as well as match nested values in Pillar, by adding colons for each level that
is being traversed. The below example would match minions with a pillar named
``foo``, which is a dict containing a key ``bar``, with a value beginning with
``baz``:

.. code-block:: bash

    salt -I 'foo:bar:baz*' test.version
