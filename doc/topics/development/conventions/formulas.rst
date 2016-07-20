.. _conventions-formula:

=============
Salt Formulas
=============

Formulas are pre-written Salt States. They are as open-ended as Salt States
themselves and can be used for tasks such as installing a package, configuring,
and starting a service, setting up users or permissions, and many other common
tasks.

All official Salt Formulas are found as separate Git repositories in the
"saltstack-formulas" organization on GitHub:

https://github.com/saltstack-formulas

As a simple example, to install the popular Apache web server (using the normal
defaults for the underlying distro) simply include the
:formula_url:`apache-formula` from a top file:

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

Here is an example of a state that uses the :formula_url:`epel-formula` in a
``require`` declaration which directs Salt to not install the ``python26``
package until after the EPEL repository has also been installed:

.. code-block:: yaml

    include:
      - epel

    python26:
      pkg.installed:
        - require:
          - pkg: epel

Including a Formula from a Top File
-----------------------------------

Some Formula perform completely standalone installations that are not
referenced from other state files. It is usually cleanest to include these
Formula directly from a Top File.

For example the easiest way to set up an OpenStack deployment on a single
machine is to include the :formula_url:`openstack-standalone-formula` directly from
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

The following example uses the stock :formula_url:`apache-formula` alongside a
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

Style
-----

Maintainability, readability, and reusability are all marks of a good Salt sls
file. This section contains several suggestions and examples.

.. code-block:: yaml

    # Deploy the stable master branch unless version overridden by passing
    # Pillar at the CLI or via the Reactor.

    deploy_myapp:
      git.latest:
        - name: git@github.com/myco/myapp.git
        - version: {{ salt.pillar.get('myapp:version', 'master') }}

Use a descriptive State ID
``````````````````````````

The ID of a state is used as a unique identifier that may be referenced via
other states in :ref:`requisites <requisites>`. It must be unique across the
whole state tree (:ref:`it is a key in a dictionary <id-declaration>`, after
all).

In addition a state ID should be descriptive and serve as a high-level hint of
what it will do, or manage, or change. For example, ``deploy_webapp``, or
``apache``, or ``reload_firewall``.

Use ``module.function`` notation
````````````````````````````````

So-called "short-declaration" notation is preferred for referencing state
modules and state functions. It provides a consistent pattern of
``module.function`` shared between Salt States, the Reactor, Salt
Mine, the Scheduler, as well as with the CLI.

.. code-block:: yaml

    # Do
    apache:
      pkg.installed:
        - name: httpd

    # Don't
    apache:
      pkg:
        - installed
        - name: httpd

Salt's state compiler will transform "short-decs" into the longer format
:ref:`when compiling the human-friendly highstate structure into the
machine-friendly lowstate structure <state-layers>`.

Specify the ``name`` parameter
``````````````````````````````

Use a unique and permanent identifier for the state ID and reserve ``name`` for
data with variability.

The :ref:`name declaration <name-declaration>` is a required parameter for all
state functions. The state ID will implicitly be used as ``name`` if it is not
explicitly set in the state.

In many state functions the ``name`` parameter is used for data that varies
such as OS-specific package names, OS-specific file system paths, repository
addresses, etc. Any time the ID of a state changes all references to that ID
must also be changed. Use a permanent ID when writing a state the first time to
future-proof that state and allow for easier refactors down the road.

