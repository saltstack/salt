==========
Requisites
==========

The Salt requisite system is used to create relationships between states. The
core idea being that, when one state is dependent somehow on another, that
inter-dependency can be easily defined.

Requisites come in two types: Direct requisites (such as ``require`` and ``watch``),
and requisite_ins (such as ``require_in`` and ``watch_in``). The relationships are
directional: a direct requisite requires something from another state, while
requisite_ins operate in the other direction. A requisite_in contains something that
is required by another state. The following example demonstrates a direct requisite:

.. code-block:: yaml

    vim:
      pkg.installed

    /etc/vimrc:
      file.managed:
        - source: salt://edit/vimrc
        - require:
          - pkg: vim

In the example above, the file ``/etc/vimrc`` depends on the vim package.

Requisite_in statements are the opposite. Instead of saying "I depend on
something", requisite_ins say "Someone depends on me":

.. code-block:: yaml

    vim:
      pkg.installed:
        - require_in:
          - file: /etc/vimrc

    /etc/vimrc:
      file.managed:
        - source: salt://edit/vimrc

So here, with a requisite_in, the same thing is accomplished as in the first
example, but the other way around. The vim package is saying "/etc/vimrc depends
on me".

In the end, a single dependency map is created and everything is executed in a
finite and predictable order.

.. note:: Requisite matching

    Requisites match on both the ID Declaration and the ``name`` parameter.
    This means that, in the example above, the ``require_in`` requisite would
    also have been matched if the ``/etc/vimrc`` state was written as follows:

    .. code-block:: yaml

        vimrc:
          file.managed:
            - name: /etc/vimrc
            - source: salt://edit/vimrc


Direct Requisite and Requisite_in types
=======================================

There are four direct requisite statements that can be used in Salt: ``require``,
``watch``, ``prereq``, and ``use``. Each direct requisite also has a corresponding
requisite_in: ``require_in``, ``watch_in``, ``prereq_in`` and ``use_in``. All of the
requisites define specific relationships and always work with the dependency
logic defined above.

Require
-------

The most basic requisite is ``require``. The behavior of require is
simple: Make sure the dependent state is executed before the depending
state. If the dependent state fails, don't run the depending state. In
the first example, the file ``/etc/vimrc`` will only run after the vim
package is installed and only if the vim package is installed successfully.

Require an entire sls file
--------------------------

As of Salt 0.16.0, it is possible to require an entire sls file. Do this by first including
the sls file and then setting a state to ``require`` the included sls file:

.. code-block:: yaml

    include:
      - foo

    bar:
      pkg.installed:
        - require:
          - sls: foo

Watch
-----

The watch statement does everything the require statement does, but with a
little more. The watch statement looks into the state modules for a function
called ``mod_watch``. If this function is not available in the corresponding
state module, then watch does the same thing as require (not all state modules
contain the ``mod_watch`` function). If the ``mod_watch`` function is in the
state module, then the watched state is checked to see if it made any changes
to the system, if it has changes, then ``mod_watch`` is called.

Perhaps the best example of using watch is with a :mod:`service.running
<salt.states.service.running>` state. When a service watches a state, then
the service is reloaded/restarted when the watched state changes:

.. code-block:: yaml

    ntpd:
      service.running:
        - watch:
          - file: /etc/ntp.conf
      file.managed:
        - name: /etc/ntp.conf
        - source: salt://ntp/files/ntp.conf

Prereq
------

The ``prereq`` requisite is a powerful requisite added in 0.16.0. This
requisite allows for actions to be taken based on the expected results of
a state that has not yet been executed. In more practical terms, a service
can be shut down because the ``prereq`` knows that underlying code is going to
be updated and the service should be off-line while the update occurs.

The motivation to add this requisite was to allow for routines to remove a
system from a load balancer while code is being updated.

The ``prereq`` checks if the required state expects to have any changes by
running the single state with ``test=True``. If the pre-required state returns
changes, then the state requiring it will execute.

