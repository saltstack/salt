.. _writing-execution-modules:

=========================
Writing Execution Modules
=========================

Salt execution modules are the functions called by the :command:`salt` command.

Modules Are Easy to Write!
==========================

Writing Salt execution modules is straightforward.

A Salt execution module is a Python or `Cython`_ module placed in a directory
called ``_modules/`` at the root of the Salt fileserver. When using the default
fileserver backend (i.e. :py:mod:`roots <salt.fileserver.roots>`), unless
environments are otherwise defined in the :conf_master:`file_roots` config
option, the ``_modules/`` directory would be located in ``/srv/salt/_modules``
on most systems.

Modules placed in ``_modules/`` will be synced to the minions when any of the
following Salt functions are called:

* :mod:`state.highstate <salt.modules.state.highstate>` (or :mod:`state.apply
  <salt.modules.state.apply_>` with no state argument)
* :mod:`saltutil.sync_modules <salt.modules.saltutil.sync_modules>`
* :mod:`saltutil.sync_all <salt.modules.saltutil.sync_all>`

Modules placed in ``_modules/`` will be synced to masters when any of the
following Salt runners are called:

* :mod:`saltutil.sync_modules <salt.runners.saltutil.sync_modules>`
* :mod:`saltutil.sync_all <salt.runners.saltutil.sync_all>`

Note that a module's default name is its filename
(i.e. ``foo.py`` becomes module ``foo``), but that its name can be overridden
by using a :ref:`__virtual__ function <virtual-modules>`.

If a Salt module has errors and cannot be imported, the Salt minion will continue
to load without issue and the module with errors will simply be omitted.

If adding a Cython module the file must be named ``<modulename>.pyx`` so that
the loader knows that the module needs to be imported as a Cython module. The
compilation of the Cython module is automatic and happens when the minion
starts, so only the ``*.pyx`` file is required.

.. _`Cython`: https://cython.org/

Zip Archives as Modules
=======================

Python 2.3 and higher allows developers to directly import zip archives
containing Python code. By setting :conf_minion:`enable_zip_modules` to
``True`` in the minion config, the Salt loader will be able to import ``.zip``
files in this fashion. This allows Salt module developers to package
dependencies with their modules for ease of deployment, isolation, etc.

For a user, Zip Archive modules behave just like other modules.  When executing
a function from a module provided as the file ``my_module.zip``, a user would
call a function within that module as ``my_module.<function>``.

Creating a Zip Archive Module
-----------------------------

A Zip Archive module is structured similarly to a simple `Python package`_.
The ``.zip`` file contains a single directory with the same name as the module.
The module code traditionally in ``<module_name>.py`` goes in
``<module_name>/__init__.py``.  The dependency packages are subdirectories of
``<module_name>/``.

Here is an example directory structure for the ``lumberjack`` module, which has
two library dependencies (``sleep`` and ``work``) to be included.

.. code-block:: bash

    modules $ ls -R lumberjack
    __init__.py     sleep           work

    lumberjack/sleep:
    __init__.py

    lumberjack/work:
    __init__.py

The contents of ``lumberjack/__init__.py`` show how to import and use these
included libraries.

.. code-block:: python

    # Libraries included in lumberjack.zip
    from lumberjack import sleep, work


    def is_ok(person):
        """Checks whether a person is really a lumberjack"""
        return sleep.all_night(person) and work.all_day(person)

Then, create the zip:

.. code-block:: console

    modules $ zip -r lumberjack lumberjack
      adding: lumberjack/ (stored 0%)
      adding: lumberjack/__init__.py (deflated 39%)
      adding: lumberjack/sleep/ (stored 0%)
      adding: lumberjack/sleep/__init__.py (deflated 7%)
      adding: lumberjack/work/ (stored 0%)
      adding: lumberjack/work/__init__.py (deflated 7%)
    modules $ unzip -l lumberjack.zip
    Archive:  lumberjack.zip
      Length     Date   Time    Name
     --------    ----   ----    ----
            0  08-21-15 20:08   lumberjack/
          348  08-21-15 20:08   lumberjack/__init__.py
            0  08-21-15 19:53   lumberjack/sleep/
           83  08-21-15 19:53   lumberjack/sleep/__init__.py
            0  08-21-15 19:53   lumberjack/work/
           81  08-21-15 19:21   lumberjack/work/__init__.py
     --------                   -------
          512                   6 files

Once placed in :conf_master:`file_roots`, Salt users can distribute and use
``lumberjack.zip`` like any other module.

.. code-block:: bash

    $ sudo salt minion1 saltutil.sync_modules
    minion1:
      - modules.lumberjack
    $ sudo salt minion1 lumberjack.is_ok 'Michael Palin'
    minion1:
      True