Comment state files
```````````````````

YAML allows comments at varying indentation levels. It is a good practice to
comment state files. Use vertical whitespace to visually separate different
concepts or actions.

.. code-block:: yaml

    # Start with a high-level description of the current sls file.
    # Explain the scope of what it will do or manage.

    # Comment individual states as necessary.
    update_a_config_file:
      # Provide details on why an unusual choice was made. For example:
      #
      # This template is fetched from a third-party and does not fit our
      # company norm of using Jinja. This must be processed using Mako.
      file.managed:
        - name: /path/to/file.cfg
        - source: salt://path/to/file.cfg.template
        - template: mako

      # Provide a description or explanation that did not fit within the state
      # ID. For example:
      #
      # Update the application's last-deployed timestamp.
      # This is a workaround until Bob configures Jenkins to automate RPM
      # builds of the app.
      cmd.run:
        # FIXME: Joe needs this to run on Windows by next quarter. Switch these
        # from shell commands to Salt's file.managed and file.replace state
        # modules.
        - name: |
            touch /path/to/file_last_updated
            sed -e 's/foo/bar/g' /path/to/file_environment
        - onchanges:
          - file: a_config_file

Be careful to use Jinja comments for commenting Jinja code and YAML comments
for commenting YAML code.

.. code-block:: jinja

    # BAD EXAMPLE
    # The Jinja in this YAML comment is still executed!
    # {% set apache_is_installed = 'apache' in salt.pkg.list_pkgs() %}

    # GOOD EXAMPLE
    # The Jinja in this Jinja comment will not be executed.
    {# {% set apache_is_installed = 'apache' in salt.pkg.list_pkgs() %} #}

Easy on the Jinja!
------------------

Jinja templating provides vast flexibility and power when building Salt sls
files. It can also create an unmaintainable tangle of logic and data. Speaking
broadly, Jinja is best used when kept apart from the states (as much as is
possible).

Below are guidelines and examples of how Jinja can be used effectively.

Know the evaluation and execution order
```````````````````````````````````````

High-level knowledge of how Salt states are compiled and run is useful when
writing states.

The default :conf_minion:`renderer` setting in Salt is Jinja piped to YAML.
Each is a separate step. Each step is not aware of the previous or following
step. Jinja is not YAML aware, YAML is not Jinja aware; they cannot share
variables or interact.

* Whatever the Jinja step produces must be valid YAML.
* Whatever the YAML step produces must be a valid :ref:`highstate data
  structure <states-highstate-example>`. (This is also true of the final step
  for :ref:`any of the alternate renderers <all-salt.renderers>` in Salt.)
* Highstate can be thought of as a human-friendly data structure; easy to write
  and easy to read.
* Salt's state compiler validates the :ref:`highstate <running-highstate>` and
  compiles it to low state.
* Low state can be thought of as a machine-friendly data structure. It is a
  list of dictionaries that each map directly to a function call.
* Salt's state system finally starts and executes on each "chunk" in the low
  state. Remember that requisites are evaluated at runtime.
* The return for each function call is added to the "running" dictionary which
  is the final output at the end of the state run.

The full evaluation and execution order::

    Jinja -> YAML -> Highstate -> low state -> execution

Avoid changing the underlying system with Jinja
```````````````````````````````````````````````

Avoid calling commands from Jinja that change the underlying system. Commands
run via Jinja do not respect Salt's dry-run mode (``test=True``)! This is
usually in conflict with the idempotent nature of Salt states unless the
command being run is also idempotent.

Inspect the local system
````````````````````````

A common use for Jinja in Salt states is to gather information about the
underlying system. The ``grains`` dictionary available in the Jinja context is
a great example of common data points that Salt itself has already gathered.
Less common values are often found by running commands. For example:

.. code-block:: jinja

    {% set is_selinux_enabled = salt.cmd.run('sestatus') == '1' %}

This is usually best done with a variable assignment in order to separate the
data from the state that will make use of the data.

Gather external data
````````````````````

One of the most common uses for Jinja is to pull external data into the state
file. External data can come from anywhere like API calls or database queries,
but it most commonly comes from flat files on the file system or Pillar data
from the Salt Master. For example:

.. code-block:: jinja

    {% set some_data = salt.pillar.get('some_data', {'sane default': True}) %}

    {# or #}

    {% import_yaml 'path/to/file.yaml' as some_data %}

    {# or #}

    {% import_json 'path/to/file.json' as some_data %}

    {# or #}

    {% import_text 'path/to/ssh_key.pub' as ssh_pub_key %}

    {# or #}

    {% from 'path/to/other_file.jinja' import some_data with context %}

This is usually best done with a variable assignment in order to separate the
data from the state that will make use of the data.

Light conditionals and looping
``````````````````````````````

Jinja is extremely powerful for programatically generating Salt states. It is
also easy to overuse. As a rule of thumb, if it is hard to read it will be hard
to maintain!

Separate Jinja control-flow statements from the states as much as is possible
to create readable states. Limit Jinja within states to simple variable
lookups.

Below is a simple example of a readable loop:

.. code-block:: yaml

    {% for user in salt.pillar.get('list_of_users', []) %}

    {# Ensure unique state IDs when looping. #}
    {{ user.name }}-{{ loop.index }}:
      user.present:
        - name: {{ user.name }}
        - shell: {{ user.shell }}

    {% endfor %}

Avoid putting a Jinja conditionals within Salt states where possible.
Readability suffers and the correct YAML indentation is difficult to see in the
surrounding visual noise. Parameterization (discussed below) and variables are
both useful techniques to avoid this. For example:

.. code-block:: yaml

    {# ---- Bad example ---- #}

    apache:
      pkg.installed:
        {% if grains.os_family == 'RedHat' %}
        - name: httpd
        {% elif grains.os_family == 'Debian' %}
        - name: apache2
        {% endif %}

    {# ---- Better example ---- #}

    {% if grains.os_family == 'RedHat' %}
    {% set name = 'httpd' %}
    {% elif grains.os_family == 'Debian' %}
    {% set name = 'apache2' %}
    {% endif %}

     apache:
      pkg.installed:
        - name: {{ name }}

    {# ---- Good example ---- #}

    {% set name = {
        'RedHat': 'httpd',
        'Debian': 'apache2',
    }.get(grains.os_family) %}

     apache:
      pkg.installed:
        - name: {{ name }}

Dictionaries are useful to effectively "namespace" a collection of variables.
This is useful with parameterization (discussed below). Dictionaries are also
easily combined and merged. And they can be directly serialized into YAML which
is often easier than trying to create valid YAML through templating. For
example:

.. code-block:: yaml

    {# ---- Bad example ---- #}

    haproxy_conf:
      file.managed:
        - name: /etc/haproxy/haproxy.cfg
        - template: jinja
        {% if 'external_loadbalancer' in grains.roles %}
        - source: salt://haproxy/external_haproxy.cfg
        {% elif 'internal_loadbalancer' in grains.roles %}
        - source: salt://haproxy/internal_haproxy.cfg
        {% endif %}
        - context:
            {% if 'external_loadbalancer' in grains.roles %}
            ssl_termination: True
            {% elif 'internal_loadbalancer' in grains.roles %}
            ssl_termination: False
            {% endif %}

    {# ---- Better example ---- #}

    {% load_yaml as haproxy_defaults %}
    common_settings:
      bind_port: 80

    internal_loadbalancer:
      source: salt://haproxy/internal_haproxy.cfg
      settings:
        bind_port: 8080
        ssl_termination: False

    external_loadbalancer:
      source: salt://haproxy/external_haproxy.cfg
      settings:
        ssl_termination: True
    {% endload %}

    {% if 'external_loadbalancer' in grains.roles %}
    {% set haproxy = haproxy_defaults['external_loadbalancer'] %}
    {% elif 'internal_loadbalancer' in grains.roles %}
    {% set haproxy = haproxy_defaults['internal_loadbalancer'] %}
    {% endif %}

    {% do haproxy.settings.update(haproxy_defaults.common_settings) %}

    haproxy_conf:
      file.managed:
        - name: /etc/haproxy/haproxy.cfg
        - template: jinja
        - source: {{ haproxy.source }}
        - context: {{ haproxy.settings | yaml() }}

There is still room for improvement in the above example. For example,
extracting into an external file or replacing the if-elif conditional with a
function call to filter the correct data more succinctly. However, the state
itself is simple and legible, the data is separate and also simple and legible.
And those suggested improvements can be made at some future date without
altering the state at all!

Avoid heavy logic and programming
`````````````````````````````````

