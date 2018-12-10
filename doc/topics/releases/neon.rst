:orphan:

==================================
Salt Release Notes - Codename Neon
==================================


Saltcheck Updates
=================

Available since 2018.3, the saltcheck module has been enhanced to:
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

XML Module
==========

A new state and execution module for editing XML files is now included. Currently it allows for
editing values from an xpath query, or editing XML IDs.

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

- The :py:func:`file.set_selinux_context <salt.modules.file.set_selinux_context>`
  module now supports perstant changes with ``persist=True`` by calling the
  :py:func:`selinux.fcontext_add_policy <salt.modules.selinux.fcontext_add_policy>` module.

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

GCE Driver
----------

The GCE salt cloud driver can now be used with GCE instance credentials by
setting the configuration paramaters ``service_account_private_key`` and
``service_account_private_email`` to an empty string.

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
