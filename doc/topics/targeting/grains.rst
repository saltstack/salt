======
Grains
======

Salt comes with an interface to derive information about the underlying system.
This is called the grains interface, because it presents salt with grains of
information.

.. glossary::

    Grains
        Static bits of information that a minion collects about the system when
        the minion first starts.

The grains interface is made available to Salt modules and components so that
the right salt minion commands are automatically available on the right
systems.

It is important to remember that grains are bits of information loaded when
the salt minion starts, so this information is static. This means that the
information in grains is unchanging, therefore the nature of the data is
static. So grains information are things like the running kernel, or the
operating system.

Match all CentOS minions:

.. code-block:: bash

    salt -G 'os:CentOS' test.ping

Match all minions with 64-bit CPUs, and return number of CPU cores for each
matching minion:

.. code-block:: bash

    salt -G 'cpuarch:x86_64' grains.item num_cpus

Additionally, globs can be used in grain matches, and grains that are nested in
a :ref:`dictionary <python2:typesmapping>` can be matched by adding a colon for
each level that is traversed. For example, the following will match hosts that
have a grain called ``ec2_tags``, which itself is a
:ref:`dict <python2:typesmapping>` with a key named ``environment``, which
has a value that contains the word ``production``:

.. code-block:: bash

    salt -G 'ec2_tags:environment:*production*'


Listing Grains
==============

Available grains can be listed by using the 'grains.ls' module:

.. code-block:: bash

    salt '*' grains.ls

Grains data can be listed by using the 'grains.items' module:

.. code-block:: bash

    salt '*' grains.items


.. _static-custom-grains:

Grains in the Minion Config
===========================

Grains can also be statically assigned within the minion configuration file.
Just add the option ``grains`` and pass options to it:

.. code-block:: yaml

    grains:
      roles:
        - webserver
        - memcache
      deployment: datacenter4
      cabinet: 13
      cab_u: 14-15

Then status data specific to your servers can be retrieved via Salt, or used
inside of the State system for matching. It also makes targeting, in the case
of the example above, simply based on specific data about your deployment.


Grains in /etc/salt/grains
==========================

If you do not want to place your custom static grains in the minion config
file, you can also put them in ``/etc/salt/grains`` on the minion. They are configured in the
same way as in the above example, only without a top-level ``grains:`` key:

.. code-block:: yaml

    roles:
      - webserver
      - memcache
    deployment: datacenter4
    cabinet: 13
    cab_u: 14-15


Matching Grains in the Top File
===============================

With correctly setup grains on the Minion, the Top file used in Pillar or during Highstate can be made really efficient.  Like for example, you could do:

.. code-block:: yaml

    'node_type:web':
        - match: grain
        - webserver

    'node_type:postgres':
        - match: grain
        - database

    'node_type:redis':
        - match: grain
        - redis

    'node_type:lb':
        - match: grain
        - lb
        
For this example to work, you would need the grain ``node_type`` and the correct value to match on.  This simple example is nice, but too much of the code is similar.  To go one step further, we can place some Jinja template code into the Top file.

.. code-block:: yaml

    {% set self = grains['node_type'] %}

        'node_type:{{ self }}':
            - match: grain
            - {{ self }}

The Jinja code simplified the Top file, and allowed SaltStack to work its magic.

.. _writing-grains:

Writing Grains
==============

Grains are easy to write. The grains interface is derived by executing
all of the "public" functions found in the modules located in the grains
package or the custom grains directory. The functions in the modules of
the grains must return a Python :ref:`dict <python2:typesmapping>`, where the
keys in the :ref:`dict <python2:typesmapping>` are the names of the grains and
the values are the values.

Custom grains should be placed in a ``_grains`` directory located under the
:conf_master:`file_roots` specified by the master config file. They will be
distributed to the minions when :mod:`state.highstate
<salt.modules.state.highstate>` is run, or by executing the
:mod:`saltutil.sync_grains <salt.modules.saltutil.sync_grains>` or
:mod:`saltutil.sync_all <salt.modules.saltutil.sync_all>` functions.

Before adding a grain to Salt, consider what the grain is and remember that
grains need to be static data. If the data is something that is likely to
change, consider using :doc:`Pillar <../pillar/index>` instead.


Precedence
==========

Core grains can be overriden by custom grains. As there are several ways of
defining custom grains, there is an order of precedence which should be kept in
mind when defining them. The order of evaluation is as follows:

1. Core grains.
2. Custom grains in ``/etc/salt/grains``.
3. Custom grains in ``/etc/salt/minion``.
4. Custom grain modules in ``_grains`` directory, synced to minions.

Each successive evaluation overrides the previous ones, so any grains defined
in ``/etc/salt/grains`` that have the same name as a core grain will override
that core grain. Similarly, ``/etc/salt/minion`` overrides both core grains and
grains set in ``/etc/salt/grains``, and custom grain modules will override
*any* grains of the same name.


Examples of Grains
==================

The core module in the grains package is where the main grains are loaded by
the Salt minion and provides the principal example of how to write grains:

:blob:`salt/grains/core.py`


Syncing Grains
==============

Syncing grains can be done a number of ways, they are automatically synced when
:mod:`state.highstate <salt.modules.state.highstate>` is called, or (as noted
above) the grains can be manually synced and reloaded by calling the
:mod:`saltutil.sync_grains <salt.modules.saltutil.sync_grains>` or
:mod:`saltutil.sync_all <salt.modules.saltutil.sync_all>` functions.
