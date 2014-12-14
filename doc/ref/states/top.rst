.. _states-top:

============
The Top File
============

The top file is used to map what SLS modules get loaded onto what minions via
the state system. The top file creates a few general abstractions. First it
maps what nodes should pull from which environments, next it defines which
matches systems should draw from.

.. _states-top-environments:

Environments
============

Environments allow conceptually organizing state tree directories. Environments
can be made to be self-contained or state trees can be made to bleed through
environments.

.. note::

    Environments in Salt are very flexible. This section defines how the top
    file can be used to define what states from what environments are to be
    used for specific minions.

    If the intent is to bind minions to specific environments, then the
    `environment` option can be set in the minion configuration file.

The environments in the top file corresponds with the environments defined in
the :conf_master:`file_roots` variable. In a simple, single environment setup
you only have the ``base`` environment, and therefore only one state tree. Here
is a simple example of :conf_master:`file_roots` in the master configuration:

.. code-block:: yaml

    file_roots:
      base:
        - /srv/salt

This means that the top file will only have one environment to pull from,
here is a simple, single environment top file:

.. code-block:: yaml

    base:
      '*':
        - core
        - edit

This also means that :file:`/srv/salt` has a state tree. But if you want to use
multiple environments, or partition the file server to serve more than
just the state tree, then the :conf_master:`file_roots` option can be expanded:

.. code-block:: yaml

    file_roots:
      base:
        - /srv/salt/base
      dev:
        - /srv/salt/dev
      qa:
        - /srv/salt/qa
      prod:
        - /srv/salt/prod

Then our top file could reference the environments:

.. code-block:: yaml

    dev:
      'webserver*dev*':
        - webserver
      'db*dev*':
        - db
    qa:
      'webserver*qa*':
        - webserver
      'db*qa*':
        - db
    prod:
      'webserver*prod*':
        - webserver
      'db*prod*':
        - db

In this setup we have state trees in three of the four environments, and no
state tree in the ``base`` environment. Notice that the targets for the minions
specify environment data. In Salt the master determines who is in what
environment, and many environments can be crossed together. For instance, a
separate global state tree could be added to the ``base`` environment if it
suits your deployment:

.. code-block:: yaml

    base:
      '*':
        - global
    dev:
      'webserver*dev*':
        - webserver
      'db*dev*':
        - db
    qa:
      'webserver*qa*':
        - webserver
      'db*qa*':
        - db
    prod:
      'webserver*prod*':
        - webserver
      'db*prod*':
        - db

In this setup all systems will pull the global SLS from the base environment,
as well as pull from their respective environments. If you assign only one SLS
to a system, as in this example, a shorthand is also available:

.. code-block:: yaml

    base:
      '*': global
    dev:
      'webserver*dev*': webserver
      'db*dev*':        db
    qa:
      'webserver*qa*': webserver
      'db*qa*':        db
    prod:
      'webserver*prod*': webserver
      'db*prod*':        db

.. note::

    The top files from all defined environments will be compiled into a single
    top file for all states. Top files are environment agnostic.

Remember, that since everything is a file in Salt, the environments are
primarily file server environments, this means that environments that have
nothing to do with states can be defined and used to distribute other files.

.. _states-top-file_roots:

A clean and recommended setup for multiple environments would look like this:

.. code-block:: yaml

    # Master file_roots configuration:
    file_roots:
      base:
        - /srv/salt/base
      dev:
        - /srv/salt/dev
      qa:
        - /srv/salt/qa
      prod:
        - /srv/salt/prod

Then only place state trees in the dev, qa, and prod environments, leaving
the base environment open for generic file transfers. Then the top.sls file
would look something like this:

.. code-block:: yaml

    dev:
      'webserver*dev*':
        - webserver
      'db*dev*':
        - db
    qa:
      'webserver*qa*':
        - webserver
      'db*qa*':
        - db
    prod:
      'webserver*prod*':
        - webserver
      'db*prod*':
        - db

Other Ways of Targeting Minions
===============================

In addition to globs, minions can be specified in top files a few other
ways. Some common ones are :doc:`compound matches </topics/targeting/compound>`
and :doc:`node groups </topics/targeting/nodegroups>`.

Here is a slightly more complex top file example, showing the different types
of matches you can perform:

.. code-block:: yaml

    base:
        '*':
            - ldap-client
            - networking
            - salt.minion

        'salt-master*':
            - salt.master

        '^(memcache|web).(qa|prod).loc$':
            - match: pcre
            - nagios.mon.web
            - apache.server

        'os:Ubuntu':
            - match: grain
            - repos.ubuntu

        'os:(RedHat|CentOS)':
            - match: grain_pcre
            - repos.epel

        'foo,bar,baz':
            - match: list
            - database

        'somekey:abc':
            - match: pillar
            - xyz

        'nag1* or G@role:monitoring':
            - match: compound
            - nagios.server

In this example ``top.sls``, all minions get the ldap-client, networking, and
salt.minion states. Any minion with an id matching the ``salt-master*`` glob
will get the salt.master state. Any minion with ids matching the regular
expression ``^(memcache|web).(qa|prod).loc$`` will get the nagios.mon.web and
apache.server states. All Ubuntu minions will receive the repos.ubuntu state,
while all RHEL and CentOS minions will receive the repos.epel state. The
minions ``foo``, ``bar``, and ``baz`` will receive the database state. Any
minion with a pillar named ``somekey``, having a value of ``abc`` will receive
the xyz state.  Finally, minions with ids matching the nag1* glob or with a
grain named ``role`` equal to ``monitoring`` will receive the nagios.server
state.

How Top Files Are Compiled
==========================

.. warning::

    There is currently a known issue with the topfile compilation. The below
    may not be completely valid until
    https://github.com/saltstack/salt/issues/12483#issuecomment-64181598
    is closed.

As mentioned earlier, the top files in the different environments are compiled
into a single set of data. The way in which this is done follows a few rules,
which are important to understand when arranging top files in different
environments. The examples below all assume that the :conf_master:`file_roots`
are set as in the :ref:`above multi-environment example
<states-top-file_roots>`.


1. The ``base`` environment's top file is processed first. Any environment which
   is defined in the ``base`` top.sls as well as another environment's top file,
   will use the instance of the environment configured in ``base`` and ignore
   all other instances.  In other words, the ``base`` top file is
   authoritative when defining environments. Therefore, in the example below,
   the ``dev`` section in ``/srv/salt/dev/top.sls`` would be completely
   ignored.

``/srv/salt/base/top.sls:``

.. code-block:: yaml

    base:
      '*':
        - common
    dev:
      'webserver*dev*':
        - webserver
      'db*dev*':
        - db

``/srv/salt/dev/top.sls:``

.. code-block:: yaml

    dev:
      '10.10.100.0/24':
        - match: ipcidr
        - deployments.dev.site1
      '10.10.101.0/24':
        - match: ipcidr
        - deployments.dev.site2

.. note::
    The rules below assume that the environments being discussed were not
    defined in the ``base`` top file.

2. If, for some reason, the ``base`` environment is not configured in the
   ``base`` environment's top file, then the other environments will be checked
   in alphabetical order. The first top file found to contain a section for the
   ``base`` environment wins, and the other top files' ``base`` sections are
   ignored. So, provided there is no ``base`` section in the ``base`` top file,
   with the below two top files the ``dev`` environment would win out, and the
   ``common.centos`` SLS would not be applied to CentOS hosts.

``/srv/salt/dev/top.sls:``

.. code-block:: yaml

    base:
      'os:Ubuntu':
        - common.ubuntu
    dev:
      'webserver*dev*':
        - webserver
      'db*dev*':
        - db

``/srv/salt/qa/top.sls:``

.. code-block:: yaml

    base:
      'os:Ubuntu':
        - common.ubuntu
      'os:CentOS':
        - common.centos
    qa:
      'webserver*qa*':
        - webserver
      'db*qa*':
        - db

3. For environments other than ``base``, the top file in a given environment
   will be checked for a section matching the environment's name. If one is
   found, then it is used. Otherwise, the remaining (non-``base``) environments
   will be checked in alphabetical order. In the below example, the ``qa``
   section in ``/srv/salt/dev/top.sls`` will be ignored, but if
   ``/srv/salt/qa/top.sls`` were cleared or removed, then the states configured
   for the ``qa`` environment in ``/srv/salt/dev/top.sls`` will be applied.

``/srv/salt/dev/top.sls:``

.. code-block:: yaml

    dev:
      'webserver*dev*':
        - webserver
      'db*dev*':
        - db
    qa:
      '10.10.200.0/24':
        - match: ipcidr
        - deployments.qa.site1
      '10.10.201.0/24':
        - match: ipcidr
        - deployments.qa.site2

``/srv/salt/qa/top.sls:``

.. code-block:: yaml

    qa:
      'webserver*qa*':
        - webserver
      'db*qa*':
        - db

.. note::
    When in doubt, the simplest way to configure your states is with a single
    top.sls in the ``base`` environment.
