.. _pillar-walk-through:

==================
Pillar Walkthrough
==================

.. note::

    This walkthrough assumes that the reader has already completed the initial
    Salt :ref:`walkthrough <tutorial-salt-walk-through>`.

Pillars are tree-like structures of data defined on the Salt Master and passed
through to minions. They allow confidential, targeted data to be securely sent
only to the relevant minion.

.. note::

    Grains and Pillar are sometimes confused, just remember that Grains
    are data about a minion which is stored or generated from the minion.
    This is why information like the OS and CPU type are found in Grains.
    Pillar is information about a minion or many minions stored or generated
    on the Salt Master.

Pillar data is useful for:

Highly Sensitive Data:
    Information transferred via pillar is guaranteed to only be presented to
    the minions that are targeted, making Pillar suitable
    for managing security information, such as cryptographic keys and
    passwords.
Minion Configuration:
    Minion modules such as the execution modules, states, and returners can
    often be configured via data stored in pillar.
Variables:
    Variables which need to be assigned to specific minions or groups of
    minions can be defined in pillar and then accessed inside sls formulas
    and template files.
Arbitrary Data:
    Pillar can contain any basic data structure in dictionary format,
    so a key/value store can be defined making it easy to iterate over a group
    of values in sls formulas.

Pillar is therefore one of the most important systems when using Salt. This
walkthrough is designed to get a simple Pillar up and running in a few minutes
and then to dive into the capabilities of Pillar and where the data is
available.

Setting Up Pillar
=================

The pillar is already running in Salt by default. To see the minion's
pillar data:

.. code-block:: bash

    salt '*' pillar.items

.. note::
    Prior to version 0.16.2, this function is named ``pillar.data``. This
    function name is still supported for backwards compatibility.

By default, the contents of the master configuration file are not loaded into
pillar for all minions. This default is stored in the ``pillar_opts`` setting,
which defaults to ``False``.

The contents of the master configuration file can be made available to minion
pillar files. This makes global configuration of services and systems very easy,
but note that this may not be desired or appropriate if sensitive data is stored
in the master's configuration file. To enable the master configuration file to be
available to minion as pillar, set ``pillar_opts: True`` in the master
configuration file, and then for appropriate minions also set ``pillar_opts: True``
in the minion(s) configuration file.

Similar to the state tree, the pillar is comprised of sls files and has a top file.
The default location for the pillar is in /srv/pillar.

.. note::

    The pillar location can be configured via the ``pillar_roots`` option inside
    the master configuration file. It must not be in a subdirectory of the state
    tree or file_roots. If the pillar is under file_roots, any pillar targeting
    can be bypassed by minions.

To start setting up the pillar, the /srv/pillar directory needs to be present:

.. code-block:: bash

    mkdir /srv/pillar

Now create a simple top file, following the same format as the top file used for
states:

``/srv/pillar/top.sls``:

.. code-block:: yaml

    base:
      '*':
        - data

This top file associates the data.sls file to all minions. Now the
``/srv/pillar/data.sls`` file needs to be populated:

``/srv/pillar/data.sls``:

.. code-block:: yaml

    info: some data

To ensure that the minions have the new pillar data, issue a command
to them asking that they fetch their pillars from the master:

.. code-block:: bash

    salt '*' saltutil.refresh_pillar

Now that the minions have the new pillar, it can be retrieved:

.. code-block:: bash

    salt '*' pillar.items

The key ``info`` should now appear in the returned pillar data.

More Complex Data
~~~~~~~~~~~~~~~~~

Unlike states, pillar files do not need to define :strong:`formulas`.
This example sets up user data with a UID:

``/srv/pillar/users/init.sls``:

.. code-block:: yaml

    users:
      thatch: 1000
      shouse: 1001
      utahdave: 1002
      redbeard: 1003

.. note::

    The same directory lookups that exist in states exist in pillar, so the
    file ``users/init.sls`` can be referenced with ``users`` in the :term:`top
    file <Top File>`.

The top file will need to be updated to include this sls file:

``/srv/pillar/top.sls``:

.. code-block:: yaml

    base:
      '*':
        - data
        - users

Now the data will be available to the minions. To use the pillar data in a
state, you can use Jinja:

``/srv/salt/users/init.sls``

.. code-block:: jinja

    {% for user, uid in pillar.get('users', {}).items() %}
    {{user}}:
      user.present:
        - uid: {{uid}}
    {% endfor %}

This approach allows for users to be safely defined in a pillar and then the
user data is applied in an sls file.

Parameterizing States With Pillar
=================================

Pillar data can be accessed in state files to customise behavior for each
minion. All pillar (and grain) data applicable to each minion is substituted
into the state files through templating before being run. Typical uses
include setting directories appropriate for the minion and skipping states
that don't apply.

A simple example is to set up a mapping of package names in pillar for
separate Linux distributions:

``/srv/pillar/pkg/init.sls``:

.. code-block:: jinja

    pkgs:
      {% if grains['os_family'] == 'RedHat' %}
      apache: httpd
      vim: vim-enhanced
      {% elif grains['os_family'] == 'Debian' %}
      apache: apache2
      vim: vim
      {% elif grains['os'] == 'Arch' %}
      apache: apache
      vim: vim
      {% endif %}

