.. _external-pillars:

================
External Pillars
================

Salt provides a mechanism for generating pillar data by calling external
pillar interfaces. This document will describe an outline of an ext_pillar
module.

Location
--------

Salt expects to find your ``ext_pillar`` module in the same location where it
looks for other python modules. If the ``extension_modules`` option in your
Salt master configuration is set, Salt will look for a ``pillar`` directory
under there and load all the modules it finds. Otherwise, it will look in
your Python site-packages ``salt/pillar`` directory.

Configuration
-------------

The external pillars that are called when a minion refreshes its pillars is
controlled by the ``ext_pillar`` option in the Salt master configuration. You
can pass a single argument, a list of arguments or a dictionary of arguments
to your pillar:

.. code-block:: yaml

    ext_pillar:
      - example_a: some argument
      - example_b:
        - argumentA
        - argumentB
      - example_c:
          keyA: valueA
          keyB: valueB


The Module
----------

Imports and Logging
-------------------

Import modules your external pillar module needs. You should first include
generic modules that come with stock Python:

.. code-block:: python

    import logging


And then start logging. This is an idiomatic way of setting up logging in Salt:

.. code-block:: python

    log = logging.getLogger(__name__)


Finally, load modules that are specific to what you are doing. You should catch
import errors and set a flag that the ``__virtual__`` function can use later.

.. code-block:: python

    try:
        import weird_thing
        EXAMPLE_A_LOADED = True
    except ImportError:
        EXAMPLE_A_LOADED = False


Options
-------

If you define an ``__opts__`` dictionary, it will be merged into the
``__opts__`` dictionary handed to the ``ext_pillar`` function later. This is a
good place to put default configuration items. The convention is to name
things ``modulename.option``.

.. code-block:: python

    __opts__ = { 'example_a.someconfig': 137 }


Initialization
--------------

If you define an ``__init__`` function, it will be called with the following
signature:

.. code-block:: python

    def __init__( __opts__ ):
        # Do init work here


**Note**: The ``__init__`` function is ran every time a particular minion causes
the external pillar to be called, so don't put heavy initialization code here.
The ``__init__`` functionality is a side-effect of the Salt loader, so it may
not be as useful in pillars as it is in other Salt items.

__virtual__
-----------

If you define a ``__virtual__`` function, you can control whether or not this
module is visible. If it returns ``False`` then Salt ignores this module. If
it returns a string, then that string will be how Salt identifies this external
pillar in its ``ext_pillar`` configuration. If you're not renaming the module,
simply return ``True`` in the ``__virtual__`` function, which is the same as if
this function did not exist, then, the name Salt's ``ext_pillar`` will use to
identify this module is its conventional name in Python.

This is useful to write modules that can be installed on all Salt masters, but
will only be visible if a particular piece of software your module requires is
installed.

.. code-block:: python

    # This external pillar will be known as `example_a`
    def __virtual__():
        if EXAMPLE_A_LOADED:
            return True
        return False


.. code-block:: python

    # This external pillar will be known as `something_else`
    __virtualname__ = 'something_else'

    def __virtual__():
        if EXAMPLE_A_LOADED:
            return __virtualname__
        return False


ext_pillar
----------

This is where the real work of an external pillar is done. If this module is
active and has a function called ``ext_pillar``, whenever a minion updates its
pillar this function is called.

How it is called depends on how it is configured in the Salt master
configuration. The first argument is always the current pillar dictionary, this
contains pillar items that have already been added, starting with the data from
``pillar_roots``, and then from any already-ran external pillars.

Using our example above:

.. code-block:: python

    ext_pillar( id, pillar, 'some argument' )                   # example_a
    ext_pillar( id, pillar, 'argumentA', 'argumentB' )          # example_b
    ext_pillar( id, pillar, keyA='valueA', keyB='valueB' )    # example_c


In the ``example_a`` case, ``pillar`` will contain the items from the
``pillar_roots``, in ``example_b`` ``pillar``  will contain that plus the items
added by ``example_a``, and in ``example_c`` ``pillar`` will contain that plus
the items added by ``example_b``. In all three cases, ``id`` will contain the
ID of the minion making the pillar request.

This function should return a dictionary, the contents of which are merged in
with all of the other pillars and returned to the minion. **Note**: this function
is called once for each minion that fetches its pillar data.

.. code-block:: python

    def ext_pillar( minion_id, pillar, *args, **kwargs ):

        my_pillar = {'external_pillar': {}}

        my_pillar['external_pillar'] = get_external_pillar_dictionary()

        return my_pillar


You can call pillar with the dictionary's top name to retrieve its data.
From above example, 'external_pillar' is the top dictionary name. Therefore:

.. code-block:: bash

    salt '*' pillar.get external_pillar


You shouldn't just add items to ``pillar`` and return that, since that will
cause Salt to merge data that already exists. Rather, just return the items
you are adding or changing. You could, however, use ``pillar`` in your module
to make some decision based on pillar data that already exists.

This function has access to some useful globals:

:__opts__:
    A dictionary of mostly Salt configuration options. If you had an
    ``__opts__`` dictionary defined in your module, those values will be
    included.

:__salt__:
    A dictionary of Salt module functions, useful so you don't have to
    duplicate functions that already exist. E.g.
    ``__salt__['cmd.run']( 'ls -l' )`` **Note**, runs on the *master*

:__grains__:
    A dictionary of the grains of the minion making this pillar call.



Example configuration
---------------------

As an example, if you wanted to add external pillar via the ``cmd_json``
external pillar, add something like this to your master config:

.. code-block:: yaml

    ext_pillar:
      - cmd_json: 'echo {\"arg\":\"value\"}'

Reminder
--------

Just as with traditional pillars, external pillars must be refreshed in order for
minions to see any fresh data:

.. code-block:: bash

    salt '*' saltutil.refresh_pillar
