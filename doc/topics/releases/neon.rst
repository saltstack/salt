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

.. code-block:: txt

    /srv/salt/apache/
        init.sls
        config.sls
        saltcheck-tests/
            init.tst
            config.tst
            deployment_validation.tst

Tests can be run for each state by name, for all apache/saltcheck/*.tst files, or for all states
assigned to the minion in top.sls. Tests may also be created with no associated state. These tests
will be run through the use of ``saltcheck.run_state_tests``, but will not be automatically run
by ``saltcheck.run_highstate_tests``.

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