The new ``pkg`` sls needs to be added to the top file:

``/srv/pillar/top.sls``:

.. code-block:: yaml

    base:
      '*':
        - data
        - users
        - pkg

Now the minions will auto map values based on respective operating systems
inside of the pillar, so sls files can be safely parameterized:

``/srv/salt/apache/init.sls``:

.. code-block:: jinja

    apache:
      pkg.installed:
        - name: {{ pillar['pkgs']['apache'] }}

Or, if no pillar is available a default can be set as well:

.. note::

    The function ``pillar.get`` used in this example was added to Salt in
    version 0.14.0

``/srv/salt/apache/init.sls``:

.. code-block:: jinja

    apache:
      pkg.installed:
        - name: {{ salt['pillar.get']('pkgs:apache', 'httpd') }}

In the above example, if the pillar value ``pillar['pkgs']['apache']`` is not
set in the minion's pillar, then the default of ``httpd`` will be used.

.. note::

    Under the hood, pillar is just a Python dict, so Python dict methods such
    as ``get`` and ``items`` can be used.

Pillar Makes Simple States Grow Easily
======================================

One of the design goals of pillar is to make simple sls formulas easily grow
into more flexible formulas without refactoring or complicating the states.

A simple formula:

``/srv/salt/edit/vim.sls``:

.. code-block:: yaml

    vim:
      pkg.installed: []

    /etc/vimrc:
      file.managed:
        - source: salt://edit/vimrc
        - mode: 644
        - user: root
        - group: root
        - require:
          - pkg: vim

Can be easily transformed into a powerful, parameterized formula:

``/srv/salt/edit/vim.sls``:

.. code-block:: jinja

    vim:
      pkg.installed:
        - name: {{ pillar['pkgs']['vim'] }}

    /etc/vimrc:
      file.managed:
        - source: {{ pillar['vimrc'] }}
        - mode: 644
        - user: root
        - group: root
        - require:
          - pkg: vim

Where the vimrc source location can now be changed via pillar:

``/srv/pillar/edit/vim.sls``:

.. code-block:: jinja

    {% if grains['id'].startswith('dev') %}
    vimrc: salt://edit/dev_vimrc
    {% elif grains['id'].startswith('qa') %}
    vimrc: salt://edit/qa_vimrc
    {% else %}
    vimrc: salt://edit/vimrc
    {% endif %}

Ensuring that the right vimrc is sent out to the correct minions.

The pillar top file must include a reference to the new sls pillar file:

``/srv/pillar/top.sls``:

.. code-block:: yaml

    base:
      '*':
        - pkg
        - edit.vim


Setting Pillar Data on the Command Line
=======================================

Pillar data can be set on the command line when running :py:func:`state.apply
<salt.modules.state.apply_` like so:

.. code-block:: bash

    salt '*' state.apply pillar='{"foo": "bar"}'
    salt '*' state.apply my_sls_file pillar='{"hello": "world"}'

Nested pillar values can also be set via the command line:

.. code-block:: bash

    salt '*' state.sls my_sls_file pillar='{"foo": {"bar": "baz"}}'

Lists can be passed via command line pillar data as follows:

.. code-block:: bash

    salt '*' state.sls my_sls_file pillar='{"some_list": ["foo", "bar", "baz"]}'

.. note::

    If a key is passed on the command line that already exists on the minion,
    the key that is passed in will overwrite the entire value of that key,
    rather than merging only the specified value set via the command line.

The example below will swap the value for vim with telnet in the previously
specified list, notice the nested pillar dict:

.. code-block:: bash

    salt '*' state.apply edit.vim pillar='{"pkgs": {"vim": "telnet"}}'

This will attempt to install telnet on your minions, feel free to
uninstall the package or replace telnet value with anything else.

.. note::
   Be aware that when sending sensitive data via pillar on the command-line
   that the publication containing that data will be received by all minions
   and will not be restricted to the targeted minions. This may represent
   a security concern in some cases.

More On Pillar
==============

Pillar data is generated on the Salt master and securely distributed to
minions. Salt is not restricted to the pillar sls files when defining the
pillar but can retrieve data from external sources. This can be useful when
information about an infrastructure is stored in a separate location.

Reference information on pillar and the external pillar interface can be found
in the Salt documentation:

:ref:`Pillar <pillar>`

Minion Config in Pillar
=======================

Minion configuration options can be set on pillars. Any option that you want
to modify, should be in the first level of the pillars, in the same way you set
the options in the config file. For example, to configure the MySQL root
password to be used by MySQL Salt execution module:

.. code-block:: yaml

    mysql.pass: hardtoguesspassword

This is very convenient when you need some dynamic configuration change that
you want to be applied on the fly. For example, there is a chicken and the egg
problem if you do this:

.. code-block:: yaml

    mysql-admin-passwd:
      mysql_user.present:
        - name: root
        - password: somepasswd

    mydb:
      mysql_db.present

The second state will fail, because you changed the root password and the
minion didn't notice it. Setting mysql.pass in the pillar, will help to sort
out the issue. But always change the root admin password in the first place.

This is very helpful for any module that needs credentials to apply state
changes: mysql, keystone, etc.

