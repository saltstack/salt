.. _targeting-pillar:

======
Pillar
======

Values stored in :ref:`Pillar <pillar>` data can be matched using the same
notation as :doc:`Grains </topics/targeting/grains>`.

.. code-block:: bash

    salt -I 'role:appserver' test.ping

Like :doc:`Grains </topics/targeting/grains>`, globbing and nested data
structures are also supported.

For example, assume a pillar variable ``appdata``, itself containing a
dictionary of application names. For each app, there is yet another dictionary,
containing key/value mappings. The SLS for such a pillar would look like this:

.. code-block:: yaml

    appdata:
        foo_app:
            foo: bar
        bar_app:
            foo: 123
        baz_app:
            foo: abc
            
To match hosts where the ``foo`` variable of ``foo_app`` begins with ``'ba'``
(which would match both ``bar`` and ``baz``), the following could be used:

.. code-block:: bash

    salt -I 'appdata:foo_app:foo:ba*' test.ping
