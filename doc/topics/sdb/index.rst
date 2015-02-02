.. _sdb:

===============================
Storing Data in Other Databases
===============================
The SDB interface is designed to store and retrieve data that, unlike pillars
and grains, is not necessarily minion-specific. The initial design goal was to
allow passwords to be stored in a secure database, such as one managed by the
keyring package, rather than as plain-text files. However, as a generic database
interface, it could conceptually be used for a number of other purposes.

SDB was added to Salt in version 2014.7.0. SDB is currently experimental, and
should probably not be used in production.


SDB Configuration
=================
In order to use the SDB interface, a configuration profile must be set up in
either the master or minion configuration file. The configuration stanza
includes the name/ID that the profile will be referred to as, a ``driver``
setting, and any other arguments that are necessary for the SDB module that will
be used. For instance, a profile called ``mykeyring``, which uses the
``system`` service in the ``keyring`` module would look like:

.. code-block:: yaml

    mykeyring:
      driver: keyring
      service: system

It is recommended to keep the name of the profile simple, as it is used in the
SDB URI as well.


SDB URIs
========
SDB is designed to make small database queries (hence the name, SDB) using a
compact URL. This allows users to reference a database value quickly inside
a number of Salt configuration areas, without a lot of overhead. The basic
format of an SDB URI is:

.. code-block:: yaml

    sdb://<profile>/<args>

The profile refers to the configuration profile defined in either the master or
the minion configuration file. The args are specific to the module referred to
in the profile, but will typically only need to refer to the key of a
key/value pair inside the database. This is because the profile itself should
define as many other parameters as possible.

For example, a profile might be set up to reference credentials for a specific
OpenStack account. The profile might look like:

.. code-block:: yaml

    kevinopenstack:
      driver: keyring
      service: salt.cloud.openstack.kevin

And the URI used to reference the password might look like:

.. code-block:: yaml

    sdb://kevinopenstack/password


Writing SDB Modules
===================
There is currently one function that MUST exist in any SDB module (``get()``)
and one that MAY exist (``set_()``). If using a (``set_()``) function, a
``__func_alias__`` dictionary MUST be declared in the module as well:

.. code-block:: python

    __func_alias__ = {
        'set_': 'set',
    }

This is because ``set`` is a Python built-in, and therefore functions should not
be created which are called ``set()``. The ``__func_alias__`` functionality is
provided via Salt's loader interfaces, and allows legally-named functions to be
referred to using names that would otherwise be unwise to use.

The ``get()`` function is required, as it will be called via functions in other
areas of the code which make use of the ``sdb://`` URI. For example, the
``config.get`` function in the ``config`` execution module uses this function.

The ``set_()`` function may be provided, but is not required, as some sources
may be read-only, or may be otherwise unwise to access via a URI (for instance,
because of SQL injection attacks).

A simple example of an SDB module is ``salt/sdb/keyring_db.py``, as it provides
basic examples of most, if not all, of the types of functionality that are
available not only for SDB modules, but for Salt modules in general.