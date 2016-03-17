.. _orchestrate-runner:

==================
Orchestrate Runner
==================

Orchestration is accomplished in salt primarily through the :ref:`Orchestrate
Runner <orchestrate-runner>`. Added in version 0.17.0, this Salt :doc:`Runner
</ref/runners/index>` can use the full suite of :doc:`requisites
</ref/states/requisites>` available in states, and can also execute
states/functions using salt-ssh.

The Orchestrate Runner
----------------------

.. versionadded:: 0.17.0

.. note:: Orchestrate Deprecates OverState

  The Orchestrate Runner (originally called the state.sls runner) offers all
  the functionality of the OverState, but with some advantages:

  * All :doc:`requisites </ref/states/requisites>` available in states can be
    used.
  * The states/functions will also work on salt-ssh minions.

  The Orchestrate Runner was added with the intent to eventually deprecate the
  OverState system, however the OverState will still be maintained until Salt
  2015.8.0.

The orchestrate runner generalizes the Salt state system to a Salt master
context.  Whereas the ``state.sls``, ``state.highstate``, et al functions are
concurrently and independently executed on each Salt minion, the
``state.orchestrate`` runner is executed on the master, giving it a
master-level view and control over requisites, such as state ordering and
conditionals.  This allows for inter minion requisites, like ordering the
application of states on different minions that must not happen simultaneously,
or for halting the state run on all minions if a minion fails one of its
states.

If you want to setup a load balancer in front of a cluster of web servers, for
example, you can ensure the load balancer is setup before the web servers or
stop the state run altogether if one of the minions does not set up correctly.

The ``state.sls``, ``state.highstate``, et al functions allow you to statefully
manage each minion and the ``state.orchestrate`` runner allows you to
statefully manage your entire infrastructure.

Executing the Orchestrate Runner
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Orchestrate Runner command format is the same as for the ``state.sls``
function, except that since it is a runner, it is executed with ``salt-run``
rather than ``salt``.  Assuming you have a state.sls file called
``/srv/salt/orch/webserver.sls`` the following command run on the master will
apply the states defined in that file.

.. code-block:: bash

    salt-run state.orchestrate orch.webserver

.. note::

    ``state.orch`` is a synonym for ``state.orchestrate``

.. versionchanged:: 2014.1.1

    The runner function was renamed to ``state.orchestrate`` to avoid confusion
    with the :mod:`state.sls <salt.modules.state.sls>` execution function. In
    versions 0.17.0 through 2014.1.0, ``state.sls`` must be used.

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


More Complex Orchestration
~~~~~~~~~~~~~~~~~~~~~~~~~~

Many states/functions can be configured in a single file, which when combined
with the full suite of :doc:`requisites </ref/states/requisites>`, can be used
to easily configure complex orchestration tasks. Additionally, the
states/functions will be executed in the order in which they are defined,
unless prevented from doing so by any :doc:`requisites
</ref/states/requisites>`, as is the default in SLS files since 0.17.0.

.. code-block:: yaml

    cmd.run:
      salt.function:
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
