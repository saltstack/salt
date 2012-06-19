===============
Ordering States
===============

When creating Salt SLS files, it is often important to ensure that they run in
a specific order. While states will always execute in the same order, that
order is not necessarily defined the way you want it.

A few tools exist in Salt to set up the correct state ordering. These tools
consist of requisite declarations and order options.

.. note::

    Salt does **not** execute :term:`state declarations <state declaration>` in
    the order they appear in the source.

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

Watch and the Watcher Function
------------------------------

The watch requisite is based on the ``watcher`` function, state Python
modules can include a function called watcher, this function is then called
if the watch call is invoked. In the case of the service module the underlying
service is restarted. In the case of the cmd state the command is executed.

The watcher function for the service state looks like this:

.. code-block:: python

    def watcher(name, sig=None):
        '''
        The service watcher, called to invoke the watch command.

        name
            The name of the init or rc script used to manage the service

        sig
            The string to search for when looking for the service process with ps
        '''
        if __salt__['service.status'](name, sig):
            changes = {name: __salt__['service.restart'](name)}
            return {'name': name,
                    'changes': changes,
                    'result': True,
                    'comment': 'Service restarted'}

        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'Service {0} started'.format(name)}

The watch requisite only works if the state that is watching has a watcher
function written. If watch is set on a state that does not have a watcher
function (like pkg), then the listed states will behave only as if they were
under a ``require`` statement.

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
