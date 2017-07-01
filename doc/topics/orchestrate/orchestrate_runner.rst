.. _orchestrate-runner:

==================
Orchestrate Runner
==================

Executing states or highstate on a minion is perfect when you want to ensure that
minion configured and running the way you want. Sometimes however you want to 
configure a set of minions all at once.

For example, if you want to set up a load balancer in front of a cluster of web 
servers you can ensure the load balancer is set up first, and then the same
matching configuration is applied consistently across the whole cluster.

Orchestration is the way to do this.


The Orchestrate Runner
----------------------

.. versionadded:: 0.17.0

.. note:: Orchestrate Deprecates OverState

  The Orchestrate Runner (originally called the state.sls runner) offers all
  the functionality of the OverState, but with some advantages:

  * All :ref:`requisites` available in states can be
    used.
  * The states/functions will also work on salt-ssh minions.

  The Orchestrate Runner replaced the OverState system in Salt 2015.8.0.

The orchestrate runner generalizes the Salt state system to a Salt master
context.  Whereas the ``state.sls``, ``state.highstate``, et al. functions are
concurrently and independently executed on each Salt minion, the
``state.orchestrate`` runner is executed on the master, giving it a
master-level view and control over requisites, such as state ordering and
conditionals.  This allows for inter minion requisites, like ordering the
application of states on different minions that must not happen simultaneously,
or for halting the state run on all minions if a minion fails one of its
states.

The ``state.sls``, ``state.highstate``, et al. functions allow you to statefully
manage each minion and the ``state.orchestrate`` runner allows you to
statefully manage your entire infrastructure.

Writing SLS Files
~~~~~~~~~~~~~~~~~

Orchestrate SLS files are stored in the same location as State SLS files. This
means that both ``file_roots`` and ``gitfs_remotes`` impact what SLS files are
available to the reactor and orchestrator.

It is recommended to keep reactor and orchestrator SLS files in their own
uniquely named subdirectories such as ``_orch/``, ``orch/``, ``_orchestrate/``,
``react/``, ``_reactor/``, etc. This will avoid duplicate naming and will help
prevent confusion.

Executing the Orchestrate Runner
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Orchestrate Runner command format is the same as for the ``state.sls``
function, except that since it is a runner, it is executed with ``salt-run``
rather than ``salt``.  Assuming you have a state.sls file called
``/srv/salt/orch/webserver.sls`` the following command, run on the master,
will apply the states defined in that file.

.. code-block:: bash

    salt-run state.orchestrate orch.webserver

.. note::

    ``state.orch`` is a synonym for ``state.orchestrate``

.. versionchanged:: 2014.1.1

    The runner function was renamed to ``state.orchestrate`` to avoid confusion
    with the :mod:`state.sls <salt.modules.state.sls>` execution function. In
    versions 0.17.0 through 2014.1.0, ``state.sls`` must be used.

Masterless Orchestration
~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2016.11.0

To support salt orchestration on masterless minions, the Orchestrate Runner is
available as an execution module. The syntax for masterless orchestration is
exactly the same, but it uses the ``salt-call`` command and the minion
configuration must contain the ``file_mode: local`` option. Alternatively,
use ``salt-call --local`` on the command line.

.. code-block:: bash

    salt-call --local state.orchestrate orch.webserver

.. note::

    Masterless orchestration supports only the ``salt.state`` command in an
    sls file; it does not (currently) support the ``salt.function`` command.

Examples
~~~~~~~~

Function
^^^^^^^^

To execute a function, use :mod:`salt.function <salt.states.saltmod.function>`:

.. code-block:: yaml

    # /srv/salt/orch/cleanfoo.sls
    cmd.run:
      salt.function:
        - tgt: '*'
        - arg:
          - rm -rf /tmp/foo

.. code-block:: bash

    salt-run state.orchestrate orch.cleanfoo

If you omit the "name" argument, the ID of the state will be the default name,
or in the case of ``salt.function``, the execution module function to run. You
can specify the "name" argument to avoid conflicting IDs:

.. code-block:: yaml

    copy_some_file:
      salt.function:
        - name: file.copy
        - tgt: '*'
        - arg:
          - /path/to/file
          - /tmp/copy_of_file
        - kwarg:
            remove_existing: true

State
^^^^^

To execute a state, use :mod:`salt.state <salt.states.saltmod.state>`.

.. code-block:: yaml

    # /srv/salt/orch/webserver.sls
    install_nginx:
      salt.state:
        - tgt: 'web*'
        - sls:
          - nginx

.. code-block:: bash

    salt-run state.orchestrate orch.webserver

Highstate
^^^^^^^^^

To run a highstate, set ``highstate: True`` in your state config:

.. code-block:: yaml

    # /srv/salt/orch/web_setup.sls
    webserver_setup:
      salt.state:
        - tgt: 'web*'
        - highstate: True

.. code-block:: bash

    salt-run state.orchestrate orch.web_setup

Runner
^^^^^^

To execute another runner, use :mod:`salt.runner <salt.states.saltmod.runner>`.
For example to use the ``cloud.profile`` runner in your orchestration state
additional options to replace values in the configured profile, use this:

.. code-block:: yaml

    # /srv/salt/orch/deploy.sls
    create_instance:
      salt.runner:
        - name: cloud.profile
        - prof: cloud-centos
        - provider: cloud
        - instances:
          - server1
        - opts:
            minion:
              master: master1

To get a more dynamic state, use jinja variables together with
``inline pillar data``.
Using the same example but passing on pillar data, the state would be like
this.

.. code-block:: yaml

    # /srv/salt/orch/deploy.sls
    {% set servers = salt['pillar.get']('servers', 'test') %}
    {% set master = salt['pillat.get']('master', 'salt') %}
    create_instance:
      salt.runner:
        - name: cloud.profile
        - prof: cloud-centos
        - provider: cloud
        - instances:
          - {{ servers }}
        - opts:
            minion:
              master: {{ master }}

To execute with pillar data.

.. code-block:: bash

    salt-run state.orch orch.deploy pillar='{"servers": "newsystem1",
    "master": "mymaster"}'


More Complex Orchestration
~~~~~~~~~~~~~~~~~~~~~~~~~~

Many states/functions can be configured in a single file, which when combined
with the full suite of :ref:`requisites`, can be used
to easily configure complex orchestration tasks. Additionally, the
states/functions will be executed in the order in which they are defined,
unless prevented from doing so by any :ref:`requisites`, as is the default in
SLS files since 0.17.0.

.. code-block:: yaml

    bootstrap_servers:
      salt.function:
        - name: cmd.run
        - tgt: 10.0.0.0/24
        - tgt_type: ipcidr
        - arg:
          - bootstrap

    storage_setup:
      salt.state:
        - tgt: 'role:storage'
        - tgt_type: grain
        - sls: ceph
        - require:
          - salt: webserver_setup

    webserver_setup:
      salt.state:
        - tgt: 'web*'
        - highstate: True

Given the above setup, the orchestration will be carried out as follows:

1. The shell command ``bootstrap`` will be executed on all minions in the
   10.0.0.0/24 subnet.

2. A Highstate will be run on all minions whose ID starts with "web", since
   the ``storage_setup`` state requires it.

3. Finally, the ``ceph`` SLS target will be executed on all minions which have
   a grain called ``role`` with a value of ``storage``.


.. note::

    Remember, salt-run is always executed on the master.
