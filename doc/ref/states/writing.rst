=============
State Modules
=============

State Modules are the components that map to actual enforcement and management
of salt states.

States are - Easy to Write!
============================

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
``file_roots`` specified by the master config file. 

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
