.. _conventions-formula:

=============
Salt Formulas
=============

Formulas are pre-written Salt States. They are as open-ended as Salt States
themselves and can be used for tasks such as installing a package, configuring
and starting a service, setting up users or permissions, and many other common
tasks.

All official Salt Formulas are found as separate Git repositories in the
"saltstack-formulas" organization on GitHub:

https://github.com/saltstack-formulas

As a simple example, to install the popular Apache web server (using the normal
defaults for the underlying distro) simply include the
:formula:`apache-formula` from a top file:

.. code-block:: yaml

    base:
      'web*':
        - apache

Installation
============

Each Salt Formula is an individual Git repository designed as a drop-in
addition to an existing Salt State tree. Formulas can be installed in the
following ways.

Adding a Formula as a GitFS remote
----------------------------------

One design goal of Salt's GitFS fileserver backend was to facilitate reusable
States. GitFS is a quick and natural way to use Formulas.

1.  :ref:`Install and configure GitFS <tutorial-gitfs>`.

2.  Add one or more Formula repository URLs as remotes in the
    :conf_master:`gitfs_remotes` list in the Salt Master configuration file:

    .. code-block:: yaml

        gitfs_remotes:
          - https://github.com/saltstack-formulas/apache-formula
          - https://github.com/saltstack-formulas/memcached-formula

    **We strongly recommend forking a formula repository** into your own GitHub
    account to avoid unexpected changes to your infrastructure.

    Many Salt Formulas are highly active repositories so pull new changes with
    care. Plus any additions you make to your fork can be easily sent back
    upstream with a quick pull request!

3.  Restart the Salt master.

Adding a Formula directory manually
-----------------------------------

Formulas are simply directories that can be copied onto the local file system
by using Git to clone the repository or by downloading and expanding a tarball
or zip file of the repository. The directory structure is designed to work with
:conf_master:`file_roots` in the Salt master configuration.

1.  Clone or download the repository into a directory:

    .. code-block:: bash

        mkdir -p /srv/formulas
        cd /srv/formulas
        git clone https://github.com/saltstack-formulas/apache-formula.git

        # or

        mkdir -p /srv/formulas
        cd /srv/formulas
        wget https://github.com/saltstack-formulas/apache-formula/archive/master.tar.gz
        tar xf apache-formula-master.tar.gz

2.  Add the new directory to :conf_master:`file_roots`:

    .. code-block:: yaml

        file_roots:
          base:
            - /srv/salt
            - /srv/formulas/apache-formula

3.  Restart the Salt Master.


Usage
=====

Each Formula is intended to be immediately usable with sane defaults without
any additional configuration. Many formulas are also configurable by including
data in Pillar; see the :file:`pillar.example` file in each Formula repository
for available options.

Including a Formula in an existing State tree
---------------------------------------------

Formula may be included in an existing ``sls`` file. This is often useful when
a state you are writing needs to ``require`` or ``extend`` a state defined in
the formula.

Here is an example of a state that uses the :formula:`epel-formula` in a
``require`` declaration which directs Salt to not install the ``python26``
package until after the EPEL repository has also been installed:

.. code-block:: yaml

    include:
      - epel

    python26:
      pkg:
        - installed
        - require:
          - pkg: epel

Including a Formula from a Top File
-----------------------------------

Some Formula perform completely standalone installations that are not
referenced from other state files. It is usually cleanest to include these
Formula directly from a Top File.

For example the easiest way to set up an OpenStack deployment on a single
machine is to include the :formula:`openstack-standalone-formula` directly from
a :file:`top.sls` file:

.. code-block:: yaml

    base:
      'myopenstackmaster':
        - openstack

Quickly deploying OpenStack across several dedicated machines could also be
done directly from a Top File and may look something like this:

.. code-block:: yaml

    base:
      'controller':
        - openstack.horizon
        - openstack.keystone
      'hyper-*':
        - openstack.nova
        - openstack.glance
      'storage-*':
        - openstack.swift

Configuring Formula using Pillar
--------------------------------

Salt Formulas are designed to work out of the box with no additional
configuration. However, many Formula support additional configuration and
customization through :ref:`Pillar <pillar>`. Examples of available options can
be found in a file named :file:`pillar.example` in the root directory of each
Formula repository.

.. _extending-formulas:

Using Formula with your own states
----------------------------------

Remember that Formula are regular Salt States and can be used with all Salt's
normal state mechanisms. Formula can be required from other States with
:ref:`requisites-require` declarations, they can be modified using ``extend``,
they can made to watch other states with :ref:`requisites-watch-in`.

The following example uses the stock :formula:`apache-formula` alongside a
custom state to create a vhost on a Debian/Ubuntu system and to reload the
Apache service whenever the vhost is changed.

.. code-block:: yaml

    # Include the stock, upstream apache formula.
    include:
      - apache

    # Use the watch_in requisite to cause the apache service state to reload
    # apache whenever the my-example-com-vhost state changes.
    my-example-com-vhost:
      file:
        - managed
        - name: /etc/apache2/sites-available/my-example-com
        - watch_in:
          - service: apache

Don't be shy to read through the source for each Formula!

Reporting problems & making additions
-------------------------------------

Each Formula is a separate repository on GitHub. If you encounter a bug with a
Formula please file an issue in the respective repository! Send fixes and
additions as a pull request. Add tips and tricks to the repository wiki.

Writing Formulas
================

Each Formula is a separate repository in the `saltstack-formulas`_ organization
on GitHub.

.. note:: Get involved creating new Formulas

    The best way to create new Formula repositories for now is to create a
    repository in your own account on GitHub and notify a SaltStack employee
    when it is ready. We will add you to the contributors team on the
    `saltstack-formulas`_ organization and help you transfer the repository
    over. Ping a SaltStack employee on IRC (``#salt`` on Freenode) or send an
    email to the `salt-users`_ mailing list.

    There are a lot of repositories in that organization! Team members can
    manage which repositories they are subscribed to on GitHub's watching page:
    https://github.com/watching.

Abstracting platform-specific data
----------------------------------

It is useful to have a single source for platform-specific or other static
information that can be reused throughout a Formula. Such a file should be
named :file:`map.jinja` and live alongside the state files.

The following is an example from the MySQL Formula. It is a simple dictionary
that serves as a lookup table (sometimes called a hash map or a dictionary).
The :py:func:`grains.filter_by <salt.modules.grains.filter_by>` function
performs a lookup on that table using the ``os_family`` grain (by default).

The result is that the ``mysql`` variable is assigned to one of *subsets* of
the lookup table for the current platform. This allows states to reference, for
example, the name of a package without worrying about the underlying OS. The
syntax for referencing a value is a normal dictionary lookup in Jinja, such as
``{{ mysql['service'] }}`` or the shorthand ``{{ mysql.service }}``.

:file:`map.jinja`:

.. code-block:: jinja

    {% set mysql = salt['grains.filter_by']({
        'Debian': {
            'server': 'mysql-server',
            'client': 'mysql-client',
            'service': 'mysql',
            'config': '/etc/mysql/my.cnf',
            'python': 'python-mysqldb',
        },
        'RedHat': {
            'server': 'mysql-server',
            'client': 'mysql',
            'service': 'mysqld',
            'config': '/etc/my.cnf',
            'python': 'MySQL-python',
        },
        'Gentoo': {
            'server': 'dev-db/mysql',
            'client': 'dev-db/mysql',
            'service': 'mysql',
            'config': '/etc/mysql/my.cnf',
            'python': 'dev-python/mysql-python',
        },
    }, merge=salt['pillar.get']('mysql:lookup')) %}

Values defined in the map file can be fetched for the current platform in any
state file using the following syntax:

.. code-block:: yaml

    {% from "mysql/map.jinja" import mysql with context %}

    mysql-server:
      pkg:
        - installed
        - name: {{ mysql.server }}
      service:
        - running
        - name: {{ mysql.service }}

Collecting common values
````````````````````````

Common values can be collected into a *base* dictionary.  This
minimizes repetition of identical values in each of the
``lookup_dict`` sub-dictionaries.  Now only the values that are
different from the base must be specified of the alternates:

:file:`map.jinja`:

.. code-block:: jinja

    {% set mysql = salt['grains.filter_by']({
        'default': {
            'server': 'mysql-server',
            'client': 'mysql-client',
            'service': 'mysql',
            'config': '/etc/mysql/my.cnf',
            'python': 'python-mysqldb',
        },
        'Debian': {
        },
        'RedHat': {
            'client': 'mysql',
            'service': 'mysqld',
            'config': '/etc/my.cnf',
            'python': 'MySQL-python',
        },
        'Gentoo': {
            'server': 'dev-db/mysql',
            'client': 'dev-db/mysql',
            'python': 'dev-python/mysql-python',
        },
    },
    merge=salt['pillar.get']('mysql:lookup'), base='default') %}


Overriding values in the lookup table
`````````````````````````````````````

Any value in the lookup table may be overridden using Pillar.

The ``merge`` keyword specifies the location of a dictionary in Pillar that can
be used to override values returned from the lookup table. If the value exists
in Pillar it will take precedence.

This is useful when software or configuration files is installed to
non-standard locations or on unsupported platforms. For example, the following
Pillar would replace the ``config`` value from the call above.

.. code-block:: yaml

    mysql:
      lookup:
        config: /usr/local/etc/mysql/my.cnf

.. note:: Protecting Expansion of Content with Special Characters

  When templating keep in mind that YAML does have special characters for
  quoting, flows and other special structure and content.  When a Jinja
  substitution may have special characters that will be incorrectly parsed by
  YAML care must be taken.  It is a good policy to use the ``yaml_encode`` or
  the ``yaml_dquote`` Jinja filters:

  .. code-block:: jinja

      {%- set foo = 7.7 %}
      {%- set bar = none %}
      {%- set baz = true %}
      {%- set zap = 'The word of the day is "salty".' %}
      {%- set zip = '"The quick brown fox . . ."' %}

      foo: {{ foo|yaml_encode }}
      bar: {{ bar|yaml_encode }}
      baz: {{ baz|yaml_encode }}
      zap: {{ zap|yaml_encode }}
      zip: {{ zip|yaml_dquote }}

  The above will be rendered as below:

  .. code-block:: yaml

      foo: 7.7
      bar: null
      baz: true
      zap: "The word of the day is \"salty\"."
      zip: "\"The quick brown fox . . .\""


Single-purpose SLS files
------------------------

Each sls file in a Formula should strive to do a single thing. This increases
the reusability of this file by keeping unrelated tasks from getting coupled
together.

As an  example, the base Apache formula should only install the Apache httpd
server and start the httpd service. This is the basic, expected behavior when
installing Apache. It should not perform additional changes such as set the
Apache configuration file or create vhosts.

If a formula is single-purpose as in the example above, other formulas, and
also other states can ``include`` and use that formula with :ref:`requisites`
without also including undesirable or unintended side-effects.

The following is a best-practice example for a reusable Apache formula. (This
skips platform-specific options for brevity. See the full
:formula:`apache-formula` for more.)

.. code-block:: yaml

    # apache/init.sls
    apache:
      pkg:
        - installed
        [...]
      service:
        - running
        [...]

    # apache/mod_wsgi.sls
    include:
      - apache

    mod_wsgi:
      pkg:
        - installed
        [...]
        - require:
          - pkg: apache

    # apache/conf.sls
    include:
      - apache

    apache_conf:
      file:
        - managed
        [...]
        - watch_in:
          - service: apache

To illustrate a bad example, say the above Apache formula installed Apache and
also created a default vhost. The mod_wsgi state would not be able to include
the Apache formula to create that dependency tree without also installing the
unneeded default vhost.

:ref:`Formulas should be reusable <extending-formulas>`. Avoid coupling
unrelated actions together.

.. _conventions-formula-parameterization:

Parameterization
----------------

*Parameterization is a key feature of Salt Formulas* and also for Salt
States. Parameterization allows a single Formula to be reused across many
operating systems; to be reused across production, development, or staging
environments; and to be reused by many people all with varying goals.

Writing states, specifying ordering and dependencies is the part that takes the
longest to write and to test. Filling those states out with data such as users
or package names or file locations is the easy part. How many users, what those
users are named, or where the files live are all implementation details that
**should be parameterized**. This separation between a state and the data that
populates a state creates a reusable formula.

In the example below the data that populates the state can come from anywhere
-- it can be hard-coded at the top of the state, it can come from an external
file, it can come from Pillar, it can come from an execution function call, or
it can come from a database query. The state itself doesn't change regardless
of where the data comes from. Production data will vary from development data
will vary from data from one company to another, however the state itself stays
the same.

.. code-block:: jinja

    {% set user_list = [
        {'name': 'larry', 'shell': 'bash'},
        {'name': 'curly', 'shell': 'bash'},
        {'name': 'moe', 'shell': 'zsh'},
    ] %}

    {# or #}

    {% set user_list = salt['pillar.get']('user_list') %}

    {# or #}

    {% load_json "default_users.json" as user_list %}

    {# or #}

    {% set user_list = salt['acme_utils.get_user_list']() %}

    {% for user in list_list %}
    {{ user.name }}:
      user.present:
        - name: {{ user.name }}
        - shell: {{ user.shell }}
    {% endfor %}

Configuration
-------------

Formulas should strive to use the defaults of the underlying platform, followed
by defaults from the upstream project, followed by sane defaults for the
formula itself.

As an example, a formula to install Apache **should not** change the default
Apache configuration file installed by the OS package. However, the Apache
formula **should** include a state to change or override the default
configuration file.

Pillar overrides
----------------

Pillar lookups must use the safe :py:func:`~salt.modules.pillar.get`
and must provide a default value. Create local variables using the Jinja
``set`` construct to increase redability and to avoid potentially hundreds or
thousands of function calls across a large state tree.

.. code-block:: jinja

    {% from "apache/map.jinja" import apache with context %}
    {% set settings = salt['pillar.get']('apache', {}) %}

    mod_status:
      file:
        - managed
        - name: {{ apache.conf_dir }}
        - source: {{ settings.get('mod_status_conf', 'salt://apache/mod_status.conf') }}
        - template: {{ settings.get('template_engine', 'jinja') }}

Any default values used in the Formula must also be documented in the
:file:`pillar.example` file in the root of the repository. Comments should be
used liberally to explain the intent of each configuration value. In addition,
users should be able copy-and-paste the contents of this file into their own
Pillar to make any desired changes.

Scripting
---------

Remember that both State files and Pillar files can easily call out to Salt
:ref:`execution modules <all-salt.modules>` and have access to all the system
grains as well.

.. code-block:: jinja

    {% if '/storage' in salt['mount.active']() %}
    /usr/local/etc/myfile.conf:
      file:
        - symlink
        - target: /storage/myfile.conf
    {% endif %}

Jinja macros to encapsulate logic or conditionals are discouraged in favor of
:ref:`writing custom execution modules  <writing-execution-modules>` in Python.

Repository structure
====================

A basic Formula repository should have the following layout:

.. code-block:: text

    foo-formula
    |-- foo/
    |   |-- map.jinja
    |   |-- init.sls
    |   `-- bar.sls
    |-- CHANGELOG.rst
    |-- LICENSE
    |-- pillar.example
    |-- README.rst
    `-- VERSION

.. seealso:: :formula:`template-formula`

    The :formula:`template-formula` repository has a pre-built layout that
    serves as the basic structure for a new formula repository. Just copy the
    files from there and edit them.

``README.rst``
--------------

The README should detail each available ``.sls`` file by explaining what it
does, whether it has any dependencies on other formulas, whether it has a
target platform, and any other installation or usage instructions or tips.

A sample skeleton for the ``README.rst`` file:

.. code-block:: rest

    ===
    foo
    ===

    Install and configure the FOO service.

    .. note::

        See the full `Salt Formulas installation and usage instructions
        <http://docs.saltstack.com/en/latest/topics/development/conventions/formulas.html>`_.

    Available states
    ================

    .. contents::
        :local:

    ``foo``
    -------

    Install the ``foo`` package and enable the service.

    ``foo.bar``
    -----------

    Install the ``bar`` package.

``CHANGELOG.rst``
-----------------

The ``CHANGELOG.rst`` file should detail the individual versions, their
release date and a set of bullet points for each version highlighting the
overall changes in a given version of the formula.

A sample skeleton for the `CHANGELOG.rst` file:

:file:`CHANGELOG.rst`:

.. code-block:: rest

    foo formula
    ===========

    0.0.2 (2013-01-01)

    - Re-organized formula file layout
    - Fixed filename used for upstart logger template
    - Allow for pillar message to have default if none specified

Versioning
----------

Formula are versioned according to Semantic Versioning, http://semver.org/.

.. note::

    Given a version number MAJOR.MINOR.PATCH, increment the:

    #. MAJOR version when you make incompatible API changes,
    #. MINOR version when you add functionality in a backwards-compatible manner, and
    #. PATCH version when you make backwards-compatible bug fixes.

    Additional labels for pre-release and build metadata are available as extensions
    to the MAJOR.MINOR.PATCH format.

Formula versions are tracked using Git tags as well as the ``VERSION`` file
in the formula repository. The ``VERSION`` file should contain the currently
released version of the particular formula.

Testing Formulas
================

A smoke-test for invalid Jinja, invalid YAML, or an invalid Salt state
structure can be performed by with the :py:func:`state.show_sls
<salt.modules.state.show_sls>` function:

.. code-block:: bash

    salt '*' state.show_sls apache

Salt Formulas can then be tested by running each ``.sls`` file via
:py:func:`state.sls <salt.modules.state.sls>` and checking the output for the
success or failure of each state in the Formula. This should be done for each
supported platform.

.. ............................................................................

.. _`saltstack-formulas`: https://github.com/saltstack-formulas
