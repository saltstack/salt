==============
Startup States
==============

Sometimes it may be desired that the salt minion execute a state run when it is
started. This alleviates the need for the master to initiate a state run on a
new minion and can make provisioning much easier.

As of Salt 0.10.3 the minion config reads options that allow for states to be
executed at startup. The options are `startup_states`, `sls_list`, and
`top_file`.

The `startup_states` option can be passed one of a number of arguments to
define how to execute states. The available options are:

:ref:`highstate <running-highstate>`
  Execute :py:func:`state.apply <salt.modules.state.apply_>`

sls
  Read in the ``sls_list`` option and execute the named sls files

top
  Read in the ``top_file`` option and execute states based on that top file
  on the Salt Master

Examples:
---------

Execute :py:func:`state.apply <salt.modules.state.apply_>` to run the
:ref:`highstate <running-highstate>` when starting the minion:

.. code-block:: yaml

   startup_states: highstate

Execute the sls files `edit.vim` and `hyper`:

.. code-block:: yaml

    startup_states: sls

    sls_list:
      - edit.vim
      - hyper
