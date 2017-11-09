:orphan:

====================================
Salt Release Notes - Codename Oxygen
====================================

Comparison Operators in Package Installation
--------------------------------------------

Salt now supports using comparison operators (e.g. ``>=1.2.3``) when installing
packages on minions which use :mod:`yum/dnf <salt.modules.yumpkg>` or
:mod:`apt <salt.modules.aptpkg>`. This is supported both in the
:py:func:`pkg.installed <salt.states.pkg.installed>` state and in the ``pkg.install``
remote execution function.

:ref:`Master Tops <master-tops-system>` Changes
-----------------------------------------------

When both :ref:`Master Tops <master-tops-system>` and a
:ref:`Top File <states-top>` produce SLS matches for a given minion, the matches
were being merged in an unpredictable manner which did not preserve ordering. This has
been changed. The top file matches now execute in the expected order, followed
by any master tops matches that are not matched via a top file.

To make master tops matches execute first, followed by top file matches, set
the new :conf_minion:`master_tops_first` minion config option to ``True``.

LDAP via External Authentication Changes
----------------------------------------
In this release of Salt, if LDAP Bind Credentials are supplied, then
these credentials will be used for all LDAP access except the first
authentication when a job is submitted.  The first authentication will
use the user's credentials as passed on the CLI.  This behavior is to
accommodate certain two-factor authentication schemes where the authentication
token can only be used once.

In previous releases the bind credentials would only be used to determine
the LDAP user's existence and group membership.  The user's LDAP credentials
were used from then on.

Stormpath External Authentication Removed
-----------------------------------------

Per Stormpath's announcement, their API will be shutting down on 8/17/2017 at
noon PST so the Stormpath external authentication module has been removed.

https://stormpath.com/oktaplusstormpath

New Grains
----------

New core grains have been added to expose any storage inititator setting.

The new grains added are:

* ``fc_wwn``: Show all fibre channel world wide port names for a host
* ``iscsi_iqn``: Show the iSCSI IQN name for a host
* ``swap_total``: Show the configured swap_total for Linux, *BSD, OS X and Solaris/SunOS

Grains Changes
--------------

* The ``virtual`` grain identifies reports KVM and VMM hypervisors when running
  an OpenBSD guest

New Modules
-----------

- :mod:`salt.modules.purefa <salt.modules.purefa>`

New NaCl Renderer
-----------------

A new renderer has been added for encrypted data.

New support for Cisco UCS Chassis
---------------------------------

The salt proxy minion now allows for control of Cisco USC chassis. See
the ``cimc`` modules for details.

New salt-ssh roster
-------------------

A new roster has been added that allows users to pull in a list of hosts
for salt-ssh targeting from a ``~/.ssh`` configuration. For full details,
please see the ``sshconfig`` roster.

New GitFS Features
------------------

Two new features which affect how GitFS maps branches/tags to fileserver
environments (i.e. ``saltenvs``) have been added:

1. It is now possible to completely turn off Salt's default mapping logic
   (aside from the mapping of the ``base`` saltenv). This can be triggered
   using the new :conf_master:`gitfs_disable_saltenv_mapping` config option.

   .. note::
       When this is disabled, only the ``base`` saltenv and any configured
       using :ref:`per-saltenv configuration parameters
       <gitfs-per-saltenv-config>` will be available.

2. The types of refs which Salt will use as saltenvs can now be controlled. In
   previous releases, branches and tags were both mapped as environments, and
   individual commit SHAs could be specified as saltenvs in states (and when
   caching files using :py:func:`cp.cache_file <salt.modules.cp.cache_file>`).
   Using the new :conf_master:`gitfs_ref_types` config option, the types of
   refs which are used as saltenvs can be restricted. This makes it possible to
   ignore all tags and use branches only, and also to keep SHAs from being made
   available as saltenvs.

Additional output modes
------------------

The ``state_output`` parameter now supports ``full_id``, ``changes_id`` and ``terse_id``.
Just like ``mixed_id``, these use the state ID as name in the highstate output.
For more information on these output modes, see the docs for the :mod:`Highstate Outputter <salt.output.highstate>`.

Windows Installer: Changes to existing config handling
------------------------------------------------------
Behavior with existing configuration has changed. With previous installers the
existing config was used and the master and minion id could be modified via the
installer. It was problematic in that it didn't account for configuration that
may be defined in the ``minion.d`` directory. This change gives you the option
via a checkbox to either use the existing config with out changes or the default
config using values you pass to the installer. If you choose to use the existing
config then no changes are made. If not, the existing config is deleted, to
include the ``minion.d`` directory, and the default config is used. A
command-line switch (``/use-existing-config``) has also been added to control
this behavior.

Windows Installer: Multi-master configuration
---------------------------------------------
The installer now has the ability to apply a multi-master configuration either
from the gui or the command line. The ``master`` field in the gui can accept
either a single master or a comma-separated list of masters. The command-line
switch (``/master=``) can accept the same.

Windows Installer: Command-line help
------------------------------------
The Windows installer will now display command-line help when a help switch
(``/?``) is passed.

Salt Cloud Features
-------------------

Pre-Flight Commands
===================

Support has been added for specified "preflight commands" to run on a VM before
the deploy script is run. These must be defined as a list in a cloud configuration
file. For example:

.. code-block:: yaml

       my-cloud-profile:
         provider: linode-config
         image: Ubuntu 16.04 LTS
         size: Linode 2048
         preflight_cmds:
           - whoami
           - echo 'hello world!'

These commands will run in sequence **before** the bootstrap script is executed.

New salt-cloud Grains
=====================

When salt cloud creates a new minon, it will now add grain information
to the minion configuration file, identifying the resources originally used
to create it.

The generated grain information will appear similar to:

.. code-block:: yaml

    grains:
      salt-cloud:
        driver: ec2
        provider: my_ec2:ec2
        profile: ec2-web

The generation of salt-cloud grains can be surpressed by the
option ``enable_cloud_grains: 'False'`` in the cloud configuration file.

Upgraded Saltify Driver
=======================

The salt-cloud Saltify driver is used to provision machines which
are not controlled by a dedicated cloud supervisor (such as typical hardware
machines) by pushing a salt-bootstrap command to them and accepting them on
the salt master. Creation of a node has been its only function and no other
salt-cloud commands were implemented.

With this upgrade, it can use the salt-api to provide advanced control,
such as rebooting a machine, querying it along with conventional cloud minions,
and, ultimately, disconnecting it from its master.

After disconnection from ("destroying" on) one master, a machine can be
re-purposed by connecting to ("creating" on) a subsequent master.

New Vagrant Driver
==================

The salt-cloud Vagrant driver brings virtual machines running in a limited
environment, such as a programmer's workstation, under salt-cloud control.
This can be useful for experimentation, instruction, or testing salt configurations.

Using salt-api on the master, and a salt-minion running on the host computer,
the Vagrant driver can create (``vagrant up``), restart (``vagrant reload``),
and destroy (``vagrant destroy``) VMs, as controlled by salt-cloud profiles
which designate a ``Vagrantfile`` on the host machine.

The master can be a very limited machine, such as a Raspberry Pi, or a small
VagrantBox VM.


New pillar/master_tops module called saltclass
----------------------------------------------