.. _`Python package`: https://docs.python.org/3/tutorial/modules.html#packages

.. _cross-calling-execution-modules:

Cross Calling Execution Modules
===============================

All of the Salt execution modules are available to each other and modules can
call functions available in other execution modules.

The variable ``__salt__`` is packed into the modules after they are loaded into
the Salt minion.

The ``__salt__`` variable is a :ref:`Python dictionary <python:typesmapping>`
containing all of the Salt functions. Dictionary keys are strings representing
the names of the modules and the values are the functions themselves.

Salt modules can be cross-called by accessing the value in the ``__salt__``
dict:

.. code-block:: python

    def foo(bar):
        return __salt__["cmd.run"](bar)

This code will call the `run` function in the :mod:`cmd <salt.modules.cmdmod>`
module and pass the argument ``bar`` to it.


Calling Execution Modules on the Salt Master
============================================

.. versionadded:: 2016.11.0

Execution modules can now also be called via the :command:`salt-run` command
using the :ref:`salt runner <salt_salt_runner>`.


Preloaded Execution Module Data
===============================

When interacting with execution modules often it is nice to be able to read
information dynamically about the minion or to load in configuration parameters
for a module.

Salt allows for different types of data to be loaded into the modules by the
minion.

Grains Data
-----------

The values detected by the Salt Grains on the minion are available in a
:ref:`Python dictionary <python:typesmapping>` named ``__grains__`` and can be
accessed from within callable objects in the Python modules.

To see the contents of the grains dictionary for a given system in your
deployment run the :func:`grains.items` function:

.. code-block:: bash

    salt 'hostname' grains.items --output=pprint

Any value in a grains dictionary can be accessed as any other Python
dictionary. For example, the grain representing the minion ID is stored in the
``id`` key and from an execution module, the value would be stored in
``__grains__['id']``.


Module Configuration
--------------------

Since parameters for configuring a module may be desired, Salt allows for
configuration information from the  minion configuration file to be passed to
execution modules.

Since the minion configuration file is a YAML document, arbitrary configuration
data can be passed in the minion config that is read by the modules. It is
therefore **strongly** recommended that the values passed in the configuration
file match the module name. A value intended for the ``test`` execution module
should be named ``test.<value>``.

The test execution module contains usage of the module configuration and the
default configuration file for the minion contains the information and format
used to pass data to the modules. :mod:`salt.modules.test`,
:file:`conf/minion`.

.. _module_init:

``__init__`` Function
---------------------

If you want your module to have different execution modes based on minion
configuration, you can use the ``__init__(opts)`` function to perform initial
module setup. The parameter ``opts`` is the complete minion configuration,
as also available in the ``__opts__`` dict.

.. code-block:: python

    """
    Cheese module initialization example
    """


    def __init__(opts):
        """
        Allow foreign imports if configured to do so
        """
        if opts.get("cheese.allow_foreign", False):
            _enable_foreign_products()


Strings and Unicode
===================

An execution  module author should always assume that strings fed to the module
have already decoded from strings into Unicode. In Python 2, these will
be of type 'Unicode' and in Python 3 they will be of type ``str``. Calling
from a state to other Salt sub-systems, should pass Unicode (or bytes if passing binary data). In the
rare event that a state needs to write directly to disk, Unicode should be
encoded to a string immediately before writing to disk. An author may use
``__salt_system_encoding__`` to learn what the encoding type of the system is.
For example, `'my_string'.encode(__salt_system_encoding__')`.


Outputter Configuration
=======================

Since execution module functions can return different data, and the way the
data is printed can greatly change the presentation, Salt allows for a specific
outputter to be set on a function-by-function basis.

This is done be declaring an ``__outputter__`` dictionary in the global scope
of the module.  The ``__outputter__`` dictionary contains a mapping of function
names to Salt :ref:`outputters <all-salt.output>`.

.. code-block:: python

    __outputter__ = {"run": "txt"}

This will ensure that the ``txt`` outputter is used to display output from the
``run`` function.

.. _virtual-modules:

Virtual Modules
===============

Virtual modules let you override the name of a module in order to use the same
name to refer to one of several similar modules. The specific module that is
loaded for a virtual name is selected based on the current platform or
environment.

For example, packages are managed across platforms using the ``pkg`` module.
``pkg`` is a virtual module name that is an alias for the specific package
manager module that is loaded on a specific system (for example, :mod:`yumpkg
<salt.modules.yumpkg>` on RHEL/CentOS systems , and :mod:`aptpkg
<salt.modules.aptpkg>` on Ubuntu).

Virtual module names are set using the ``__virtual__`` function and the
:ref:`virtual name <modules-virtual-name>`.

``__virtual__`` Function
========================

