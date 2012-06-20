======
Grains
======

Salt comes with an interface to derive information about the underlying system.
This is called the grains interface, because it presents salt with grains of
information.

The grains interface is made available to Salt modules and components so that
the right salt minion commands are automatically available on the right
systems.

It is important to remember that grains are bits of information loaded when
the salt minion starts, so this information is static. This means that the
information in grains is unchanging, therefore the nature of the data is
static. So grains information are things like the running kernel, or the
operating system.

Match all CentOS minions::

    salt -G 'os:CentOS' test.ping

Match all minions with 64-bit CPUs and return number of available cores::

    salt -G 'cpuarch:x86_64' grains.item num_cpus

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

Writing Grains
==============

Grains are easy to write. The grains interface is derived by executing
all of the "public" functions found in the modules located in the grains
package or the custom grains directory. The functions in the modules of
the grains must return a Python `dict`_, where the keys in the dict are the
names of the grains and the values are the values.

Custom grains should be placed in a ``_grains`` directory located under
your :conf_master:`file_roots`. Before adding a grain to Salt, consider
what the grain is and remember that grains need to be static data.

.. _`dict`: http://docs.python.org/library/stdtypes.html#typesmapping

Examples of Grains
------------------

The core module in the grains package is where the main grains are loaded by
the Salt minion and provides the principal example of how to write grains:

:blob:`salt/grains/core.py`

Syncing Grains
--------------

Syncing grains can be done a number of ways, they are automatically synced when
state.highstate is called, or the grains can be synced and reloaded by calling
the saltutil.sync_grains or saltutil.sync_all functions.
