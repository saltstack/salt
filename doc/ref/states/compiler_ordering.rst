=====================================
Understanding State Compiler Ordering
=====================================

.. note::

    This tutorial is an intermediate level tutorial. Some basic understanding
    of the state system and writing Salt Formulas is assumed.

Salt's state system is built to deliver all of the power of configuration
management systems without sacrificing simplicity. This tutorial is made to
help users understand in detail just how the order is defined for state
executions in Salt.

This tutorial is written to represent the behavior of Salt as of version
0.17.0.

Compiler Basics
===============

To understand ordering in depth some very basic knowledge about the state
compiler is very helpful. No need to worry though, this is very high level!

High Data and Low Data
----------------------

When defining Salt Formulas in YAML the data that is being represented is
referred to by the compiler as High Data. When the data is initially
loaded into the compiler it is a single large python dictionary, this
dictionary can be viewed raw by running:

.. code-block:: bash

    salt '*' state.show_highstate

This "High Data" structure is then compiled down to "Low Data". The Low
Data is what is matched up to create individual executions in Salt's
configuration management system. The
low data is an ordered list of single state calls to execute. Once the
low data is compiled the evaluation order can be seen.

The low data can be viewed by running:

.. code-block:: bash

    salt '*' state.show_lowstate

.. note::

    The state execution module contains MANY functions for evaluating the
    state system and is well worth a read! These routines can be very useful
    when debugging states or to help deepen one's understanding of Salt's
    state system.

As an example, a state written thusly:

.. code-block:: yaml

    apache:
      pkg.installed:
        - name: httpd
      service.running:
        - name: httpd
        - watch:
          - file: apache_conf
          - pkg: apache

    apache_conf:
      file.managed:
        - name: /etc/httpd/conf.d/httpd.conf
        - source: salt://apache/httpd.conf

Will have High Data which looks like this represented in json:

.. code-block:: json

    {
        "apache": {
            "pkg": [
                {
                    "name": "httpd"
                },
                "installed",
                {
                    "order": 10000
                }
            ],
            "service": [
                {
                    "name": "httpd"
                },
                {
                    "watch": [
                        {
                            "file": "apache_conf"
                        },
                        {
                            "pkg": "apache"
                        }
                    ]
                },
                "running",
                {
                    "order": 10001
                }
            ],
            "__sls__": "blah",
            "__env__": "base"
        },
        "apache_conf": {
            "file": [
                {
                    "name": "/etc/httpd/conf.d/httpd.conf"
                },
                {
                    "source": "salt://apache/httpd.conf"
                },
                "managed",
                {
                    "order": 10002
                }
            ],
            "__sls__": "blah",
            "__env__": "base"
        }
    }

The subsequent Low Data will look like this:

.. code-block:: json

    [
        {
            "name": "httpd",
            "state": "pkg",
            "__id__": "apache",
            "fun": "installed",
            "__env__": "base",
            "__sls__": "blah",
            "order": 10000
        },
        {
            "name": "httpd",
            "watch": [
                {
                    "file": "apache_conf"
                },
                {
                    "pkg": "apache"
                }
            ],
            "state": "service",
            "__id__": "apache",
            "fun": "running",
            "__env__": "base",
            "__sls__": "blah",
            "order": 10001
        },
        {
            "name": "/etc/httpd/conf.d/httpd.conf",
            "source": "salt://apache/httpd.conf",
            "state": "file",
            "__id__": "apache_conf",
            "fun": "managed",
            "__env__": "base",
            "__sls__": "blah",
            "order": 10002
        }
    ]

This tutorial discusses the Low Data evaluation and the state runtime.

Ordering Layers
===============

Salt defines 2 order interfaces which are evaluated in the state runtime and
defines these orders in a number of passes.

Definition Order
----------------

.. note::

    The Definition Order system can be disabled by turning the option
    ``state_auto_order`` to ``False`` in the master configuration file.

The top level of ordering is the `Definition Order`. The `Definition Order`
is the order in which states are defined in salt formulas. This is very
straightforward on basic states which do not contain ``include`` statements
or a ``top`` file, as the states are just ordered from the top of the file,
but the include system starts to bring in some simple rules for how the
`Definition Order` is defined.

Looking back at the "Low Data" and "High Data" shown above, the order key has
been transparently added to the data to enable the `Definition Order`.

The Include Statement
~~~~~~~~~~~~~~~~~~~~~

