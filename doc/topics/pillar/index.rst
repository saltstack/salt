==============
Pillar of Salt
==============

Pillar is an interface for Salt designed to offer global values to be
distributed to all minions. Pillar data is managed in a similar way to
the salt state tree.

Pillar was added to Salt in version 0.9.8 as an experimental add on.

Declaring the Master Pillar
===========================

The Salt Master server maintains a pillar_roots setup that matches the
structure of the file_roots used in the Salt file server. Like the
Salt file server the ``pillar_roots`` option in the master config is based
on environments mapping to directories. The pillar data is then mapped to
minions based on matchers in a top file which is laid out in the same way
as the state top file.

The configuration for the pillar_roots in the master config is identical in
behavior and function as the file_roots configuration:

.. code-block:: yaml

    pillar_roots:
      base:
        - /srv/pillar

This example configuration declares that the base environment will be located
in the /srv/pillar directory. The top file used matches the name of the top file
used for states, and has the same structure:

.. code-block:: yaml

    base:
      '*':
        - packages

This simple pillar top file declares that information for all minions can be
found in the package's sls file:

.. code-block:: yaml

    {% if grains['os'] == 'RedHat' %}
    apache: httpd
    git: git
    {% elif grains['os'] == 'Debian' %}
    apache: apache2
    git: git-core
    {% endif %}

Now this data can be used from within modules, renderers, state sls files and
more via the shared pillar dict:

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

Refreshing Pillar Data
======================

When pillar data is changed on the master the minions need to refresh the data
locally. This is done with the ``saltutil.refresh_pillar`` function.

.. code-block:: yaml

    salt '*' saltutil.refresh_pillar
