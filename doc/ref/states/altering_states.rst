.. _altering_states:

===============
Altering States
===============

.. note::

    The ``unless``, ``onlyif``, and ``check_cmd`` options will be supported
    starting with the feature release codenamed Helium

The state altering system is used to make sure that states are evaluated exactly
as the user expects.  It can be used to double check that a state preformed
exactly how it was expected to, or to make 100% sure that a state only runs
under certain conditions.  The use of unless or onlyif options help make states
even more stateful.  The check_cmds option helps ensure that the result of a
state is evaluated correctly.

Unless
------

Use unless to only run if any of the specified commands return False.

.. code-block:: yaml

    vim:
      pkg.installed:
        - unless:
            - rpm -q vim-enhanced
            - ls /usr/bin/vim

This state will not run if the vim-enhanced package is already installed, or if
/usr/bin/vim exists.  It gives more granular control over when a state should be
run.

Onlyif
------

Onlyif is the opposite of Unless.  If all of the commands in onlyif return True,
then the state is run.

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

This will ensure that the stop_volume and delete modules are only run if the
gluster commands return back a 0 ret value.

Check_Cmd
---------

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
=================

There are two commands used for the above checks.

`mod_run_check` is used to check for onlyif and unless.  If the goal is to
override the global check for these to variables, include a mod_run_check in the
salt/states/ file.

`mod_run_check_cmd` is used to check for the check_cmd options.  To override
this one, include a mod_run_check_cmd in the states file for the state.
