.. _best-practices:

============================
Salt :index:`Best Practices`
============================

Salt's extreme flexibility leads to many questions concerning the structure of
configuration files.

This document exists to clarify these points through examples and code.

.. important::
   The guidance here should be taken in combination with :ref:`hardening-salt`.

General rules
-------------

1. Modularity and clarity should be emphasized whenever possible.
2. Create clear relations between pillars and states.
3. Use variables when it makes sense but don't overuse them.
4. Store sensitive data in pillar.
5. Don't use grains for matching in your pillar top file for any sensitive
   pillars.
6. When accessing modules from within a template, use the mapping
   key syntax instead of the attribute one to avoid edge cases. Example:

   .. code-block:: jinja

       {%- set do_this = salt['pillar.get']('foo:bar') %}
       {%- set avoid_this = salt.pillar.get('foo:bar') %}

   .. include:: ../_incl/grains_passwords.rst

Structuring States and Formulas
-------------------------------

When structuring Salt States and Formulas it is important to begin with the
directory structure. A proper directory structure clearly defines the
functionality of each state to the user via visual inspection of the state's
name.

Reviewing the :formula_url:`MySQL Salt Formula <mysql-formula>`
it is clear to see the benefits to the end-user when reviewing a sample of the
available states:

.. code-block:: bash

    /srv/salt/mysql/files/
    /srv/salt/mysql/client.sls
    /srv/salt/mysql/map.jinja
    /srv/salt/mysql/python.sls
    /srv/salt/mysql/server.sls

This directory structure would lead to these states being referenced in a top
file in the following way:

.. code-block:: yaml

    base:
      'web*':
        - mysql.client
        - mysql.python
      'db*':
        - mysql.server

This clear definition ensures that the user is properly informed of what each
state will do.

Another example comes from the :formula_url:`vim-formula`:

.. code-block:: bash

    /srv/salt/vim/files/
    /srv/salt/vim/absent.sls
    /srv/salt/vim/init.sls
    /srv/salt/vim/map.jinja
    /srv/salt/vim/nerdtree.sls
    /srv/salt/vim/pyflakes.sls
    /srv/salt/vim/salt.sls

Once again viewing how this would look in a top file:

/srv/salt/top.sls:

.. code-block:: yaml

    base:
      'web*':
        - vim
        - vim.nerdtree
        - vim.pyflakes
        - vim.salt
      'db*':
        - vim.absent

The usage of a clear top-level directory as well as properly named states
reduces the overall complexity and leads a user to both understand what will
be included at a glance and where it is located.

In addition :ref:`Formulas <conventions-formula>` should
be used as often as possible.

.. note::

    Formulas repositories on the saltstack-formulas GitHub organization should
    not be pointed to directly from systems that automatically fetch new
    updates such as GitFS or similar tooling. Instead formulas repositories
    should be forked on GitHub or cloned locally, where unintended, automatic
    changes will not take place.


Structuring Pillar Files
------------------------

:ref:`Pillars <pillar>` are used to store
secure and insecure data pertaining to minions. When designing the structure
of the ``/srv/pillar`` directory, the pillars contained within
should once again be focused on clear and concise data which users can easily
review, modify, and understand.

The ``/srv/pillar/`` directory is primarily controlled by ``top.sls``. It
should be noted that the pillar ``top.sls`` is not used as a location to
declare variables and their values. The ``top.sls`` is used as a way to
include other pillar files and organize the way they are matched based on
environments or grains.

An example ``top.sls`` may be as simple as the following:

/srv/pillar/top.sls:

.. code-block:: yaml

    base:
      '*':
        - packages

Any number of matchers can be added to the base environment. For example, here
is an expanded version of the Pillar top file stated above:

/srv/pillar/top.sls:

.. code-block:: yaml

    base:
      '*':
        - packages
      'web*':
        - apache
        - vim

Or an even more complicated example, using a variety of matchers in numerous
environments:

/srv/pillar/top.sls:

.. code-block:: yaml

    base:
      '*':
        - apache
    dev:
      'os:Debian':
        - match: grain
        - vim
    test:
      '* and not G@os: Debian':
        - match: compound
        - emacs

It is clear to see through these examples how the top file provides users with
power but when used incorrectly it can lead to confusing configurations. This
is why it is important to understand that the top file for pillar is not used
for variable definitions.

Each SLS file within the ``/srv/pillar/`` directory should correspond to the
states which it matches.

This would mean that the ``apache`` pillar file should contain data relevant to
Apache. Structuring files in this way once again ensures modularity, and
creates a consistent understanding throughout our Salt environment. Users can
expect that pillar variables found in an Apache state will live inside of an
Apache pillar:

``/srv/pillar/apache.sls``:

.. code-block:: yaml

    apache:
      lookup:
        name: httpd
        config:
          tmpl: /etc/httpd/httpd.conf

While this pillar file is simple, it shows how a pillar file explicitly
relates to the state it is associated with.


Variable Flexibility
--------------------

Salt allows users to define variables in SLS files. When creating a state
variables should provide users with as much flexibility as possible. This
means that variables should be clearly defined and easy to manipulate, and
that sane defaults should exist in the event a variable is not properly
defined. Looking at several examples shows how these different items can
lead to extensive flexibility.

Although it is possible to set variables locally, this is generally not
preferred:

``/srv/salt/apache/conf.sls``:

.. code-block:: jinja

    {% set name = 'httpd' %}
    {% set tmpl = 'salt://apache/files/httpd.conf' %}

    include:
      - apache

    apache_conf:
      file.managed:
        - name: {{ name }}
        - source: {{ tmpl }}
        - template: jinja
        - user: root
        - watch_in:
          - service: apache


When generating this information it can be easily transitioned to the pillar
where data can be overwritten, modified, and applied to multiple states, or
locations within a single state:

``/srv/pillar/apache.sls``:

.. code-block:: yaml

    apache:
      lookup:
        name: httpd
        config:
          tmpl: salt://apache/files/httpd.conf

``/srv/salt/apache/conf.sls``:

.. code-block:: jinja

    {% from "apache/map.jinja" import apache with context %}

    include:
      - apache

    apache_conf:
      file.managed:
        - name: {{ salt['pillar.get']('apache:lookup:name') }}
        - source: {{ salt['pillar.get']('apache:lookup:config:tmpl') }}
        - template: jinja
        - user: root
        - watch_in:
          - service: apache

This flexibility provides users with a centralized location to modify
variables, which is extremely important as an environment grows.

Modularity Within States
------------------------

Ensuring that states are modular is one of the key concepts to understand
within Salt. When creating a state a user must consider how many times the
state could be re-used, and what it relies on to operate. Below are several
examples which will iteratively explain how a user can go from a state which
is not very modular to one that is:

``/srv/salt/apache/init.sls``:

.. code-block:: yaml

    httpd:
      pkg:
        - installed
      service.running:
        - enable: True

    /etc/httpd/httpd.conf:
      file.managed:
        - source: salt://apache/files/httpd.conf
        - template: jinja
        - watch_in:
          - service: httpd

The example above is probably the worst-case scenario when writing a state.
There is a clear lack of focus by naming both the pkg/service, and managed
file directly as the state ID. This would lead to changing multiple requires
within this state, as well as others that may depend upon the state.

Imagine if a require was used for the ``httpd`` package in another state, and
then suddenly it's a custom package. Now changes need to be made in multiple
locations which increases the complexity and leads to a more error prone
configuration.

There is also the issue of having the configuration file located in the init,
as a user would be unable to simply install the service and use the default
conf file.

Our second revision begins to address the referencing by using ``- name``, as
opposed to direct ID references:

``/srv/salt/apache/init.sls``:

.. code-block:: yaml

    apache:
      pkg.installed:
        - name: httpd
      service.running:
        - name: httpd
        - enable: True

    apache_conf:
      file.managed:
        - name: /etc/httpd/httpd.conf
        - source: salt://apache/files/httpd.conf
        - template: jinja
        - watch_in:
          - service: apache

The above init file is better than our original, yet it has several issues
which lead to a lack of modularity. The first of these problems is the usage
of static values for items such as the name of the service, the name of the
managed file, and the source of the managed file. When these items are hard
coded they become difficult to modify and the opportunity to make mistakes
arises. It also leads to multiple edits that need to occur when changing
these items (imagine if there were dozens of these occurrences throughout the
state!). There is also still the concern of the configuration file data living
in the same state as the service and package.

In the next example steps will be taken to begin addressing these issues.
Starting with the addition of a map.jinja file (as noted in the
:ref:`Formula documentation <conventions-formula>`), and
modification of static values:

``/srv/salt/apache/map.jinja``:

.. code-block:: jinja

    {% set apache = salt['grains.filter_by']({
        'Debian': {
            'server': 'apache2',
            'service': 'apache2',
            'conf': '/etc/apache2/apache.conf',
        },
        'RedHat': {
            'server': 'httpd',
            'service': 'httpd',
            'conf': '/etc/httpd/httpd.conf',
        },
    }, merge=salt['pillar.get']('apache:lookup')) %}

/srv/pillar/apache.sls:

.. code-block:: yaml

    apache:
      lookup:
        config:
          tmpl: salt://apache/files/httpd.conf

``/srv/salt/apache/init.sls``:

.. code-block:: jinja

    {% from "apache/map.jinja" import apache with context %}

    apache:
      pkg.installed:
        - name: {{ apache.server }}
      service.running:
        - name: {{ apache.service }}
        - enable: True

    apache_conf:
      file.managed:
        - name: {{ apache.conf }}
        - source: {{ salt['pillar.get']('apache:lookup:config:tmpl') }}
        - template: jinja
        - user: root
        - watch_in:
          - service: apache

The changes to this state now allow us to easily identify the location of the
variables, as well as ensuring they are flexible and easy to modify.
While this takes another step in the right direction, it is not yet complete.
Suppose the user did not want to use the provided conf file, or even their own
configuration file, but the default apache conf. With the current state setup
this is not possible. To attain this level of modularity this state will need
to be broken into two states.

``/srv/salt/apache/map.jinja``:

.. code-block:: jinja

    {% set apache = salt['grains.filter_by']({
        'Debian': {
            'server': 'apache2',
            'service': 'apache2',
            'conf': '/etc/apache2/apache.conf',
        },
        'RedHat': {
            'server': 'httpd',
            'service': 'httpd',
            'conf': '/etc/httpd/httpd.conf',
        },
    }, merge=salt['pillar.get']('apache:lookup')) %}

``/srv/pillar/apache.sls``:

.. code-block:: yaml

    apache:
      lookup:
        config:
          tmpl: salt://apache/files/httpd.conf


``/srv/salt/apache/init.sls``:

.. code-block:: jinja

    {% from "apache/map.jinja" import apache with context %}

    apache:
      pkg.installed:
        - name: {{ apache.server }}
      service.running:
        - name: {{ apache.service }}
        - enable: True

``/srv/salt/apache/conf.sls``:

.. code-block:: jinja

    {% from "apache/map.jinja" import apache with context %}

    include:
      - apache

    apache_conf:
      file.managed:
        - name: {{ apache.conf }}
        - source: {{ salt['pillar.get']('apache:lookup:config:tmpl') }}
        - template: jinja
        - user: root
        - watch_in:
          - service: apache

This new structure now allows users to choose whether they only wish to
install the default Apache, or if they wish, overwrite the default package,
service, configuration file location, or the configuration file itself. In
addition to this the data has been broken between multiple files allowing for
users to identify where they need to change the associated data.


Storing Secure Data
-------------------

Secure data refers to any information that you would not wish to share with
anyone accessing a server. This could include data such as passwords,
keys, or other information.

As all data within a state is accessible by EVERY server that is connected
it is important to store secure data within pillar. This will ensure that only
those servers which require this secure data have access to it. In this
example a use can go from an insecure configuration to one which is only
accessible by the appropriate hosts:

``/srv/salt/mysql/testerdb.sls``:

.. code-block:: yaml

    testdb:
      mysql_database.present:
        - name: testerdb

``/srv/salt/mysql/user.sls``:

.. code-block:: yaml

    include:
      - mysql.testerdb

    testdb_user:
      mysql_user.present:
        - name: frank
        - password: "test3rdb"
        - host: localhost
        - require:
          - sls: mysql.testerdb

Many users would review this state and see that the password is there in plain
text, which is quite problematic. It results in several issues which may not
be immediately visible.

The first of these issues is clear to most users -- the password being visible
in this state. This  means that any minion will have a copy of this, and
therefore the password which is a major security concern as minions may not
be locked down as tightly as the master server.

The other issue that can be encountered is access by users on the master. If
everyone has access to the states (or their repository), then they are able to
review this password. Keeping your password data accessible by only a few
users is critical for both security and peace of mind.

There is also the issue of portability. When a state is configured this way
it results in multiple changes needing to be made. This was discussed in the
sections above but it is a critical idea to drive home. If states are not
portable it may result in more work later!

Fixing this issue is relatively simple, the content just needs to be moved to
the associated pillar:

``/srv/pillar/mysql.sls``:

.. code-block:: yaml

    mysql:
      lookup:
        name: testerdb
        password: test3rdb
        user: frank
        host: localhost

``/srv/salt/mysql/testerdb.sls``:

.. code-block:: jinja

    testdb:
      mysql_database.present:
        - name: {{ salt['pillar.get']('mysql:lookup:name') }}

``/srv/salt/mysql/user.sls``:

.. code-block:: jinja

    include:
      - mysql.testerdb

    testdb_user:
      mysql_user.present:
        - name: {{ salt['pillar.get']('mysql:lookup:user') }}
        - password: {{ salt['pillar.get']('mysql:lookup:password') }}
        - host: {{ salt['pillar.get']('mysql:lookup:host') }}
        - require:
          - sls: mysql.testerdb

Now that the database details have been moved to the associated pillar file,
only machines which are targeted via pillar will have access to these details.
Access to users who should not be able to review these details can also be
prevented while ensuring that they are still able to write states which take
advantage of this information.
