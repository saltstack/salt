===============
Ordering States
===============

The way in which configuration management systems are executed is a hotly
debated topic in the configuration management world. Two
major philosophies exist on the subject, to either execute in an imperative
fashion where things are executed in the order in which they are defined, or
in a declarative fashion where dependencies need to be mapped between objects.

Imperative ordering is finite and generally considered easier to write, but
declarative ordering is much more powerful and flexible but generally considered
more difficult to create.

Salt has been created to get the best of both worlds. States are evaluated in
a finite order, which guarantees that states are always executed in the same
order, and the states runtime is declarative, making Salt fully aware of
dependencies via the requisite system.

State Auto Ordering
===================

.. versionadded: 0.17.0

Salt always executes states in a finite manner, meaning that they will always
execute in the same order regardless of the system that is executing them.
But in Salt 0.17.0, the ``state_auto_order`` option was added. This option
makes states get evaluated in the order in which they are defined in sls
files.

The evaluation order makes it easy to know what order the states will be
executed in, but it is important to note that the requisite system will
override the ordering defined in the files, and the ``order`` option described
below will also override the order in which states are defined in sls files.

If the classic ordering is preferred (lexicographic), then set ``state_auto_order``
to ``False`` in the master configuration file.

Requisite Statements
====================

.. note::

    This document represents behavior exhibited by Salt requisites as of
    version 0.9.7 of Salt.

Often when setting up states any single action will require or depend on
another action. Salt allows you to build relationships between states with
requisite statements. A requisite statement ensure that the named state is
evaluated before the state requiring it. There are two types of requisite
statements in Salt, **require** and **watch**.

These requisite statements are applied to a specific state declaration:

.. code-block:: yaml

    httpd:
      pkg:
        - installed
      file.managed:
        - name: /etc/httpd/conf/httpd.conf
        - source: salt://httpd/httpd.conf
        - require:
          - pkg: httpd

In this example we use the **require** requisite to declare that the file
/etc/httpd/conf/httpd.conf should only be set up if the pkg state executes
successfully.

The requisite system works by finding the states that are required and
executing them before the state that requires them. Then the required states
can be evaluated to see if they have executed correctly.

.. note:: Requisite matching

    Requisites match on both the ID Declaration and the ``name`` parameter.
    Therefore, if you are using the ``pkgs`` or ``sources`` argument to install
    a list of packages in a pkg state, it's important to note that you cannot
    have a requisite that matches on an individual package in the list.


Multiple Requisites
-------------------

The requisite statement is passed as a list, allowing for the easy addition of
more requisites. Both requisite types can also be separately declared:

.. code-block:: yaml

    httpd:
      pkg:
        - installed
      service.running:
        - enable: True
        - watch:
          - file: /etc/httpd/conf/httpd.conf
        - require:
          - pkg: httpd
          - user: httpd
          - group: httpd
      file.managed:
        - name: /etc/httpd/conf/httpd.conf
        - source: salt://httpd/httpd.conf
        - require:
          - pkg: httpd
      user:
        - present
      group:
        - present

In this example the httpd service is only going to be started if the package,
user, group and file are executed successfully.

The Require Requisite
---------------------

The foundation of the requisite system is the ``require`` requisite. The
require requisite ensures that the required state(s) are executed before the
requiring state. So, if a state is declared that sets down a vimrc, then it
would be pertinent to make sure that the vimrc file would only be set down if
the vim package has been installed:

.. code-block:: yaml

    vim:
      pkg:
        - installed
      file.managed:
        - source: salt://vim/vimrc
        - require:
          - pkg: vim

In this case, the vimrc file will only be applied by Salt if and after the vim
package is installed.

The Watch Requisite
-------------------

The ``watch`` requisite is more advanced than the ``require`` requisite. The
watch requisite executes the same logic as require (therefore if something is
watched it does not need to also be required) with the addition of executing
logic if the required states have changed in some way.

