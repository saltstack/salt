.. _conventions-formula:

=============
Salt Formulas
=============

Formulas are pre-written Salt States. They are as open-ended as Salt States
themselves and can be used for tasks such as installing a package, configuring
and starting a service, setting up users or permissions, and many other common
tasks.

.. note:: Formulas require Salt 0.17 or later.

    More accurately, Formulas are not tested on earlier versions of Salt so
    your mileage may vary.

    All Formulas require the grains execution module that shipped with Salt
    0.16.4. Earlier Salt versions may copy :blob:`salt/modules/grains.py`
    into the :file:`/srv/salt/_modules` directory and it will be automatically
    distributed to all minions.

    Some Formula utilize features added in Salt 0.17 and will not work on
    earlier Salt versions.

All official Salt Formulas are found as separate Git repositories in the
"saltstack-formulas" organization on GitHub:

https://github.com/saltstack-formulas

As an example, quickly install and configure the popular memcached server using
sane defaults simply by including the :formula:`memcached-formula` repository
into an existing Salt States tree.

Installation
============

Each Salt Formula is an individual Git repository designed as a drop-in
addition to an existing Salt State tree. Formulas can be installed in the
following ways.

Adding a Formula as a GitFS remote
----------------------------------

One design goal of Salt's GitFS fileserver backend was to facilitate reusable
States so this is a quick and natural way to use Formulas.

.. seealso:: :ref:`Setting up GitFS <tutorial-gitfs>`

1.  Add one or more Formula repository URLs as remotes in the
    :conf_master:`gitfs_remotes` list in the Salt Master configuration file.
2.  Restart the Salt master.

Adding a Formula directory manually
-----------------------------------

Since Formulas are simply directories they can be copied onto the local file
system by using Git to clone the repository or by downloading and expanding a
tarball or zip file of the directory.

* Clone the repository manually and add a new entry to
  :conf_master:`file_roots` pointing to the clone's directory.

* Clone the repository manually and then copy or link the Formula directory
  into ``file_roots``.

Usage
=====

Each Formula is intended to be immediately usable with sane defaults without
any additional configuration. Many formulas are also configurable by including
data in Pillar Many formulas are also configurable by including data in Pillar;
see the :file:`pillar.example` file in each Formula repository for available
options.

Including a Formula in an existing State tree
---------------------------------------------

Formula may be included in an existing ``sls`` file. This is often useful when
a state you are writing needs to ``require`` or ``extend`` a state defined in
the formula.

Here is an example of a state that uses the :formula:`epel-formula` in a
``require`` declaration which directs Salt to not install the ``python26``
package until after the EPEL repository has also been installed:

.. code:: yaml

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

.. code:: yaml

    base:
      'myopenstackmaster':
        - openstack

Quickly deploying OpenStack across several dedicated machines could also be
done directly from a Top File and may look something like this:

.. code:: yaml

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

Modifying default Formula behavior
----------------------------------

