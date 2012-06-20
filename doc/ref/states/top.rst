============
The Top File
============

The top file is used to map what SLS modules get loaded onto what minions via
the state system. The top file creates a few general abstractions. First it
maps what nodes should pull from which environments, next it defines which
matches systems should draw from.

Environments
============

The environments in the top file corresponds with the environments defined in
the file_roots variable. In a simple, single environment setup you only have
the base environment, and therefore only one state tree. Here is a simple
example of file_roots in the master configuration:

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

This also means that /srv/salt has a state tree. But if you want to use
multiple environments, or partition the file server to serve more than
just the state tree, then the file_roots option can be expanded:

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

In this setup we have state trees in 3 of the 4 environments, and no state
tree in the base environment. Notice that the targets for the minions
specify environment data. In Salt the master determines who is in what
environment, and many environments can be crossed together. For instance,
a separate global state tree could be added to the base environment if
it suits your deployment:

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
as well as pull from their respective environments.

Remember, that since everything is a file in Salt, the environments are
primarily file server environments, this means that environments that have
nothing to do with states can be defined and used to distribute other files.

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

Then only place state trees in the dev, qa and prod environments, leaving
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

        'os:(RedHat|CentOS)'
            - match: grain_pcre
            - repos.epel

        'foo,bar,baz':
            - match: list
            - database

        'somekey:abc'
            - match: pillar
            - xyz

        'nag1* or G@role:monitoring':
            - match: compound
            - nagios.server

In this example ``top.sls``, all minions get the ldap-client, networking and
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

