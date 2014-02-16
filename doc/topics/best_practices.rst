===================
Salt Best Practices
===================

Salt's extreme flexibility leads to many questions concerning how states,
pillars, and other portions of Salt should be structured and laid out. This
document attempts to clarify these points through the usage of examples and
existing code which will empower users to know they are making a decision
which will ensure extensibility throughout the life cycle of an infrastructure.


Structuring States and Formulas
-------------------------------

When structuring Salt States and Formulas it is important to begin with the
directory structure. A proper directory structure clearly defines the
functionality of each state to the user via visual inspection of the state's
name. Reviewing the `MySQL Salt formula
<https://github.com/saltstack-formulas/mysql-formula>`_ it is clear to see
the benefits to the end user when reviewing a sample of the available states:

.. code-block:: bash

    /srv/salt/mysql/files/
    /srv/salt/mysql/client.sls
    /srv/salt/mysql/map.jinja
    /srv/salt/mysql/python.sls
    /srv/salt/mysql/server.sls

This directory structure would lead to these states being referenced in a top
file in the following way:

.. code-block:: bash

    base:
      'web*':
        - mysql.client
        - mysql.python
      'db*':
        - mysql.server

This clear definition ensures that the user is properly informed of what each
state will do.

Reviewing another example such as the `vim formula 
<https://github.com/saltstack-formulas/vim-formula>`_:

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

.. code-block:: bash

    base:
      'web*':
        - vim
        - vim.nerdtree
        - vim.pyflakes
        - vim.salt
      'db*':
        - vim.absent

The usage of a clear top level directory, as well as properly named states
reduces the overall complexity, and leads a user to both understand what will be
included at a glance, and where it is located.

In addition
`Formulas <http://docs.saltstack.com/topics/conventions/formulas.html>`_ should
be used as often as possible.


Structuring Pillar Files
-----------------------

Pillars (link) are used to store both secure, and insecure data pertaining to
minions. When designing the structure of the ``/srv/pillar`` directory, and
the pillars contained within there should once again be a focus on clear and
concise data which users can easily review, modify, and understand. Once again
examples will be used which highlight a transition from a lack of modularity,
to a design which exhibits ease of use and clarity.

The /srv/pillar/ directory is primarily controlled by the top.sls. It should
be noted that the pillar top.sls is not used as a location to declare variables
and their values. The top.sls is used as a way to include other pillar files
and organize the way they are matched based on enviroments or grains.

An example top.sls may be as simple as the following:

/srv/pillar/top.sls:

.. code-block:: yaml

    base:
      '*':
        - packages

Or much more complicated, using a variety of matchers:

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
      'and not G@os: Debian':
        - match: compound
        - emacs

It's simple to see through these examples how the top file provides users with
power, but when used incorrectly it can lead to confusing configurations. This
is why it is important to understand that the top file for pillar is not used
for variable definitions.

Each sls file within the /srv/pillar/ directory should correspond to the
states which it matches. This would mean that the apache pillar file should
contain data relevant to apache. Structuring our files in this way once again
ensures modularity, and creates a consistant understanding throughout our Salt
environment. Users can expect that pillar variables found in an apache state
will live inside of an apache pillar:

/srv/salt/pillar/apache.sls

.. code-block:: yaml

    apache:
      lookup:
        name: httpd
        config:
          tmpl: 
      


Variable Flexibility
--------------------

Salt allows users to define variables in several locations, within the states
themselves, inside of pillars, as well as map files. When creating a state
variables should provide users with as much flexibility as possible. This means
that variables should be clearly defined and easy to manipulate, and that sane
defaults should exist in the event a variable is not properly defined. Looking
at several examples shows how these different items can lead to extensive
flexibility.

Transitioning variables from states to pillars: 

.. code-block:: yaml

    {% set myvar = 'myvalue' %}
    {% set myothervar = 'myothervalue' %}

    

    
When generating this information it can be easily transitioned to the pillar
where data can be overwritten, 

