=================
Execution Modules
=================

Salt execution modules are the functions called by the :command:`salt` command.

.. note::

    Salt execution modules are different from state modules and cannot be
    called directly within state files.  You must use the :mod:`module <salt.states.module>`
    state module to call execution modules within state runs.

.. seealso:: :ref:`Full list of builtin modules <all-salt.modules>`

Salt ships with many modules that cover a wide variety of tasks.

.. _writing-execution-modules:

Modules Are Easy to Write!
==========================

Writing Salt execution modules is straightforward.

A Salt execution modules is a Python or `Cython`_ module
placed in a directory called ``_modules/``
within the :conf_master:`file_roots` as specified by the master config file. By
default this is `/srv/salt/_modules` on Linux systems.


Modules placed in ``_modules/`` will be synced to the minions when any of the following
Salt functions are called:

* :mod:`state.highstate <salt.modules.state.highstate>`
* :mod:`saltutil.sync_modules <salt.modules.saltutil.sync_modules>`
* :mod:`saltutil.sync_all <salt.modules.saltutil.sync_all>`

Note that a module's default name is its filename
(i.e. ``foo.py`` becomes module ``foo``), but that its name can be overridden
by using a :ref:`__virtual__ function <virtual-modules>`.

If a Salt module has errors and cannot be imported, the Salt minion will continue
to load without issue and the module with errors will simply be omitted.

If adding a Cython module the file must be named ``<modulename>.pyx`` so that
the loader knows that the module needs to be imported as a Cython module. The
compilation of the Cython module is automatic and happens when the minion
starts, so only the ``*.pyx`` file is required.

.. _`Cython`: http://cython.org/

Cross-Calling Modules
=====================

All of the Salt execution modules are available to each other and modules can call
functions available in other execution modules.

The variable ``__salt__`` is packed into the modules after they are loaded into
the Salt minion.

The ``__salt__`` variable is a :ref:`Python dictionary <python2:typesmapping>`
containing all of the Salt functions. Dictionary keys are strings representing the
names of the modules and the values are the functions themselves.

Salt modules can be cross-called by accessing the value in the ``__salt__`` dict:

.. code-block:: python

    def foo(bar):
        return __salt__['cmd.run'](bar)

This code will call the `run` function in the :mod:`cmd <salt.modules.cmdmod>` and pass the argument
``bar`` to it.


Preloaded Execution Module Data
===============================

When interacting with execution modules often it is nice to be able to read information
dynamically about the minion or to load in configuration parameters for a module.

Salt allows for different types of data to be loaded into the modules by the
minion.

Grains Data
-----------

The values detected by the Salt Grains on the minion are available in a
:ref:`dict <python2:typesmapping>` named ``__grains__`` and can be accessed
from within callable objects in the Python modules.

To see the contents of the grains dictionary for a given system in your deployment
run the :func:`grains.items` function:

.. code-block:: bash

    salt 'hostname' grains.items --output=pprint

Any value in a grains dictionary can be accessed as any other Python dictionary. For
example, the grain representing the minion ID is stored in the ``id`` key and from
an execution module, the value would be stored in ``__grains__['id']``.


Module Configuration
--------------------

Since parameters for configuring a module may be desired, Salt allows for
configuration information from the  minion configuration file to be passed to
execution modules.

Since the minion configuration file is a YAML document, arbitrary configuration
data can be passed in the minion config that is read by the modules. It is therefore
**strongly** recommended that the values passed in the configuration file match
the module name. A value intended for the ``test`` execution module should be named
``test.<value>``.

The test execution module contains usage of the module configuration and the default
configuration file for the minion contains the information and format used to
pass data to the modules. :mod:`salt.modules.test`, :file:`conf/minion`.

Printout Configuration
======================

Since execution module functions can return different data, and the way the data is
printed can greatly change the presentation, Salt has a printout configuration.

When writing a module the ``__outputter__`` dictionary can be declared in the module.
The ``__outputter__`` dictionary contains a mapping of function name to Salt
Outputter.

.. code-block:: python

    __outputter__ = {
                    'run': 'txt'
                    }

This will ensure that the text outputter is used.


.. _virtual-modules:

Virtual Modules
===============

Sometimes an execution module should be presented in a generic way. A good example of this
can be found in the package manager modules. The package manager changes from
one operating system to another, but the Salt execution module that interfaces with the
package manager can be presented in a generic way.

The Salt modules for package managers all contain a ``__virtual__`` function
which is called to define what systems the module should be loaded on.

The ``__virtual__`` function is used to return either a
:ref:`string <python2:typesseq>` or :py:data:`False`. If
False is returned then the module is not loaded, if a string is returned then
the module is loaded with the name of the string.

