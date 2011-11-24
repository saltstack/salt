===============
Ordering States
===============

When creating salt sls files, it is often important to ensure that they run in
a specific order. While states will always execute in the same order, that
order is not nessisarily defined the way you want it.

A few tools exist in Salt to set up the corect state ordering, these tools
consist of requisite declarations and order options.

The Order Option
================

Before using the order option, remember that the majority of state ordering
should be done with requisite statements, and that a requisite statement
will override an order option.

The order option is used by adding an order number to a state declaration
with the option `order`:

.. code-block:: yaml
    vim:
      pkg:
        - installed
        - order: 1

By adding the order option to `1` this ensures that the vim package will be
installed in tandem with any other state declaration set to the order `1`.

Any state declared without an order option will be executed after all states
with order options are executed.
