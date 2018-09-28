:orphan:

==================================
Salt Release Notes - Codename Neon
==================================


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

- The :py:mod:`win_servermanager <salt.states.win_servermanager>` state has been
  changed as follows:

    - Support for the ``force`` kwarg has been removed from the
      :py:func:`win_servermanager.installed <salt.status.win_servermanager.installed>`
      function. Please use ``recurse`` instead.

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
