:orphan:

==================================
Salt Release Notes - Codename Neon
==================================

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

Deprecations
============

Module Deprecations
-------------------

- The hipchat module has been removed due to the service being retired.
  :py:func:`Google Chat <salt.modules.google_chat>`,
  :py:func:`MS Teams <salt.modules.msteams>`, or
  :py:func:`Slack <salt.modules.slack_notify>` may be suitable replacements.


State Deprecations
------------------

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
