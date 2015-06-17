=================================================
States Tutorial, Part 5 - Orchestration with Salt
=================================================

.. note::

  This tutorial builds on some of the topics covered in the earlier
  :doc:`States Walkthrough <states_pt1>` pages. It is recommended to start with
  :doc:`Part 1 <states_pt1>` if you are not familiar with how to use states.


Orchestration is accomplished in salt primarily through the :ref:`Orchestrate
Runner <orchestrate-runner>`. Added in version 0.17.0, this Salt :doc:`Runner
</ref/runners/index>` can use the full suite of :doc:`requisites
</ref/states/requisites>` available in states, and can also execute
states/functions using salt-ssh.


.. _orchestrate-runner:

The Orchestrate Runner
----------------------

.. versionadded:: 0.17.0

* All :doc:`requisites </ref/states/requisites>` available in states can be
  used.
* The states/functions can be executed using salt-ssh.

Configuration Syntax
~~~~~~~~~~~~~~~~~~~~

To execute a state, use :mod:`salt.state <salt.states.saltmod.state>`:

.. code-block:: yaml

    install_nginx:
      salt.state:
        - tgt: 'web*'
        - sls:
          - nginx

To execute a function, use :mod:`salt.function <salt.states.saltmod.function>`:

.. code-block:: yaml

    cmd.run:
      salt.function:
        - tgt: '*'
        - arg:
          - rm -rf /tmp/foo


Triggering a Highstate
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    webserver_setup:
      salt.state:
        - tgt: 'web*'
        - highstate: True

Executing the Orchestrate Runner
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Orchestrate Runner can be executed using the ``state.orchestrate`` runner
function. ``state.orch`` also works, for those that would like to type less.

Assuming that your ``base`` environment is located at ``/srv/salt``, and you
have placed a configuration file in ``/srv/salt/orchestration/webserver.sls``,
then the following could both be used:

.. code-block:: bash

    salt-run state.orchestrate orchestration.webserver
    salt-run state.orch orchestration.webserver

.. versionchanged:: 2014.1.1

    The runner function was renamed to ``state.orchestrate``. In versions
    0.17.0 through 2014.1.0, ``state.sls`` must be used. This was renamed to
    avoid confusion with the :mod:`state.sls <salt.modules.state.sls>`
    execution function.

    .. code-block:: bash

        salt-run state.sls orchestration.webserver


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
