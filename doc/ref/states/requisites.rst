.. _requisites:

===========================================
Requisites and Other Global State Arguments
===========================================

Requisites
==========

The Salt requisite system is used to create relationships between states. The
core idea being that, when one state is dependent somehow on another, that
inter-dependency can be easily defined. These dependencies are expressed by
declaring the relationships using state names and ID's or names.  The
generalized form of a requisite target is ``<state name> : <ID or name>``.
The specific form is defined as a :ref:`Requisite Reference
<requisite-reference>`

Requisites come in two types: Direct requisites (such as ``require``),
and requisite_ins (such as ``require_in``). The relationships are
directional: a direct requisite requires something from another state.
However, a requisite_in inserts a requisite into the targeted state pointing to
the targeting state. The following example demonstrates a direct requisite:

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
on me". This will result in a ``require`` being inserted into the
``/etc/vimrc`` state which targets the ``vim`` state.

In the end, a single dependency map is created and everything is executed in a
finite and predictable order.

Requisite matching
------------------

Requisites need two pieces of information for matching: The state module name –
e.g. ``pkg`` –, and the identifier – e.g. vim –, which can be either the ID (the
first line in the stanza) or the ``- name`` parameter.

.. code-block:: yaml

    - require:
      - pkg: vim

Glog matching in requisites
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.9.8

Glob matching is supported in requisites. This is mostly useful for file
changes. In the example below, a change in ``/etc/apache2/httpd.conf`` or
``/etc/apache2/sites-available/default.conf`` will reload/restart the service:

.. code-block:: yaml

    apache2:
      service.running:
        - watch:
          - file: /etc/apache2/*

Omitting state module in requisites
-----------------------------------

.. versionadded:: 2016.3.0

In version 2016.3.0, the state module name was made optional. If the state module
is omitted, all states matching the ID will be required, regardless of which
module they are using.

.. code-block:: yaml

    - require:
      - vim

State target matching
~~~~~~~~~~~~~~~~~~~~~

In order to understand how state targets are matched, it is helpful to know
:ref:`how the state compiler is working <compiler-ordering>`. Consider the following
example:

.. code-block:: yaml

    Deploy server package:
      file.managed:
        - name: /usr/local/share/myapp.tar.xz
        - source: salt://myapp.tar.xz

    Extract server package:
      archive.extracted:
        - name: /usr/local/share/myapp
        - source: /usr/local/share/myapp.tar.xz
        - archive_format: tar
        - onchanges:
          - file: Deploy server package

The first formula is converted to a dictionary which looks as follows (represented
as YAML, some properties omitted for simplicity) as `High Data`:

.. code-block:: yaml

    Deploy server package:
      file:
        - managed
        - name: /usr/local/share/myapp.tar.xz
        - source: salt://myapp.tar.xz

The ``file.managed`` format used in the formula is essentially syntactic sugar:
at the end, the target is ``file``, which is used in the ``Extract server package``
state above.

Identifier matching
~~~~~~~~~~~~~~~~~~~

Requisites match on both the ID Declaration and the ``name`` parameter.
This means that, in the "Deploy server package" example above, a ``require``
requisite would match with ``Deploy server package`` *or* ``/usr/local/share/myapp.tar.xz``,
so either of the following versions for "Extract server package" works:

.. code-block:: yaml

    # (Archive arguments omitted for simplicity)

    # Match by ID declaration
    Extract server package:
      archive.extracted:
        - onchanges:
          - file: Deploy server package

    # Match by name parameter
    Extract server package:
      archive.extracted:
        - onchanges:
          - file: /usr/local/share/myapp.tar.xz


Requisite overview
~~~~~~~~~~~~~~~~~~


+------------+-------------------+---------------+------------+--------------------+
| name       | state is only     | state is only | order      | comment            |
|  of        | executed if       | executed if   |            |  or                |
|            | target execution  | target has    | 1.target   |                    |
|            |                   |               | 2.state    |                    |
| requisite  | result is         | changes       | (default)  | description        |
+============+===================+===============+============+====================+
| require    | success           |               | default    | state will always  |
|            |                   |               |            | execute unless     |
|            |                   |               |            | target fails       |
+------------+-------------------+---------------+------------+--------------------+
| watch      | success           |               | default    | like require,      |
|            |                   |               |            | but adds additional|
|            |                   |               |            | behaviour          |
|            |                   |               |            | (mod_watch)        |
+------------+-------------------+---------------+------------+--------------------+
| prereq     | success           | has changes   | switched   | like onchanges,    |
|            |                   | (run          |            | except order       |
|            |                   | individually  |            |                    |
|            |                   | as dry-run)   |            |                    |
+------------+-------------------+---------------+------------+--------------------+
| onchanges  | success           | has changes   | default    | execute state if   |
|            |                   |               |            | target execution   |
|            |                   |               |            | result is success  |
|            |                   |               |            | and target has     |
|            |                   |               |            | changes            |
+------------+-------------------+---------------+------------+--------------------+
| onfail     | failed            |               | default    | Only requisite     |
|            |                   |               |            | where state exec.  |
|            |                   |               |            | if target fails    |
+------------+-------------------+---------------+------------+--------------------+


In this table, the following short form of terms is used:

* **state** (= dependent state): state containing requisite
* **target** (= state target) : state referenced by requisite



Direct Requisite and Requisite_in types
---------------------------------------

There are several direct requisite statements that can be used in Salt:

* ``require``
* ``watch``
* ``prereq``
* ``use``
* ``onchanges``
* ``onfail``

Each direct requisite also has a corresponding requisite_in:

* ``require_in``
* ``watch_in``
* ``prereq_in``
* ``use_in``
* ``onchanges_in``
* ``onfail_in``

There are several corresponding requisite_any statements:

* ``require_any``
* ``watch_any``
* ``onchanges_any``
* ``onfail_any``

All of the requisites define specific relationships and always work with the
dependency logic defined above.

.. _requisites-require:

require
~~~~~~~

The use of ``require`` demands that the required state executes before the
dependent state. The state containing the ``require`` requisite is defined as the
dependent state. The state specified in the ``require`` statement is defined as the
required state. If the required state's execution succeeds, the dependent state
will then execute. If the required state's execution fails, the dependent state
will not execute. In the first example above, the file ``/etc/vimrc`` will only
execute after the vim package is installed successfully.

Require an Entire SLS File
~~~~~~~~~~~~~~~~~~~~~~~~~~

As of Salt 0.16.0, it is possible to require an entire sls file. Do this first by
including the sls file and then setting a state to ``require`` the included sls file:

.. code-block:: yaml

    include:
      - foo

    bar:
      pkg.installed:
        - require:
          - sls: foo

This will add all of the state declarations found in the given sls file. This means
that every state in sls `foo` will be required. This makes it very easy to batch
large groups of states easily in any requisite statement.

.. _requisites-require_any:

require_any
~~~~~~~~~~~

.. versionadded:: 2018.3.0

The use of ``require_any`` demands that one of the required states executes before the
dependent state. The state containing the ``require_any`` requisite is defined as the
dependent state. The states specified in the ``require_any`` statement are defined as the
required states. If at least one of the required state's execution succeeds, the dependent state
will then execute.  If all of the executions by the required states fail, the dependent state
will not execute.

.. code-block:: yaml

    A:
      cmd.run:
        - name: echo A
        - require_any:
          - cmd: B
          - cmd: C
          - cmd: D
    B:
      cmd.run:
        - name: echo B

    C:
      cmd.run:
        - name: /bin/false

    D:
      cmd.run:
        - name: echo D

In this example `A` will run because at least one of the requirements specified,
`B`, `C`, or `D` will succeed.

.. _requisites-watch:

watch
~~~~~

``watch`` statements are used to add additional behavior when there are changes
in other states.

.. note::

    If a state should only execute when another state has changes, and
    otherwise do nothing, the new ``onchanges`` requisite should be used
    instead of ``watch``. ``watch`` is designed to add *additional* behavior
    when there are changes, but otherwise the state executes normally.

The state containing the ``watch`` requisite is defined as the watching
state. The state specified in the ``watch`` statement is defined as the watched
state. When the watched state executes, it will return a dictionary containing
a key named "changes". Here are two examples of state return dictionaries,
shown in json for clarity:

.. code-block:: json

    {
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
    }

    {
        "local": {
            "pkgrepo_|-salt-minion_|-salt-minion_|-managed": {
                "comment": "Package repo 'salt-minion' already configured",
                "__run_num__": 0,
                "changes": {},
                "name": "salt-minion",
                "result": true
            }
        }
    }

If the "result" of the watched state is ``True``, the watching state *will
execute normally*, and if it is ``False``, the watching state will never run.
This part of ``watch`` mirrors the functionality of the ``require`` requisite.

If the "result" of the watched state is ``True`` *and* the "changes"
key contains a populated dictionary (changes occurred in the watched state),
then the ``watch`` requisite can add additional behavior. This additional
behavior is defined by the ``mod_watch`` function within the watching state
module. If the ``mod_watch`` function exists in the watching state module, it
will be called *in addition to* the normal watching state. The return data
from the ``mod_watch`` function is what will be returned to the master in this
case; the return data from the main watching function is discarded.

If the "changes" key contains an empty dictionary, the ``watch`` requisite acts
exactly like the ``require`` requisite (the watching state will execute if
"result" is ``True``, and fail if "result" is ``False`` in the watched state).

.. note::

    Not all state modules contain ``mod_watch``. If ``mod_watch`` is absent
    from the watching state module, the ``watch`` requisite behaves exactly
    like a ``require`` requisite.

A good example of using ``watch`` is with a :mod:`service.running
<salt.states.service.running>` state. When a service watches a state, then
the service is reloaded/restarted when the watched state changes, in addition
to Salt ensuring that the service is running.

.. code-block:: yaml

    ntpd:
      service.running:
        - watch:
          - file: /etc/ntp.conf
      file.managed:
        - name: /etc/ntp.conf
        - source: salt://ntp/files/ntp.conf

watch_any
~~~~~~~~~

.. versionadded:: 2018.3.0

The state containing the ``watch_any`` requisite is defined as the watching
state. The states specified in the ``watch_any`` statement are defined as the watched
states. When the watched states execute, they will return a dictionary containing
a key named "changes".

If the "result" of any of the watched states is ``True``, the watching state *will
execute normally*, and if all of them are ``False``, the watching state will never run.
This part of ``watch`` mirrors the functionality of the ``require`` requisite.

If the "result" of any of the watched states is ``True`` *and* the "changes"
key contains a populated dictionary (changes occurred in the watched state),
then the ``watch`` requisite can add additional behavior. This additional
behavior is defined by the ``mod_watch`` function within the watching state
module. If the ``mod_watch`` function exists in the watching state module, it
will be called *in addition to* the normal watching state. The return data
from the ``mod_watch`` function is what will be returned to the master in this
case; the return data from the main watching function is discarded.

If the "changes" key contains an empty dictionary, the ``watch`` requisite acts
exactly like the ``require`` requisite (the watching state will execute if
"result" is ``True``, and fail if "result" is ``False`` in the watched state).

.. code-block:: yaml

    apache2:
      service.running:
        - watch_any:
          - file: /etc/apache2/sites-available/site1.conf
          - file: apache2-site2
      file.managed:
        - name: /etc/apache2/sites-available/site1.conf
        - source: salt://apache2/files/site1.conf
    apache2-site2:
      file.managed:
        - name: /etc/apache2/sites-available/site2.conf
        - source: salt://apache2/files/site2.conf

In this example, the service will be reloaded/restarted if either of the
file.managed states has a result of True and has changes.

.. _requisites-prereq:

prereq
~~~~~~

.. versionadded:: 0.16.0

``prereq`` allows for actions to be taken based on the expected results of
a state that has not yet been executed. The state containing the ``prereq``
requisite is defined as the pre-requiring state. The state specified in the
``prereq`` statement is defined as the pre-required state.

When a ``prereq`` requisite is evaluated, the pre-required state reports if it
expects to have any changes. It does this by running the pre-required single
state as a test-run by enabling ``test=True``. This test-run will return a
dictionary containing a key named "changes". (See the ``watch`` section above
for examples of "changes" dictionaries.)

If the "changes" key contains a populated dictionary, it means that the
pre-required state expects changes to occur when the state is actually
executed, as opposed to the test-run. The pre-requiring state will now
actually run. If the pre-requiring state executes successfully, the
pre-required state will then execute. If the pre-requiring state fails, the
pre-required state will not execute.

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

.. _requisites-onfail:

onfail
~~~~~~

.. versionadded:: 2014.7.0

The ``onfail`` requisite allows for reactions to happen strictly as a response
to the failure of another state. This can be used in a number of ways, such as
executing a second attempt to set up a service or begin to execute a separate
thread of states because of a failure.

The ``onfail`` requisite is applied in the same way as ``require`` as ``watch``:

.. code-block:: yaml

    primary_mount:
      mount.mounted:
        - name: /mnt/share
        - device: 10.0.0.45:/share
        - fstype: nfs

    backup_mount:
      mount.mounted:
        - name: /mnt/share
        - device: 192.168.40.34:/share
        - fstype: nfs
        - onfail:
          - mount: primary_mount

.. note::

    Setting failhard (:ref:`globally <global-failhard>` or in
    :ref:`the failing state <state-level-failhard>`) to ``True`` will cause
    ``onfail``, ``onfail_in`` and ``onfail_any`` requisites to be ignored.
    If you want to combine a global failhard set to True with ``onfail``,
    ``onfail_in`` or ``onfail_any``, you will have to explicitly set failhard
    to ``False`` (overriding the global setting) in the state that could fail.

.. note::

    Beginning in the ``2016.11.0`` release of Salt, ``onfail`` uses OR logic for
    multiple listed ``onfail`` requisites. Prior to the ``2016.11.0`` release,
    ``onfail`` used AND logic. See `Issue #22370`_ for more information.

.. _Issue #22370: https://github.com/saltstack/salt/issues/22370

.. _requisites-onfail_any:

onfail_any
~~~~~~~~~~

.. versionadded:: 2018.3.0

The ``onfail_any`` requisite allows for reactions to happen strictly as a response
to the failure of at least one other state. This can be used in a number of ways, such as
executing a second attempt to set up a service or begin to execute a separate
thread of states because of a failure.

The ``onfail_any`` requisite is applied in the same way as ``require_any`` and ``watch_any``:

.. code-block:: yaml

    primary_mount:
      mount.mounted:
        - name: /mnt/share
        - device: 10.0.0.45:/share
        - fstype: nfs

    secondary_mount:
      mount.mounted:
        - name: /mnt/code
        - device: 10.0.0.45:/code
        - fstype: nfs

    backup_mount:
      mount.mounted:
        - name: /mnt/share
        - device: 192.168.40.34:/share
        - fstype: nfs
        - onfail_any:
          - mount: primary_mount
          - mount: secondary_mount

In this example, the `backup_mount` will be mounted if either of the
`primary_mount` or `secondary_mount` states results in a failure.

.. _requisites-onchanges:

onchanges
~~~~~~~~~

.. versionadded:: 2014.7.0

The ``onchanges`` requisite makes a state only apply if the required states
generate changes, and if the watched state's "result" is ``True``. This can be
a useful way to execute a post hook after changing aspects of a system.

If a state has multiple ``onchanges`` requisites then the state will trigger
if any of the watched states changes.

.. note::
    One easy-to-make mistake is to use ``onchanges_in`` when ``onchanges`` is
    supposed to be used. For example, the below configuration is not correct:

    .. code-block:: yaml

        myservice:
          pkg.installed:
            - name: myservice
          file.managed:
            - name: /etc/myservice/myservice.conf
            - source: salt://myservice/files/myservice.conf
            - mode: 600
          cmd.run:
            - name: /usr/libexec/myservice/post-changes-hook.sh
            - onchanges_in:
              - file: /etc/myservice/myservice.conf

    This will set up a requisite relationship in which the ``cmd.run`` state
    always executes, and the ``file.managed`` state only executes if the
    ``cmd.run`` state has changes (which it always will, since the ``cmd.run``
    state includes the command results as changes).

    It may semantically seem like the ``cmd.run`` state should only run
    when there are changes in the file state, but remember that requisite
    relationships involve one state watching another state, and a
    :ref:`requisite_in <requisites-onchanges-in>` does the opposite: it forces
    the specified state to watch the state with the ``requisite_in``.

    The correct usage would be:

    .. code-block:: yaml

        myservice:
          pkg.installed:
            - name: myservice
          file.managed:
            - name: /etc/myservice/myservice.conf
            - source: salt://myservice/files/myservice.conf
            - mode: 600
          cmd.run:
            - name: /usr/libexec/myservice/post-changes-hook.sh
            - onchanges:
              - file: /etc/myservice/myservice.conf

.. _requisites-onchanges_any:

onchanges_any
~~~~~~~~~~~~~

.. versionadded:: 2018.3.0

The ``onchanges_any`` requisite makes a state only apply one of the required states
generates changes, and if one of the watched state's "result" is ``True``. This can be
a useful way to execute a post hook after changing aspects of a system.

.. code-block:: yaml

    myservice:
      pkg.installed:
        - name: myservice
        - name: yourservice
      file.managed:
        - name: /etc/myservice/myservice.conf
        - source: salt://myservice/files/myservice.conf
        - mode: 600
      file.managed:
        - name: /etc/yourservice/yourservice.conf
        - source: salt://yourservice/files/yourservice.conf
        - mode: 600
      cmd.run:
        - name: /usr/libexec/myservice/post-changes-hook.sh
        - onchanges_any:
          - file: /etc/myservice/myservice.conf
          - file: /etc/your_service/yourservice.conf

In this example, the `cmd.run` would be run only if either of the
`file.managed` states generated changes and at least one of the
watched state's "result" is ``True``.

use
~~~

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

    /etc/bar.conf:
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

runas
~~~~~

.. versionadded:: 2017.7.0

The ``runas`` global option is used to set the user which will be used to run
the command in the ``cmd.run`` module.

.. code-block:: yaml

    django:
      pip.installed:
        - name: django >= 1.6, <= 1.7
        - runas: daniel
        - require:
          - pkg: python-pip

In the above state, the pip command run by ``cmd.run`` will be run by the daniel user.

runas_password
~~~~~~~~~~~~~~

.. versionadded:: 2017.7.2

The ``runas_password`` global option is used to set the password used by the
runas global option. This is required by ``cmd.run`` on Windows when ``runas``
is specified. It will be set when ``runas_password`` is defined in the state.

.. code-block:: yaml

    run_script:
      cmd.run:
        - name: Powershell -NonInteractive -ExecutionPolicy Bypass -File C:\\Temp\\script.ps1
        - runas: frank
        - runas_password: supersecret

In the above state, the Powershell script run by ``cmd.run`` will be run by the
frank user with the password ``supersecret``.

.. _requisites-require-in:
.. _requisites-watch-in:
.. _requisites-onchanges-in:

The _in versions of requisites
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All of the requisites also have corresponding requisite_in versions, which do
the reverse of their normal counterparts. The examples below all use
``require_in`` as the example, but note that all of the ``_in`` requisites work
the same way: They result in a normal requisite in the targeted state, which
targets the state which has defines the requisite_in. Thus, a ``require_in``
causes the target state to ``require`` the targeting state. Similarly, a
``watch_in`` causes the target state to ``watch`` the targeting state. This
pattern continues for the rest of the requisites.

If a state declaration needs to be required by another state declaration then
``require_in`` can accommodate it. Therefore, these two sls files would be the
same in the end:

Using ``require``

.. code-block:: yaml

    httpd:
      pkg.installed: []
      service.running:
        - require:
          - pkg: httpd

Using ``require_in``

.. code-block:: yaml

    httpd:
      pkg.installed:
        - require_in:
          - service: httpd
      service.running: []

The ``require_in`` statement is particularly useful when assigning a require
in a separate sls file. For instance it may be common for httpd to require
components used to set up PHP or mod_python, but the HTTP state does not need
to be aware of the additional components that require it when it is set up:

http.sls

.. code-block:: yaml

    httpd:
      pkg.installed: []
      service.running:
        - require:
          - pkg: httpd

php.sls

.. code-block:: yaml

    include:
      - http

    php:
      pkg.installed:
        - require_in:
          - service: httpd

mod_python.sls

.. code-block:: yaml

    include:
      - http

    mod_python:
      pkg.installed:
        - require_in:
          - service: httpd

Now the httpd server will only start if both php and mod_python are first verified to
be installed. Thus allowing for a requisite to be defined "after the fact".


.. _requisites-fire-event:

Fire Event Notifications
========================

.. versionadded:: 2015.8.0

The `fire_event` option in a state will cause the minion to send an event to
the Salt Master upon completion of that individual state.

The following example will cause the minion to send an event to the Salt Master
with a tag of `salt/state_result/20150505121517276431/dasalt/nano` and the
result of the state will be the data field of the event. Notice that the `name`
of the state gets added to the tag.

.. code-block:: yaml

    nano_stuff:
      pkg.installed:
        - name: nano
        - fire_event: True

In the following example instead of setting `fire_event` to `True`,
`fire_event` is set to an arbitrary string, which will cause the event to be
sent with this tag:
`salt/state_result/20150505121725642845/dasalt/custom/tag/nano/finished`

.. code-block:: yaml

    nano_stuff:
      pkg.installed:
        - name: nano
        - fire_event: custom/tag/nano/finished

Altering States
===============

The state altering system is used to make sure that states are evaluated exactly
as the user expects. It can be used to double check that a state preformed
exactly how it was expected to, or to make 100% sure that a state only runs
under certain conditions. The use of unless or onlyif options help make states
even more stateful. The ``check_cmd`` option helps ensure that the result of a
state is evaluated correctly.

Reload
------

``reload_modules`` is a boolean option that forces salt to reload its modules
after a state finishes. ``reload_pillar`` and ``reload_grains`` can also be set.
See :ref:`Reloading Modules <reloading-modules>`.

.. code-block:: yaml

    grains_refresh:
      module.run:
       - name: saltutil.refresh_grains
       - reload_grains: true

    grains_read:
      module.run:
       - name: grains.items

.. _unless-requisite:

Unless
------

.. versionadded:: 2014.7.0

The ``unless`` requisite specifies that a state should only run when any of
the specified commands return ``False``. The ``unless`` requisite operates
as NAND and is useful in giving more granular control over when a state should
execute.

**NOTE**: Under the hood ``unless`` calls ``cmd.retcode`` with
``python_shell=True``. This means the commands referenced by ``unless`` will be
parsed by a shell, so beware of side-effects as this shell will be run with the
same privileges as the salt-minion. Also be aware that the boolean value is
determined by the shell's concept of ``True`` and ``False``, rather than Python's
concept of ``True`` and ``False``.

.. code-block:: yaml

    vim:
      pkg.installed:
        - unless:
          - rpm -q vim-enhanced
          - ls /usr/bin/vim

In the example above, the state will only run if either the vim-enhanced
package is not installed (returns ``False``) or if /usr/bin/vim does not
exist (returns ``False``). The state will run if both commands return
``False``.

However, the state will not run if both commands return ``True``.

Unless checks are resolved for each name to which they are associated.

For example:

.. code-block:: yaml

    deploy_app:
      cmd.run:
        - names:
          - first_deploy_cmd
          - second_deploy_cmd
        - unless: some_check

In the above case, ``some_check`` will be run prior to _each_ name -- once for
``first_deploy_cmd`` and a second time for ``second_deploy_cmd``.

.. versionchanged:: 3000
    The ``unless`` requisite can take a module as a dictionary field in unless.
    The dictionary must contain an argument ``fun`` which is the module that is
    being run, and everything else must be passed in under the args key or will
    be passed as individual kwargs to the module function.

    .. code-block:: yaml

        install apache on debian based distros:
          cmd.run:
            - name: make install
            - cwd: /path/to/dir/whatever-2.1.5/
            - unless:
              - fun: file.file_exists
                path: /usr/local/bin/whatever

    .. code-block:: yaml

      set mysql root password:
        debconf.set:
          - name: mysql-server-5.7
          - data:
              'mysql-server/root_password': {'type': 'password', 'value': {{pillar['mysql.pass']}} }
          - unless:
            - fun: pkg.version
              args:
                - mysql-server-5.7

.. _onlyif-requisite:

Onlyif
------

.. versionadded:: 2014.7.0

The ``onlyif`` requisite specifies that if each command listed in ``onlyif``
returns ``True``, then the state is run. If any of the specified commands
return ``False``, the state will not run.

**NOTE**: Under the hood ``onlyif`` calls ``cmd.retcode`` with
``python_shell=True``. This means the commands referenced by ``onlyif`` will be
parsed by a shell, so beware of side-effects as this shell will be run with the
same privileges as the salt-minion. Also be aware that the boolean value is
determined by the shell's concept of ``True`` and ``False``, rather than Python's
concept of ``True`` and ``False``.

.. code-block:: yaml

    stop-volume:
      module.run:
        - name: glusterfs.stop_volume
        - m_name: work
        - onlyif:
          - gluster volume status work
        - order: 1

    remove-volume:
      module.run:
        - name: glusterfs.delete
        - m_name: work
        - onlyif:
          - gluster volume info work
        - watch:
          - cmd: stop-volume

The above example ensures that the stop_volume and delete modules only run
if the gluster commands return a 0 ret value.

.. versionchanged:: 3000
    The ``onlyif`` requisite can take a module as a dictionary field in onlyif.
    The dictionary must contain an argument ``fun`` which is the module that is
    being run, and everything else must be passed in under the args key or will
    be passed as individual kwargs to the module function.

    .. code-block:: yaml

        install apache on redhat based distros:
          pkg.latest:
            - name: httpd
            - onlyif:
              - fun: match.grain
                tgt: 'os_family: RedHat'

        install apache on debian based distros:
          pkg.latest:
            - name: apache2
            - onlyif:
              - fun: match.grain
                tgt: 'os_family: Debian'

    .. code-block:: yaml

      arbitrary file example:
        file.touch:
          - name: /path/to/file
          - onlyif:
            - fun: file.search
              args:
                - /etc/crontab
                - 'entry1'

runas
~~~~~

.. versionadded:: 2014.7.0

listen and its counterpart listen_in trigger mod_wait functions for states,
when those states succeed and result in changes, similar to how watch its
counterpart watch_in. Unlike watch and watch_in, listen, and listen_in will
not modify the order of states and can be used to ensure your states are
executed in the order they are defined. All listen/listen_in actions will occur
at the end of a state run, after all states have completed.

.. code-block:: yaml

 restart-apache2:
   service.running:
     - name: apache2
     - listen:
       - file: /etc/apache2/apache2.conf

 configure-apache2:
   file.managed:
     - name: /etc/apache2/apache2.conf
     - source: salt://apache2/apache2.conf

This example will cause apache2 to be restarted when the apache2.conf file is
changed, but the apache2 restart will happen at the end of the state run.

.. code-block:: yaml

 restart-apache2:
   service.running:
     - name: apache2

 configure-apache2:
   file.managed:
     - name: /etc/apache2/apache2.conf
     - source: salt://apache2/apache2.conf
     - listen_in:
       - service: apache2

This example does the same as the above example, but puts the state argument
on the file resource, rather than the service resource.

check_cmd
---------

.. versionadded:: 2014.7.0

Check Command is used for determining that a state did or did not run as
expected.

**NOTE**: Under the hood ``check_cmd`` calls ``cmd.retcode`` with
``python_shell=True``. This means the commands referenced by unless will be
parsed by a shell, so beware of side-effects as this shell will be run with the
same privileges as the salt-minion.

.. code-block:: yaml

    comment-repo:
      file.replace:
        - name: /etc/yum.repos.d/fedora.repo
        - pattern: '^enabled=0'
        - repl: enabled=1
        - check_cmd:
          - "! grep 'enabled=0' /etc/yum.repos.d/fedora.repo"

This will attempt to do a replace on all ``enabled=0`` in the .repo file, and
replace them with ``enabled=1``. The ``check_cmd`` is just a bash command. It
will do a grep for ``enabled=0`` in the file, and if it finds any, it will
return a 0, which will be inverted by the leading ``!``, causing ``check_cmd``
to set the state as failed. If it returns a 1, meaning it didn't find any
``enabled=0``, it will be inverted by the leading ``!``, returning a 0, and
declaring the function succeeded.

**NOTE**: This requisite ``check_cmd`` functions differently than the ``check_cmd``
of the ``file.managed`` state.

Overriding Checks
-----------------

There are two commands used for the above checks.

``mod_run_check`` is used to check for ``onlyif`` and ``unless``. If the goal is to
override the global check for these to variables, include a ``mod_run_check`` in the
salt/states/ file.

``mod_run_check_cmd`` is used to check for the check_cmd options. To override
this one, include a ``mod_run_check_cmd`` in the states file for the state.

Retrying States
===============

.. versionadded:: 2017.7.0

The retry option in a state allows it to be executed multiple times until a desired
result is obtained or the maximum number of attempts have been made.

The retry option can be configured by the ``attempts``, ``until``, ``interval``, and
``splay`` parameters.

The ``attempts`` parameter controls the maximum number of times the state will be
run.  If not specified or if an invalid value is specified, ``attempts`` will default
to ``2``.

The ``until`` parameter defines the result that is required to stop retrying the state.
If not specified or if an invalid value is specified, ``until`` will default to ``True``

The ``interval`` parameter defines the amount of time, in seconds, that the system
will wait between attempts.  If not specified or if an invalid value is specified,
``interval`` will default to ``30``.

The ``splay`` parameter allows the ``interval`` to be additionally spread out.  If not
specified or if an invalid value is specified, ``splay`` defaults to ``0`` (i.e. no
splaying will occur).

The following example will run the pkg.installed state until it returns ``True`` or it has
been run ``5`` times.  Each attempt will be ``60`` seconds apart and the interval will be splayed
up to an additional ``10`` seconds:

.. code-block:: yaml

    my_retried_state:
      pkg.installed:
        - name: nano
        - retry:
            attempts: 5
            until: True
            interval: 60
            splay: 10

The following example will run the pkg.installed state with all the defaults for ``retry``.
The state will run up to ``2`` times, each attempt being ``30`` seconds apart, or until it
returns ``True``.

.. code-block:: yaml

    install_nano:
      pkg.installed:
        - name: nano
        - retry: True

The following example will run the file.exists state every ``30`` seconds up to ``15`` times
or until the file exists (i.e. the state returns ``True``).

.. code-block:: yaml

    wait_for_file:
      file.exists:
        - name: /path/to/file
        - retry:
            attempts: 15
            interval: 30

Return data from a retried state
--------------------------------

When a state is retried, the returned output is as follows:

The ``result`` return value is the ``result`` from the final run.  For example, imagine a state set
to ``retry`` up to three times or ``until`` ``True``.  If the state returns ``False`` on the first run
and then ``True`` on the second, the ``result`` of the state will be ``True``.

The ``started`` return value is the ``started`` from the first run.

The ``duration`` return value is the total duration of all attempts plus the retry intervals.

The ``comment`` return value will include the result and comment from all previous attempts.

For example:

.. code-block:: yaml

    wait_for_file:
      file.exists:
        - name: /path/to/file
        - retry:
            attempts: 10
            interval: 2
            splay: 5

Would return similar to the following.  The state result in this case is ``False`` (file.exist was run 10
times with a 2 second interval, but the file specified did not exist on any run).

.. code-block:: none

          ID: wait_for_file
    Function: file.exists
      Result: False
     Comment: Attempt 1: Returned a result of "False", with the following comment: "Specified path /path/to/file does not exist"
              Attempt 2: Returned a result of "False", with the following comment: "Specified path /path/to/file does not exist"
              Attempt 3: Returned a result of "False", with the following comment: "Specified path /path/to/file does not exist"
              Attempt 4: Returned a result of "False", with the following comment: "Specified path /path/to/file does not exist"
              Attempt 5: Returned a result of "False", with the following comment: "Specified path /path/to/file does not exist"
              Attempt 6: Returned a result of "False", with the following comment: "Specified path /path/to/file does not exist"
              Attempt 7: Returned a result of "False", with the following comment: "Specified path /path/to/file does not exist"
              Attempt 8: Returned a result of "False", with the following comment: "Specified path /path/to/file does not exist"
              Attempt 9: Returned a result of "False", with the following comment: "Specified path /path/to/file does not exist"
              Specified path /path/to/file does not exist
     Started: 09:08:12.903000
    Duration: 47000.0 ms
     Changes:
