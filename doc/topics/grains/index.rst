.. _grains:

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


Listing Grains
==============

Available grains can be listed by using the 'grains.ls' module:

.. code-block:: bash

    salt '*' grains.ls

Grains data can be listed by using the 'grains.items' module:

.. code-block:: bash

    salt '*' grains.items


.. _static-custom-grains:

Using grains in a state
=======================

To use a grain in a state you can access it via `{{ grains['key'] }}`.

Grains in the Minion Config
===========================

Grains can also be statically assigned within the minion configuration file.
Just add the option :conf_minion:`grains` and pass options to it:

.. code-block:: yaml

    grains:
      roles:
        - webserver
        - memcache
      deployment: datacenter4
      cabinet: 13
      cab_u: 14-15

Then status data specific to your servers can be retrieved via Salt, or used
inside of the State system for matching. It also makes it possible to target based on specific data about your deployment, as in the example above.


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

.. note::

    Grains in ``/etc/salt/grains`` are ignored if you specify the same grains in the minion config.

.. note::

    Grains are static, and since they are not often changed, they will need a grains refresh when they are updated. You can do this by calling: ``salt minion saltutil.refresh_modules``

.. note::

    You can equally configure static grains for Proxy Minions.
    As multiple Proxy Minion processes can run on the same machine, you need
    to index the files using the Minion ID, under ``/etc/salt/proxy.d/<minion ID>/grains``.
    For example, the grains for the Proxy Minion ``router1`` can be defined
    under ``/etc/salt/proxy.d/router1/grains``, while the grains for the
    Proxy Minion ``switch7`` can be put in ``/etc/salt/proxy.d/switch7/grains``.

Matching Grains in the Top File
===============================

With correctly configured grains on the Minion, the :term:`top file` used in
Pillar or during Highstate can be made very efficient. For example, consider
the following configuration:

.. code-block:: yaml

    'roles:webserver':
      - match: grain
      - state0

    'roles:memcache':
      - match: grain
      - state1
      - state2

For this example to work, you would need to have defined the grain
``role`` for the minions you wish to match.

.. _writing-grains:

Writing Grains
==============

The grains are derived by executing all of the "public" functions (i.e. those
which do not begin with an underscore) found in the modules located in the
Salt's core grains code, followed by those in any custom grains modules. The
functions in a grains module must return a :ref:`Python dictionary
<python:typesmapping>`, where the dictionary keys are the names of grains, and
each key's value is that value for that grain.

Custom grains modules should be placed in a subdirectory named ``_grains``
located under the :conf_master:`file_roots` specified by the master config
file. The default path would be ``/srv/salt/_grains``. Custom grains modules
will be distributed to the minions when :mod:`state.highstate
<salt.modules.state.highstate>` is run, or by executing the
:mod:`saltutil.sync_grains <salt.modules.saltutil.sync_grains>` or
:mod:`saltutil.sync_all <salt.modules.saltutil.sync_all>` functions.

Grains modules are easy to write, and (as noted above) only need to return a
dictionary. For example:

.. code-block:: python

   def yourfunction():
        # initialize a grains dictionary
        grains = {}
        # Some code for logic that sets grains like
        grains['yourcustomgrain'] = True
        grains['anothergrain'] = 'somevalue'
        return grains

The name of the function does not matter and will not factor into the grains
data at all; only the keys/values returned become part of the grains.

When to Use a Custom Grain
--------------------------

Before adding new grains, consider what the data is and remember that grains
should (for the most part) be static data.

If the data is something that is likely to change, consider using :ref:`Pillar
<pillar>` or an execution module instead. If it's a simple set of
key/value pairs, pillar is a good match. If compiling the information requires
that system commands be run, then putting this information in an execution
module is likely a better idea.

Good candidates for grains are data that is useful for targeting minions in the
:ref:`top file <states-top>` or the Salt CLI. The name and data structure of
the grain should be designed to support many platforms, operating systems or
applications. Also, keep in mind that Jinja templating in Salt supports
referencing pillar data as well as invoking functions from execution modules,
so there's no need to place information in grains to make it available to Jinja
templates. For example:

.. code-block:: text

    ...
    ...
    {{ salt['module.function_name']('argument_1', 'argument_2') }}
    {{ pillar['my_pillar_key'] }}
    ...
    ...

.. warning::

    Custom grains will not be available in the top file until after the first
    :ref:`highstate <running-highstate>`. To make custom grains available on a
    minion's first highstate, it is recommended to use :ref:`this example
    <minion-start-reactor>` to ensure that the custom grains are synced when
    the minion starts.

Loading Custom Grains
---------------------

If you have multiple functions specifying grains that are called from a ``main``
function, be sure to prepend grain function names with an underscore. This prevents
Salt from including the loaded grains from the grain functions in the final
grain data structure. For example, consider this custom grain file:

.. code-block:: python

    #!/usr/bin/env python
    def _my_custom_grain():
        my_grain = {'foo': 'bar', 'hello': 'world'}
        return my_grain


    def main():
        # initialize a grains dictionary
        grains = {}
        grains['my_grains'] = _my_custom_grain()
        return grains

The output of this example renders like so:

.. code-block:: bash

    # salt-call --local grains.items
    local:
        ----------
        <Snipped for brevity>
        my_grains:
            ----------
            foo:
                bar
            hello:
                world

However, if you don't prepend the ``my_custom_grain`` function with an underscore,
the function will be rendered twice by Salt in the items output: once for the
``my_custom_grain`` call itself, and again when it is called in the ``main``
function:

.. code-block:: bash

    # salt-call --local grains.items
    local:
    ----------
        <Snipped for brevity>
        foo:
            bar
        <Snipped for brevity>
        hello:
            world
        <Snipped for brevity>
        my_grains:
            ----------
            foo:
                bar
            hello:
                world


Precedence
==========

Core grains can be overridden by custom grains. As there are several ways of
defining custom grains, there is an order of precedence which should be kept in
mind when defining them. The order of evaluation is as follows:

1. Core grains.
2. Custom grains in ``/etc/salt/grains``.
3. Custom grains in ``/etc/salt/minion``.
4. Custom grain modules in ``_grains`` directory, synced to minions.

Each successive evaluation overrides the previous ones, so any grains defined
by custom grains modules synced to minions that have the same name as a core
grain will override that core grain. Similarly, grains from
``/etc/salt/minion`` override both core grains and custom grain modules, and
grains in ``_grains`` will override *any* grains of the same name.

For custom grains, if the function takes an argument ``grains``, then the
previously rendered grains will be passed in.  Because the rest of the grains
could be rendered in any order, the only grains that can be relied upon to be
passed in are ``core`` grains. This was added in the 2019.2.0 release.


Examples of Grains
==================

The core module in the grains package is where the main grains are loaded by
the Salt minion and provides the principal example of how to write grains:

:blob:`salt/grains/core.py`


Syncing Grains
==============

Syncing grains can be done a number of ways. They are automatically synced when
:mod:`state.highstate <salt.modules.state.highstate>` is called, or (as noted
above) the grains can be manually synced and reloaded by calling the
:mod:`saltutil.sync_grains <salt.modules.saltutil.sync_grains>` or
:mod:`saltutil.sync_all <salt.modules.saltutil.sync_all>` functions.

.. note::

    When the :conf_minion:`grains_cache` is set to False, the grains dictionary is built
    and stored in memory on the minion. Every time the minion restarts or
    ``saltutil.refresh_grains`` is run, the grain dictionary is rebuilt from scratch.
