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

.. _orchestrate-runner-fail-functions:

Fail Functions
**************

When running a remote execution function in orchestration, certain return
values for those functions may indicate failure, while the function itself
doesn't set a return code. For those circumstances, using a "fail function"
allows for a more flexible means of assessing success or failure.

A fail function can be written as part of a :ref:`custom execution module
<writing-execution-modules>`. The function should accept one argument, and
return a boolean result. For example:

.. code-block:: python

    def check_func_result(retval):
        if some_condition:
            return True
        else:
            return False


The function can then be referenced in orchestration SLS like so:

.. code-block:: yaml

    do_stuff:
      salt.function:
        - name: modname.funcname
        - tgt: '*'
        - fail_function: mymod.check_func_result

.. important::
    Fail functions run *on the master*, so they must be synced using ``salt-run
    saltutil.sync_modules``.

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

.. code-block:: jinja

    # /srv/salt/orch/deploy.sls
    {% set servers = salt['pillar.get']('servers', 'test') %}
    {% set master = salt['pillar.get']('master', 'salt') %}
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

.. _orchestrate-runner-return-codes-runner-wheel:

Return Codes in Runner/Wheel Jobs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2018.3.0

State (``salt.state``) jobs are able to report failure via the :ref:`state
return dictionary <state-return-data>`. Remote execution (``salt.function``)
jobs are able to report failure by setting a ``retcode`` key in the
``__context__`` dictionary. However, runner (``salt.runner``) and wheel
(``salt.wheel``) jobs would only report a ``False`` result when the
runner/wheel function raised an exception. As of the 2018.3.0 release, it is
now possible to set a retcode in runner and wheel functions just as you can do
in remote execution functions. Here is some example pseudocode:

.. code-block:: python

    def myrunner():
        ...
        # do stuff
        ...
        if some_error_condition:
            __context__["retcode"] = 1
        return result

This allows a custom runner/wheel function to report its failure so that
requisites can accurately tell that a job has failed.


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

    Remember, salt-run is *always* executed on the master.

.. _orchestrate-runner-parsing-results-programatically:

Parsing Results Programmatically
--------------------------------

Orchestration jobs return output in a specific data structure. That data
structure is represented differently depending on the outputter used. With the
default outputter for orchestration, you get a nice human-readable output.
Assume the following orchestration SLS:

.. code-block:: yaml

    good_state:
      salt.state:
        - tgt: myminion
        - sls:
        - succeed_with_changes

    bad_state:
      salt.state:
        - tgt: myminion
        - sls:
        - fail_with_changes

    mymod.myfunc:
      salt.function:
        - tgt: myminion

    mymod.myfunc_false_result:
      salt.function:
        - tgt: myminion


Running this using the default outputter would produce output which looks like
this:

.. code-block:: text

    fa5944a73aa8_master:
    ----------
              ID: good_state
        Function: salt.state
          Result: True
         Comment: States ran successfully. Updating myminion.
         Started: 21:08:02.681604
        Duration: 265.565 ms
         Changes:
                  myminion:
                  ----------
                            ID: test succeed with changes
                      Function: test.succeed_with_changes
                        Result: True
                       Comment: Success!
                       Started: 21:08:02.835893
                      Duration: 0.375 ms
                       Changes:
                                ----------
                                testing:
                                    ----------
                                    new:
                                        Something pretended to change
                                    old:
                                        Unchanged

                  Summary for myminion
                  ------------
                  Succeeded: 1 (changed=1)
                  Failed:    0
                  ------------
                  Total states run:     1
                  Total run time:   0.375 ms
    ----------
              ID: bad_state
        Function: salt.state
          Result: False
         Comment: Run failed on minions: myminion
         Started: 21:08:02.947702
        Duration: 177.01 ms
         Changes:
                  myminion:
                  ----------
                            ID: test fail with changes
                      Function: test.fail_with_changes
                        Result: False
                       Comment: Failure!
                       Started: 21:08:03.116634
                      Duration: 0.502 ms
                       Changes:
                                ----------
                                testing:
                                    ----------
                                    new:
                                        Something pretended to change
                                    old:
                                        Unchanged

                  Summary for myminion
                  ------------
                  Succeeded: 0 (changed=1)
                  Failed:    1
                  ------------
                  Total states run:     1
                  Total run time:   0.502 ms
    ----------
              ID: mymod.myfunc
        Function: salt.function
          Result: True
         Comment: Function ran successfully. Function mymod.myfunc ran on myminion.
         Started: 21:08:03.125011
        Duration: 159.488 ms
         Changes:
                  myminion:
                      True
    ----------
              ID: mymod.myfunc_false_result
        Function: salt.function
          Result: False
         Comment: Running function mymod.myfunc_false_result failed on minions: myminion. Function mymod.myfunc_false_result ran on myminion.
         Started: 21:08:03.285148
        Duration: 176.787 ms
         Changes:
                  myminion:
                      False

    Summary for fa5944a73aa8_master
    ------------
    Succeeded: 2 (changed=4)
    Failed:    2
    ------------
    Total states run:     4
    Total run time: 778.850 ms


