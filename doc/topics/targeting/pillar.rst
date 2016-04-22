.. _targeting-pillar:

======================
Targeting using Pillar
======================

Pillar data can be used when targeting minions. This allows for ultimate
control and flexibility when targeting minions.

.. code-block:: bash

    salt -I 'somekey:specialvalue' test.ping

Like with :ref:`Grains <targeting-grains>`, it is possible to use globbing
as well as match nested values in Pillar, by adding colons for each level that
is being traversed. The below example would match minions with a pillar named
``foo``, which is a dict containing a key ``bar``, with a value beginning with
``baz``:

.. code-block:: bash

    salt -I 'foo:bar:baz*' test.ping
