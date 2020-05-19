=====================
salt.renderers.yamlex
=====================

YAMLEX renderer is a replacement of the YAML renderer.
It's 100% YAML with a pinch of Salt magic:

* All mappings are automatically OrderedDict
* All strings are automatically str obj
* data aggregation with !aggregation yaml tag, based on the ``salt.utils.aggregation`` module.
* data aggregation over documents for pillar

Instructed aggregation within the ``!aggregation`` and the ``!reset`` tags:

.. code-block:: yaml

    #!yamlex
    foo: !aggregate first
    foo: !aggregate second
    bar: !aggregate {first: foo}
    bar: !aggregate {second: bar}
    baz: !aggregate 42
    qux: !aggregate default
    !reset qux: !aggregate my custom data

is roughly equivalent to

.. code-block:: yaml

    foo: [first, second]
    bar: {first: foo, second: bar}
    baz: [42]
    qux: [my custom data]


Reference
---------

.. automodule:: salt.renderers.yamlex
    :members: