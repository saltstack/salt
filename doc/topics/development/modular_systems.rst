===============
Modular Systems
===============

When first working with Salt, it is not always clear where all of the modular
components are and what they do. Salt comes loaded with more modular systems
than many users are aware of, making Salt very easy to extend in many places.

The most commonly used modular systems are execution modules and states. But
the modular systems extend well beyond the more easily exposed components
and are often added to Salt to make the complete system more flexible.

Execution Modules
=================

Execution modules make up the core of the functionality used by Salt to
interact with client systems. The execution modules create the core system
management library used by all Salt systems, including states, which
interact with minion systems.

Execution modules are completely open ended in their execution. They can
be used to do anything required on a minion, from installing packages to
detecting information about the system. The only restraint in execution
modules is that the defined functions always return a JSON serializable
object.

For a list of all built in execution modules, click :ref:`here
<all-salt.modules>`

For information on writing execution modules, see :ref:`this page
<writing-execution-modules>`.


Interactive Debugging
=====================

Sometimes debugging with ``print()`` and extra logs sprinkled everywhere is not
the best strategy.

IPython is a helpful debug tool that has an interactive python environment
which can be embedded in python programs.

First the system will require IPython to be installed.

.. code-block:: bash

    # Debian
    apt-get install ipython

    # Arch Linux
    pacman -Syu ipython2

    # RHEL/CentOS (via EPEL)
    yum install python-ipython


Now, in the troubling python module, add the following line at a location where
the debugger should be started:

.. code-block:: python

    test = 'test123'
    import IPython; IPython.embed_kernel()

After running a Salt command that hits that line, the following will show up in
the log file:

.. code-block:: text

    [CRITICAL] To connect another client to this kernel, use:
    [IPKernelApp] --existing kernel-31271.json

Now on the system that invoked ``embed_kernel``, run the following command from
a shell:

.. code-block:: bash

    # NOTE: use ipython2 instead of ipython for Arch Linux
    ipython console --existing

This provides a console that has access to all the vars and functions, and even
supports tab-completion.

.. code-block:: python

    print(test)
    test123

To exit IPython and continue running Salt, press ``Ctrl-d`` to logout.


State Modules
=============

State modules are used to define the state interfaces used by Salt States.
These modules are restrictive in that they must follow a number of rules to
function properly.

.. note::

    State modules define the available routines in sls files. If calling
    an execution module directly is desired, take a look at the `module`
    state.

Auth
====

The auth module system allows for external authentication routines to be easily
added into Salt. The `auth` function needs to be implemented to satisfy the
requirements of an auth module. Use the ``pam`` module as an example.

Fileserver
==========

The fileserver module system is used to create fileserver backends used by the
Salt Master. These modules need to implement the functions used in the
fileserver subsystem. Use the ``gitfs`` module as an example.

Grains
======

Grain modules define extra routines to populate grains data. All defined
public functions will be executed and MUST return a Python dict object. The
dict keys will be added to the grains made available to the minion.

Output
======

The output modules supply the outputter system with routines to display data
in the terminal. These modules are very simple and only require the `output`
function to execute. The default system outputter is the ``nested`` module.

Pillar
======

Used to define optional external pillar systems. The pillar generated via
the filesystem pillar is passed into external pillars. This is commonly used
as a bridge to database data for pillar, but is also the backend to the libvirt
state used to generate and sign libvirt certificates on the fly.

Renderers
=========

Renderers are the system used to render sls files into salt highdata for the
state compiler. They can be as simple as the ``py`` renderer and as complex as
``stateconf`` and ``pydsl``.

Returners
=========

Returners are used to send data from minions to external sources, commonly
databases. A full returner will implement all routines to be supported as an
external job cache. Use the ``redis`` returner as an example.

Runners
=======

Runners are purely master-side execution sequences.

Tops
====

Tops modules are used to convert external data sources into top file data for
the state system.

Wheel
=====

The wheel system is used to manage master side management routines. These
routines are primarily intended for the API to enable master configuration.
