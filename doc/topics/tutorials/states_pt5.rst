=================================================
States Tutorial, Part 5 - Orchestration with Salt
=================================================

.. note::

  This tutorial builds on some of the topics covered in the earlier
  :doc:`States Walkthrough <states_pt1>` pages. It is recommended to start with
  :doc:`Part 1 <states_pt1>` if you are not familiar with how to use states.


Orchestration can be accomplished in two distinct ways:

1. The :ref:`OverState System <states-overstate>`. Added in version 0.11.0,
   this Salt :doc:`Runner </ref/runners/index>` allows for SLS files to be
   organized into stages, and to require that one or more stages successfully
   execute before another stage will run.

2. The :ref:`Orchestrate Runner <orchestrate-runner>`. Added in version 0.17.0,
   this Salt :doc:`Runner </ref/runners/index>` can use the full suite of
   :doc:`requisites </ref/states/requisites>` available in states, and can also
   execute states/functions using salt-ssh. This runner was designed with the
   eventual goal of replacing the :ref:`OverState <states-overstate>`. 


.. _states-overstate:

The OverState System
--------------------

Often, servers need to be set up and configured in a specific order, and systems
should only be set up if systems earlier in the sequence have been set up
without any issues.

The OverState system can be used to orchestrate deployment in a smooth and
reliable way across multiple systems in small to large environments.

The OverState SLS
~~~~~~~~~~~~~~~~~

The OverState system is managed by an SLS file named ``overstate.sls``, located
in the root of a Salt fileserver environment.

The overstate.sls configures an unordered list of stages, each stage defines
the minions on which to execute the state, and can define what sls files to
run, execute a :mod:`state.highstate <salt.modules.state.highstate>`, or
execute a function. Here's a sample ``overstate.sls``:

.. code-block:: yaml

    mysql:
      match: 'db*'
      sls:
        - mysql.server
        - drbd
    webservers:
      match: 'web*'
      require:
        - mysql
    all:
      match: '*'
      require:
        - mysql
        - webservers

Given the above setup, the OverState will be carried out as follows:

1. The ``mysql`` stage will be executed first because it is required by the
   ``webservers`` and ``all`` stages.  It will execute :mod:`state.sls
   <salt.modules.state.sls>` once for each of the two listed SLS targets
   (``mysql.server`` and ``drbd``).  These states will be executed on all
   minions whose minion ID starts with "db".
   
2. The ``webservers`` stage will then be executed, but only if the ``mysql``
   stage executes without any failures. The ``webservers`` stage will execute a
   :mod:`state.highstate <salt.modules.state.highstate>` on all minions whose
   minion IDs start with "web".

3. Finally, the ``all`` stage will execute, running :mod:`state.highstate
   <salt.modules.state.highstate>` on all systems, if and only if the ``mysql``
   and ``webservers`` stages completed without any failures.

Any failure in the above steps would cause the requires to fail, preventing the
dependent stages from executing.


Using Functions with OverState
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the above example, you'll notice that the stages lacking an ``sls`` entry
run a :mod:`state.highstate <salt.modules.state.highstate>`. As mentioned
earlier, it is also possible to execute other functions in a stage. This
functionality was added in version 0.15.0.

Running a function is easy:

.. code-block:: yaml

    http:
      function:
        pkg.install:
          - httpd


The list of function arguments are defined after the declared function. So, the
above stage would run ``pkg.install http``. Requisites only function properly
if the given function supports returning a custom return code.

Executing an OverState
~~~~~~~~~~~~~~~~~~~~~~

Since the OverState is a :doc:`Runner </ref/runners/index>`, it is executed
using the ``salt-run`` command. The runner function for the OverState is
``state.over``.

.. code-block:: bash

    salt-run state.over

The function will by default look in the root of the ``base`` environment (as
defined in :conf_master:`file_roots`) for a file called ``overstate.sls``, and
then execute the stages defined within that file.

Different environments and paths can be used as well, by adding them as
positional arguments:

.. code-block:: bash

    salt-run state.over dev /root/other-overstate.sls

The above would run an OverState using the ``dev`` fileserver environment, with
the stages defined in ``/root/other-overstate.sls``.

.. warning::

    Since these are positional arguments, when defining the path to the
    overstate file the environment must also be specified, even if it is the
    ``base`` environment.

.. note::

    Remember, salt-run is always executed on the master.


.. _orchestrate-runner:

The Orchestrate Runner
----------------------

.. versionadded:: 0.17.0

As noted above in the introduction, the Orchestrate Runner (originally called
the state.sls runner) offers all the functionality of the OverState, but with a
couple advantages:

* All :doc:`requisites </ref/states/requisites>` available in states can be
  used.
* The states/functions can be executed using salt-ssh.

The Orchestrate Runner was added with the intent to eventually deprecate the
OverState system, however the OverState will still be maintained for the
foreseeable future.

Configuration Syntax
~~~~~~~~~~~~~~~~~~~~

The configuration differs slightly from that of the OverState, and more closely
resembles the configuration schema used for states.

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

Wheras with the OverState, a Highstate is run by simply omitting an ``sls`` or
``function`` argument, with the Orchestrate Runner the Highstate must
explicitly be requested by using ``highstate: True``:

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