Basically, if there is an include statement in a formula, then the formulas
which are included will be run BEFORE the contents of the formula which
is including them. Also, the include statement is a list, so they will be
loaded in the order in which they are included.

In the following case:

``foo.sls``

.. code-block:: yaml

    include:
      - bar
      - baz

``bar.sls``

.. code-block:: yaml

    include:
      - quo

``baz.sls``

.. code-block:: yaml

    include:
      - qux

In the above case if ``state.apply foo`` were called then the formulas will be
loaded in the following order:

1. quo
2. bar
3. qux
4. baz
5. foo

The `order` Flag
----------------

The `Definition Order` happens transparently in the background, but the
ordering can be explicitly overridden using the ``order`` flag in states:

.. code-block:: yaml

    apache:
      pkg.installed:
        - name: httpd
        - order: 1

This order flag will over ride the definition order, this makes it very
simple to create states that are always executed first, last or in specific
stages, a great example is defining a number of package repositories that
need to be set up before anything else, or final checks that need to be
run at the end of a state run by using ``order: last`` or ``order: -1``.

When the order flag is explicitly set the `Definition Order` system will omit
setting an order for that state and directly use the order flag defined.

Lexicographical Fall-back
-------------------------

Salt states were written to ALWAYS execute in the same order. Before the
introduction of `Definition Order` in version 0.17.0 everything was ordered
lexicographically according to the name of the state, then function then id.

This is the way Salt has always ensured that states always run in the same
order regardless of where they are deployed, the addition of the
`Definition Order` method mealy makes this finite ordering easier to follow.

The lexicographical ordering is still applied but it only has any effect when
two order statements collide. This means that if multiple states are assigned
the same order number that they will fall back to lexicographical ordering
to ensure that every execution still happens in a finite order.

.. note::

    If running with ``state_auto_order: False`` the ``order`` key is not
    set automatically, since the Lexicographical order can be derived
    from other keys.

Requisite Ordering
------------------

Salt states are fully declarative, in that they are written to declare the
state in which a system should be. This means that components can require that
other components have been set up successfully. Unlike the other ordering
systems, the `Requisite` system in Salt is evaluated at runtime.

The requisite system is also built to ensure that the ordering of execution
never changes, but is always the same for a given set of states. This is
accomplished by using a runtime that processes states in a completely
predictable order instead of using an event loop based system like other
declarative configuration management systems.

Runtime Requisite Evaluation
----------------------------

The requisite system is evaluated as the components are found, and the
requisites are always evaluated in the same order. This explanation will
be followed by an example, as the raw explanation may be a little dizzying
at first as it creates a linear dependency evaluation sequence.

The "Low Data" is an ordered list or dictionaries, the state runtime evaluates
each dictionary in the order in which they are arranged in the list. When
evaluating a single dictionary it is checked for requisites, requisites are
evaluated in order, ``require`` then ``watch`` then ``prereq``.

.. note::

    If using requisite in statements like require_in and watch_in these will
    be compiled down to require and watch statements before runtime evaluation.

Each requisite contains an ordered list of requisites, these requisites are
looked up in the list of dictionaries and then executed. Once all requisites
have been evaluated and executed then the requiring state can safely be run
(or not run if requisites have not been met).

This means that the requisites are always evaluated in the same order, again
ensuring one of the core design principals of Salt's State system to ensure
that execution is always finite is intact.

Simple Runtime Evaluation Example
---------------------------------

Given the above "Low Data" the states will be evaluated in the following order:

1. The pkg.installed is executed ensuring that the apache package is
   installed, it contains no requisites and is therefore the first defined
   state to execute.
2. The service.running state is evaluated but NOT executed, a watch requisite
   is found, therefore they are read in order, the runtime first checks for
   the file, sees that it has not been executed and calls for the file state
   to be evaluated.
3. The file state is evaluated AND executed, since it, like the pkg state does
   not contain any requisites.
4. The evaluation of the service state continues, it next checks the pkg
   requisite and sees that it is met, with all requisites met the service
   state is now executed.

Best Practice
-------------

The best practice in Salt is to choose a method and stick with it, official
states are written using requisites for all associations since requisites
create clean, traceable dependency trails and make for the most portable
formulas. To accomplish something similar to how classical imperative
systems function all requisites can be omitted and the ``failhard`` option
then set to ``True`` in the master configuration, this will stop all state runs at
the first instance of a failure.

In the end, using requisites creates very tight and fine grained states,
not using requisites makes full sequence runs and while slightly easier
to write, and gives much less control over the executions.