Jinja is not Python. It was made by Python programmers and shares many
semantics and some syntax but it does not allow for abitrary Python function
calls or Python imports. Jinja is a fast and efficient templating language but
the syntax can be verbose and visually noisy.

Once Jinja use within an sls file becomes slightly complicated -- long chains
of if-elif-elif-else statements, nested conditionals, complicated dictionary
merges, wanting to use sets -- instead consider using a different Salt
renderer, such as the Python renderer. As a rule of thumb, if it is hard to
read it will be hard to maintain -- switch to a format that is easier to read.

Using alternate renderers is very simple to do using Salt's "she-bang" syntax
at the top of the file. The Python renderer must simply return the correct
:ref:`highstate data structure <states-highstate-example>`. The following
example is a state tree of two sls files, one simple and one complicated.

``/srv/salt/top.sls``:

.. code-block:: yaml

    base:
      '*':
        - common_configuration
        - roles_configuration

``/srv/salt/common_configuration.sls``:

.. code-block:: yaml

    common_users:
      user.present:
        - names: [larry, curly, moe]

``/srv/salt/roles_configuration``:

.. code-block:: python

    #!py
    def run():
        list_of_roles = set()

        # This example has the minion id in the form 'web-03-dev'.
        # Easily access the grains dictionary:
        try:
            app, instance_number, environment = __grains__['id'].split('-')
            instance_number = int(instance_number)
        except ValueError:
            app, instance_number, environment = ['Unknown', 0, 'dev']

        list_of_roles.add(app)

        if app == 'web' and environment == 'dev':
            list_of_roles.add('primary')
            list_of_roles.add('secondary')
        elif app == 'web' and environment == 'staging':
            if instance_number == 0:
                list_of_roles.add('primary')
            else:
                list_of_roles.add('secondary')

        # Easily cross-call Salt execution modules:
        if __salt__['myutils.query_valid_ec2_instance']():
            list_of_roles.add('is_ec2_instance')

        return {
            'set_roles_grains': {
                'grains.present': [
                    {'name': 'roles'},
                    {'value': list(list_of_roles)},
                ],
            },
        }

Jinja Macros
````````````

In Salt sls files Jinja macros are useful for one thing and one thing only:
creating mini templates that can be reused and rendered on demand. Do not fall
into the trap of thinking of macros as functions; Jinja is not Python (see
above).

Macros are useful for creating reusable, parameterized states. For example:

.. code-block:: yaml

    {% macro user_state(state_id, user_name, shell='/bin/bash', groups=[]) %}
    {{ state_id }}:
      user.present:
        - name: {{ user_name }}
        - shell: {{ shell }}
        - groups: {{ groups | json() }}
    {% endmacro %}

    {% for user_info in salt.pillar.get('my_users', []) %}
    {{ user_state('user_number_' ~ loop.index, **user_info) }}
    {% endfor %}

Macros are also useful for creating one-off "serializers" that can accept a
data structure and write that out as a domain-specific configuration file. For
example, the following macro could be used to write a php.ini config file:

``/srv/salt/php.sls``:

.. code-block:: yaml

    php_ini:
      file.managed:
        - name: /etc/php.ini
        - source: salt://php.ini.tmpl
        - template: jinja
        - context:
            php_ini_settings: {{ salt.pillar.get('php_ini', {}) | json() }}

``/srv/pillar/php.sls``:

.. code-block:: yaml

    php_ini:
      PHP:
        engine: 'On'
        short_open_tag: 'Off'
        error_reporting: 'E_ALL & ~E_DEPRECATED & ~E_STRICT'

``/srv/salt/php.ini.tmpl``:

.. code-block:: jinja

    {% macro php_ini_serializer(data) %}
    {% for section_name, name_val_pairs in data.items() %}
    [{{ section_name }}]
    {% for name, val in name_val_pairs.items() -%}
    {{ name }} = "{{ val }}"
    {% endfor %}
    {% endfor %}
    {% endmacro %}

    ; File managed by Salt at <{{ source }}>.
    ; Your changes will be overwritten.

    {{ php_ini_serializer(php_ini_settings) }}

Abstracting static defaults into a lookup table
-----------------------------------------------

Separate data that a state uses from the state itself to increases the
flexibility and reusability of a state.

An obvious and common example of this is platform-specific package names and
file system paths. Another example is sane defaults for an application, or
common settings within a company or organization. Organizing such data as a
dictionary (aka hash map, lookup table, associative array) often provides a
lightweight namespacing and allows for quick and easy lookups. In addition,
using a dictionary allows for easily merging and overriding static values
within a lookup table with dynamic values fetched from Pillar.

A strong convention in Salt Formulas is to place platform-specific data, such
as package names and file system paths, into a file named :file:`map.jinja`
that is placed alongside the state files.

The following is an example from the MySQL Formula.
The :py:func:`grains.filter_by <salt.modules.grains.filter_by>` function
performs a lookup on that table using the ``os_family`` grain (by default).

The result is that the ``mysql`` variable is assigned to a *subset* of
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
      pkg.installed:
        - name: {{ mysql.server }}
      service.running:
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
    merge=salt['pillar.get']('mysql:lookup', default='default') %}


Overriding values in the lookup table
`````````````````````````````````````

Allow static values within lookup tables to be overridden. This is a simple
pattern which once again increases flexibility and reusability for state files.

The ``merge`` argument in :py:func:`filter_by <salt.modules.grains.filter_by>`
specifies the location of a dictionary in Pillar that can be used to override
values returned from the lookup table. If the value exists in Pillar it will
take precedence.

This is useful when software or configuration files is installed to
non-standard locations or on unsupported platforms. For example, the following
Pillar would replace the ``config`` value from the call above.

.. code-block:: yaml

    mysql:
      lookup:
        config: /usr/local/etc/mysql/my.cnf

.. note:: Protecting Expansion of Content with Special Characters

  When templating keep in mind that YAML does have special characters for
  quoting, flows, and other special structure and content.  When a Jinja
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

The :py:func:`filter_by <salt.modules.grains.filter_by>` function performs a
simple dictionary lookup but also allows for fetching data from Pillar and
overriding data stored in the lookup table. That same workflow can be easily
performed without using ``filter_by``; other dictionaries besides data from
Pillar can also be used.

.. code-block:: jinja

    {% set lookup_table = {...} %}
    {% do lookup_table.update(salt.pillar.get('my:custom:data')) %}

When to use lookup tables
`````````````````````````

The ``map.jinja`` file is only a convention within Salt Formulas. This greater
pattern is useful for a wide variety of data in a wide variety of workflows.
This pattern is not limited to pulling data from a single file or data source.
This pattern is useful in States, Pillar and the Reactor, for example.

Working with a data structure instead of, say, a config file allows the data to
be cobbled together from multiple sources (local files, remote Pillar, database
queries, etc), combined, overridden, and searched.

Below are a few examples of what lookup tables may be useful for and how they
may be used and represented.

Platform-specific information
.............................

An obvious pattern and one used heavily in Salt Formulas is extracting
platform-specific information such as package names and file system paths in
a file named ``map.jinja``. The pattern is explained in detail above.

Sane defaults
.............

Application settings can be a good fit for this pattern. Store default
settings along with the states themselves and keep overrides and sensitive
settings in Pillar. Combine both into a single dictionary and then write the
application config or settings file.

The example below stores most of the Apache Tomcat ``server.xml`` file
alongside the Tomcat states and then allows values to be updated or augmented
via Pillar. (This example uses the BadgerFish format for transforming JSON to
XML.)

``/srv/salt/tomcat/defaults.yaml``:

.. code-block:: yaml

    Server:
      '@port': '8005'
      '@shutdown': SHUTDOWN
      GlobalNamingResources:
        Resource:
          '@auth': Container
          '@description': User database that can be updated and saved
          '@factory': org.apache.catalina.users.MemoryUserDatabaseFactory
          '@name': UserDatabase
          '@pathname': conf/tomcat-users.xml
          '@type': org.apache.catalina.UserDatabase
      # <...snip...>

``/srv/pillar/tomcat.sls``:

.. code-block:: yaml

    appX:
      server_xml_overrides:
        Server:
          Service:
            '@name': Catalina
            Connector:
              '@port': '8009'
              '@protocol': AJP/1.3
              '@redirectPort': '8443'
              # <...snip...>

``/srv/salt/tomcat/server_xml.sls``:

.. code-block:: yaml

    {% import_yaml 'tomcat/defaults.yaml' as server_xml_defaults %}
    {% set server_xml_final_values = salt.pillar.get(
        'appX:server_xml_overrides',
        default=server_xml_defaults,
        merge=True)
    %}

    appX_server_xml:
      file.serialize:
        - name: /etc/tomcat/server.xml
        - dataset: {{ server_xml_final_values | json() }}
        - formatter: xml_badgerfish

The :py:func:`file.serialize <salt.states.file.serialize>` state can provide a
shorthand for creating some files from data structures. There are also many
examples within Salt Formulas of creating one-off "serializers" (often as Jinja
macros) that reformat a data structure to a specific config file format. For
example, `Nginx vhosts`__ or the `php.ini`__

__: https://github.com/saltstack-formulas/nginx-formula/blob/5cad4512/nginx/ng/vhosts_config.sls
__: https://github.com/saltstack-formulas/php-formula/blob/82e2cd3a/php/ng/files/php.ini

Environment specific information
................................

A single state can be reused when it is parameterized as described in the
section below, by separating the data the state will use from the state that
performs the work. This can be the difference between deploying *Application X*
and *Application Y*, or the difference between production and development. For
example:

``/srv/salt/app/deploy.sls``:

.. code-block:: yaml

    {# Load the map file. #}
    {% import_yaml 'app/defaults.yaml' as app_defaults %}

    {# Extract the relevant subset for the app configured on the current
       machine (configured via a grain in this example). #}
    {% app = app_defaults.get(salt.grains.get('role') %}

    {# Allow values from Pillar to (optionally) update values from the lookup
       table. #}
    {% do app_defaults.update(salt.pillar.get('myapp', {}) %}

    deploy_application:
      git.latest:
        - name: {{ app.repo_url }}
        - version: {{ app.version }}
        - target: {{ app.deploy_dir }}

    myco/myapp/deployed:
      event.send:
        - data:
            version: {{ app.version }}
        - onchanges:
          - git: deploy_application

``/srv/salt/app/defaults.yaml``:

.. code-block:: yaml

    appX:
      repo_url: git@github.com/myco/appX.git
      target: /var/www/appX
      version: master
    appY:
      repo_url: git@github.com/myco/appY.git
      target: /var/www/appY
      version: v1.2.3.4

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
:formula_url:`apache-formula` for more.)

.. code-block:: yaml

    # apache/init.sls
    apache:
      pkg.installed:
        [...]
      service.running:
        [...]

    # apache/mod_wsgi.sls
    include:
      - apache

    mod_wsgi:
      pkg.installed:
        [...]
        - require:
          - pkg: apache

    # apache/conf.sls
    include:
      - apache

    apache_conf:
      file.managed:
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
      file.managed:
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

.. seealso:: :formula_url:`template-formula`

    The :formula_url:`template-formula` repository has a pre-built layout that
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
:py:func:`state.apply <salt.modules.state.apply_>` and checking the output for
the success or failure of each state in the Formula. This should be done for
each supported platform.

.. ............................................................................

.. _`saltstack-formulas`: https://github.com/saltstack-formulas
