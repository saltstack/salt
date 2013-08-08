==========
Requisites
==========

The Salt requisite system is used to create relationships between states. The
core idea being that, when one state is dependent somehow on another, that
inter-dependency can be easily defined.

Requisites come in two types. Direct requisites, and requisite_ins. The
relationships are directional, so a requisite statement makes the requiring
state declaration depend on the required state declaration:

.. code-block:: yaml

    vim:
      pkg.installed

    /etc/vimrc:
      file.managed:
        - source: salt://edit/vimrc
        - require:
          - pkg: vim

So in this example, the file ``/etc/vimrc`` depends on the vim package.

Requisite_in statements are the opposite, instead of saying "I depend on
something", requisite_ins say "Someone depends on me":

.. code-block:: yaml

    vim:
      pkg.installed:
        - require_in:
          - file: /etc/vimrc

    /etc/vimrc:
      file.managed:
        - source: salt://edit/vimrc

So here, with a requisite_in, the same thing is accomplished, but just from
the other way around. The vim package is saying "/etc/vimrc depends on me".

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


Requisite and Requisite in types
================================

There are three requisite statements that can be used in Salt. the ``require``,
``watch`` and ``use`` requisites. Each requisite also has a corresponding
requisite_in: ``require_in``, ``watch_in`` and ``use_in``. All of the
requisites define specific relationships and always work with the dependency
logic defined above.

Require
-------

The most basic requisite statement is ``require``. The behavior of require is
simple. Make sure that the dependent state is executed before the depending
state, and if the dependent state fails, don't run the depending state. So in
the above examples the file ``/etc/vimrc`` will only be applied after the vim
package is installed and only if the vim package is installed successfully.

Require an entire sls file
--------------------------

As of Salt 0.16.0, it is possible to require an entire sls file. Do this by first including
the sls file and then setting a state to ``require`` the included sls file.

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
state module, then watch does the same thing as require. If the ``mod_watch``
function is in the state module, then the watched state is checked to see if
it made any changes to the system, if it has, then ``mod_watch`` is called.

Perhaps the best example of using watch is with a :mod:`service.running
<salt.states.service.running>` state. When a service watches a state, then
the service is reloaded/restarted when the watched state changes::

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
expects to deploy fresh code via the file.recurse call, and the site-code
deployment will only be executed if the graceful-down run completes
successfully.

Use
---

The ``use`` requisite is used to inherit the arguments passed in another
id declaration. This is useful when many files need to have the same defaults.

The ``use`` statement was developed primarily for the networking states but
can be used on any states in Salt. This made sense for the networking state
because it can define a long list of options that need to be applied to
multiple network interfaces.

.. _requisites-require-in:

Require In
----------

The ``require_in`` requisite is the literal reverse of ``require``. If
a state declaration needs to be required by another state declaration then
require_in can accommodate it, so these two sls files would be the same in
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

Watch in functions the same was as require in, but applies a watch statement
rather than a require statement to the external state declaration.

Prereq In
---------

The ``prereq_in`` requisite in follows the same assignment logic as the
``require_in`` requisite in. The ``prereq_in`` call simply assigns
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