This means that the package manager modules can be presented as the ``pkg`` module
regardless of what the actual module is named.

Since ``__virtual__`` is called before the module is loaded, ``__salt__`` will be
unavailable as it will not have been packed into the module at this point in time.

The package manager modules are among the best example of using the ``__virtual__``
function. Some examples:

- :blob:`pacman.py <salt/modules/pacman.py>`
- :blob:`yumpkg.py <salt/modules/yumpkg.py>`
- :blob:`aptpkg.py <salt/modules/aptpkg.py>`
- :blob:`at.py <salt/modules/at.py>`

.. note::
    Modules which return a string from ``__virtual__`` that is already used by a module that
    ships with Salt will _override_ the stock module.

Returning Error Information from ``__virtual__``
------------------------------------------------

Optionally, modules may additionally return a list of reasons that a module could
not be loaded. For example, if a dependency for 'my_mod' was not met, a
__virtual__ function could do as follows:

 return False, ['My Module must be installed before this module can be
 used.']


Documentation
=============

Salt execution modules are documented. The :func:`sys.doc` function will return the
documentation for all available modules:

.. code-block:: bash

    salt '*' sys.doc

The ``sys.doc`` function simply prints out the docstrings found in the modules; when
writing Salt execution modules, please follow the formatting conventions for docstrings as
they appear in the other modules.

Adding Documentation to Salt Modules
------------------------------------

It is strongly suggested that all Salt modules have documentation added.

To add documentation add a `Python docstring`_ to the function.

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

.. _`Python docstring`: http://docs.python.org/2/glossary.html#term-docstring

Documentation added to execution modules in docstrings will automatically be added
to the online web-based documentation.


Add Execution Module Metadata
-----------------------------

When writing a Python docstring for an execution module, add information about the module
using the following field lists:

.. code-block:: text

    :maintainer:    Thomas Hatch <thatch@saltstack.com, Seth House <shouse@saltstack.com>
    :maturity:      new
    :depends:       python-mysqldb
    :platform:      all

The maintainer field is a comma-delimited list of developers who help maintain
this module.

The maturity field indicates the level of quality and testing for this module.
Standard labels will be determined.

The depends field is a comma-delimited list of modules that this module depends
on.

The platform field is a comma-delimited list of platforms that this module is
known to run on.

Log Output
==========

You can call the logger from custom modules to write messages to the minion
logs. The following code snippet demonstrates writing log messages:

.. code-block:: python

    import logging

    log = logging.getLogger(__name__)

    log.info('Here is Some Information')
    log.warning('You Should Not Do That')
    log.error('It Is Busted')

Private Functions
=================

In Salt, Python callable objects contained within an execution module are made available
to the Salt minion for use. The only exception to this rule is a callable
object with a name starting with an underscore ``_``.

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

.. note::

    Some callable names also end with an underscore ``_``, to avoid keyword clashes
    with Python keywords.  When using execution modules, or state modules, with these
    in them the trailing underscore should be omitted.

Useful Decorators for Modules
=============================

Depends Decorator
-----------------
When writing execution modules there are many times where some of the module will
work on all hosts but some functions have an external dependency, such as a service
that needs to be installed or a binary that needs to be present on the system.

Instead of trying to wrap much of the code in large try/except blocks, a decorator can
be used.

If the dependencies passed to the decorator don't exist, then the salt minion will remove
those functions from the module on that host.

If a "fallback_function" is defined, it will replace the function instead of removing it

.. code-block:: python

    import logging

    from salt.utils.decorators import depends

    log = logging.getLogger(__name__)

    try:
        import dependency_that_sometimes_exists
    except ImportError as e:
        log.trace('Failed to import dependency_that_sometimes_exists: {0}'.format(e))

    @depends('dependency_that_sometimes_exists')
    def foo():
        '''
        Function with a dependency on the "dependency_that_sometimes_exists" module,
        if the "dependency_that_sometimes_exists" is missing this function will not exist
        '''
        return True

    def _fallback():
        '''
        Fallback function for the depends decorator to replace a function with
        '''
        return '"dependency_that_sometimes_exists" needs to be installed for this function to exist'

    @depends('dependency_that_sometimes_exists', fallback_function=_fallback)
    def foo():
        '''
        Function with a dependency on the "dependency_that_sometimes_exists" module.
        If the "dependency_that_sometimes_exists" is missing this function will be
        replaced with "_fallback"
        '''
        return True

In addition to global dependancies the depends decorator also supports raw booleans.

.. code-block:: python

    from salt.utils.decorators import depends

    HAS_DEP = False
    try:
        import dependency_that_sometimes_exists
        HAS_DEP = True
    except ImportError:
        pass

    @depends(HAS_DEP)
    def foo():
        return True
