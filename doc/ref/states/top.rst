.. _states-top:

============
The Top File
============

Introduction
============

Most infrastructures are made up of groups of machines, each machine in the
group performing a role similar to others. Those groups of machines work
in concert with each other to create an application stack.

To effectively manage those groups of machines, an administrator needs to
be able to create roles for those groups. For example, a group of machines
that serve front-end web traffic might have roles which indicate that
those machines should all have the Apache webserver package installed and
that the Apache service should always be running.

In Salt, the file which contains a mapping between groups of machines on a
network and the configuration roles that should be applied to them is
called a ``top file``.

Top files are named ``top.sls`` by default and they are so-named because they
always exist in the "top" of a directory hierarchy that contains state files.
That directory hierarchy is called a ``state tree``.

A Basic Example
===============

Top files have three components:

    - Environment: A state tree directory containing a set of state files to
      configure systems.

    - Target: A grouping of machines which will have a set of states applied
      to them.

    - State files: A list of state files to apply to a target. Each state
      file describes one or more states to be configured and enforced
      on the targeted machines.


The relationship between these three components is nested as follows:

    - Environments contain targets

    - Targets contain states


Putting these concepts together, we can describe a scenario in which all
minions with an ID that begins with ``web`` have an ``apache`` state applied
to them:

.. code-block:: yaml

    base:          # Apply SLS files from the directory root for the 'base' environment
      'web*':      # All minions with a minion_id that begins with 'web'
        - apache   # Apply the state file named 'apache.sls'


.. _states-top-environments:

Environments
============

Environments are directory hierarchies which contain a top files and a set
of state files.

Environments can be used in many ways, however there is no requirement that
they be used at all. In fact, the most common way to deploy Salt is with
a single environment, called ``base``. It is recommended that users only
create multiple environments if they have a use case which specifically
calls for multiple versions of state trees.


Getting Started with Top Files
==============================

Each environment is defined inside a salt master configuration variable
called, :conf_master:`file_roots` .


In the most common single-environment setup, only the ``base`` environment is
defined in :conf_master:`file_roots` along with only one directory path for
the state tree.


.. code-block:: yaml

    file_roots:
      base:
        - /srv/salt

In the above example, the top file will only have a single environment to pull
from.


Next is a simple single-environment top file placed in ``/srv/salt/top.sls``,
illustrating that for the environment called ``base``, all minions will have the
state files named ``core.sls`` and ``edit.sls`` applied to them.

.. code-block:: yaml

    base:
      '*':
        - core
        - edit

Assuming the ``file_roots`` configuration from above, Salt will look in the
``/srv/salt`` directory for ``core.sls`` and ``edit.sls``.


Multiple Environments
=====================

In some cases, teams may wish to create versioned state trees which can be
used to test Salt configurations in isolated sets of systems such as a staging
environment before deploying states into production.

For this case, multiple environments can be used to accomplish this task.


To create multiple environments, the :conf_master:`file_roots` option can be
expanded:

.. code-block:: yaml

    file_roots:
      dev:
        - /srv/salt/dev
      qa:
        - /srv/salt/qa
      prod:
        - /srv/salt/prod

In the above, we declare three environments: ``dev``, ``qa`` and ``prod``.
Each environment has a single directory assigned to it.

Our top file references the environments:

.. code-block:: yaml

    dev:
      'webserver*':
        - webserver
      'db*':
        - db
    qa:
      'webserver*':
        - webserver
      'db*':
        - db
    prod:
      'webserver*':
        - webserver
      'db*':
        - db

As seen above, the top file now declares the three environments and for each,
targets are defined to map globs of minion IDs to state files. For example,
all minions which have an ID beginning with the string ``webserver`` will have the
webserver state from the requested environment assigned to it.

In this manner, a proposed change to a state could first be made in a state
file in ``/srv/salt/dev`` and then be applied to development webservers before
moving the state into QA by copying the state file into ``/srv/salt/qa``.


Choosing an Environment to Target
=================================

The top file is used to assign a minion to an environment unless overridden
using the methods described below. The environment in the top file must match
an environment in :conf_master:`file_roots` in order for any states to be
applied to that minion. The states that will be applied to a minion in a given
environment can be viewed using the :py:func:`state.show_top
<salt.modules.state.show_top>` execution function.

Minions may be pinned to a particular environment by setting the ``environment``
value in the minion configuration file. In doing so, a minion will only
request files from the environment to which it is assigned.

The environment to use may also be dynamically selected at the time that
a ``salt``, ``salt-call`` or ``salt-ssh`` by passing passing a flag to the
execution module being called. This is most commonly done with
functions in the ``state`` module by using the ``saltenv=`` argument. For
example, to run a ``highstate`` on all minions, using the state files in
the ``prod`` state tree, run: ``salt '*' state.highstate saltenv=prod``.

.. note::
    Not all functions accept ``saltenv`` as an argument See individual
    function documentation to verify.



Shorthand
=========
If you assign only one SLS to a system, as in this example, a shorthand is
also available:

.. code-block:: yaml

    base:
      '*': global
    dev:
      'webserver*': webserver
      'db*':        db
    qa:
      'webserver*': webserver
      'db*':        db
    prod:
      'webserver*': webserver
      'db*':        db


Advanced Minion Targeting
=========================

In addition to globs, minions can be specified in top files a few other
ways. Some common ones are :doc:`compound matches </topics/targeting/compound>`
and :doc:`node groups </topics/targeting/nodegroups>`.

Below is a slightly more complex top file example, showing the different types
of matches you can perform:

.. code-block:: yaml

    # All files will be taken from the file path specified in the base
    # environment in the ``file_roots`` configuration value.

    base:
        # All minions get the following three state files applied

        '*':
            - ldap-client
            - networking
            - salt.minion

        # All minions which have an ID that begins with the phrase
        # 'salt-master' will have an SLS file applied that is named
        # 'master.sls' and is in the 'salt' directory, underneath
        # the root specified in the ``base`` environment in the
        # configuration value for ``file_roots``.

        'salt-master*':
            - salt.master

        # Minions that have an ID matching the following regular
        # expression will have the state file called 'web.sls' in the
        # nagios/mon directory applied. Additionally, minions matching
        # the regular expression will also have the 'server.sls' file
        # in the apache/ directory applied.

        # NOTE!
        #
        # Take note of the 'match' directive here, which tells Salt
        # to treat the target string as a regex to be matched!

        '^(memcache|web).(qa|prod).loc$':
            - match: pcre
            - nagios.mon.web
            - apache.server

        # Minions that have a grain set indicating that they are running
        # the Ubuntu operating system will have the state file called
        # 'ubuntu.sls' in the 'repos' directory applied.
        #
        # Again take note of the 'match' directive here which tells
        # Salt to match against a grain instead of a minion ID.

        'os:Ubuntu':
            - match: grain
            - repos.ubuntu

        # Minions that are either RedHat or CentOS should have the 'epel.sls'
        # state applied, from the 'repos/' directory.

        'os:(RedHat|CentOS)':
            - match: grain_pcre
            - repos.epel

        # The three minions with the IDs of 'foo', 'bar' and 'baz' should
        # have 'database.sls' applied.

        'foo,bar,baz':
            - match: list
            - database

        # Any minion for which the pillar key 'somekey' is set and has a value
        # of that key matching 'abc' will have the 'xyz.sls' state applied.

        'somekey:abc':
            - match: pillar
            - xyz

        # All minions which begin with the strings 'nag1' or any minion with
        # a grain set called 'role' with the value of 'monitoring' will have
        # the 'server.sls' state file applied from the 'nagios/' directory.

        'nag1* or G@role:monitoring':
            - match: compound
            - nagios.server

How Top Files Are Compiled
==========================

When using multiple environments, it is not necessary to create a top file for
each environment. The most common approach, and the easiest to maintain, is
to use a single top file placed in only one environment.

However, some workflows do call for multiple top files. In this case, top
files may be merged together to create ``high data`` for the state compiler
to use as a source to compile states on a minion.

For the following discussion of top file compilation, assume the following
configuration:


``/etc/salt/master``:

.. code-block:: yaml

    <snip>
    file_roots:
      first_env:
        - /srv/salt/first
      second_env:
        - /srv/salt/second


``/srv/salt/first/top.sls``:

.. code-block:: yaml

    first_env:
      '*':
        - first
    second_env:
      '*':
        - second

The astute reader will ask how the state compiler resolves which should be
an obvious conflict if a minion is not pinned to a particular environment
and if no environment argument is passed into a state function.

Given the above, it is initially unclear whether ``first.sls`` will be applied
or whether ``second.sls`` will be applied in a ``salt '*' state.highstate`` command.

When conflicting keys arise, there are several configuration options which
control the behaviour of salt:

    - ``env_order``
        Setting ``env_order`` will set the order in which environments are processed
        by the state compiler.

    - ``top_file_merging_strategy``
        Can be set to ``same``, which will process only the top file from the environment
        that the minion belongs to via the ``environment`` configuration setting or
        the environment that is requested via the ``saltenv`` argument supported
        by some functions in the ``state`` module.

        Can also be set to ``merge``. This is the default. When set to ``merge``,
        top files will be merged together. The order in which top files are
        merged together can be controlled with ``env_order``.

    - ``default_top``
        If ``top_file_merging_strategy`` is set to ``same`` and an environment does
        not contain a top file, the top file in the environment specified by
        ``default_top`` will be used instead.
