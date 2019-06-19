.. _ssh-wrapper:

===========
SSH Wrapper
===========

Salt-SSH Background
===================

Salt-SSH works by creating a tar ball of salt, a bunch of python modules, and a generated
short minion config. It then copies this onto the destination host over ssh, then
uses that host's local python install to run ``salt-client --local`` with any requested modules.
It does not automatically copy over states or cache files and since it is uses a local file_client,
modules that rely on :py:func:`cp.cache* <salt.modules.cp>` functionality do not work.

SSH Wrapper modules
===================

To support cp modules or other functionality which might not otherwise work in the remote environment,
a wrapper module can be created. These modules are run from the salt-master initiating the salt-ssh
command and can include logic to support the needed functionality. SSH Wrapper modules are located in
/salt/client/ssh/wrapper/ and are named the same as the execution module being extended. Any functions
defined inside of the wrapper module are called from the ``salt-ssh module.function argument``
command rather than executing on the minion.

State Module example
--------------------

Running salt states on an salt-ssh minion, obviously requires the state files themselves. To support this,
a state module wrapper script exists at salt/client/ssh/wrapper/state.py, and includes standard state
functions like :py:func:`apply <salt.modules.state.apply>`, :py:func:`sls <salt.modules.state.sls>`,
and :py:func:`highstate <salt.modules.state.highstate>`. When executing ``salt-ssh minion state.highstate``,
these wrapper functions are used and include the logic to walk the low_state output for that minion to
determine files used, gather needed files, tar them together, transfer the tar file to the minion over
ssh, and run a state on the ssh minion. This state then extracts the tar file, applies the needed states
and data, and cleans up the transferred files.

Wrapper Handling
----------------

From the wrapper script any invocations of ``__salt__['some.module']()`` do not run on the master
which is running the wrapper, but instead magically are invoked on the minion over ssh.
Should the function being called exist in the wrapper, the wrapper function will be
used instead.

One way of supporting this workflow may be to create a wrapper function which performs the needed file
copy operations. Now that files are resident on the ssh minion, the next step is to run the original
execution module function. But since that function name was already overridden by the wrapper, a
function alias can be created in the original execution module, which can then be called from the
wrapper.

Example
```````

The saltcheck module needs sls and tst files on the minion to function. The invocation of
:py:func:`saltcheck.run_state_tests <salt.modules.saltcheck.run_state_tests>` is run from
the wrapper module, and is responsible for performing the needed file copy. The
:py:func:`saltcheck <salt.modules.saltcheck>` execution module includes an alias line of
``run_state_tests_ssh = salt.utils.functools.alias_function(run_state_tests, 'run_state_tests_ssh')``
which creates an alias of ``run_state_tests`` with the name ``run_state_tests_ssh``. At the end of
the ``run_state_tests`` function in the wrapper module, it then calls
``__salt__['saltcheck.run_state_tests_ssh']()``. Since this function does not exist in the wrapper script,
the call is made on the remote minion, which then having the needed files, runs as expected.
