=======
Modules
=======

Salt modules are the functions called by the :command:`salt` command.

Full list of builtin modules
============================

.. toctree::
    :maxdepth: 1
    :glob:

    *

Easy Modules to write
=====================

Salt modules are amazingly simple to write, just write a regular Python module
or a regular Cython module and place it in the ``salt/modules`` directory.

Since Salt modules are just Python/Cython modules there are no restraints as to
what you can put inside of a salt module, and if a Salt module has errors and
cannot import the Salt minion will continue to load without issue, the module
with errors will simply be omitted.

If adding a Cython module the file must be named ``<modulename>.pyx`` so that
the loader knows that the module needs to be imported as a Cython module. The
compilation of the Cython module is automatic and happens when the minion
starts, so only the ``*.pyx`` file is required.

Preloaded Modules Data
======================

When interacting with modules often it is nice to be able to read information
dynamically about the minion, or load in configuration parameters for a module.
Salt allows for different types of data to be loaded into the modules by the
minion, as of this writing Salt loads information gathered from the Salt Grains
system and from the minion configuration file.

Grains Data
-----------

The Salt minion detects information about the system when started. This allows
for modules to be written dynamically with respect to the underlying hardware
and OS. This information is referred to as Salt Grains, or "grains of salt".
The Grains system was introduced to replace Facter, since relying on a Ruby
application from a Python application was both slow and inefficient. Grains
support replaces Facter in all releases after 0.8

The values detected by the Salt Grains on the minion are available in a dict by
the name of ``__grains__`` and can be accessed from within callable objects in
the Python modules.

To see the contents of the grains dict for a given system in your deployment
run the :func:`grains.items` function:

.. code-block:: bash

    salt 'hostname' grains.items

To use the ``__grains__`` dict simply call it as a Python dict from within your
code, an excellent example is available in the Grains module:
:mod:`salt.modules.grains`.

Module Configuration
--------------------

Since parameters for configuring a module may be desired, Salt allows for
configuration information stored in the main minion config file to be passed to
the modules.

Since the minion configuration file is a yaml document, arbitrary configuration
data can be passed in the minion config that is read by the modules. It is
**strongly** recommended that the values passed in the configuration file match
the module. This means that a value intended for the ``test`` module should be
named ``test.<value>``.

Configuration also requires that default configuration parameters need to be
loaded as well. This can be done simply by adding the ``__opts__`` dict to the
top level of the module.

The test module contains usage of the module configuration, and the default
configuration file for the minion contains the information and format used to
pass data to the modules. :mod:`salt.modules.test`, :file:`conf/minion`.

Documentation
=============

Salt modules are self documenting, the :func:`sys.doc` function will return the
documentation for all available Facter modules:

.. code-block:: bash

    salt '*' sys.doc

This function simple prints out the docstrings found in the modules, when
writing salt modules, please follow the formating conventions for docstrings as
they appear in the other modules.

How Functions are Read
======================

In Salt Python callable objects contained within a module are made available to
the Salt minion for use. The only exception to this rule is a callable object
with a name starting with an underscore ``_``.

Objects Loaded Into the Salt Minion
-----------------------------------

.. code-block:: python

    def foo(bar):
        return bar

    class baz:
        def __init__(self, quo):
            return quo

Objects NOT Loaded into the Salt Minion
---------------------------------------

.. code-block:: python

    def _foobar(baz): # Preceded with an _
        return baz

    cheese = {} # Not a callable python object