This module clones the behaviour of reclass (http://reclass.pantsfullofunix.net/), without the need of an external app, and add several features to improve flexibility.
Saltclass lets you define your nodes from simple ``yaml`` files (``.yml``) through hierarchical class inheritance with the possibility to override pillars down the tree.

**Features**

- Define your nodes through hierarchical class inheritance
- Reuse your reclass datas with minimal modifications
    - applications => states
    - parameters => pillars
- Use Jinja templating in your yaml definitions
- Access to the following Salt objects in Jinja
    - ``__opts__``
    - ``__salt__``
    - ``__grains__``
    - ``__pillars__``
    - ``minion_id``
- Chose how to merge or override your lists using ^ character (see examples)
- Expand variables ${} with possibility to escape them if needed \${} (see examples)
- Ignores missing node/class and will simply return empty without breaking the pillar module completely - will be logged

An example subset of datas is available here: http://git.mauras.ch/salt/saltclass/src/master/examples

==========================  ===========
Terms usable in yaml files  Description
==========================  ===========
classes                     A list of classes that will be processed in order
states                      A list of states that will be returned by master_tops function
pillars                     A yaml dictionnary that will be returned by the ext_pillar function
environment                 Node saltenv that will be used by master_tops
==========================  ===========

A class consists of:

- zero or more parent classes
- zero or more states
- any number of pillars

A child class can override pillars from a parent class.
A node definition is a class in itself with an added ``environment`` parameter for ``saltenv`` definition.

**class names**

Class names mimic salt way of defining states and pillar files.
This means that ``default.users`` class name will correspond to one of these:

- ``<saltclass_path>/classes/default/users.yml``
- ``<saltclass_path>/classes/default/users/init.yml``

**Saltclass tree**

A saltclass tree would look like this:

.. code-block:: text

    <saltclass_path>
    ├── classes
    │   ├── app
    │   │   ├── borgbackup.yml
    │   │   └── ssh
    │   │       └── server.yml
    │   ├── default
    │   │   ├── init.yml
    │   │   ├── motd.yml
    │   │   └── users.yml
    │   ├── roles
    │   │   ├── app.yml
    │   │   └── nginx
    │   │       ├── init.yml
    │   │       └── server.yml
    │   └── subsidiaries
    │       ├── gnv.yml
    │       ├── qls.yml
    │       └── zrh.yml
    └── nodes
        ├── geneva
        │   └── gnv.node1.yml
        ├── lausanne
        │   ├── qls.node1.yml
        │   └── qls.node2.yml
        ├── node127.yml
        └── zurich
            ├── zrh.node1.yml
            ├── zrh.node2.yml
            └── zrh.node3.yml

**Examples**

``<saltclass_path>/nodes/lausanne/qls.node1.yml``

.. code-block:: yaml

    environment: base

    classes:
    {% for class in ['default'] %}
      - {{ class }}
    {% endfor %}
      - subsidiaries.{{ __grains__['id'].split('.')[0] }}

``<saltclass_path>/classes/default/init.yml``

.. code-block:: yaml

    classes:
      - default.users
      - default.motd

    states:
      - openssh

    pillars:
      default:
        network:
          dns:
            srv1: 192.168.0.1
            srv2: 192.168.0.2
            domain: example.com
        ntp:
          srv1: 192.168.10.10
          srv2: 192.168.10.20

``<saltclass_path>/classes/subsidiaries/gnv.yml``

.. code-block:: yaml

    pillars:
      default:
        network:
          sub: Geneva
          dns:
            srv1: 10.20.0.1
            srv2: 10.20.0.2
            srv3: 192.168.1.1
            domain: gnv.example.com
        users:
          adm1:
            uid: 1210
            gid: 1210
            gecos: 'Super user admin1'
            homedir: /srv/app/adm1
          adm3:
            uid: 1203
            gid: 1203
            gecos: 'Super user adm

Variable expansions:

Escaped variables are rendered as is - ``${test}``

Missing variables are rendered as is - ``${net:dns:srv2}``

.. code-block:: yaml

    pillars:
      app:
      config:
        dns:
          srv1: ${default:network:dns:srv1}
          srv2: ${net:dns:srv2}
        uri: https://application.domain/call?\${test}
        prod_parameters:
          - p1
          - p2
          - p3
      pkg:
        - app-core
        - app-backend

List override:

Not using ``^`` as the first entry will simply merge the lists

.. code-block:: yaml

    pillars:
      app:
        pkg:
          - ^
          - app-frontend


**Known limitation**

Currently you can't have both a variable and an escaped variable in the same string as the escaped one will not be correctly rendered - '\${xx}' will stay as is instead of being rendered as '${xx}'

Newer PyWinRM Versions
----------------------

Versions of ``pywinrm>=0.2.1`` are finally able to disable validation of self
signed certificates.  :ref:`Here<new-pywinrm>` for more information.

DigitalOcean
------------

The DigitalOcean driver has been renamed to conform to the companies name.  The
new driver name is ``digitalocean``.  The old name ``digital_ocean`` and a
short one ``do`` will still be supported through virtual aliases, this is mostly
cosmetic.

Solaris Logical Domains In Virtual Grain
----------------------------------------

Support has been added to the ``virtual`` grain for detecting Solaris LDOMs
running on T-Series SPARC hardware.  The ``virtual_subtype`` grain is
populated as a list of domain roles.

Lists of comments in state returns
----------------------------------

State functions can now return a list of strings for the ``comment`` field,
as opposed to only a single string.
This is meant to ease writing states with multiple or multi-part comments.

Beacon configuration changes
----------------------------

In order to remain consistent and to align with other Salt components such as states,
support for configuring beacons using dictionary based configuration has been deprecated
in favor of list based configuration.  All beacons have a validation function which will
check the configuration for the correct format and only load if the validation passes.

- ``avahi_announce`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          avahi_announce:
            run_once: True
            servicetype: _demo._tcp
            port: 1234
            txt:
              ProdName: grains.productname
              SerialNo: grains.serialnumber
              Comments: 'this is a test'

    New behavior:

    .. code-block:: yaml

        beacons:
          avahi_announce:
            - run_once: True
            - servicetype: _demo._tcp
            - port: 1234
            - txt:
                ProdName: grains.productname
                SerialNo: grains.serialnumber
                Comments: 'this is a test'

 - ``bonjour_announce`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          bonjour_announce:
            run_once: True
            servicetype: _demo._tcp
            port: 1234
            txt:
              ProdName: grains.productname
              SerialNo: grains.serialnumber
              Comments: 'this is a test'

    New behavior:

    .. code-block:: yaml

        beacons:
          bonjour_announce:
            - run_once: True
            - servicetype: _demo._tcp
            - port: 1234
            - txt:
                ProdName: grains.productname
                SerialNo: grains.serialnumber
                Comments: 'this is a test'

- ``btmp`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          btmp: {}

    New behavior:

    .. code-block:: yaml

        beacons:
          btmp: []

- ``glxinfo`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          glxinfo:
            user: frank
            screen_event: True

    New behavior:

    .. code-block:: yaml

        beacons:
          glxinfo:
            - user: frank
            - screen_event: True

- ``haproxy`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
            haproxy:
                - www-backend:
                    threshold: 45
                    servers:
                        - web1
                        - web2
                - interval: 120

    New behavior:

    .. code-block:: yaml

        beacons:
          haproxy:
            - backends:
                www-backend:
                  threshold: 45
                  servers:
                    - web1
                    - web2
            - interval: 120

- ``inotify`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          inotify:
            /path/to/file/or/dir:
                mask:
                  - open
                  - create
                  - close_write
                recurse: True
                auto_add: True
                exclude:
                  - /path/to/file/or/dir/exclude1
                  - /path/to/file/or/dir/exclude2
                  - /path/to/file/or/dir/regex[a-m]*$:
                regex: True
            coalesce: True

    New behavior:

    .. code-block:: yaml

        beacons:
          inotify:
            - files:
                /path/to/file/or/dir:
                  mask:
                    - open
                    - create
                    - close_write
                  recurse: True
                  auto_add: True
                  exclude:
                    - /path/to/file/or/dir/exclude1
                    - /path/to/file/or/dir/exclude2
                    - /path/to/file/or/dir/regex[a-m]*$:
                  regex: True
            - coalesce: True

- ``journald`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          journald:
            sshd:
              SYSLOG_IDENTIFIER: sshd
              PRIORITY: 6

    New behavior:

    .. code-block:: yaml

        beacons:
          journald:
            - services:
                sshd:
                  SYSLOG_IDENTIFIER: sshd
                  PRIORITY: 6

- ``load`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          load:
            1m:
              - 0.0
              - 2.0
            5m:
              - 0.0
              - 1.5
            15m:
              - 0.1
              - 1.0
            emitatstartup: True
            onchangeonly: False

    New behavior:

    .. code-block:: yaml

        beacons:
          load:
            - averages:
                1m:
                  - 0.0
                  - 2.0
                5m:
                  - 0.0
                  - 1.5
                15m:
                  - 0.1
                  - 1.0
            - emitatstartup: True
            - onchangeonly: False

- ``log`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
            log:
              file: <path>
              <tag>:
                regex: <pattern>

    New behavior:

    .. code-block:: yaml

        beacons:
            log:
              - file: <path>
              - tags:
                  <tag>:
                    regex: <pattern>

- ``network_info`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          network_info:
            - eth0:
                type: equal
                bytes_sent: 100000
                bytes_recv: 100000
                packets_sent: 100000
                packets_recv: 100000
                errin: 100
                errout: 100
                dropin: 100
                dropout: 100

    New behavior:

    .. code-block:: yaml

        beacons:
          network_info:
            - interfaces:
                eth0:
                  type: equal
                  bytes_sent: 100000
                  bytes_recv: 100000
                  packets_sent: 100000
                  packets_recv: 100000
                  errin: 100
                  errout: 100
                  dropin: 100
                  dropout: 100

- ``network_settings`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          network_settings:
            eth0:
              ipaddr:
              promiscuity:
                onvalue: 1
            eth1:
              linkmode:

    New behavior:

    .. code-block:: yaml

        beacons:
          network_settings:
            - interfaces:
                - eth0:
                    ipaddr:
                    promiscuity:
                      onvalue: 1
                - eth1:
                    linkmode:

- ``proxy_example`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          proxy_example:
            endpoint: beacon
        ```

    New behavior:
        ```
        beacons:
          proxy_example:
            - endpoint: beacon

- ``ps`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          ps:
            - salt-master: running
            - mysql: stopped

    New behavior:

    .. code-block:: yaml

        beacons:
          ps:
            - processes:
                salt-master: running
                mysql: stopped

- ``salt_proxy`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          salt_proxy:
            - p8000: {}
            - p8001: {}

    New behavior:

    .. code-block:: yaml

        beacons:
          salt_proxy:
            - proxies:
                p8000: {}
                p8001: {}

- ``sensehat`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          sensehat:
            humidity: 70%
            temperature: [20, 40]
            temperature_from_pressure: 40
            pressure: 1500

    New behavior:

    .. code-block:: yaml

        beacons:
          sensehat:
            - sensors:
                humidity: 70%
                temperature: [20, 40]
                temperature_from_pressure: 40
                pressure: 1500

- ``service`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          service:
            salt-master:
            mysql:

    New behavior:

    .. code-block:: yaml

        beacons:
          service:
            - services:
                nginx:
                    onchangeonly: True
                    delay: 30
                    uncleanshutdown: /run/nginx.pid

- ``sh`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          sh: {}

    New behavior:

    .. code-block:: yaml

        beacons:
          sh: []

- ``status`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          status: {}

    New behavior:

    .. code-block:: yaml

        beacons:
          status: []

- ``telegram_bot_msg`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          telegram_bot_msg:
            token: "<bot access token>"
            accept_from:
              - "<valid username>"
            interval: 10

    New behavior:

    .. code-block:: yaml

        beacons:
          telegram_bot_msg:
            - token: "<bot access token>"
            - accept_from:
              - "<valid username>"
            - interval: 10

- ``twilio_txt_msg`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          twilio_txt_msg:
            account_sid: "<account sid>"
            auth_token: "<auth token>"
            twilio_number: "+15555555555"
            interval: 10

    New behavior:

    .. code-block:: yaml

        beacons:
          twilio_txt_msg:
            - account_sid: "<account sid>"
            - auth_token: "<auth token>"
            - twilio_number: "+15555555555"
            - interval: 10

- ``wtmp`` beacon

    Old behavior:

    .. code-block:: yaml

        beacons:
          wtmp: {}

    New behavior:

    .. code-block:: yaml

        beacons:
          wtmp: []

Deprecations
------------

Configuration Option Deprecations
=================================

- The ``requests_lib`` configuration option has been removed. Please use
  ``backend`` instead.

Profitbricks Cloud Updated Dependency
=====================================

The minimum version of the ``profitbrick`` python package for the ``profitbricks``
cloud driver has changed from 3.0.0 to 3.1.0.

Azure Cloud Updated Dependency
------------------------------

The azure sdk used for the ``azurearm`` cloud driver now depends on ``azure-cli>=2.0.12``

Module Deprecations
===================

The ``blockdev`` execution module has been removed. Its functions were merged
with the ``disk`` module. Please use the ``disk`` execution module instead.

The ``lxc`` execution module had the following changes:

- The ``dnsservers`` option to the ``cloud_init_interface`` function no longer
  defaults to ``4.4.4.4`` and ``8.8.8.8``.
- The ``dns_via_dhcp`` option to the ``cloud_init_interface`` function defaults
  to ``True`` now instead of ``False``.

The ``win_psget`` module had the following changes:

- The ``psversion`` function was removed. Please use ``cmd.shell_info`` instead.

The ``win_service`` module had the following changes:

- The ``config`` function was removed. Please use the ``modify`` function
  instead.
- The ``binpath`` option was removed from the ``create`` function. Please use
  ``bin_path`` instead.
- The ``depend`` option was removed from the ``create`` function. Please use
  ``dependencies`` instead.
- The ``DisplayName`` option was removed from the ``create`` function. Please
  use ``display_name`` instead.
- The ``error`` option was removed from the ``create`` function. Please use
  ``error_control`` instead.
- The ``group`` option was removed from the ``create`` function. Please use
  ``load_order_group`` instead.
- The ``obj`` option was removed from the ``create`` function. Please use
  ``account_name`` instead.
- The ``password`` option was removed from the ``create`` function. Please use
  ``account_password`` instead.
- The ``start`` option was removed from the ``create`` function. Please use
  ``start_type`` instead.
- The ``type`` option was removed from the ``create`` function. Please use
  ``service_type`` instead.

Runner Deprecations
===================

The ``manage`` runner had the following changes:

- The ``root_user`` kwarg was removed from the ``bootstrap`` function. Please
  use ``salt-ssh`` roster entries for the host instead.

State Deprecations
==================

The ``archive`` state had the following changes:

- The ``tar_options`` and the ``zip_options`` options were removed from the
  ``extracted`` function. Please use ``options`` instead.

The ``cmd`` state had the following changes:

- The ``user`` and ``group`` options were removed from the ``run`` function.
  Please use ``runas`` instead.
- The ``user`` and ``group`` options were removed from the ``script`` function.
  Please use ``runas`` instead.
- The ``user`` and ``group`` options were removed from the ``wait`` function.
  Please use ``runas`` instead.
- The ``user`` and ``group`` options were removed from the ``wait_script``
  function. Please use ``runas`` instead.

The ``file`` state had the following changes:

- The ``show_diff`` option was removed. Please use ``show_changes`` instead.

Grain Deprecations
==================

For ``smartos`` some grains have been deprecated. These grains will be removed in Neon.

- The ``hypervisor_uuid`` has been replaced with ``mdata:sdc:server_uuid`` grain.
- The ``datacenter`` has been replaced with ``mdata:sdc:datacenter_name`` grain.

Minion Blackout
---------------

During a blackout, minions will not execute any remote execution commands,
except for :mod:`saltutil.refresh_pillar <salt.modules.saltutil.refresh_pillar>`.
Previously, support was added so that blackouts are enabled using a special
pillar key, ``minion_blackout`` set to ``True`` and an optional pillar key
``minion_blackout_whitelist`` to specify additional functions that are permitted
during blackout. This release adds support for using this feature in the grains
as well, by using special grains keys ``minion_blackout`` and
``minion_blackout_whitelist``.

Pillar Deprecations
-------------------

The legacy configuration for ``git_pillar`` has been removed. Please use the new
configuration for ``git_pillar``, which is documented in the external pillar module
for :mod:`git_pillar <salt.pillar.git_pillar>`.

Utils Deprecations
==================

The ``salt.utils.cloud.py`` file had the following change:

- The ``fire_event`` function now requires a ``sock_dir`` argument. It was previously
  optional.

Other Miscellaneous Deprecations
================================

The ``version.py`` file had the following changes:

- The ``rc_info`` function was removed. Please use ``pre_info`` instead.

Warnings for moving away from the ``env`` option were removed. ``saltenv`` should be
used instead. The removal of these warnings does not have a behavior change. Only
the warning text was removed.

Sentry Log Handler
------------------

Configuring sentry raven python client via ``project``, ``servers``, ``public_key
and ``secret_key`` is deprecated and won't work with sentry clients > 3.0.
Instead, the ``dsn`` config param must be used.
