:orphan:

==================================
Salt Release Notes - Codename Neon
==================================

Saltcheck Updates
=================

Available since 2018.3, the :py:func:`saltcheck module <salt.modules.saltcheck>`
has been enhanced to:

* Support saltenv environments
* Associate tests with states by naming convention
* Adds report_highstate_tests function
* Adds empty and notempty assertions
* Adds skip keyword
* Adds print_result keyword
* Adds assertion_section keyword
* Use saltcheck.state_apply to run state.apply for test setup or teardown
* Changes output to display test time
* Works with salt-ssh

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


Troubleshooting Jinja map files
===============================

A new :py:func:`execution module <salt.modules.jinja>` for ``map.jinja`` troubleshooting
has been added.

Assuming the map is loaded in your formula SLS as follows:

.. code-block:: jinja

  {% from "myformula/map.jinja" import myformula with context %}

The following command can be used to load the map and check the results:

.. code-block:: bash

  salt myminion jinja.load_map myformula/map.jinja myformula

The module can be also used to test ``json`` and ``yaml`` maps:

.. code-block:: bash

  salt myminion jinja.import_yaml myformula/defaults.yaml

  salt myminion jinja.import_json myformula/defaults.json


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

- Added new :py:func:`ssh_auth.manage <salt.states.ssh_auth.manage>` state to
  ensure only the specified ssh keys are present for the specified user.


Deprecations
============

Module Deprecations
-------------------

- The hipchat module has been removed due to the service being retired.
  :py:func:`Google Chat <salt.modules.google_chat>`,
  :py:func:`MS Teams <salt.modules.msteams>`, or
  :py:func:`Slack <salt.modules.slack_notify>` may be suitable replacements.

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

State Deprecations
------------------

- The hipchat state has been removed due to the service being retired.
  :py:func:`MS Teams <salt.states.msteams>` or
  :py:func:`Slack <salt.states.slack>` may be suitable replacements.

Fileserver Deprecations
-----------------------

- The hgfs fileserver had the following config options removed:

    - The ``hgfs_env_whitelist`` config option has been removed in favor of ``hgfs_saltenv_whitelist``.
    - The ``hgfs_env_blacklist`` config option has been removed in favor of ``hgfs_saltenv_blacklist``.

- The svnfs fileserver had the following config options removed:

    - The ``svnfs_env_whitelist`` config option has been removed in favor of ``svnfs_saltenv_whitelist``.
    - The ``svnfs_env_blacklist`` config option has been removed in favor of ``svnfs_saltenv_blacklist``.

Engine Removal
--------------

- The hipchat engine has been removed due to the service being retired. For users migrating
  to Slack, the :py:func:`slack <salt.engines.slack>` engine may be a suitable replacement.

Returner Removal
----------------

- The hipchat returner has been removed due to the service being retired. For users migrating
  to Slack, the :py:func:`slack <salt.returners.slack_returner>` returner may be a suitable
  replacement.

Grain Deprecations
------------------

For ``smartos`` some grains have been deprecated. These grains have been removed.

  - The ``hypervisor_uuid`` has been replaced with ``mdata:sdc:server_uuid`` grain.
  - The ``datacenter`` has been replaced with ``mdata:sdc:datacenter_name`` grain.

salt.auth.Authorize Class Removal
---------------------------------
- The salt.auth.Authorize Class inside of the `salt/auth/__init__.py` file has been removed and
  the `any_auth` method inside of the file `salt/utils/minions.py`. These method and classes were
  not being used inside of the salt code base.