The ``__virtual__`` function returns either a :ref:`string <python:typesseq>`,
:py:data:`True`, :py:data:`False`, or :py:data:`False` with an :ref:`error
string <modules-error-info>`. If a string is returned then the module is loaded
using the name of the string as the virtual name. If ``True`` is returned the
module is loaded using the current module name. If ``False`` is returned the
module is not loaded. ``False`` lets the module perform system checks and
prevent loading if dependencies are not met.

Since ``__virtual__`` is called before the module is loaded, ``__salt__`` will
be unreliable as not all modules will be available at this point in time. The
``__pillar__`` and ``__grains__`` :ref:`"dunder" dictionaries <dunder-dictionaries>`
are available however.

.. note::
    Modules which return a string from ``__virtual__`` that is already used by
    a module that ships with Salt will _override_ the stock module.

.. _modules-error-info:

Returning Error Information from ``__virtual__``
------------------------------------------------

Optionally, Salt plugin modules, such as execution, state, returner, beacon,
etc. modules may additionally return a string containing the reason that a
module could not be loaded.  For example, an execution module called ``cheese``
and a corresponding state module also called ``cheese``, both depending on a
utility called ``enzymes`` should have ``__virtual__`` functions that handle
the case when the dependency is unavailable.

.. code-block:: python

    """
    Cheese execution (or returner/beacon/etc.) module
    """
    try:
        import enzymes

        HAS_ENZYMES = True
    except ImportError:
        HAS_ENZYMES = False


    def __virtual__():
        """
        only load cheese if enzymes are available
        """
        if HAS_ENZYMES:
            return "cheese"
        else:
            return (
                False,
                "The cheese execution module cannot be loaded: enzymes unavailable.",
            )


    def slice():
        pass

.. code-block:: python

    """
    Cheese state module. Note that this works in state modules because it is
    guaranteed that execution modules are loaded first
    """


    def __virtual__():
        """
        only load cheese if enzymes are available
        """
        # predicate loading of the cheese state on the corresponding execution module
        if "cheese.slice" in __salt__:
            return "cheese"
        else:
            return False, "The cheese state module cannot be loaded: enzymes unavailable."

Examples
--------

The package manager modules are among the best examples of using the
``__virtual__`` function. A table of all the virtual ``pkg`` modules can be
found :ref:`here <virtual-pkg>`.

.. _module-provider-override:

Overriding Virtual Module Providers
-----------------------------------

Salt often uses OS grains (``os``, ``osrelease``, ``os_family``, etc.) to
determine which module should be loaded as the virtual module for ``pkg``,
``service``, etc. Sometimes this OS detection is incomplete, with new distros
popping up, existing distros changing init systems, etc. The virtual modules
likely to be affected by this are in the list below (click each item for more
information):

- :ref:`pkg <virtual-pkg>`
- :ref:`service <virtual-service>`
- :ref:`user <virtual-user>`
- :ref:`shadow <virtual-shadow>`
- :ref:`group <virtual-group>`

If Salt is using the wrong module for one of these, first of all, please
`report it on the issue tracker`__, so that this issue can be resolved for a
future release. To make it easier to troubleshoot, please also provide the
:py:mod:`grains.items <salt.modules.grains.items>` output, taking care to
redact any sensitive information.

Then, while waiting for the SaltStack development team to fix the issue, Salt
can be made to use the correct module using the :conf_minion:`providers` option
in the minion config file:

.. code-block:: yaml

    providers:
      service: systemd
      pkg: aptpkg

The above example will force the minion to use the :py:mod:`systemd
<salt.modules.systemd>` module to provide service management, and the
:py:mod:`aptpkg <salt.modules.aptpkg>` module to provide package management.

.. __: https://github.com/saltstack/salt/issues/new

Logging Restrictions
--------------------

As a rule, logging should not be done anywhere in a Salt module before it is
loaded. This rule apples to all code that would run before the ``__virtual__()``
function, as well as the code within the ``__virtual__()`` function itself.

If logging statements are made before the virtual function determines if
the module should be loaded, then those logging statements will be called
repeatedly. This clutters up log files unnecessarily.

Exceptions may be considered for logging statements made at the ``trace`` level.
However, it is better to provide the necessary information by another means.
One method is to :ref:`return error information <modules-error-info>` in the
``__virtual__()`` function.

.. _modules-virtual-name:

``__virtualname__``
===================

``__virtualname__`` is a variable that is used by the documentation build
system to know the virtual name of a module without calling the ``__virtual__``
function. Modules that return a string from the ``__virtual__`` function
must also set the ``__virtualname__`` variable.

To avoid setting the virtual name string twice, you can implement
``__virtual__`` to return the value set for ``__virtualname__`` using a pattern
similar to the following:

.. code-block:: python

   # Define the module's virtual name
   __virtualname__ = "pkg"


   def __virtual__():
       """
       Confine this module to Mac OS with Homebrew.
       """

       if salt.utils.path.which("brew") and __grains__["os"] == "MacOS":
           return __virtualname__
       return False

The ``__virtual__()`` function can return a ``True`` or ``False`` boolean, a tuple,
or a string. If it returns a ``True`` value, this ``__virtualname__`` module-level
attribute can be set as seen in the above example. This is the string that the module
should be referred to as.

When ``__virtual__()`` returns a tuple, the first item should be a boolean and the
second should be a string. This is typically done when the module should not load. The
first value of the tuple is ``False`` and the second is the error message to display
for why the module did not load.

For example:

.. code-block:: python

    def __virtual__():
        """
        Only load if git exists on the system
        """
        if salt.utils.path.which("git") is None:
            return (False, "The git execution module cannot be loaded: git unavailable.")
        else:
            return True

Documentation
=============

Salt execution modules are documented. The :func:`sys.doc` function will return
the documentation for all available modules:

.. code-block:: bash

    salt '*' sys.doc

The ``sys.doc`` function simply prints out the docstrings found in the modules;
when writing Salt execution modules, please follow the formatting conventions
for docstrings as they appear in the other modules.

Adding Documentation to Salt Modules
------------------------------------

It is strongly suggested that all Salt modules have documentation added.

To add documentation add a `Python docstring`_ to the function.

.. code-block:: python

    def spam(eggs):
        """
        A function to make some spam with eggs!

        CLI Example::

            salt '*' test.spam eggs
        """
        return eggs

Now when the sys.doc call is executed the docstring will be cleanly returned
to the calling terminal.

.. _`Python docstring`: https://docs.python.org/3/glossary.html#term-docstring

Documentation added to execution modules in docstrings will automatically be
added to the online web-based documentation.


Add Execution Module Metadata
-----------------------------

When writing a Python docstring for an execution module, add information about
the module using the following field lists:

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

    log.info("Here is Some Information")
    log.warning("You Should Not Do That")
    log.error("It Is Busted")

Aliasing Functions
==================

Sometimes one wishes to use a function name that would shadow a python built-in.
A common example would be ``set()``. To support this, append an underscore to
the function definition, ``def set_():``, and use the ``__func_alias__`` feature
to provide an alias to the function.

``__func_alias__`` is a dictionary where each key is the name of a function in
the module, and each value is a string representing the alias for that function.
When calling an aliased function from a different execution module, state
module, or from the cli, the alias name should be used.

.. code-block:: python

    __func_alias__ = {
        "set_": "set",
        "list_": "list",
    }

Private Functions
=================

In Salt, Python callable objects contained within an execution module are made
available to the Salt minion for use. The only exception to this rule is a
callable object with a name starting with an underscore ``_``.

Objects Loaded Into the Salt Minion
-----------------------------------

.. code-block:: python

    def foo(bar):
        return bar

Objects NOT Loaded into the Salt Minion
---------------------------------------

.. code-block:: python

    def _foobar(baz):  # Preceded with an _
        return baz


    cheese = {}  # Not a callable Python object

Useful Decorators for Modules
=============================

Depends Decorator
-----------------

When writing execution modules there are many times where some of the module
will work on all hosts but some functions have an external dependency, such as
a service that needs to be installed or a binary that needs to be present on
the system.

Instead of trying to wrap much of the code in large try/except blocks, a
decorator can be used.

If the dependencies passed to the decorator don't exist, then the salt minion
will remove those functions from the module on that host.

If a ``fallback_function`` is defined, it will replace the function instead of
removing it

.. code-block:: python

    import logging

    from salt.utils.decorators import depends

    log = logging.getLogger(__name__)

    try:
        import dependency_that_sometimes_exists
    except ImportError as e:
        log.trace("Failed to import dependency_that_sometimes_exists: {0}".format(e))


    @depends("dependency_that_sometimes_exists")
    def foo():
        """
        Function with a dependency on the "dependency_that_sometimes_exists" module,
        if the "dependency_that_sometimes_exists" is missing this function will not exist
        """
        return True


    def _fallback():
        """
        Fallback function for the depends decorator to replace a function with
        """
        return '"dependency_that_sometimes_exists" needs to be installed for this function to exist'


    @depends("dependency_that_sometimes_exists", fallback_function=_fallback)
    def foo():
        """
        Function with a dependency on the "dependency_that_sometimes_exists" module.
        If the "dependency_that_sometimes_exists" is missing this function will be
        replaced with "_fallback"
        """
        return True

In addition to global dependencies the depends decorator also supports raw
booleans.

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
