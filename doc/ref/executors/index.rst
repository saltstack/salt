.. _executors:

=========
Executors
=========

Executors are used by minion to execute module functions. Executors can be used
to modify the functions behavior, do any pre-execution steps or execute in a
specific way like sudo executor.

Executors could be passed as a list and they will be used one-by-one in the
order. If an executor returns ``None`` the next one will be called. If an
executor returns non-``None`` the execution sequence is terminated and the
returned value is used as a result. It's a way executor could control modules
execution working as a filter. Note that executor could actually not execute
the function but just do something else and return ``None`` like ``splay``
executor does. In this case some other executor have to be used as a final
executor that will actually execute the function. See examples below.

Executors list could be passed by minion config file in the following way:

.. code-block:: yaml

    module_executors:
      - splay
      - direct_call
    splaytime: 30

The same could be done by command line:

.. code-block:: bash

    salt -t 40 --module-executors='[splay, direct_call]' --executor-opts='{splaytime: 30}' '*' test.version

And the same command called via netapi will look like this:

.. code-block:: bash

    curl -sSk https://localhost:8000 \
        -H 'Accept: application/x-yaml' \
        -H 'X-Auth-Token: 697adbdc8fe971d09ae4c2a3add7248859c87079' \
        -H 'Content-type: application/json' \
        -d '[{
            "client": "local",
            "tgt": "*",
            "fun": "test.version",
            "module_executors": ["splay", "direct_call"],
            "executor_opts": {"splaytime": 10}
            }]'

.. seealso:: :ref:`The full list of executors <all-salt.executors>`

Writing Salt Executors
----------------------

A Salt executor is written in a similar manner to a Salt execution module.
Executor is a python module placed into the ``executors`` folder and containing
the ``execute`` function with the following signature:

.. code-block:: python

    def execute(opts, data, func, args, kwargs):
        ...

Where the args are:

``opts``:
  Dictionary containing the minion configuration options
``data``:
  Dictionary containing the load data including ``executor_opts`` passed via
  cmdline/API.
``func``, ``args``, ``kwargs``:
  Execution module function to be executed and its arguments. For instance the
  simplest ``direct_call`` executor just runs it as ``func(*args, **kwargs)``.
``Returns``:
  ``None`` if the execution sequence must be continued with the next executor.
  Error string or execution result if the job is done and execution must be
  stopped.

Specific options could be passed to the executor via minion config or via
``executor_opts`` argument. For instance to access ``splaytime`` option set by
minion config executor should access ``opts.get('splaytime')``. To access the
option set by commandline or API ``data.get('executor_opts',
{}).get('splaytime')`` should be used. So if an option is safe and must be
accessible by user executor should check it in both places, but if an option is
unsafe it should be read from the only config ignoring the passed request data.

There is also a function named ``all_missing_func`` which the name of the
``func`` is passed, which can be used to verify if the command should still be
run, even if it is not loaded in minion_mods.