.. code-block:: yaml

    graceful-down:
      cmd.run:
        - name: service apache graceful
        - prereq:
          - file: site-code

    site-code:
      file.recurse:
        - name: /opt/site_code
        - source: salt://site/code

In this case the apache server will only be shutdown if the site-code state
expects to deploy fresh code via the file.recurse call. The site-code
deployment will only be executed if the graceful-down run completes
successfully.

Use
---

The ``use`` requisite is used to inherit the arguments passed in another
id declaration. This is useful when many files need to have the same defaults.

.. code-block:: yaml

    /etc/foo.conf:
      file.managed:
        - source: salt://foo.conf
        - template: jinja
        - mkdirs: True
        - user: apache
        - group: apache
        - mode: 755

    /etc/bar.conf
      file.managed:
        - source: salt://bar.conf
        - use:
          - file: /etc/foo.conf

The ``use`` statement was developed primarily for the networking states but
can be used on any states in Salt. This makes sense for the networking state
because it can define a long list of options that need to be applied to
multiple network interfaces.

The ``use`` statement does not inherit the requisites arguments of the
targeted state. This means also a chain of ``use`` requisites would not
inherit inherited options.

.. _requisites-require-in:

Require In
----------

The ``require_in`` requisite is the literal reverse of ``require``. If
a state declaration needs to be required by another state declaration then
require_in can accommodate it. Therefore, these two sls files would be same in
the end:

Using ``require``

.. code-block:: yaml

    httpd:
      pkg:
        - installed
      service:
        - running
        - require:
          - pkg: httpd

Using ``require_in``

.. code-block:: yaml

    httpd:
      pkg:
        - installed
        - require_in:
          - service: httpd
      service:
        - running

The ``require_in`` statement is particularly useful when assigning a require
in a separate sls file. For instance it may be common for httpd to require
components used to set up PHP or mod_python, but the HTTP state does not need
to be aware of the additional components that require it when it is set up:

http.sls

.. code-block:: yaml

    httpd:
      pkg:
        - installed
      service:
        - running
        - require:
          - pkg: httpd

php.sls

.. code-block:: yaml

    include:
      - http

    php:
      pkg:
        - installed
        - require_in:
          - service: httpd

mod_python.sls

.. code-block:: yaml

    include:
      - http

    mod_python:
      pkg:
        - installed
        - require_in:
          - service: httpd

Now the httpd server will only start if php or mod_python are first verified to
be installed. Thus allowing for a requisite to be defined "after the fact".

.. _requisites-watch-in:

Watch In
--------

``watch_in`` functions the same way as ``require_in``, but applies
a ``watch`` statement rather than a ``require`` statement to the external state
declaration.

A good example of when to use ``watch_in`` versus ``watch`` is in regards to writing
an Apache state in conjunction with a git state for a Django application. On the most
basic level, using either the ``watch`` or the ``watch_in`` requisites, the resulting
behavior will be the same: Apache restarts each time the Django git state changes.

.. code-block:: yaml

    apache:
      pkg:
        - installed
      service:
        - watch:
          - git: django_git

    django_git:
      git:
        - latest

However, by using ``watch_in``, the approach is improved. By writing ``watch_in`` in
the depending states (such as the Django state and any other states that require Apache
to restart), the dependent state (Apache state) is de-coupled from the depending states:

.. code-block:: yaml

    apache:
      pkg:
        - installed
        - name: httpd

    django_git:
      git:
        - latest
        - name: git@github.com/example/mydjangoproject.git
        - watch_in:
          - service: apache

Prereq In
---------

The ``prereq_in`` requisite_in follows the same assignment logic as the
``require_in`` requisite_in. The ``prereq_in`` call simply assigns
``prereq`` to the state referenced. The above example for ``prereq`` can
be modified to function in the same way using ``prereq_in``:

.. code-block:: yaml

    graceful-down:
      cmd.run:
        - name: service apache graceful

    site-code:
      file.recurse:
        - name: /opt/site_code
        - source: salt://site/code
        - prereq_in:
          - cmd: graceful-down

