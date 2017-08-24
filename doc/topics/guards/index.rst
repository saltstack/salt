.. _guards:

.. index:: ! Guards, Salt Guards

===========
Salt Guards
===========

The Salt guards subsystem hooks into the Salt state compiler
and allows specifying custom checks to execute before running states.
Guard modules can specify checks to run against each lowstate chunk,
which will cause the execution of that state to fail,
or checks that run against multiple chunks (e.g. during highstate),
which will raise errors before any of those chunks run.

This is useful for specifying custom lints or policy at a more granular level
than enabling or disabling states, and less intrusively than adding specific
pillar overrides functionality in state modules themselves.

Guard modules can be enabled and configured via Salt minion options.
A few guard modules are included for purposes of demonstration:

- A `noop` module that simply logs the arguments passed to it,
  which is useful for developing new modules without reading
  through the details of the Salt state compiler itself.

- A module which checks for multiple states managing the same AWS resource,
  added in response to a real issue caused by running into rate limits
  due to duplicate states for the same resource.

Guard functions are executed against lowstate chunks instead of highstate data
to prevent re-implementing Salt compiler functionality, like expanding `names`.
However, in the future this may be extended to add new 'guard types'
that are run at different points in the compiler flow,
e.g. to check the requisites of a state or usage of `pkgs` over `names`
for installing packages, which would need to run earlier.

Salt State Compiler
===================

The guard subystem is part of the Salt state compiler.
More documentation is available at the links below,
but at a high level the state compiler takes user-specified SLS code
and transforms it via a number of operations into a set of `chunks`,
each of which has the complete information required for a single state call.

.. seealso::

   :ref:`Overview of State System Layers<state-layers>`

   :ref:`State System Tutorial<state-compiler-tutorial>`


Configuration
=============

Guards can be enabled in the minion options, as well as via the pillar.
All guards from both sources will be run; neither location can override
or update the other to avoid skirting around guards.

To enable, set the `guards` key to a list of guard modules names.
# TODO: enable configuring guards

A complete example
------------------

Put this into your minion configuration:

.. code-block:: yaml

  guards:
    - noop


Writing guard modules
=====================

Most installations that use guards are expected to write custom guards.
The current API is two required top-level functions in each guard module,
`check_chunks` and `check_state`.
Each function takes one parameter; `check_state` is called once for each
lowstate chunk, while `check_chunks` is called on the entire lowstate.
Each function should return a list of strings, each of which should
be an error message indicating the failed safety check.

Guard modules should be read-only and should avoid mutating the passed-in data.
They currently do not have access to utils or execution modules,
as the intent is for them to do pure checking of the chunk data structures.

To avoid having to learn the details of the Salt state compiler,
it is recommended to enable the `noop` guard and run Salt in test mode with
debug logging enabled. The `noop` guard will show you the data structure
available to work with in the guard module.