.. code-block:: yaml

    - source: {{ salt['pillar.get']('apache:lookup:name')     
 
Modularity Within States
------------------------

Ensuring that states are modular is one of the key concepts to understand
within Salt. When creating a state a user must consider how many times the
state could be re-used, and what it relies on to operate. Below are several
examples which will iteratively explain how a user can go from a state which
is not very modular, to one that is:

apache/init.sls:

.. code-block:: yaml

    httpd:
      pkg:
        - installed
      service:
        - running
        - enable: True

    /etc/httpd/httpd.conf:
      file:
        - managed
        - source: salt://apache/files/httpd.conf
        - template: jinja
        - watch_in:
          - service: httpd

The example above is probably the worst case scenario when writing a state.
There is a clear lack of focus by naming both the pkg/service, and managed file
directly as the state ID. This would lead to changing multiple requires within
this state, as well as others that may depend upon the state. Imagine if a
require was used for the httpd package in another state, and then suddenly
it's a custom package. Now changes need to be made in multiple locations which
increases the complexity, and leads to a more error prone configuration.

apache/init.sls:

.. code-block:: yaml

    apache:
      pkg:
        - installed
        - name: httpd
      service:
        - name: httpd
        - enable: True
        - running

    apache_conf:
      file: 
        - managed
        - name: /etc/httpd/httpd.conf
        - source: salt://apache/files/httpd.conf
        - template: jinja
        - watch_in:
          - service: apache

The above init file has several issues which lead to a lack of modularity. The
first of these problems is the usage of static values for items such as the
name of the service, the name of the managed file, and the source of the
managed file. When these items are hard coded they become difficult to modify
and the opportunity to make mistakes arises. It also leads to multiple edits
that need to occur when changing these items (imagine if there were dozens of
these occurrences throughout the state!).

In the next example steps will be taken to begin addressing this state file,
starting with the addition of a map.jinja (as noted in the Formula
documentationt [link here]), and modification of static values:

apache/map.jinja:

.. code-block:: yaml

apache/init.sls:

.. code-block:: yaml

    {% from "apache/map.jinja" import apache with context %}

    apache:
      pkg:
        - installed
        - name: {{ apache.server }}
      service:
        - name: {{ apache.service }}
        - enable: True
        - running

    apache_conf:
      file
        - managed
        - name {{ apache.conf }}
        - source: {{ salt['pillar.get']('apache:lookup:config:tmpl') }}
        - template: jinja
        - user: root
        - watch_in:
          - service: apache

The changes to this state now allow us to easily identify the location of the
variables, as well as ensuring they are flexible and easy to modify. There are
also defaults in place should the user choose to not use the modified conf.
While this takes another step in the right direction, it is not yet complete.
Supposed the user didn't want to use the provided conf file, or even their own
configuration file, but the default apache file. With the current state setup
this is not possible. To attain this level of modularity this state will need
to be broken into two states.

apache/init.sls:

.. code-block:: yaml

    {% from "apache/map.jinja" import apache with context %}

    apache:
      pkg:
        - installed
        - name: {{ apache.server }}
      service:
        - name: {{ apache.service }}
        - enable: True
        - running

apache/conf.sls:

.. code-block:: yaml

    {% from "apache/map.jinja" import apache with context %}

    include:
      apache

    apache_conf:
      file
        - managed
        - name {{ apache.conf }}
        - source: {{ salt['pillar.get']('apache:lookup:config:tmpl') }}
        - template: jinja
        - user: root
        - watch_in:
          - service: apache

This new structure now allows users to choose whether they only wish to install
the default Apache, or if they wish, overwrite the default package, service,
configuration file location, or the configuration file itself. In addition to
this the data has been broken between multiple files allowing for users to
identify where they need to change the associated data.


Storing Secure Data
-------------------

Secure data refers to any information that you would not wish to share with
anyone accessing a server. This could include data such as passwords,
usernames, keys, or other information.

As all data within a state is accesible by EVERY server within an environment,
it is important to store secure data within pillar. This will ensure that only
those servers which require this secure data have access to it. In this
example a use can go from very insecure data to data which is only accessible
by the appropriate hosts:

mysql/user.sls:

.. code-block:: yaml

    testdb:
      mysql_database:
        - present:
        - name: testerdb

    testdb_user:
      mysql_user:
        - present
        - name: frank
        - password: "test3rdb"
        - host: localhost
        - require:
          - mysql_database: testdb

Many users would review this state and see that the password is there in plain
text, which is quite problematic. It results in several issues which may not be
immediately visible. 

The first of these issues is clear to most users, the password being visible
in this state. This  means that any minion will have a copy of this, and
therefore the password which is a major security concern as minions may not
be locked downas tightly as the master server.

The other issue that can be encountered is access by users ON the master. If
everyone has access to the states (or their repository), then they are able to
review this password. Keeping your password data accessible by only a few
users is critical for both security, and peace of mind.

There is also the issue of portability. When a state is configured this way,
it results in multiple changes needing to be made. This was discussed in the
sections above, but it is a critical idea to drive home. If states are not
portable it may result in more work later!
