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
states/functions using salt-ssh. This runner replaces the :ref:`OverState
<states-overstate>`.

.. _orchestrate-runner:

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
  Boron.

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


.. _states-overstate:

The OverState System
--------------------

.. warning::

    The OverState runner is deprecated, and will be removed in the feature
    release of Salt codenamed Boron. (Three feature releases after 2014.7.0,
    which is codenamed Helium)

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

.. note::
   The ``match`` argument uses :ref:`compound matching <targeting-compound>`

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
   <salt.modules.state.highstate>` on all systems, if, and only if the ``mysql``
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
