.. _targeting-grains:

======
Grains
======

Salt comes with an interface to derive information about the underlying system.
This is called the grains interface, because it presents salt with grains of
information. Grains are collected for the operating system, domain name,
IP address, kernel, OS type, memory, and many other system properties.

The grains interface is made available to Salt modules and components so that
the right salt minion commands are automatically available on the right
systems.

Grain data is relatively static, though if system information changes
(for example, if network settings are changed), or if a new value is assigned
to a custom grain, grain data is refreshed.

.. note::

    Grains resolve to lowercase letters. For example, ``FOO``, and ``foo``
    target the same grain.

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

With correctly configured grains on the Minion, the :term:`top file` used in
Pillar or during Highstate can be made very efficient. For example, consider
the following configuration:

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

For this example to work, you would need to have defined the grain
``node_type`` for the minions you wish to match. This simple example is nice,
but too much of the code is similar. To go one step further, Jinja templating
can be used to simplify the :term:`top file`.

.. code-block:: yaml

    {% set node_type = salt['grains.get']('node_type', '') %}

    {% if node_type %}
      'node_type:{{ self }}':
        - match: grain
        - {{ self }}
    {% endif %}

Using Jinja templating, only one match entry needs to be defined.

.. note::

    The example above uses the :mod:`grains.get <salt.modules.grains.get>`
    function to account for minions which do not have the ``node_type`` grain
    set.

.. _writing-grains:

Writing Grains
==============

The grains interface is derived by executing
all of the "public" functions found in the modules located in the grains
package or the custom grains directory. The functions in the modules of
the grains must return a Python :ref:`dict <python2:typesmapping>`, where the
keys in the :ref:`dict <python2:typesmapping>` are the names of the grains and
the values are the values.

Custom grains should be placed in a ``_grains`` directory located under the
:conf_master:`file_roots` specified by the master config file.  The default path
would be ``/srv/salt/_grains``.  Custom grains will be
distributed to the minions when :mod:`state.highstate
<salt.modules.state.highstate>` is run, or by executing the
:mod:`saltutil.sync_grains <salt.modules.saltutil.sync_grains>` or
:mod:`saltutil.sync_all <salt.modules.saltutil.sync_all>` functions.

Grains are easy to write, and only need to return a dictionary.  A common
approach would be code something similar to the following:

.. code-block:: python

   #!/usr/bin/env python
   def yourfunction():
        # initialize a grains dictionary
        grains = {}
        # Some code for logic that sets grains like
        grains['yourcustomgrain']=True
        grains['anothergrain']='somevalue'
        return grains

Before adding a grain to Salt, consider what the grain is and remember that
grains need to be static data. If the data is something that is likely to
change, consider using :doc:`Pillar <../pillar/index>` instead.

.. warning::

    Custom grains will not be available in the top file until after the first
    :ref:`highstate <running-highstate>`. To make custom grains available on a
    minion's first highstate, it is recommended to use :ref:`this example
    <minion-start-reactor>` to ensure that the custom grains are synced when
    the minion starts.


Precedence
==========

Core grains can be overridden by custom grains. As there are several ways of
defining custom grains, there is an order of precedence which should be kept in
mind when defining them. The order of evaluation is as follows:

1. Core grains.
2. Custom grain modules in ``_grains`` directory, synced to minions.
3. Custom grains in ``/etc/salt/grains``.
4. Custom grains in ``/etc/salt/minion``.

Each successive evaluation overrides the previous ones, so any grains defined
by custom grains modules synced to minions that have the same name as a core
grain will override that core grain. Similarly, grains from
``/etc/salt/grains`` override both core grains and custom grain modules, and
grains in ``/etc/salt/minion`` will override *any* grains of the same name.


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
