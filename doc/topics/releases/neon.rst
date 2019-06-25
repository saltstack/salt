:orphan:

==================================
Salt Release Notes - Codename Neon
==================================


Execution Module for Checking Jinja Map Files
=============================================

To aid in troubleshooting, an execution module has been added, which allows one
to see the data loaded from a jinja map, or imported using ``import_yaml`` or
``import_json``. See :py:mod:`here <salt.modules.jinja>` for more information.


Saltcheck Updates
=================

Available since 2018.3, the :py:func:`saltcheck module <salt.modules.saltcheck>`
has been enhanced to:

* Support saltenv environments
* Associate tests with states by naming convention
* Adds empty and notempty assertions
* Adds skip keyword
* Adds print_result keyword
* Adds assertion_section keyword
* Use saltcheck.state_apply to run state.apply for test setup or teardown
* Changes output to display test time

Saltcheck provides unittest like functionality requiring only the knowledge of
salt module execution and yaml. Saltcheck uses salt modules to return data, then
runs an assertion against that return. This allows for testing with all the
features included in salt modules.

In order to run state and highstate saltcheck tests, a sub-folder in the state directory
must be created and named ``saltcheck-tests``. Tests for a state should be created in files
ending in ``*.tst`` and placed in the ``saltcheck-tests`` folder. ``tst`` files are run
through the salt rendering system, enabling tests to be written in yaml (or renderer of choice),
and include jinja, as well as the usual grain and pillar information. Like states, multiple tests can
be specified in a ``tst`` file. Multiple ``tst`` files can be created in the ``saltcheck-tests``
folder, and should be named the same as the associated state. The ``id`` of a test works in the
same manner as in salt state files and should be unique and descriptive.

Usage
-----

Example file system layout:

.. code-block:: text

    /srv/salt/apache/
        init.sls
        config.sls
        saltcheck-tests/
            init.tst
            config.tst
            deployment_validation.tst

