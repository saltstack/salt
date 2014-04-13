.. _pillar:

=================================
Storing Static Data in the Pillar
=================================

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

The configuration for the :conf_master:`pillar_roots` in the master config file
is identical in behavior and function as :conf_master:`file_roots`:

.. code-block:: yaml

    pillar_roots:
      base:
        - /srv/pillar

This example configuration declares that the base environment will be located
in the ``/srv/pillar`` directory. It must not be in a subdirectory of the
state tree. The top file used matches the name of the top file used for States,
and has the same structure:

``/srv/pillar/top.sls``

.. code-block:: yaml

    base:
      '*':
        - packages

This further example shows how to use other standard top matching types (grain
matching is used in this example) to deliver specific salt pillar data to
minions with different ``os`` grains:

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
more via the shared pillar :ref:`dict <python2:typesmapping>`:

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



Note that you cannot just list key/value-information in ``top.sls``.

Pillar namespace flattened
==========================

The separate pillar files all share the same namespace. Given 
a ``top.sls`` of:

.. code-block:: yaml

    base:
      '*':
        - packages
        - services

a ``packages.sls`` file of:

.. code-block:: yaml

    bind: bind9

and a ``services.sls`` file of:

.. code-block:: yaml

    bind: named

Then a request for the ``bind`` pillar will only return 'named'; the 'bind9'
value is not available. It is better to structure your pillar files with more
hierarchy. For example your ``package.sls`` file could look like:

.. code-block:: yaml

    packages:
      bind: bind9

Including Other Pillars
=======================

.. versionadded:: 0.16.0

Pillar SLS files may include other pillar files, similar to State files.
Two syntaxes are available for this purpose. The simple form simply includes
the additional pillar as if it were part of the same file:

.. code-block:: yaml

    include:
      - users

The full include form allows two additional options -- passing default values
to the templating engine for the included pillar file as well as an optional
key under which to nest the results of the included pillar:

.. code-block:: yaml

    include:
      - users:
          defaults:
              sudo: ['bob', 'paul']
          key: users

With this form, the included file (users.sls) will be nested within the 'users'
key of the compiled pillar. Additionally, the 'sudo' value will be available
as a template variable to users.sls.


Viewing Minion Pillar
=====================

Once the pillar is set up the data can be viewed on the minion via the
``pillar`` module, the pillar module comes with two functions,
:mod:`pillar.items <salt.modules.pillar.items>` and and :mod:`pillar.raw
<salt.modules.pillar.raw>`.  :mod:`pillar.items <salt.modules.pillar.items>`
will return a freshly reloaded pillar and :mod:`pillar.raw
<salt.modules.pillar.raw>` will return the current pillar without a refresh:

.. code-block:: bash

    salt '*' pillar.items

.. note::
    Prior to version 0.16.2, this function is named ``pillar.data``. This
    function name is still supported for backwards compatibility.


Pillar "get" Function
=====================

.. versionadded:: 0.14.0

The :mod:`pillar.get <salt.modules.pillar.get>` function works much in the same
way as the ``get`` method in a python dict, but with an enhancement: nested
dict components can be extracted using a `:` delimiter.

If a structure like this is in pillar:

.. code-block:: yaml

    foo:
      bar:
        baz: qux

Extracting it from the raw pillar in an sls formula or file template is done
this way:

.. code-block:: jinja

    {{ pillar['foo']['bar']['baz'] }}

Now, with the new :mod:`pillar.get <salt.modules.pillar.get>` function the data
can be safely gathered and a default can be set, allowing the template to fall
back if the value is not available:

.. code-block:: jinja

    {{ salt['pillar.get']('foo:bar:baz', 'qux') }}

This makes handling nested structures much easier.

.. note:: ``pillar.get()`` vs ``salt['pillar.get']()``

    It should be noted that within templating, the ``pillar`` variable is just
    a dictionary.  This means that calling ``pillar.get()`` inside of a
    template will just use the default dictionary ``.get()`` function which
    does not include the extra ``:`` delimeter functionality.  It must be
    called using the above syntax (``salt['pillar.get']('foo:bar:baz',
    'qux')``) to get the salt function, instead of the default dictionary
    behavior.


Refreshing Pillar Data
======================

When pillar data is changed on the master the minions need to refresh the data
locally. This is done with the ``saltutil.refresh_pillar`` function.

.. code-block:: yaml

    salt '*' saltutil.refresh_pillar

This function triggers the minion to asynchronously refresh the pillar and will
always return ``None``.

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
``baz``:

.. code-block:: bash

    salt -I 'foo:bar:baz*' test.ping


Master Config In Pillar
=======================

For convenience the data stored in the master configuration file is made
available in all minion's pillars. This makes global configuration of services
and systems very easy but may not be desired if sensitive data is stored in the
master configuration.

To disable the master config from being added to the pillar set ``pillar_opts``
to ``False``:

.. code-block:: yaml

    pillar_opts: False
