.. _ordering:

===============
Ordering States
===============

The way in which configuration management systems are executed is a hotly
debated topic in the configuration management world. Two
major philosophies exist on the subject, to either execute in an imperative
fashion where things are executed in the order in which they are defined, or
in a declarative fashion where dependencies need to be mapped between objects.

Imperative ordering is finite and generally considered easier to write, but
declarative ordering is much more powerful and flexible but generally considered
more difficult to create.

Salt has been created to get the best of both worlds. States are evaluated in
a finite order, which guarantees that states are always executed in the same
order, and the states runtime is declarative, making Salt fully aware of
dependencies via the `requisite` system.

.. _ordering_auto_order:

State Auto Ordering
===================

.. versionadded: 0.17.0

Salt always executes states in a finite manner, meaning that they will always
execute in the same order regardless of the system that is executing them.
But in Salt 0.17.0, the ``state_auto_order`` option was added. This option
makes states get evaluated in the order in which they are defined in sls
files, including the top.sls file.

The evaluation order makes it easy to know what order the states will be
executed in, but it is important to note that the requisite system will
override the ordering defined in the files, and the ``order`` option described
below will also override the order in which states are defined in sls files.

If the classic ordering is preferred (lexicographic), then set
``state_auto_order`` to ``False`` in the master configuration file. Otherwise,
``state_auto_order`` defaults to ``True``.


.. _ordering_requisites:

Requisite Statements
====================

.. note::

    This document represents behavior exhibited by Salt requisites as of
    version 0.9.7 of Salt.

Often when setting up states any single action will require or depend on
another action. Salt allows for the building of relationships between states
with requisite statements. A requisite statement ensures that the named state
is evaluated before the state requiring it. There are three types of requisite
statements in Salt, **require**, **watch**, and **prereq**.

These requisite statements are applied to a specific state declaration:

.. code-block:: yaml

    httpd:
      pkg.installed: []
      file.managed:
        - name: /etc/httpd/conf/httpd.conf
        - source: salt://httpd/httpd.conf
        - require:
          - pkg: httpd

In this example, the **require** requisite is used to declare that the file
/etc/httpd/conf/httpd.conf should only be set up if the pkg state executes
successfully.

The requisite system works by finding the states that are required and
executing them before the state that requires them. Then the required states
can be evaluated to see if they have executed correctly.

Require statements can refer to any state defined in Salt. The basic examples
are `pkg`, `service`, and `file`, but any used state can be referenced.

In addition to state declarations such as pkg, file, etc., **sls** type requisites
are also recognized, and essentially allow 'chaining' of states. This provides a
mechanism to ensure the proper sequence for complex state formulas, especially when
the discrete states are split or groups into separate sls files:

.. code-block:: yaml

    include:
      - network

    httpd:
      pkg.installed: []
      service.running:
        - require:
          - pkg: httpd
          - sls: network

In this example, the httpd service running state will not be applied
(i.e., the httpd service will not be started) unless both the httpd package is
installed AND the network state is satisfied.

.. note:: Requisite matching

    Requisites match on both the ID Declaration and the ``name`` parameter.
    Therefore, if using the ``pkgs`` or ``sources`` argument to install
    a list of packages in a pkg state, it's important to note that it is
    impossible to match an individual package in the list, since all packages
    are installed as a single state.


Multiple Requisites
-------------------

The requisite statement is passed as a list, allowing for the easy addition of
more requisites. Both requisite types can also be separately declared:

.. code-block:: yaml

    httpd:
      pkg.installed: []
      service.running:
        - enable: True
        - watch:
          - file: /etc/httpd/conf/httpd.conf
        - require:
          - pkg: httpd
          - user: httpd
          - group: httpd
      file.managed:
        - name: /etc/httpd/conf/httpd.conf
        - source: salt://httpd/httpd.conf
        - require:
          - pkg: httpd
      user.present: []
      group.present: []

In this example, the httpd service is only going to be started if the package,
user, group, and file are executed successfully.


Requisite Documentation
-----------------------

For detailed information on each of the individual requisites, :ref:`please
look here. <requisites>`


The Order Option
================

Before using the `order` option, remember that the majority of state ordering
should be done with a :ref:`requisite-declaration`, and that a requisite
declaration will override an `order` option, so a state with order option
should not require or required by other states.

The order option is used by adding an order number to a state declaration
with the option `order`:

.. code-block:: yaml

    vim:
      pkg.installed:
        - order: 1

By adding the order option to `1` this ensures that the vim package will be
installed in tandem with any other state declaration set to the order `1`.

Any state declared without an order option will be executed after all states
with order options are executed.

But this construct can only handle ordering states from the beginning.
Certain circumstances will present a situation where it is desirable to send
a state to the end of the line. To do this, set the order to ``last``:

.. code-block:: yaml

    vim:
      pkg.installed:
        - order: last