Remember that Formula are regular Salt States and can be used with all Salt's
normal mechanisms for determining execution order. Formula can be required from
other States with ``require`` declarations, they can be modified using
``extend``, they can made to watch other states with ``watch_in``, they can be
used as templates for other States with ``use``. Don't be shy to read through
the source for each Formula!

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
    when it is ready. We will add you as a collaborator on the
    `saltstack-formulas`_ organization and help you transfer the repository
    over. Ping a SaltStack employee on IRC (``#salt`` on Freenode) or send an
    email to the Salt mailing list.

Repository structure
--------------------

A basic Formula repository should have the following layout::

    foo-formula
    |-- foo/
    |   |-- map.jinja
    |   |-- init.sls
    |   `-- bar.sls
    |-- LICENSE
    |-- pillar.example
    `-- README.rst

``README.rst``
--------------

The README should detail each available ``.sls`` file by explaining what it
does, whether it has any dependencies on other formulas, whether it has a
target platform, and any other installation or usage instructions or tips.

A sample skeleton for the ``README.rst`` file:

.. code:: rest

    foo
    ===

    Install and configure the FOO service.

    .. note::

        See the full `Salt Formulas installation and usage instructions
        <http://docs.saltstack.com/topics/conventions/formulas.html>`_.

    Available states
    ----------------

    ``foo``
        Install the ``foo`` package and enable the service.
    ``foo.bar``
        Install the ``bar`` package.

``map.jinja``
-------------

It is useful to have a single source for platform-specific or other
parameterized information that can be reused throughout a Formula. See
":ref:`conventions-formula-parameterization`" below for more information. Such
a file should be named :file:`map.jinja` and live alongside the state
files.

The following is an example from the MySQL Formula.

:file:`map.jinja`:

.. code:: jinja

    {% set mysql = salt['grains.filter_by']({
        'Debian': {
            'server': 'mysql-server',
            'client': 'mysql-client',
            'service': 'mysql',
            'config': '/etc/mysql/my.cnf',
        },
        'RedHat': {
            'server': 'mysql-server',
            'client': 'mysql',
            'service': 'mysqld',
            'config': '/etc/my.cnf',
        },
        'Gentoo': {
            'server': 'dev-db/mysql',
            'mysql-client': 'dev-db/mysql',
            'service': 'mysql',
            'config': '/etc/mysql/my.cnf',
        },
    }, merge=salt['pillar.get']('mysql:lookup')) %}

Any of the values defined above can be fetched for the current platform in any
state file using the following syntax:

.. code:: yaml

    {% from "mysql/map.jinja" import mysql with context %}

    mysql-server:
      pkg:
        - installed
        - name: {{ mysql.server }}
      service:
        - running
        - name: {{ mysql.service }}
        - require:
          - pkg: mysql-server

    mysql-config:
      file:
        - managed
        - name: {{ mysql.config }}
        - source: salt://mysql/conf/my.cnf
        - watch:
          - service: mysql-server

SLS files
---------

Each state in a Formula should use sane defaults (as much as is possible) and
use Pillar to allow for customization.

The root state, in particular, and most states in general, should strive to do
no more than the basic expected thing and advanced configuration should be put
in child states build on top of the basic states.

For example, the root Apache should only install the Apache httpd server and
make sure the httpd service is running. It can then be used by more advanced
states::

    # apache/init.sls
    httpd:
      pkg:
        - installed
      service:
        - running

    # apache/mod_wsgi.sls
    include:
      - apache

    mod_wsgi:
      pkg:
        - installed
        - require:
          - pkg: apache

    # apache/debian/vhost_setup.sls
    {% if grains['os_family'] == 'Debian' %}
    a2dissite 000-default:
      cmd.run:
        - onlyif: test -L /etc/apache2/sites-enabled/000-default
        - require:
          - pkg: apache
    {% endif %}

Platform agnostic
`````````````````

Each Salt Formula must be able to be run without error on any platform. If the
formula is not applicable to a platform it should do nothing. See the
:formula:`epel-formula` for an example.

Any platform-specific states must be wrapped in conditional statements:

.. code:: jinja

    {% if grains['os_family'] == 'Debian' %}
    ...
    {% endif %}

A handy method for using platform-specific values is to create a lookup table
using the :py:func:`~salt.modules.grains.filter_by` function:

.. code:: jinja

    {% set apache = salt['grains.filter_by']({
        'Debian': {'conf': '/etc/apache2/conf.d'},
        'RedHat': {'conf': '/etc/httpd/conf.d'},
    }) %}

    myconf:
      file:
        - managed
        - name: {{ apache.conf }}/myconf.conf

.. _conventions-formula-parameterization:

Configuration and parameterization
----------------------------------

Each Formula should strive for sane defaults that can then be customized using
Pillar. Pillar lookups must use the safe :py:func:`~salt.modules.pillar.get`
and must provide a default value:

.. code:: jinja

    {% if salt['pillar.get']('horizon:use_ssl', False) %}
    ssl_crt: {{ salt['pillar.get']('horizon:ssl_crt', '/etc/ssl/certs/horizon.crt') }}
    ssl_key: {{ salt['pillar.get']('horizon:ssl_key', '/etc/ssl/certs/horizon.key') }}
    {% endif %}

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

.. code:: jinja

    {% if '/storage' in salt['mount.active']() %}
    /usr/local/etc/myfile.conf:
      file:
        - symlink
        - target: /storage/myfile.conf
    {% endif %}

Jinja macros are generally discouraged in favor of adding functions to existing
Salt modules or adding new modules. An example of this is the
:py:func:`~salt.modules.grains.filter_by` function.

Versioning
----------

Formula versions are tracked using Git tags.

Testing Formulas
----------------

Salt Formulas are tested by running each ``.sls`` file via :py:func:`state.sls
<salt.modules.state.sls>` and checking the output for success or failure. This
is done for each supported platform.

.. ............................................................................

.. _`saltstack-formulas`: https://github.com/saltstack-formulas
