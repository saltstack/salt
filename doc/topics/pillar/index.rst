==============
Pillar of Salt
==============

Pillar is an interface for Salt designed to offer global values that can be
distributed to all minions. Pillar data is managed in a similar way to
the Salt State Tree.

Pillar was added to Salt in version 0.9.8 as an experimental add on.

Declaring the Master Pillar
===========================

The Salt Master server maintains a pillar_roots setup that matches the
structure of the file_roots used in the Salt file server. Like the
Salt file server the ``pillar_roots`` option in the master config is based
on environments mapping to directories. The pillar data is then mapped to
minions based on matchers in a top file which is laid out in the same way
as the state top file.

The configuration for the ``pillar_roots`` in the master config is identical in
behavior and function as the ``file_roots`` configuration:

.. code-block:: yaml

    pillar_roots:
      base:
        - /srv/pillar

This example configuration declares that the base environment will be located
in the ``/srv/pillar`` directory. The top file used matches the name of the top file
used for States, and has the same structure:

``/srv/pillar/top.sls``

.. code-block:: yaml

    base:
      '*':
        - packages
      'someminion':
        - someminion-specials

This simple pillar top file declares that information for all minions can be
found in the ``packages.sls`` file [#nokeyvalueintop]_, while
``someminion-specials.sls`` contains overriding or additional information just
for one special minion.

``/srv/pillar/packages.sls``

.. code-block:: yaml

    {% if grains['os'] == 'RedHat' %}
    apache: httpd
    git: git
    {% elif grains['os'] == 'Debian' %}
    apache: apache2
    git: git-core
    {% endif %}
    somekey: globalvalue

``/srv/pillar/someminion-specials.sls``

.. code-block:: yaml

    somekey: specialvalue

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

To use pillar data in a file that is managed on a minion, use a file state like
this:

``/srv/salt/top.sls``

.. code-block:: yaml

    base:
      '*':
        - managed_files

``/srv/salt/managed_files.sls``

.. code-block:: yaml

    /tmp/some-managed-file.txt:
      file:
        - managed
        - template: jinja
        - source: salt://files/some-managed-file.txt

``/srv/salt/files/some-managed-file.txt``

.. code-block:: yaml

    This will yield 'globalvalue' on all minions but will yield 'specialvalue'
    on 'someminion':
    somekey has value: {{ pillar['somekey'] }}

.. _`dict`: http://docs.python.org/library/stdtypes.html#mapping-types-dict

Footnotes
---------

.. [#nokeyvalueintop] Note that you cannot just list key/value-information in ``top.sls``.

Refreshing Pillar Data
======================

When pillar data is changed on the master the minions need to refresh the data
locally. This is done with the ``saltutil.refresh_pillar`` function.

.. code-block:: yaml

    salt '*' saltutil.refresh_pillar

Targeting with Pillar
=====================

Pillar data can be used when targeting minions. This allows for ultimate
control and flexibility when targeting minions.

.. code-block:: bash

    salt -I 'somekey:specialvalue' test.ping
