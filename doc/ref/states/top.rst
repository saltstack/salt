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

- **Environment:** A state tree directory containing a set of state files to
  configure systems.

- **Target:** A grouping of machines which will have a set of states applied to
  them.

- **State files:** A list of state files to apply to a target. Each state file
  describes one or more states to be configured and enforced on the targeted
  machines.


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
target expressions are defined to map minions to state files. For example, all
minions which have an ID beginning with the string ``webserver`` will have the
webserver state from the requested environment assigned to it.

In this manner, a proposed change to a state could first be made in a state
file in ``/srv/salt/dev`` and then be applied to development webservers before
moving the state into QA by copying the state file into ``/srv/salt/qa``.


Choosing an Environment to Target
=================================

The top file is used to assign a minion to an environment unless overridden
using the methods described below. The environment in the top file must match
valid fileserver environment (a.k.a. ``saltenv``) in order for any states to be
applied to that minion. When using the default fileserver backend, environments
are defined in :conf_master:`file_roots`.

The states that will be applied to a minion in a given environment can be
viewed using the :py:func:`state.show_top <salt.modules.state.show_top>`
function.

Minions may be pinned to a particular environment by setting the
:conf_minion:`environment` value in the minion configuration file. In doing so,
a minion will only request files from the environment to which it is assigned.

The environment may also be dynamically selected at runtime by passing it to
the ``salt``, ``salt-call`` or ``salt-ssh`` command. This is most commonly done
with functions in the ``state`` module by using the ``saltenv`` argument. For
example, to run a ``highstate`` on all minions, using only the top file and SLS
files in the ``prod`` environment, run: ``salt '*' state.highstate
saltenv=prod``.

.. note::
    Not all functions accept ``saltenv`` as an argument, see the documentation
    for an individual function documentation to verify.


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

In the examples above, notice that all of the target expressions are globs. The
default match type in top files (since version 2014.7.0) is actually the
:ref:`compound matcher <targeting-compound>`, not the glob matcher as in the
CLI.

A single glob, when passed through the compound matcher, acts the same way as
matching by glob, so in most cases the two are indistinguishable. However,
there is an edge case in which a minion ID contains whitespace. While it is not
recommended to include spaces in a minion ID, Salt will not stop you from doing
so. However, since compound expressions are parsed word-by-word, if a minion ID
contains spaces it will fail to match. In this edge case, it will be necessary
to explicitly use the ``glob`` matcher:

.. code-block:: yaml

    base:
      'minion 1':
        - match: glob
        - foo

.. _top-file-match-types:

The available match types which can be set for a target expression in the top
file are:

============ ================================================================================================================
Match Type   Description
============ ================================================================================================================
glob         Full minion ID or glob expression to match multiple minions (e.g. ``minion123`` or ``minion*``)
pcre         Perl-compatible regular expression (PCRE) matching a minion ID (e.g.  ``web[0-3].domain.com``)
grain        Match a :ref:`grain <grain>`, optionally using globbing (e.g. ``kernel:Linux`` or ``kernel:*BSD``)
grain_pcre   Match a :ref:`grain <grain>` using PCRE (e.g. ``kernel:(Free|Open)BSD``)
list         Comma-separated list of minions (e.g. ``minion1,minion2,minion3``)
pillar       :ref:`Pillar <pillar>` match, optionally using globbing (e.g. ``role:webserver`` or ``role:web*``)
pillar_pcre  :ref:`Pillar <pillar>` match using PCRE (e.g. ``role:web(server|proxy)``
pillar_exact :ref:`Pillar <pillar>` match with no globbing or PCRE (e.g. ``role:webserver``)
ipcidr       Subnet or IP address (e.g. ``172.17.0.0/16`` or ``10.2.9.80``)
data         Match values kept in the minion's datastore (created using the :mod:`data <salt.modules.data>` execution module)
range        :ref:`Range <targeting-range>` cluster
compound     Complex expression combining multiple match types (see :ref:`here <targeting-compound>`)
nodegroup    Pre-defined compound expressions in the master config file (see :ref:`here <targeting-nodegroups>`)
============ ================================================================================================================

Below is a slightly more complex top file example, showing some of the above
match types:

.. code-block:: yaml

    # All files will be taken from the file path specified in the base
    # environment in the ``file_roots`` configuration value.

    base:
        # All minions which begin with the strings 'nag1' or any minion with
        # a grain set called 'role' with the value of 'monitoring' will have
        # the 'server.sls' state file applied from the 'nagios/' directory.

        'nag1* or G@role:monitoring':
            - nagios.server

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

How Top Files Are Compiled
==========================

When a :ref:`highstate <running-highstate>` is executed and an environment is
specified (either using the :conf_minion:`environment` config option or by
passing the saltenv when executing the :ref:`highstate <running-highstate>`),
then that environment's top file is the only top file used to assign states to
minions, and only states from the specified environment will be run.

The remainder of this section applies to cases in which a :ref:`highstate
<running-highstate>` is executed without an environment specified.

With no environment specified, the minion will look for a top file in each
environment, and each top file will be processed to determine the SLS files to
run on the minions. By default, the top files from each environment will be
merged together. In configurations with many environments, such as with
:ref:`GitFS <tutorial-gitfs>` where each branch and tag is treated as a
distinct environment, this may cause unexpected results as SLS files from older
tags cause defunct SLS files to be included in the highstate. In cases like
this, it can be helpful to set :conf_minion:`top_file_merging_strategy` to
``same`` to force each environment to use its own top file.

.. code-block:: yaml

    top_file_merging_strategy: same

Another option would be to set :conf_minion:`state_top_saltenv` to a specific
environment, to ensure that any top files in other environments are
disregarded:

.. code-block:: yaml

    state_top_saltenv: base

With :ref:`GitFS <tutorial-gitfs>`, it can also be helpful to simply manage
each environment's top file separately, and/or manually specify the environment
when executing the highstate to avoid any complicated merging scenarios.
:conf_master:`gitfs_env_whitelist` and :conf_master:`gitfs_env_blacklist` can
also be used to hide unneeded branches and tags from GitFS to reduce the number
of top files in play.

When using multiple environments, it is not necessary to create a top file for
each environment. The easiest-to-maintain approach is to use a single top file
placed in the ``base`` environment. This is often infeasible with :ref:`GitFS
<tutorial-gitfs>` though, since branching/tagging can easily result in extra
top files. However, when only the default (``roots``) fileserver backend is
used, a single top file in the ``base`` environment is the most common way of
configuring a :ref:`highstate <running-highstate>`.

The following minion configuration options affect how top files are compiled
when no environment is specified:

- :conf_minion:`state_top_saltenv`
- :conf_minion:`top_file_merging_strategy`
- :conf_minion:`env_order`
- :conf_minion:`default_top`

Top File Compilation Examples
=============================

For the scenarios below, assume the following configuration:

**/etc/salt/master**:

.. code-block:: yaml

    file_roots:
      base:
        - /srv/salt/base
      dev:
        - /srv/salt/dev
      qa:
        - /srv/salt/qa

**/srv/salt/base/top.sls**:

.. code-block:: yaml

    base:
      '*':
        - base1
    dev:
      '*':
        - dev1
    qa:
      '*':
        - qa1

**/srv/salt/dev/top.sls**:

.. code-block:: yaml

    base:
      'minion1':
        - base2
    dev:
      'minion2':
        - dev2
    qa:
      '*':
        - qa2

.. note::
    For the purposes of these examples, there is no top file in the ``qa``
    environment.

Scenario 1 - ``dev`` Environment Specified
------------------------------------------

In this scenario, the :ref:`highstate <running-highstate>` was either invoked
with ``saltenv=dev`` or the minion has ``environment: dev`` set in the minion
config file. The result will be that only the ``dev2`` SLS from the dev
environment will be part of the :ref:`highstate <running-highstate>`, and it
will be applied to minion2, while minion1 will have no states applied to it.

If the ``base`` environment were specified, the result would be that only the
``base1`` SLS from the ``base`` environment would be part of the
:ref:`highstate <running-highstate>`, and it would be applied to all minions.

If the ``qa`` environment were specified, the :ref:`highstate
<running-highstate>` would exit with an error.

Scenario 2 - No Environment Specified, :conf_minion:`top_file_merging_strategy` is "merge"
------------------------------------------------------------------------------------------

In this scenario, assuming that the ``base`` environment's top file was
evaluated first, the ``base1``, ``dev1``, and ``qa1`` states would be applied
to all minions. If, for instance, the ``qa`` environment is not defined in
**/srv/salt/base/top.sls**, then because there is no top file for the ``qa``
environment, no states from the ``qa`` environment would be applied.

Scenario 3 - No Environment Specified, :conf_minion:`top_file_merging_strategy` is "same"
-----------------------------------------------------------------------------------------

.. versionchanged:: 2016.11.0
    In prior versions, "same" did not quite work as described below (see
    here__). This has now been corrected. It was decided that changing
    something like top file handling in a point release had the potential to
    unexpectedly impact users' top files too much, and it would be better to
    make this correction in a feature release.

.. __: https://github.com/saltstack/salt/issues/35045

In this scenario, ``base1`` from the ``base`` environment is applied to all
minions. Additionally, ``dev2`` from the ``dev`` environment is applied to
minion2.

If :conf_minion:`default_top` is unset (or set to ``base``, which happens to be
the default), then ``qa1`` from the ``qa`` environment will be applied to all
minions. If :conf_minion:`default_top` were set to ``dev``, then ``qa2`` from
the ``qa`` environment would be applied to all minions.
