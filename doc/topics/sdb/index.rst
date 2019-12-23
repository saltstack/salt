.. _sdb:

===============================
Storing Data in Other Databases
===============================
The SDB interface is designed to store and retrieve data that, unlike pillars
and grains, is not necessarily minion-specific. The initial design goal was to
allow passwords to be stored in a secure database, such as one managed by the
keyring package, rather than as plain-text files. However, as a generic database
interface, it could conceptually be used for a number of other purposes.

SDB was added to Salt in version 2014.7.0.


SDB Configuration
=================
In order to use the SDB interface, a configuration profile must be set up.
To be available for master commands, such as runners, it needs to be
configured in the master configuration. For modules executed on a minion, it
can be set either in the minion configuration file, or as a pillar. The
configuration stanza includes the name/ID that the profile will be referred to
as, a ``driver`` setting, and any other arguments that are necessary for the SDB
module that will be used. For instance, a profile called ``mykeyring``, which
uses the ``system`` service in the ``keyring`` module would look like:

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


Getting, Setting and Deleting SDB Values
========================================
Once an SDB driver is configured, you can use the ``sdb`` execution module to
get, set and delete values from it. There are two functions that may appear in
most SDB modules: ``get``, ``set`` and ``delete``.

Getting a value requires only the SDB URI to be specified. To retrieve a value
from the ``kevinopenstack`` profile above, you would use:

.. code-block:: bash

    salt-call sdb.get sdb://kevinopenstack/password

.. warning::
    The ``vault`` driver previously only supported splitting the path and key with
    a question mark. This has since been deprecated in favor of using the standard
    / to split the path and key. The use of the questions mark will still be supported
    to ensure backwards compatibility, but please use the prefered method using /.
    The deprecated approach required the full path to where the key is stored,
    followed by a question mark, followed by the key to be retrieved.  If you were
    using a profile called ``myvault``, you would use a URI that looks like:

    .. code-block:: bash

        salt-call sdb.get 'sdb://myvault/secret/salt?saltstack'

    Instead of the above please use the prefered URI using / instead:

    .. code-block:: bash

        salt-call sdb.get 'sdb://myvault/secret/salt/saltstack'

Setting a value uses the same URI as would be used to retrieve it, followed
by the value as another argument.

.. code-block:: bash

    salt-call sdb.set 'sdb://myvault/secret/salt/saltstack' 'super awesome'

Deleting values (if supported by the driver) is done pretty much the same way as
getting them. Provided that you have a profile called ``mykvstore`` that uses
a driver allowing to delete values you would delete a value as shown below:

.. code-block:: bash

    salt-call sdb.delete 'sdb://mykvstore/foobar'

The ``sdb.get``, ``sdb.set`` and ``sdb.delete`` functions are also available in
the runner system:

.. code-block:: bash

    salt-run sdb.get 'sdb://myvault/secret/salt/saltstack'
    salt-run sdb.set 'sdb://myvault/secret/salt/saltstack' 'super awesome'
    salt-run sdb.delete 'sdb://mykvstore/foobar'


Using SDB URIs in Files
=======================
SDB URIs can be used in both configuration files, and files that are processed
by the renderer system (jinja, mako, etc.). In a configuration file (such as
``/etc/salt/master``, ``/etc/salt/minion``, ``/etc/salt/cloud``, etc.), make an
entry as usual, and set the value to the SDB URI. For instance:

.. code-block:: yaml

    mykey: sdb://myetcd/mykey

To retrieve this value using a module, the module in question must use the
``config.get`` function to retrieve configuration values. This would look
something like:

.. code-block:: python

    mykey = __salt__['config.get']('mykey')

Templating renderers use a similar construct. To get the ``mykey`` value from
above in Jinja, you would use:

.. code-block:: jinja

    {{ salt['config.get']('mykey') }}

When retrieving data from configuration files using ``config.get``, the SDB
URI need only appear in the configuration file itself.

If you would like to retrieve a key directly from SDB, you would call the
``sdb.get`` function directly, using the SDB URI. For instance, in Jinja:

.. code-block:: jinja

    {{ salt['sdb.get']('sdb://myetcd/mykey') }}

When writing Salt modules, it is not recommended to call ``sdb.get`` directly,
as it requires the user to provide values in SDB, using a specific URI. Use
``config.get`` instead.

.. _sdb-writing-modules:

Writing SDB Modules
===================
There is currently one function that MUST exist in any SDB module (``get()``),
one that SHOULD exist (``set_()``) and one that MAY exist (``delete()``). If
using a (``set_()``) function, a ``__func_alias__`` dictionary MUST be declared
in the module as well:

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

The ``delete()`` function may be provided as well, but is not required, as many
sources may be read-only or restrict such operations.

A simple example of an SDB module is ``salt/sdb/keyring_db.py``, as it provides
basic examples of most, if not all, of the types of functionality that are
available not only for SDB modules, but for Salt modules in general.
