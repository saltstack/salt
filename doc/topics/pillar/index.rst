.. _pillar:

=================================
Storing Static Data in the Pillar
=================================

Pillar is an interface for Salt designed to offer global values that can be
distributed to minions. Pillar data is managed in a similar way as
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
state tree.

The top file used matches the name of the top file used for States,
and has the same structure:

``/srv/pillar/top.sls``

.. code-block:: yaml

    base:
      '*':
        - packages

In the above top file, it is declared that in the ``base`` environment, the
glob matching all minions will have the pillar data found in the ``packages``
pillar available to it. Assuming the ``pillar_roots`` value of ``/srv/pillar``
taken from above, the ``packages`` pillar would be located at
``/srv/pillar/packages.sls``.

Any number of matchers can be added to the base environment. For example, here
is an expanded version of the Pillar top file stated above:

/srv/pillar/top.sls:

.. code-block:: yaml

    base:
      '*':
        - packages
      'web*':
        - vim

In this expanded top file, minions that match ``web*`` will have access to the
``/srv/pillar/packages.sls`` file, as well as the ``/srv/pillar/vim.sls`` file.

Another example shows how to use other standard top matching types
to deliver specific salt pillar data to minions with different properties.

Here is an example using the ``grains`` matcher to target pillars to minions
by their ``os`` grain:

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

    company: Foo Industries

.. important::
  See :ref:`Is Targeting using Grain Data Secure? <faq-grain-security>` for
  important security information.

The above pillar sets two key/value pairs. If a minion is running RedHat, then
the ``apache`` key is set to ``httpd`` and the ``git`` key is set to the value
of ``git``. If the minion is running Debian, those values are changed to
``apache2`` and ``git-core`` respectively. All minions that have this pillar
targeting to them via a top file will have the key of ``company`` with a value
of ``Foo Industries``.

Consequently this data can be used from within modules, renderers, State SLS
files, and more via the shared pillar :ref:`dict <python2:typesmapping>`:

.. code-block:: yaml

    apache:
      pkg.installed:
        - name: {{ pillar['apache'] }}

.. code-block:: yaml

    git:
      pkg.installed:
        - name: {{ pillar['git'] }}

Finally, the above states can utilize the values provided to them via Pillar.
All pillar values targeted to a minion are available via the 'pillar'
dictionary. As seen in the above example, Jinja substitution can then be
utilized to access the keys and values in the Pillar dictionary.

Note that you cannot just list key/value-information in ``top.sls``. Instead,
target a minion to a pillar file and then list the keys and values in the
pillar. Here is an example top file that illustrates this point:

.. code-block:: yaml

    base:
      '*':
         - common_pillar

And the actual pillar file at '/srv/pillar/common_pillar.sls':

.. code-block:: yaml

    foo: bar
    boo: baz

Pillar namespace flattened
==========================

The separate pillar files all share the same namespace. Given a ``top.sls`` of:

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

Then a request for the ``bind`` pillar will only return ``named``; the
``bind9`` value is not available. It is better to structure your pillar files
with more hierarchy. For example your ``package.sls`` file could look like:

.. code-block:: yaml

    packages:
      bind: bind9

Pillar Namespace Merges
=======================

With some care, the pillar namespace can merge content from multiple pillar
files under a single key, so long as conflicts are avoided as described above.

For example, if the above example were modified as follows, the values are
merged below a single key:

.. code-block:: yaml

    base:
      '*':
        - packages
        - services

And a ``packages.sls`` file like:

.. code-block:: yaml

    bind:
      package-name: bind9
      version: 9.9.5

And a ``services.sls`` file like:

.. code-block:: yaml

    bind:
      port: 53
      listen-on: any

The resulting pillar will be as follows:

.. code-block:: bash

    $ salt-call pillar.get bind
    local:
        ----------
        listen-on:
            any
        package-name:
            bind9
        port:
            53
        version:
            9.9.5

.. note::
    Pillar files are applied in the order they are listed in the top file.
    Therefore conflicting keys will be overwritten in a 'last one wins' manner!
    For example, in the above scenario conflicting key values in ``services``
    will overwrite those in ``packages`` because it's at the bottom of the list.

Including Other Pillars
=======================

.. versionadded:: 0.16.0

Pillar SLS files may include other pillar files, similar to State files. Two
syntaxes are available for this purpose. The simple form simply includes the
additional pillar as if it were part of the same file:

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
``pillar`` module, the pillar module comes with functions,
:mod:`pillar.items <salt.modules.pillar.items>` and :mod:`pillar.raw
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
    does not include the extra ``:`` delimiter functionality.  It must be
    called using the above syntax (``salt['pillar.get']('foo:bar:baz',
    'qux')``) to get the salt function, instead of the default dictionary
    behavior.


Refreshing Pillar Data
======================

When pillar data is changed on the master the minions need to refresh the data
locally. This is done with the ``saltutil.refresh_pillar`` function.

.. code-block:: bash

    salt '*' saltutil.refresh_pillar

This function triggers the minion to asynchronously refresh the pillar and will
always return ``None``.


Set Pillar Data at the Command Line
===================================

Pillar data can be set at the command line like the following example:

.. code-block:: bash

    salt '*' state.highstate pillar='{"cheese": "spam"}'

This will create a dict with a key of 'cheese' and a value of 'spam'. A list
can be created like this:

.. code-block:: bash

    salt '*' state.highstate pillar='["cheese", "milk", "bread"]'

.. note::

    Be aware that when sending sensitive data via pillar on the command-line
    that the publication containing that data will be received by all minions
    and will not be restricted to the targeted minions. This may represent
    a security concern in some cases.


Master Config In Pillar
=======================

For convenience the data stored in the master configuration file can be made
available in all minion's pillars. This makes global configuration of services
and systems very easy but may not be desired if sensitive data is stored in the
master configuration. This option is disabled by default.

To enable the master config from being added to the pillar set ``pillar_opts``
to ``True``:

.. code-block:: yaml

    pillar_opts: True


Minion Config in Pillar
=======================

Minion configuration options can be set on pillars. Any option that you want
to modify, should be in the first level of the pillars, in the same way you set
the options in the config file. For example, to configure the MySQL root
password to be used by MySQL Salt execution module, set the following pillar
variable:

.. code-block:: yaml

    mysql.pass: hardtoguesspassword


Master Provided Pillar Error
============================

By default if there is an error rendering a pillar, the detailed error is
hidden and replaced with:

.. code-block:: bash

    Rendering SLS 'my.sls' failed. Please see master log for details.

The error is protected because it's possible to contain templating data
which would give that minion information it shouldn't know, like a password!

To have the master provide the detailed error that could potentially carry
protected data set ``pillar_safe_render_error`` to ``False``:

.. code-block:: yaml

    pillar_safe_render_error: False

.. toctree::
    ../tutorials/pillar