However, using the ``json`` outputter, you can get the output in an easily
loadable and parsable format:

.. code-block:: bash

    salt-run state.orchestrate test --out=json

.. code-block:: json

    {
        "outputter": "highstate",
        "data": {
            "fa5944a73aa8_master": {
                "salt_|-good_state_|-good_state_|-state": {
                    "comment": "States ran successfully. Updating myminion.",
                    "name": "good_state",
                    "start_time": "21:35:16.868345",
                    "result": true,
                    "duration": 267.299,
                    "__run_num__": 0,
                    "__jid__": "20171130213516897392",
                    "__sls__": "test",
                    "changes": {
                        "ret": {
                            "myminion": {
                                "test_|-test succeed with changes_|-test succeed with changes_|-succeed_with_changes": {
                                    "comment": "Success!",
                                    "name": "test succeed with changes",
                                    "start_time": "21:35:17.022592",
                                    "result": true,
                                    "duration": 0.362,
                                    "__run_num__": 0,
                                    "__sls__": "succeed_with_changes",
                                    "changes": {
                                        "testing": {
                                            "new": "Something pretended to change",
                                            "old": "Unchanged"
                                        }
                                    },
                                    "__id__": "test succeed with changes"
                                }
                            }
                        },
                        "out": "highstate"
                    },
                    "__id__": "good_state"
                },
                "salt_|-bad_state_|-bad_state_|-state": {
                    "comment": "Run failed on minions: test",
                    "name": "bad_state",
                    "start_time": "21:35:17.136511",
                    "result": false,
                    "duration": 197.635,
                    "__run_num__": 1,
                    "__jid__": "20171130213517202203",
                    "__sls__": "test",
                    "changes": {
                        "ret": {
                            "myminion": {
                                "test_|-test fail with changes_|-test fail with changes_|-fail_with_changes": {
                                    "comment": "Failure!",
                                    "name": "test fail with changes",
                                    "start_time": "21:35:17.326268",
                                    "result": false,
                                    "duration": 0.509,
                                    "__run_num__": 0,
                                    "__sls__": "fail_with_changes",
                                    "changes": {
                                        "testing": {
                                            "new": "Something pretended to change",
                                            "old": "Unchanged"
                                        }
                                    },
                                    "__id__": "test fail with changes"
                                }
                            }
                        },
                        "out": "highstate"
                    },
                    "__id__": "bad_state"
                },
                "salt_|-mymod.myfunc_|-mymod.myfunc_|-function": {
                    "comment": "Function ran successfully. Function mymod.myfunc ran on myminion.",
                    "name": "mymod.myfunc",
                    "start_time": "21:35:17.334373",
                    "result": true,
                    "duration": 151.716,
                    "__run_num__": 2,
                    "__jid__": "20171130213517361706",
                    "__sls__": "test",
                    "changes": {
                        "ret": {
                            "myminion": true
                        },
                        "out": "highstate"
                    },
                    "__id__": "mymod.myfunc"
                },
                "salt_|-mymod.myfunc_false_result-mymod.myfunc_false_result-function": {
                    "comment": "Running function mymod.myfunc_false_result failed on minions: myminion. Function mymod.myfunc_false_result ran on myminion.",
                    "name": "mymod.myfunc_false_result",
                    "start_time": "21:35:17.486625",
                    "result": false,
                    "duration": 174.241,
                    "__run_num__": 3,
                    "__jid__": "20171130213517536270",
                    "__sls__": "test",
                    "changes": {
                        "ret": {
                            "myminion": false
                        },
                        "out": "highstate"
                    },
                    "__id__": "mymod.myfunc_false_result"
                }
            }
        },
        "retcode": 1
    }


The 2018.3.0 release includes a couple fixes to make parsing this data easier and
more accurate. The first is the ability to set a :ref:`return code
<orchestrate-runner-return-codes-runner-wheel>` in a custom runner or wheel
function, as noted above. The second is a change to how failures are included
in the return data. Prior to the 2018.3.0 release, minions that failed a
``salt.state`` orchestration job would show up in the ``comment`` field of the
return data, in a human-readable string that was not easily parsed. They are
now included in the ``changes`` dictionary alongside the minions that
succeeded. In addition, ``salt.function`` jobs which failed because the
:ref:`fail function <orchestrate-runner-fail-functions>` returned ``False``
used to handle their failures in the same way ``salt.state`` jobs did, and this
has likewise been corrected.


Running States on the Master without a Minion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The orchestrate runner can be used to execute states on the master without
using a minion. For example, assume that ``salt://foo.sls`` contains the
following SLS:

.. code-block:: yaml

    /etc/foo.conf:
      file.managed:
        - source: salt://files/foo.conf
        - mode: 0600

In this case, running ``salt-run state.orchestrate foo`` would be the
equivalent of running a ``state.sls foo``, but it would execute on the master
only, and would not require a minion daemon to be running on the master.

This is not technically orchestration, but it can be useful in certain use
cases.

Limitations
^^^^^^^^^^^

Only one SLS target can be run at a time using this method, while using
:py:func:`state.sls <salt.modules.state.sls>` allows for multiple SLS files to
be passed in a comma-separated list.
