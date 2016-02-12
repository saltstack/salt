.. _state-layers:

===================
State System Layers
===================

The Salt state system is comprised of multiple layers. While using Salt does
not require an understanding of the state layers, a deeper understanding of
how Salt compiles and manages states can be very beneficial.

.. _state-layers-function-call:

Function Call
=============

The lowest layer of functionality in the state system is the direct state
function call. State executions are executions of single state functions at
the core. These individual functions are defined in state modules and can
be called directly via the ``state.single`` command.

.. code-block:: bash

    salt '*' state.single pkg.installed name='vim'

.. _state-layers-low-chunk:

Low Chunk
=========

The low chunk is the bottom of the Salt state compiler. This is a data
representation of a single function call. The low chunk is sent to the state
caller and used to execute a single state function.

A single low chunk can be executed manually via the ``state.low`` command.

.. code-block:: bash

    salt '*' state.low '{name: vim, state: pkg, fun: installed}'

The passed data reflects what the state execution system gets after compiling
the data down from sls formulas.

.. _state-layers-low-state:

Low State
=========

The `Low State` layer is the list of low chunks "evaluated" in order. To see
what the low state looks like for a highstate, run:

.. code-block:: bash

    salt '*' state.show_lowstate

This will display the raw lowstate in the order which each low chunk will be
evaluated. The order of evaluation is not necessarily the order of execution,
since requisites are evaluated at runtime. Requisite execution and evaluation
is finite; this means that the order of execution can be ascertained with 100%
certainty based on the order of the low state.

.. _state-layers-high-data:

High Data
=========

High data is the data structure represented in YAML via SLS files. The High
data structure is created by merging the data components rendered inside sls
files (or other render systems). The High data can be easily viewed by
executing the ``state.show_highstate`` or ``state.show_sls`` functions. Since
this data is a somewhat complex data structure, it may be easier to read using
the json, yaml, or pprint outputters:

.. code-block:: bash

    salt '*' state.show_highstate --out yaml
    salt '*' state.show_sls edit.vim --out pprint

.. _state-layers-sls:

SLS
===

Above "High Data", the logical layers are no longer technically required to be
executed, or to be executed in a hierarchy. This means that how the High data
is generated is optional and very flexible. The SLS layer allows for many
mechanisms to be used to render sls data from files or to use the fileserver
backend to generate sls and file data from external systems.

The SLS layer can be called directly to execute individual sls formulas.

.. note::

    SLS Formulas have historically been called "SLS files". This is because a
    single SLS was only constituted in a single file. Now the term
    "SLS Formula" better expresses how a compartmentalized SLS can be expressed
    in a much more dynamic way by combining pillar and other sources, and the
    SLS can be dynamically generated.

To call a single SLS formula named ``edit.vim``, execute ``state.sls``:

.. code-block:: bash

    salt '*' state.sls edit.vim

.. _state-layers-highstate:

HighState
=========

Calling SLS directly logically assigns what states should be executed from the
context of the calling minion. The Highstate layer is used to allow for full
contextual assignment of what is executed where to be tied to groups of, or
individual, minions entirely from the master. This means that the environment of
a minion, and all associated execution data pertinent to said minion, can be
assigned from the master without needing to execute or configure anything on
the target minion. This also means that the minion can independently retrieve
information about its complete configuration from the master.

To execute the High State call ``state.highstate``:

.. code-block:: bash

    salt '*' state.highstate

.. _state-layers-orchestrate:

Orchestrate
===========

The orchestrate layer expresses the highest functional layer of Salt's automated
logic systems. The Overstate allows for stateful and functional orchestration
of routines from the master. The orchestrate defines in data execution stages
which minions should execute states, or functions, and in what order using
requisite logic.