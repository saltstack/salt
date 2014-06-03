.. _requisites:

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

The use of ``require`` demands that the dependent state executes before the
depending state. The state containing the ``require`` requisite is defined as the
depending state. The state specified in the ``require`` statement is defined as the
dependent state. If the dependent state's execution succeeds, the depending state
will then execute. If the dependent state's execution fails, the depending state
will not execute. In the first example above, the file ``/etc/vimrc`` will only
execute after the vim package is installed successfully.

Require an entire sls file
--------------------------

As of Salt 0.16.0, it is possible to require an entire sls file. Do this first by
including the sls file and then setting a state to ``require`` the included sls file:

.. code-block:: yaml

    include:
      - foo

    bar:
      pkg.installed:
        - require:
          - sls: foo

Watch
-----

``watch`` statements are used to monitor changes in other states. The state containing
the ``watch`` requisite is defined as the watching state. The state specified in the
``watch`` statement is defined as the watched state. When the watched state executes,
it will return a dictionary containing a key named "changes". Here are two examples
of state return dictionaries, shown in json for clarity:

.. code-block:: json

    "local": {
        "file_|-/tmp/foo_|-/tmp/foo_|-directory": {
            "comment": "Directory /tmp/foo updated",
            "__run_num__": 0,
            "changes": {
                "user": "bar"
            },
            "name": "/tmp/foo",
            "result": true
        }
    }

    "local": {
        "pkgrepo_|-salt-minion_|-salt-minion_|-managed": {
            "comment": "Package repo 'salt-minion' already configured",
            "__run_num__": 0,
            "changes": {},
            "name": "salt-minion",
            "result": true
        }
    }

If the "changes" key contains a populated dictionary, it means that changes in
the watched state occurred. The watching state will now execute. If the "changes"
key contains an empty dictionary, this means that changes in the watched state
did not occur and the watching state will not execute.

The behavior of ``watch`` depends on the presence of a function called
``mod_watch`` in the watching state module. Note: Not all state modules contain
``mod_watch``. If ``mod_watch`` is present, the watched state is checked to see
if it made any changes to the system. If the watched state returns changes, the
``mod_watch`` function is called and the watching state executes. If the watching
state does not contain ``mod_watch``, then watch behaves the same way as the
``require`` requisite: the watching state will only execute if the watched state
executes successfully. If the watched state fails, then the watching state will
not run.

A good example of using ``watch`` is with a :mod:`service.running
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

.. versionadded:: 0.16.0

``prereq`` allows for actions to be taken based on the expected results of
a state that has not yet been executed. The state containing the ``prereq``
requisite is defined as the pre-requiring state. The state specified in the
``prereq`` statement is defined as the pre-required state.

When ``prereq`` is called, the pre-required state reports if it expects to
have any changes. It does this by running the pre-required single state as a
test-run by enabling ``test=True``. This test-run will return a dictionary
containing a key named "changes". (See the ``watch`` section above for
examples of "changes" dictionaries.)

If the "changes" key contains a populated dictionary, it means that the
pre-required state expects changes to occur when the state is actually
executed, as opposed to the test-run. The pre-required state will now
actually run. If the pre-required state executes successfully, the
pre-requiring state will then execute. If the pre-required state fails, the
pre-requiring state will not execute.

If the "changes" key contains an empty dictionary, this means that changes are
not expected by the pre-required state. Neither the pre-required state nor the
pre-requiring state will run.

The best way to define how ``prereq`` operates is displayed in the following
practical example: When a service should be shut down because underlying code
is going to change, the service should be off-line while the update occurs. In
this example, ``graceful-down`` is the pre-requiring state and ``site-code``
is the pre-required state.

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

Onfail
------

.. versionadded:: Helium

The ``onfail`` requisite allows for reactions to happen strictly as a response
to the failure of another state. This can be used in a number of ways, such as
executing a second attempt to set up a service or begin to execute a separate
thread of states because of a failure.

The ``onfail`` requisite is applied in the same way as ``require`` as ``watch``:

.. code-block:: yaml

    primary_mount:
      mount:
        - mounted
        - name: /mnt/share
        - device: 10.0.0.45:/share
        - fstype: nfs

    backup_mount:
      mount:
        - mounted
        - name: /mnt/share
        - device: 192.168.40.34:/share
        - fstype: nfs
        - onfail:
          - mount: primary_mount

Onchanges
---------

.. versionadded:: Helium

The ``onchanges`` requisite makes a state only apply if the required states
generate changes. This can be a useful way to execute a post hook after
changing aspects of a system.

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
require_in can accommodate it. Therefore, these two sls files would be the
same in the end:

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
        - name: httpd
      service:
        - watch:
          - git: django_git

    django_git:
      git:
        - latest
        - name: git@github.com/example/mydjangoproject.git

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

Altering Statefulness
=====================

To alter if a state runs or not, or how the return data from a state is
interpreted, :ref:`See the document on altering states. <altering_states>` for
more information about pre and post run checks.
