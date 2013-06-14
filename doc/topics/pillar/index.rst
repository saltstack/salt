==============
Pillar of Salt
==============

Pillar is an interface for Salt designed to offer global values that can be
distributed to all minions. Pillar data is managed in a similar way as
the Salt State Tree.

Pillar was added to Salt in version 0.9.8

.. note:: Storing sensitive data

    Unlike state tree, pillar data is only available for the targeted
    minion specified by the matcher type.  This makes it useful for
    storing sensitive data specific to a particular minion.

Declaring the Master Pillar
===========================

The Salt Master server maintains a pillar_roots setup that matches the
structure of the file_roots used in the Salt file server. Like the
Salt file server the ``pillar_roots`` option in the master config is based
on environments mapping to directories. The pillar data is then mapped to
minions based on matchers in a top file which is laid out in the same way
as the state top file. Salt pillars can use the same matcher types as the
standard top file.

The configuration for the ``pillar_roots`` in the master config is identical in
behavior and function as the ``file_roots`` configuration:

.. code-block:: yaml

    pillar_roots:
      base:
        - /srv/pillar

This example configuration declares that the base environment will be located
in the ``/srv/pillar`` directory. The top file used matches the name of the top
file used for States, and has the same structure:

``/srv/pillar/top.sls``

.. code-block:: yaml

    base:
      '*':
        - packages

This further example shows how to use other standard top matching types (grain
matching is used in this example) to deliver specific salt pillar data to minions
with different 'os' grains:

.. code-block:: yaml

    dev:
      'os:Debian':
        - match: grain  
        - servers

``/srv/pillar/packages.sls``

.. code-block:: yaml

    {% if grains['os'] == 'RedHat' %}
    apache: httpd
    git: git
    {% elif grains['os'] == 'Debian' %}
    apache: apache2
    git: git-core
    {% endif %}

Now this data can be used from within modules, renderers, State SLS files, and
more via the shared pillar `dict`_:

.. code-block:: yaml

    apache:
      pkg:
        - installed
        - name: {{ pillar['apache'] }}

.. code-block:: yaml

    git:
      pkg:
        - installed
        - name: {{ pillar['git'] }}

.. _`dict`: http://docs.python.org/library/stdtypes.html#mapping-types-dict

Viewing Minion Pillar
=====================

Once the pillar is set up the data can be viewed on the minion via the
``pillar`` module, the pillar module comes with two functions, ``pillar.data``
and ``pillar.raw``. ``pillar.data`` will return a freshly reloaded pillar and
``pillar.raw`` wil return the current pillar without a refresh:

.. code-block:: bash

    # salt '*' pillar.data


Footnotes
---------

.. [#nokeyvalueintop] Note that you cannot just list key/value-information in ``top.sls``.

Refreshing Pillar Data
======================

When pillar data is changed on the master the minions need to refresh the data
locally. This is done with the ``saltutil.refresh_pillar`` function.

.. code-block:: yaml

    salt '*' saltutil.refresh_pillar

This function triggers the minion to refresh the pillar and will always return
``True``

Targeting with Pillar
=====================

Pillar data can be used when targeting minions. This allows for ultimate
control and flexibility when targeting minions.

.. code-block:: bash

    salt -I 'somekey:specialvalue' test.ping

Like with :doc:`Grains <../targeting/grains>`, it is possible to use globbing
as well as match nested values in Pillar, by adding colons for each level that
is being traversed. The below example would match minions with a pillar named
``foo``, which is a dict containing a key ``bar``, with a value beginning with
``baz``::

    salt -I 'foo:bar:baz*'


Master Config In Pillar
=======================

For convenience the data stored in the master configuration file is made
available in all minion's pillars. This makes global configuration of services
and systems very easy but may not be desired if sensitive data is stored in the
master configuration.

To disable the master config from being added to the pillar set `pillar_opts`
to `False`:

.. code-block:: yaml

    pillar_opts: False
