=============
State Modules
=============

State Modules are the components that map to actual enforcement and management
of Salt states.

States are - Easy to Write!
===========================

State Modules should be easy to write and straightforward. The information
passed to the SLS data structures will map directly to the states modules.

Mapping the information from the SLS data is simple, this example should
illustrate:

.. code-block:: yaml

    /etc/salt/master: # maps to "name"
      file: # maps to State module filename eg https://github.com/saltstack/salt/blob/develop/salt/states/file.py
        - managed # maps to the managed function in the file State module
        - user: root # one of many options passed to the manage function
        - group: root
        - mode: 644
        - source: salt://salt/master

Therefore this SLS data can be directly linked to a module, function and
arguments passed to that function.

This does issue the burden, that function names, state names and function
arguments should be very human readable inside state modules, since they
directly define the user interface.

Using Custom State Modules
==========================

Place your custom state modules inside a ``_states`` directory within the
``file_roots`` specified by the master config file. These custom state modules
can then be distributed in a number of ways. Custom state modules are
distributed when state.highstate is run, or via the saltutil.sync_states
function.

Cross Calling Modules
=====================

As with Execution Modules, State Modules can also make use of the ``__salt__``
and ``__grains__`` data.

It is important to note that the real work of state management should not be
done in the state module unless it is needed. A good example is the pkg state
module. This module does not do any package management work, it just calls the
pkg execution module. This makes the pkg state module completely generic, which
is why there is only one pkg state module and many backend pkg execution
modules.

On the other hand some modules will require that the logic be placed in the
state module, a good example of this is the file module. But in the vast
majority of cases this is not the best approach, and writing specific
execution modules to do the backend work will be the optimal solution.

Return Data
===========

A State Module must return a dict containing the following keys/values:

- **name:** The same value passed to the state as "name".
- **changes:** A dict describing the changes made. Each thing changed should
  be a key, with its value being another dict with keys called "old" and "new"
  containing the old/new values. For example, the pkg state's **changes** dict
  has one key for each package changed, with the "old" and "new" keys in its
  sub-dict containing the old and new versions of the package.
- **result:** A boolean value. *True* if the action was successful, otherwise
  *False*.
- **comment:** A string containing a summary of the result.

Test State
==========

All states should check for and support ``test`` being passed in the options. 
This will return data about what changes would occur if the state were actually 
run. An example of such a check could look like this:

.. code-block:: python

    # Return comment of changes if test.
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'State Foo will execute with param {0}'.format(bar)
        return ret

Make sure to test and return before performing any real actions on the minion.

Watcher Function
================

If the state being written should support the watch requisite then a watcher
function needs to be declared. The watcher function is called whenever the
watch requisite is invoked and should be generic to the behavior of the state
itself.

The watcher function should accept all of the options that the normal state
functions accept (as they will be passed into the watcher function).

A watcher function typically is used to execute state specific reactive
behavior, for instance, the watcher for the service module restarts the
named service and makes it useful for the watcher to make the service
react to changes in the environment.

The watcher function also needs to return the same data that a normal state
function returns.


Mod_init Interface
==================

Some states need to execute something only once to ensure that an environment
has been set up, or certain conditions global to the state behavior can be
predefined. This is the realm of the mod_init interface.

A state module can have a function called **mod_init** which executes when the
first state of this type is called. This interface was created primarily to
improve the pkg state. When packages are installed the package metadata needs
to be refreshed, but refreshing the package metadata every time a package is
installed is wasteful. The mod_init function for the pkg state sets a flag down
so that the first, and only the first, package installation attempt will refresh
the package database (the package database can of course be manually called to
refresh via the ``refresh`` option in the pkg state).

The mod_init function must accept the **Low State Data** for the given
executing state as an argument. The low state data is a dict and can be seen by
executing the state.show_lowstate function. Then the mod_init function must
return a bool. If the return value is True, then the mod_init function will not
be executed again, meaning that the needed behavior has been set up. Otherwise,
if the mod_init function returns False, then the function will be called the
next time.

A good example of the mod_init function is found in the pkg state module:

.. code-block:: python

    def mod_init(low):
        '''
        Refresh the package database here so that it only needs to happen once
        '''
        if low['fun'] == 'installed' or low['fun'] == 'latest':
            rtag = __gen_rtag()
            if not os.path.exists(rtag):
                open(rtag, 'w+').write('')
            return True
        else:
            return False

The mod_init function in the pkg state accepts the low state data as ``low``
and then checks to see if the function being called is going to install
packages, if the function is not going to install packages then there is no
need to refresh the package database. Therefore if the package database is
prepared to refresh, then return True and the mod_init will not be called
the next time a pkg state is evaluated, otherwise return False and the mod_init
will be called next time a pkg state is evaluated.
