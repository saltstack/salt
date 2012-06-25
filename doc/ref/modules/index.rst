=======
Modules
=======

Salt modules are the functions called by the :command:`salt` command.

.. seealso:: :ref:`Full list of builtin modules <all-salt.modules>`

    Salt ships with many modules that cover a wide variety of tasks.

Easy Modules to write
=====================

Salt modules are amazingly simple to write. Just write a regular Python module
or a regular `Cython`_ module and place it in the ``salt/modules`` directory. You
can also place them in a directory called ``_modules/`` in your state directory.

Since Salt modules are just Python/Cython modules, there are no restraints on
what you can put inside of a Salt module. If a Salt module has errors and
cannot be imported, the Salt minion will continue to load without issue and the
module with errors will simply be omitted.

If adding a Cython module the file must be named ``<modulename>.pyx`` so that
the loader knows that the module needs to be imported as a Cython module. The
compilation of the Cython module is automatic and happens when the minion
starts, so only the ``*.pyx`` file is required.

.. _`Cython`: http://cython.org/

Cross Calling Modules
=====================

All of the Salt modules are available to each other, and can be "cross called".
This means that, when creating a module, functions in modules that already exist
can be called.

The variable ``__salt__`` is packed into the modules after they are loaded into
the Salt minion. This variable is a `Python dictionary`_ of all of the Salt
functions, laid out in the same way that they are made available to the Salt
command.

Salt modules can be cross called by accessing the value in the ``__salt__``
dict:

.. code-block:: python

    def foo(bar):
        return __salt__['cmd.run'](bar)

This code will call the Salt cmd module's ``run`` function and pass the argument
``bar``.

.. _`Python dictionary`: http://docs.python.org/library/stdtypes.html#typesmapping

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
and operating system. This information is referred to as Salt Grains, or
"grains of salt". The Grains system was introduced to replace Facter, since
relying on a Ruby application from a Python application was both slow and
inefficient. Grains support replaces Facter in all Salt releases after 0.8

The values detected by the Salt Grains on the minion are available in a `dict`_
named ``__grains__`` and can be accessed from within callable objects in
the Python modules.

To see the contents of the grains dict for a given system in your deployment
run the :func:`grains.items` function:

.. code-block:: bash

    salt 'hostname' grains.items

To use the ``__grains__`` dict simply call it as a Python dict from within your
code, an excellent example is available in the Grains module:
:mod:`salt.modules.grains`.

.. _`dict`: http://docs.python.org/library/stdtypes.html#typesmapping

Module Configuration
--------------------

Since parameters for configuring a module may be desired, Salt allows for
configuration information stored in the main minion config file to be passed to
the modules.

Since the minion configuration file is a YAML document, arbitrary configuration
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

Printout Configuration
======================

Since module functions can return different data, and the way the data is
printed can greatly change the presentation, Salt has a printout
configuration.

When writing a module the ``__outputter__`` dict can be declared in the module.
The ``__outputter__`` dict contains a mapping of function name to Salt
Outputter.

.. code-block:: python

    __outputter__ = {
                    'run': 'txt'
                    }

This will ensure that the text outputter is used.

Virtual Modules
===============

Sometimes a module should be presented in a generic way. A good example of this
can be found in the package manager modules. The package manager changes from
one operating system to another, but the Salt module that interfaces with the
package manager can be presented in a generic way.

The Salt modules for package managers all contain a ``__virtual__`` function
which is called to define what systems the module should be loaded on.

The ``__virtual__`` function is used to return either a `string`_ or `False`_. If
False is returned then the module is not loaded, if a string is returned then
the module is loaded with the name of the string.

This means that the package manager modules can be presented as the ``pkg`` module
regardless of what the actual module is named.

The package manager modules are the best example of using the ``__virtual__``
function:
:blob:`salt/modules/pacman.py`
:blob:`salt/modules/yumpkg.py`
:blob:`salt/modules/apt.py`

.. _`string`: http://docs.python.org/library/stdtypes.html#typesseq
.. _`False`: http://docs.python.org/library/constants.html#False

Documentation
=============

Salt modules are self documenting, the :func:`sys.doc` function will return the
documentation for all available Facter modules:

.. code-block:: bash

    salt '*' sys.doc

This function simple prints out the docstrings found in the modules, when
writing Salt modules, please follow the formating conventions for docstrings as
they appear in the other modules.

Adding Documentation to Salt Modules
------------------------------------

Since life is much better with documentation, it is strongly suggested that
all Salt modules have documentation added. Any Salt modules submitted for
inclusion in the main distribution of Salt will be required to have
documentation.

Documenting Salt modules is easy! Just add a `Python docstring`_ to the function.

.. code-block:: python

    def spam(eggs):
        '''
        A function to make some spam with eggs!

        CLI Example::

            salt '*' test.spam eggs
        '''
        return eggs

Now when the sys.doc call is executed the docstring will be cleanly returned
to the calling terminal.

.. _`Python docstring`: #term-docstring

How Functions are Read
======================

In Salt, Python callable objects contained within a module are made available to
the Salt minion for use. The only exception to this rule is a callable object
with a name starting with an underscore ``_``.

Objects Loaded Into the Salt Minion
-----------------------------------

.. code-block:: python

    def foo(bar):
        return bar

    class baz:
        def __init__(self, quo):
            pass

Objects NOT Loaded into the Salt Minion
---------------------------------------

.. code-block:: python

    def _foobar(baz): # Preceded with an _
        return baz

    cheese = {} # Not a callable Python object

Examples of Salt Modules
========================

The existing Salt modules should be fairly easy to read and understand, the
goal of the main distribution's Salt modules is not only to build a set of
functions for Salt, but to stand as examples for building out more Salt
modules.

The existing modules can be found here:
:blob:`salt/modules`

The most simple module is the test module, it contains the simplest Salt
function, ``test.ping``:

.. code-block:: python

    def ping():
        '''
        Just used to make sure the minion is up and responding
        Return True

        CLI Example::

            salt '*' test.ping
        '''
        return True
