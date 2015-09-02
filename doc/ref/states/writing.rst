=============
State Modules
=============

State Modules are the components that map to actual enforcement and management
of Salt states.

States are Easy to Write!
=========================

State Modules should be easy to write and straightforward. The information
passed to the SLS data structures will map directly to the states modules.

Mapping the information from the SLS data is simple, this example should
illustrate:

.. code-block:: yaml

    /etc/salt/master: # maps to "name"
      file: # maps to State module filename e.g. https://github.com/saltstack/salt/tree/develop/salt/states/file.py
        - managed # maps to the managed function in the file State module
        - user: root # one of many options passed to the manage function
        - group: root
        - mode: 644
        - source: salt://salt/master

Therefore this SLS data can be directly linked to a module, function, and
arguments passed to that function.

This does issue the burden, that function names, state names and function
arguments should be very human readable inside state modules, since they
directly define the user interface.

.. admonition:: Keyword Arguments

    Salt passes a number of keyword arguments to states when rendering them,
    including the environment, a unique identifier for the state, and more.
    Additionally, keep in mind that the requisites for a state are part of the
    keyword arguments. Therefore, if you need to iterate through the keyword
    arguments in a state, these must be considered and handled appropriately.
    One such example is in the :mod:`pkgrepo.managed
    <salt.states.pkgrepo.managed>` state, which needs to be able to handle
    arbitrary keyword arguments and pass them to module execution functions.
    An example of how these keyword arguments can be handled can be found
    here_.

    .. _here: https://github.com/saltstack/salt/blob/v0.16.2/salt/states/pkgrepo.py#L163-183


Using Custom State Modules
==========================

Place your custom state modules inside a ``_states`` directory within the
:conf_master:`file_roots` specified by the master config file. These custom
state modules can then be distributed in a number of ways. Custom state modules
are distributed when :mod:`state.highstate <salt.modules.state.highstate>` is
run, or by executing the :mod:`saltutil.sync_states
<salt.modules.saltutil.sync_states>` or :mod:`saltutil.sync_all
<salt.modules.saltutil.sync_all>` functions.

Any custom states which have been synced to a minion, that are named the
same as one of Salt's default set of states, will take the place of the default
state with the same name. Note that a state's default name is its filename
(i.e. ``foo.py`` becomes state ``foo``), but that its name can be overridden
by using a :ref:`__virtual__ function <virtual-modules>`.


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
- **result:** A tristate value.  ``True`` if the action was successful,
  ``False`` if it was not, or ``None`` if the state was run in test mode,
  ``test=True``, and changes would have been made if the state was not run in
  test mode.

  +--------------------+-----------+-----------+
  |                    | live mode | test mode |
  +====================+===========+===========+
  | no changes         | ``True``  | ``True``  |
  +--------------------+-----------+-----------+
  | successful changes | ``True``  | ``None``  |
  +--------------------+-----------+-----------+
  | failed changes     | ``False`` | ``None``  |
  +--------------------+-----------+-----------+

  .. note::

      Test mode does not predict if the changes will be successful or not.

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


Full State Module Example
=========================

The following is a simplistic example of a full state module and function.
Remember to call out to execution modules to perform all the real work. The
state module should only perform "before" and "after" checks.

1.  Make a custom state module by putting the code into a file at the following
    path: **/srv/salt/_states/my_custom_state.py**.

2.  Distribute the custom state module to the minions:

    .. code-block:: bash

        salt '*' saltutil.sync_states

3.  Write a new state to use the custom state by making a new state file, for
    instance **/srv/salt/my_custom_state.sls**.

4.  Add the following SLS configuration to the file created in Step 3:

    .. code-block:: yaml

        human_friendly_state_id:        # An arbitrary state ID declaration.
          my_custom_state:              # The custom state module name.
            - enforce_custom_thing      # The function in the custom state module.
            - name: a_value             # Maps to the ``name`` parameter in the custom function.
            - foo: Foo                  # Specify the required ``foo`` parameter.
            - bar: False                # Override the default value for the ``bar`` parameter.

Example state module
--------------------

.. code-block:: python

    import salt.exceptions

    def enforce_custom_thing(name, foo, bar=True):
        '''
        Enforce the state of a custom thing

        This state module does a custom thing. It calls out to the execution module
        ``my_custom_module`` in order to check the current system and perform any
        needed changes.

        name
            The thing to do something to
        foo
            A required argument
        bar : True
            An argument with a default value
        '''
        ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

        # Start with basic error-checking. Do all the passed parameters make sense
        # and agree with each-other?
        if bar == True and foo.startswith('Foo'):
            raise salt.exceptions.SaltInvocationError(
                'Argument "foo" cannot start with "Foo" if argument "bar" is True.')

        # Check the current state of the system. Does anything need to change?
        current_state = __salt__['my_custom_module.current_state'](name)

        if current_state == foo:
            ret['result'] = True
            ret['comment'] = 'System already in the correct state'
            return ret

        # The state of the system does need to be changed. Check if we're running
        # in ``test=true`` mode.
        if __opts__['test'] == True:
            ret['comment'] = 'The state of "{0}" will be changed.'.format(name)
            ret['changes'] = {
                'old': current_state,
                'new': 'Description, diff, whatever of the new state',
            }

            # Return ``None`` when running with ``test=true``.
            ret['result'] = None

            return ret

        # Finally, make the actual change and return the result.
        new_state = __salt__['my_custom_module.change_state'](name, foo)

        ret['comment'] = 'The state of "{0}" was changed!'.format(name)

        ret['changes'] = {
            'old': current_state,
            'new': new_state,
        }

        ret['result'] = True

        return ret
