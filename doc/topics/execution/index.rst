.. _remote-execution:

================
Remote Execution
================

Running pre-defined or arbitrary commands on remote hosts, also known as
remote execution, is the core function of Salt. The following links explore
modules and returners, which are two key elements of remote execution.

**Salt Execution Modules**

Salt execution modules are called by the remote execution system to perform
a wide variety of tasks. These modules provide functionality such as installing
packages, restarting a service, running a remote command, transferring files,
and so on.

    :ref:`Full list of execution modules <all-salt.modules>`
        Contains: a list of core modules that ship with Salt.

    :ref:`Writing execution modules <writing-execution-modules>`
        Contains: a guide on how to write Salt modules.

.. toctree::

    ../tutorials/modules
    remote_execution
    ../../ref/modules/index
    ../../ref/returners/index
    ../../ref/executors/index
