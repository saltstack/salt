.. _requisites:

===========================================
Requisites and Other Global State Arguments
===========================================

Requisites
==========

The Salt requisite system is used to create relationships between states. The
core idea being that, when one state is dependent somehow on another, that
inter-dependency can be easily defined.

Requisites come in two types: Direct requisites (such as ``require``),
and requisite_ins (such as ``require_in``). The relationships are
directional: a direct requisite requires something from another state.
However, a requisite_in inserts a requisite into the targeted state pointing to
the targeting state.  The following example demonstrates a direct requisite:

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
on me".  This will result in a ``require`` being inserted into the
``/etc/vimrc`` state which  targets the ``vim`` state.

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
---------------------------------------

There are six direct requisite statements that can be used in Salt:
``require``, ``watch``, ``prereq``, ``use``, ``onchanges``, and ``onfail``.
Each direct requisite also has a corresponding requisite_in: ``require_in``,
``watch_in``, ``prereq_in``, ``use_in``, ``onchanges_in``, and ``onfail_in``.
All of the requisites define specific relationships and always work with the
dependency logic defined above.

.. _requisites-require:

require
~~~~~~~

The use of ``require`` demands that the dependent state executes before the
depending state. The state containing the ``require`` requisite is defined as the
depending state. The state specified in the ``require`` statement is defined as the
dependent state. If the dependent state's execution succeeds, the depending state
will then execute. If the dependent state's execution fails, the depending state
will not execute. In the first example above, the file ``/etc/vimrc`` will only
execute after the vim package is installed successfully.

Require an entire sls file
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

.. _requisites-watch:

watch
~~~~~

``watch`` statements are used to add additional behavior when there are changes
in other states.

.. note::

    If a state should only execute when another state has changes, and
    otherwise do nothing, the new ``onchanges`` requisite should be used
    instead of ``watch``.  ``watch`` is designed to add *additional* behavior
    when there are changes, but otherwise execute normally.

The state containing the ``watch`` requisite is defined as the watching
state. The state specified in the ``watch`` statement is defined as the watched
state. When the watched state executes, it will return a dictionary containing
a key named "changes". Here are two examples of state return dictionaries,
shown in json for clarity:

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

If the "result" of the watched state is ``True``, the watching state *will
execute normally*.  This part of ``watch`` mirrors the functionality of the
``require`` requisite.  If the "result" of the watched state is ``False``, the
watching state will never run, nor will the watching state's ``mod_watch``
function execute.

However, if the "result" of the watched state is ``True``, and the "changes"
key contains a populated dictionary (changes occurred in the watched state),
then the ``watch`` requisite can add additional behavior.  This additional
behavior is defined by the ``mod_watch`` function within the watching state
module.  If the ``mod_watch`` function exists in the watching state module, it
will be called *in addition to* the normal watching state.  The return data
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

.. _requisites-prereq:

prereq
~~~~~~

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

onchanges
~~~~~~~~~

.. versionadded:: 2014.7.0

The ``onchanges`` requisite makes a state only apply if the required states
generate changes, and if the watched state's "result" is ``True``. This can be
a useful way to execute a post hook after changing aspects of a system.

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
.. _requisites-watch-in:

The _in versions of requisites
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All of the requisites also have corresponding requisite_in versions, which do
the reverse of their normal counterparts.  The examples below all use
``require_in`` as the example, but note that all of the ``_in`` requisites work
the same way:  They result in a normal requisite in the targeted state, which
targets the state which has defines the requisite_in.  Thus, a ``require_in``
causes the target state to ``require`` the targeting state.  Similarly, a
``watch_in`` causes the target state to ``watch`` the targeting state.  This
pattern continues for the rest of the requisites.

If a state declaration needs to be required by another state declaration then
``require_in`` can accommodate it. Therefore, these two sls files would be the
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


Altering States
===============

The state altering system is used to make sure that states are evaluated exactly
as the user expects.  It can be used to double check that a state preformed
exactly how it was expected to, or to make 100% sure that a state only runs
under certain conditions.  The use of unless or onlyif options help make states
even more stateful.  The check_cmds option helps ensure that the result of a
state is evaluated correctly.

Unless
------

.. versionadded:: 2014.7.0

The ``unless`` requisite specifies that a state should only run when any of
the specified commands return ``False``. The ``unless`` requisite operates
as NOR and is useful in giving more granular control over when a state should
execute.

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

Onlyif
------

.. versionadded:: 2014.7.0

``onlyif`` is the opposite of ``unless``. If all of the commands in ``onlyif``
return ``True``, then the state is run. If any of the specified commands
return ``False``, the state will not run.

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

Listen/Listen_in
----------------

.. versionadded:: 2014.7.0

listen and its counterpart listen_in trigger mod_wait functions for states,
when those states succeed and result in changes, similar to how watch its
counterpart watch_in. Unlike watch and watch_in, listen and listen_in will
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
     - path: /etc/apache2/apache2.conf
     - source: salt://apache2/apache2.conf

This example will cause apache2 to be restarted when the apache2.conf file is
changed, but the apache2 restart will happen at the end of the state run.

.. code-block:: yaml

 restart-apache2:
   service.running:
     - name: apache2

 configure-apache2:
   file.managed:
     - path: /etc/apache2/apache2.conf
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

.. code-block:: yaml

    comment-repo:
      file.replace:
        - path: /etc/yum.repos.d/fedora.repo
        - pattern: ^enabled=0
        - repl: enabled=1
        - check_cmd:
          - grep 'enabled=0' /etc/yum.repos.d/fedora.repo && return 1 || return 0

This will attempt to do a replace on all enabled=0 in the .repo file, and
replace them with enabled=1.  The check_cmd is just a bash command.  It will do
a grep for enabled=0 in the file, and if it finds any, it will return a 0, which
will prompt the && portion of the command to return a 1, causing check_cmd to
set the state as failed.  If it returns a 1, meaning it didn't find any
'enabled=0' it will hit the || portion of the command, returning a 0, and
declaring the function succeeded.

Overriding Checks
-----------------

There are two commands used for the above checks.

``mod_run_check`` is used to check for ``onlyif`` and ``unless``.  If the goal is to
override the global check for these to variables, include a ``mod_run_check`` in the
salt/states/ file.

``mod_run_check_cmd`` is used to check for the check_cmd options.  To override
this one, include a ``mod_run_check_cmd`` in the states file for the state.
