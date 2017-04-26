:orphan:

====================================
Salt Release Notes - Codename Oxygen
====================================

Configuration Option Deprecations
---------------------------------

- The ``requests_lib`` configuration option has been removed. Please use
  ``backend`` instead.

Module Deprecations
-------------------

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

State Deprecations
------------------

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
