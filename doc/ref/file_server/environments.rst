.. _file-server-environments:

===========================================
Requesting Files from Specific Environments
===========================================

The Salt fileserver supports multiple environments, allowing for SLS files and
other files to be isolated for better organization.

For the default backend (called :py:mod:`roots <salt.fileserver.roots>`),
environments are defined using the :conf_master:`roots <file_roots>` option.
Other backends (such as :py:mod:`gitfs <salt.fileserver.gitfs>`) define
environments in their own ways. For a list of available fileserver backends,
see :ref:`here <all-salt.fileserver>`.

.. _querystring-syntax:

Querystring Syntax
==================

Any ``salt://`` file URL can specify its fileserver environment using a
querystring syntax, like so:

.. code-block:: bash

    salt://path/to/file?saltenv=foo

In :ref:`Reactor <reactor>` configurations, this method must be used to pull
files from an environment other than ``base``.

In States
=========

Minions can be instructed which environment to use both globally, and for a
single state, and multiple methods for each are available:

Globally
--------

A minion can be pinned to an environment using the :conf_minion:`environment`
option in the minion config file.

Additionally, the environment can be set for a single call to the following
functions:

- :py:mod:`state.apply <salt.modules.state.apply>`
- :py:mod:`state.highstate <salt.modules.state.highstate>`
- :py:mod:`state.sls <salt.modules.state.sls>`
- :py:mod:`state.top <salt.modules.state.top>`

.. note::
    When the ``saltenv`` parameter is used to trigger a :ref:`highstate
    <running-highstate>` using either :py:mod:`state.apply
    <salt.modules.state.apply>` or :py:mod:`state.highstate
    <salt.modules.state.highstate>`, only states from that environment will be
    applied.

On a Per-State Basis
--------------------

Within an individual state, there are two ways of specifying the environment.
The first is to add a ``saltenv`` argument to the state. This example will pull
the file from the ``config`` environment:

.. code-block:: yaml

    /etc/foo/bar.conf:
      file.managed:
        - source: salt://foo/bar.conf
        - user: foo
        - mode: 600
        - saltenv: config

Another way of doing the same thing is to use the :ref:`querystring syntax
<querystring-syntax>` described above:

.. code-block:: yaml

    /etc/foo/bar.conf:
      file.managed:
        - source: salt://foo/bar.conf?saltenv=config
        - user: foo
        - mode: 600

.. note::
    Specifying the environment using either of the above methods is only
    necessary in cases where a state from one environment needs to access files
    from another environment. If the SLS file containing this state was in the
    ``config`` environment, then it would look in that environment by default.
