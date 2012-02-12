===============
Ordering States
===============

When creating salt sls files, it is often important to ensure that they run in
a specific order. While states will always execute in the same order, that
order is not necessarily defined the way you want it.

A few tools exist in Salt to set up the correct state ordering. These tools
consist of requisite declarations and order options.

.. note:: 

    Salt does **not** execute :term:`state declarations <state declaration>` in
    the order they appear in the source.

The Order Option
================

Before using the order option, remember that the majority of state ordering
should be done with a :term:`requisite declaration`, and that a requisite
declaration will override an order option.

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

But this construct can only handle ordering states from the beginning.
Sometimes you may want to send a state to the end of the line. To do this,
set the order to ``last``:

.. code-block:: yaml

    vim:
      pkg:
        - installed
        - order: last