The watch requisite checks to see if the watched states have returned any
changes. If the watched state returns changes, and the watched states execute
successfully, then the watching state will execute a function that reacts to
the changes in the watched states.

Perhaps an example can better explain the behavior:

.. code-block:: yaml

    redis:
      pkg:
        - latest
      file.managed:
        - source: salt://redis/redis.conf
        - name: /etc/redis.conf
        - require:
          - pkg: redis
      service.running:
        - enable: True
        - watch:
          - file: /etc/redis.conf
          - pkg: redis

In this example the redis service will only be started if the file
/etc/redis.conf is applied, and the file is only applied if the package is
installed. This is normal require behavior, but if the watched file changes,
or the watched package is installed or upgraded, then the redis service is
restarted.

Watch and the mod_watch Function
--------------------------------

The watch requisite is based on the ``mod_watch`` function. Python state
modules can include a function called ``mod_watch`` which is then called
if the watch call is invoked. When ``mod_watch`` is called depends on the
execution of the watched state, which:

  - If no changes then just run the watching state itself as usual.
    ``mod_watch`` is not called. This behavior is same as using a ``require``.

  - If changes then run the watching state *AND* if that changes nothing then
    react by calling ``mod_watch``.

When reacting, in the case of the service module the underlying service is
restarted. In the case of the cmd state the command is executed.

The ``mod_watch`` function for the service state looks like this:

.. code-block:: python

    def mod_watch(name, sig=None, reload=False, full_restart=False):
        '''
        The service watcher, called to invoke the watch command.

        name
            The name of the init or rc script used to manage the service

        sig
            The string to search for when looking for the service process with ps
        '''
        if __salt__['service.status'](name, sig):
            if 'service.reload' in __salt__ and reload:
                restart_func = __salt__['service.reload']
            elif 'service.full_restart' in __salt__ and full_restart:
                restart_func = __salt__['service.full_restart']
            else:
                restart_func = __salt__['service.restart']
        else:
            restart_func = __salt__['service.start']

        result = restart_func(name)
        return {'name': name,
                'changes': {name: result},
                'result': result,
                'comment': 'Service restarted' if result else \
                           'Failed to restart the service'
               }

The watch requisite only works if the state that is watching has a
``mod_watch`` function written. If watch is set on a state that does not have
a ``mod_watch`` function (like pkg), then the listed states will behave only
as if they were under a ``require`` statement.

Also notice that a ``mod_watch`` may accept additional keyword arguments,
which, in the sls file, will be taken from the same set of arguments specified
for the state that includes the ``watch`` requisite. This means, for the
earlier ``service.running`` example above,  you can tell the service to
``reload`` instead of restart like this:

.. code-block:: yaml

  redis:

    # ... other state declarations omitted ...

      service.running:
        - enable: True
        - reload: True
        - watch:
          - file: /etc/redis.conf
          - pkg: redis


The Order Option
================

Before using the order option, remember that the majority of state ordering
should be done with a :term:`requisite declaration`, and that a requisite
declaration will override an order option.

The order option is used by adding an order number to a state declaration
with the option `order`:

.. code-block:: yaml

    vim:
      pkg.installed:
        - order: 1

By adding the order option to `1` this ensures that the vim package will be
installed in tandem with any other state declaration set to the order `1`.

Any state declared without an order option will be executed after all states
with order options are executed.

But this construct can only handle ordering states from the beginning.
Sometimes you may want to send a state to the end of the line. To do this,
set the order to ``last``:

.. code-block:: yaml

    vim:
      pkg.installed:
        - order: last

Remember that requisite statements override the order option. So the order
option should be applied to the highest component of the requisite chain:

.. code-block:: yaml

    vim:
      pkg.installed:
        - order: last
        - require:
          - file: /etc/vimrc

    /etc/vimrc:
      file.managed:
        - source: salt://edit/vimrc