Tests can be run for each state by name, for all ``apache/saltcheck/*.tst`` files,
or for all states assigned to the minion in top.sls. Tests may also be created
with no associated state. These tests will be run through the use of
``saltcheck.run_state_tests``, but will not be automatically run by
``saltcheck.run_highstate_tests``.

.. code-block:: bash

    salt '*' saltcheck.run_state_tests apache,apache.config
    salt '*' saltcheck.run_state_tests apache check_all=True
    salt '*' saltcheck.run_highstate_tests
    salt '*' saltcheck.run_state_tests apache.deployment_validation

Example Tests
-------------

.. code-block:: jinja

    {# will run the common salt state before further testing #}
    setup_test_environment:
      module_and_function: saltcheck.state_apply
      args:
        - common
      pillar-data:
        data: value

    {% for package in ["apache2", "openssh"] %}
    {# or another example #}
    {# for package in salt['pillar.get']("packages") #}
    jinja_test_{{ package }}_latest:
      module_and_function: pkg.upgrade_available
      args:
        - {{ package }}
      assertion: assertFalse
    {% endfor %}

    validate_user_present_and_shell:
      module_and_function: user.info
      args:
        - root
      assertion: assertEqual
      expected-return: /bin/bash
      assertion_section: shell
      print_result: False

    skip_test:
      module_and_function: pkg.upgrade_available
      args:
        - apache2
      assertion: assertFalse
      skip: True

Output Format Changes
---------------------

Saltcheck output has been enhanced to display the time taken per test. This results
in a change to the output format.

Previous Output:

.. code-block:: text

  local:
    |_
      ----------
      ntp:
          ----------
          ntp-client-installed:
              Pass
          ntp-service-status:
              Pass
    |_
      ----------
      TEST RESULTS:
          ----------
          Failed:
              0
          Missing Tests:
              0
          Passed:
              2

New output:

.. code-block:: text

  local:
    |_
      ----------
      ntp:
          ----------
          ntp-client-installed:
              ----------
              duration:
                  1.0408
              status:
                  Pass
          ntp-service-status:
              ----------
              duration:
                  1.464
              status:
                  Pass
    |_
      ----------
      TEST RESULTS:
          ----------
          Execution Time:
              2.5048
          Failed:
              0
          Missing Tests:
              0
          Passed:
              2
          Skipped:
              0

Unless and onlyif Enhancements
==============================

The ``unless`` and ``onlyif`` requisites can now be operated with salt modules.
The dictionary must contain an argument ``fun`` which is the module that is
being run, and everything else must be passed in under the args key or will be
passed as individual kwargs to the module function.

.. code-block:: yaml

  install apache on debian based distros:
    cmd.run:
      - name: make install
      - cwd: /path/to/dir/whatever-2.1.5/
      - unless:
        - fun: file.file_exists
          path: /usr/local/bin/whatever

.. code-block:: yaml

  set mysql root password:
    debconf.set:
      - name: mysql-server-5.7
      - data:
          'mysql-server/root_password': {'type': 'password', 'value': {{pillar['mysql.pass']}} }
      - unless:
        - fun: pkg.version
          args:
            - mysql-server-5.7


Keystore State and Module
=========================

A new :py:func:`state <salt.states.keystore>` and
:py:func:`execution module <salt.modules.keystore>` for manaing Java
Keystore files is now included. It allows for adding/removing/listing
as well as managing keystore files.

.. code-block:: bash

  # salt-call keystore.list /path/to/keystore.jks changeit
  local:
    |_
      ----------
      alias:
          hostname1
      expired:
          True
      sha1:
          CB:5E:DE:50:57:99:51:87:8E:2E:67:13:C5:3B:E9:38:EB:23:7E:40
      type:
          TrustedCertEntry
      valid_start:
          August 22 2012
      valid_until:
          August 21 2017

.. code-block:: yaml

  define_keystore:
    keystore.managed:
      - name: /tmp/statestore.jks
      - passphrase: changeit
      - force_remove: True
      - entries:
        - alias: hostname1
          certificate: /tmp/testcert.crt
        - alias: remotehost
          certificate: /tmp/512.cert
          private_key: /tmp/512.key
        - alias: stringhost
          certificate: |
            -----BEGIN CERTIFICATE-----
            MIICEjCCAX
            Hn+GmxZA
            -----END CERTIFICATE-----


XML State and Module
====================

A new :py:func:`state <salt.states.xml>` and
:py:func:`execution module <salt.modules.xml>` for editing XML files is
now included. Currently it allows for editing values from an xpath query, or
editing XML IDs.

.. code-block:: bash

  # salt-call xml.set_attribute /tmp/test.xml ".//actor[@id='3']" editedby "Jane Doe"
  local:
      True
  # salt-call xml.get_attribute /tmp/test.xml ".//actor[@id='3']"
  local:
      ----------
      editedby:
          Jane Doe
      id:
          3
  # salt-call xml.get_value /tmp/test.xml ".//actor[@id='2']"
  local:
      Liam Neeson
  # salt-call xml.set_value /tmp/test.xml ".//actor[@id='2']" "Patrick Stewart"
  local:
      True
  # salt-call xml.get_value /tmp/test.xml ".//actor[@id='2']"
  local:
      Patrick Stewart

.. code-block:: yaml

    ensure_value_true:
      xml.value_present:
        - name: /tmp/test.xml
        - xpath: .//actor[@id='1']
        - value: William Shatner

Slot Syntax Updates
===================

The slot syntax has been updated to support parsing dictionary responses and to append text.

.. code-block:: yaml

  demo dict parsing and append:
    test.configurable_test_state:
      - name: slot example
      - changes: False
      - comment: __slot__:salt:test.arg(shell="/bin/bash").kwargs.shell ~ /appended

.. code-block:: none

  local:
    ----------
          ID: demo dict parsing and append
    Function: test.configurable_test_state
        Name: slot example
      Result: True
     Comment: /bin/bash/appended
     Started: 09:59:58.623575
    Duration: 1.229 ms
     Changes:

State Changes
=============

- The :py:func:`file.rename <salt.states.file.rename>` state will now return a
  ``True`` result (and make no changes) when the destination file already
  exists, and ``Force`` is not set to ``True``. In previous releases, a
  ``False`` result would be returned, but this meant that subsequent runs of
  the state would fail due to the destination file being present.

- The :py:func:`file.managed <salt.states.file.managed>` state now supports
  setting selinux contexts.

  .. code-block:: yaml

    /tmp/selinux.test
      file.managed:
        - user: root
        - selinux:
            seuser: system_u
            serole: object_r
            setype: system_conf_t
            seranage: s0

- The ``onchanges`` and ``prereq`` :ref:`requisites <requisites>` now behave
  properly in test mode.

- Adding a new option for the State compiler, ``disabled_requisites`` will allow
  requisites to be disabled during State runs.

- Added new :py:func:`ssh_auth.manage <salt.states.ssh_auth.manage>` state to
  ensure only the specified ssh keys are present for the specified user.

- Added new :py:func:`saltutil <salt.states.saltutil>` state to use instead of
  ``module.run`` to more easily handle change.

- Added new `onfail_all` requisite form to allow for AND logic when adding
  onfail states.

Module Changes
==============

- The :py:func:`debian_ip <salt.modules.debian_ip>` module used by the
  :py:func:`network.managed <salt.states.network.managed>` state has been
  heavily refactored. The order that options appear in inet/inet6 blocks may
  produce cosmetic changes. Many options without an 'ipvX' prefix will now be
  shared between inet and inet6 blocks. The options ``enable_ipv4`` and
  ``enabled_ipv6`` will now fully remove relevant inet/inet6 blocks. Overriding
  options by prefixing them with 'ipvX' will now work with most options (i.e.
  ``dns`` can be overriden by ``ipv4dns`` or ``ipv6dns``). The ``proto`` option
  is now required.

- Added new :py:func:`boto_ssm <salt.modules.boto_ssm>` module to set and query
  secrets in AWS SSM parameters.

- Added new :py:func:`flatpak <salt.modules.flatpak>` module to work with flatpak packages.
  
- The :py:func:`file.set_selinux_context
  <salt.modules.file.set_selinux_context>` module now supports persistant
  changes with ``persist=True`` by calling the
  :py:func:`selinux.fcontext_add_policy
  <salt.modules.selinux.fcontext_add_policy>` module.

- The :py:func:`config.option <salt.modules.config.option>` now also returns
  matches from the grains, making it align better with :py:func:`config.get
  <salt.modules.config.get>`.

- Configuration for Docker registries is no longer restricted only to pillar
  data, and is now loaded using :py:func:`config.option
  <salt.modules.config.option>`. More information on registry authentication
  can be found :ref:`here <docker-authentication>`.

- The :py:func:`yumpkg <salt.modules.yumpkg>` module has been updated to support
  VMWare's Photon OS, which uses tdnf (a C implementation of dnf).

- The :py:func:`chocolatey.bootstrap <salt.modules.chocolatey.bootstrap>` function
  has been updated to support offline installation.

- The :py:func:`chocolatey.unbootstrap <salt.modules.chocolatey.unbootstrap>` function
  has been added to uninstall Chocolatey.

Runner Changes
==============

- The :py:func:`saltutil.sync_auth <salt.runners.saltutil.sync_auth>` function
  has been added to sync loadable auth modules. :py:func:`saltutil.sync_all <salt.runners.saltutil.sync_all>`
  will also include these modules.

Util Changes
============

- The :py:func:`win_dotnet <salt.utils.win_dotnet>` Salt util has been added to
  make it easier to detect the versions of .NET installed on the system. It includes
  the following functions:

    - :py:func:`versions <salt.utils.win_dotnet.versions>`
    - :py:func:`versions_list <salt.utils.win_dotnet.versions_list>`
    - :py:func:`versions_details <salt.utils.win_dotnet.versions_details>`
    - :py:func:`version_at_least <salt.utils.win_dotnet.version_at_least>`

Serializer Changes
==================

- The configparser serializer and deserializer functions can now be made to preserve
  case of item names by passing 'preserve_case=True' in the options parameter of the function.

  .. note::
      This is a parameter consumed only by the salt.serializer.configparser serialize and
      deserialize functions and not the low-level configparser python object.

  For example, in a file.serialze state:

  .. code-block:: yaml

    some.ini:
      - file.serialize:
         - formatter: configparser
         - merge_if_exists: True
         - deserializer_opts:
           - preserve_case: True
         - serializer_opts:
           - preserve_case: True

Enhancements to Engines
=======================

Multiple copies of a particular Salt engine can be configured by including
the ``engine_module`` parameter in the engine configuration.

.. code-block:: yaml

   engines:
     - production_logstash:
         host: production_log.my_network.com
         port: 5959
         proto: tcp
         engine_module: logstash
     - develop_logstash:
         host: develop_log.my_network.com
         port: 5959
         proto: tcp
         engine_module: logstash

Enhancements to Beacons
=======================
Multiple copies of a particular Salt beacon can be configured by including
the ``beacon_module`` parameter in the beacon configuration.

 .. code-block:: yaml

    beacons:
      watch_importand_file:
        - files:
            /etc/important_file: {}
        - beacon_module: inotify
      watch_another_file:
        - files:
            /etc/another_file: {}
        - beacon_module: inotify

Salt Cloud Features
===================

General
-------

The salt-cloud WinRM util has been extended to allow for an Administrator
account rename during deployment (for example, the Administator account
being renamed by an Active Directory group policy).

GCE Driver
----------

The GCE salt cloud driver can now be used with GCE instance credentials by
setting the configuration paramaters ``service_account_private_key`` and
``service_account_private_email`` to an empty string.

VMWware Driver
--------------

The VMWare driver has been updated to:
    Allow specifying a Windows domain to join during customization.
    Allow specifying timezone for the system during customization.
    Allow disabling the Windows autologon after deployment.
    Allow specifying the source template/VM's datacenter (to allow cloning between datacenters).

Salt Api
========

salt-api will now work on Windows platforms with limited support.
You will be able to configure the ``rest_cherrypy`` module, without ``pam``
external authentication and without ssl support.

Example configuration:

.. code-block:: yaml

    external_auth:
      auto:
        saltuser:
          -.*

    rest_cherrypy:
      host: 127.0.0.1
      port: 8000



Deprecations
============

RAET Transport
--------------

Support for RAET has been removed. Please use the ``zeromq`` or ``tcp`` transport
instead of ``raet``.

Module Deprecations
-------------------

- The :py:mod:`dockermod <salt.modules.dockermod>` module has been
  changed as follows:

    - Support for the ``tags`` kwarg has been removed from the
      :py:func:`dockermod.resolve_tag <salt.modules.dockermod.resolve_tag>`
      function.
    - Support for the ``network_id`` kwarg has been removed from the
      :py:func:`dockermod.connect_container_to_network <salt.modules.dockermod.connect_container_to_network>`
      function. Please use ``net_id`` instead.
    - Support for the ``name`` kwarg has been removed from the
      :py:func:`dockermod.sls_build <salt.modules.dockermod.sls_build>`
      function. Please use ``repository`` and ``tag`` instead.
    - Support for the ``image`` kwarg has been removed from the following
      functions. In all cases, please use both the ``repository`` and ``tag``
      options instead:

        - :py:func:`dockermod.build <salt.modules.dockermod.build>`
        - :py:func:`dockermod.commit <salt.modules.dockermod.commit>`
        - :py:func:`dockermod.import <salt.modules.dockermod.import_>`
        - :py:func:`dockermod.load <salt.modules.dockermod.load>`
        - :py:func:`dockermod.tag <salt.modules.dockermod.tag_>`

- The :py:mod`firewalld <salt.modules.firewalld>` module has been changed as
  follows:

    - Support for the ``force_masquerade`` option has been removed from the
      :py:func:`firewalld.add_port <salt.module.firewalld.add_port` function. Please
      use the :py:func:`firewalld.add_masquerade <salt.modules.firewalld.add_masquerade`
      function instead.
    - Support for the ``force_masquerade`` option has been removed from the
      :py:func:`firewalld.add_port_fwd <salt.module.firewalld.add_port_fwd` function. Please
      use the :py:func:`firewalld.add_masquerade <salt.modules.firewalld.add_masquerade`
      function instead.

- The :py:mod:`ssh <salt.modules.ssh>` execution module has been
  changed as follows:

    - Support for the ``ssh.get_known_host`` function has been removed. Please use the
      :py:func:`ssh.get_known_host_entries <salt.modules.ssh.get_known_host_entries>`
      function instead.
    - Support for the ``ssh.recv_known_host`` function has been removed. Please use the
      :py:func:`ssh.recv_known_host_entries <salt.modules.ssh.recv_known_host_entries>`
      function instead.

- The :py:mod:`test <salt.modules.test>` execution module has been changed as follows:

    - Support for the :py:func:`test.rand_str <salt.modules.test.rand_str>` has been
      removed. Please use the :py:func:`test.random_hash <salt.modules.test.random_hash>`
      function instead.

- The hipchat module has been removed due to the service being retired.
  :py:func:`Google Chat <salt.modules.google_chat>`,
  :py:func:`MS Teams <salt.modules.msteams>`, or
  :py:func:`Slack <salt.modules.slack_notify>` may be suitable replacements.


State Deprecations
------------------

- The :py:mod`firewalld <salt.states.firewalld>` state has been changed as follows:

    - The default setting for the ``prune_services`` option in the
      :py:func:`firewalld.present <salt.states.firewalld.present>` function has changed
      from ``True`` to ``False``.

- The :py:mod:`win_servermanager <salt.states.win_servermanager>` state has been
  changed as follows:

    - Support for the ``force`` kwarg has been removed from the
      :py:func:`win_servermanager.installed <salt.states.win_servermanager.installed>`
      function. Please use ``recurse`` instead.

- The hipchat state has been removed due to the service being retired.
  :py:func:`MS Teams <salt.states.msteams>` or
  :py:func:`Slack <salt.states.slack>` may be suitable replacements.

Engine Removal
--------------

- The hipchat engine has been removed due to the service being retired. For users migrating
  to Slack, the :py:func:`slack <salt.engines.slack>` engine may be a suitable replacement.

Returner Removal
----------------

- The hipchat returner has been removed due to the service being retired. For users migrating
  to Slack, the :py:func:`slack <salt.returners.slack_returner>` returner may be a suitable
  replacement.
