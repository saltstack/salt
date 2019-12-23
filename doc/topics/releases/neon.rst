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

- The heat module has removed the ``enviroment`` kwarg from the
  :py:func:`heat.create_stack <salt.modules.heat.create_stack>` and
  :py:func:`heat.update_stack <salt.modules.heat.update_stack>` functions due
  to a spelling error. Please use ``environment`` instead.

- The :py:mod:`ssh <salt.modules.ssh>` execution module has been
  changed as follows:

    - Support for the ``ssh.get_known_host`` function has been removed. Please use the
      :py:func:`ssh.get_known_host_entries <salt.modules.ssh.get_known_host_entries>`
      function instead.
    - Support for the ``ssh.recv_known_host`` function has been removed. Please use the
      :py:func:`ssh.recv_known_host_entries <salt.modules.ssh.recv_known_host_entries>`
      function instead.

- The :py:mod`firewalld <salt.modules.firewalld>` module has been changed as
  follows:

    - The default setting for the ``force_masquerade`` option in the
      :py:func:`firewalld.add_port <salt.module.firewalld.add_port` function has changed
      from ``True`` to ``False``.
    - Support for the ``force_masquerade`` option in the
      :py:func:`firewalld.add_port_fwd <salt.module.firewalld.add_port_fwd` function has
      been changed from ``True`` to ``False``.

State Deprecations
------------------

- The hipchat state has been removed due to the service being retired.
  :py:func:`MS Teams <salt.states.msteams>` or
  :py:func:`Slack <salt.states.slack>` may be suitable replacements.

- The cmd state module has removed the ``quiet`` kwarg from the
  :py:func:`cmd.run <salt.states.cmd.run>` function. Please
  set ``output_loglevel`` to ``quiet`` instead.

- The heat state module has removed the ``enviroment`` kwarg from the
  :py:func:`heat.deployed <salt.states.heat.deployed>` function due
  to a spelling error. Please use ``environment`` instead.

- The :py:mod`firewalld <salt.states.firewalld>` state has been changed as follows:

    - The default setting for the ``prune_services`` option in the
      :py:func:`firewalld.present <salt.states.firewalld.present>` function has changed
      from ``True`` to ``False``.

Fileserver Deprecations
-----------------------

- The hgfs fileserver had the following config options removed:

    - The ``hgfs_env_whitelist`` config option has been removed in favor of ``hgfs_saltenv_whitelist``.
    - The ``hgfs_env_blacklist`` config option has been removed in favor of ``hgfs_saltenv_blacklist``.

- The svnfs fileserver had the following config options removed:

    - The ``svnfs_env_whitelist`` config option has been removed in favor of ``svnfs_saltenv_whitelist``.
    - The ``svnfs_env_blacklist`` config option has been removed in favor of ``svnfs_saltenv_blacklist``.

- The gitfs fileserver had the following config options removed:

    - The ``gitfs_env_whitelist`` config option has been removed in favor of ``gitfs_saltenv_whitelist``.
    - The ``gitfs_env_blacklist`` config option has been removed in favor of ``gitfs_saltenv_blacklist``.

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

Cloud Deprecations
------------------

- The nova cloud driver has been removed in favor of the openstack cloud driver.


Jinja Filter Deprecations
-------------------------

- The following jinja filters are set to be removed in the Aluminium release:

  - :jinja_ref:`json_decode_dict` in favor of :jinja_ref:`tojson`
  - :jinja_ref:`json_decode_list` in favor of :jinja_ref:`tojson`

Utils Deprecations
------------------
- All of the functions in salt.utils.__init__.py have been removed. These
  include:

    - `salt.utils.option`
    - `salt.utils.required_module_list`
    - `salt.utils.required_modules_error`
    - `salt.utils.get_accumulator_dir`. Please use :py:func:`salt.state.get_accumulator_dir` instead.
    - `salt.utils.fnmatch_multiple`. Please use :py:func:`salt.utils.itertools.fnmatch_multiple` instead.
    - `salt.utils.appendproctitle`. Please use :py:func:`salt.utils.process.appendproctitle` instead.
    - `salt.utils.daemonize`. Please use :py:func:`salt.utils.process.daemonize` instead.
    - `salt.utils.daemonize_if`. Please use :py:func:`salt.utils.process.daemonize_if` instead.
    - `salt.utils.reinit_crypto`. Please use :py:func:`salt.utils.crypt.reinit_crypto` instead.
    - `salt.utils.pem_finger`. Please use :py:func:`salt.utils.crypt.pem_finger` instead.
    - `salt.utils.to_bytes`. Please use :py:func:`salt.utils.stringutils.to_bytes` instead.
    - `salt.utils.to_str`. Please use :py:func:`salt.utils.stringutils.to_str` instead.
    - `salt.utils.to_unicode`. Please use :py:func:`salt.utils.stringutils.to_unicode` instead.
    - `salt.utils.str_to_num`. Please use :py:func:`salt.utils.stringutils.to_num` instead.
    - `salt.utils.is_quoted`. Please use :py:func:`salt.utils.stringutils.is_quoted` instead.
    - `salt.utils.dequote`. Please use :py:func:`salt.utils.stringutils.dequote` instead.
    - `salt.utils.is_hex`. Please use :py:func:`salt.utils.stringutils.is_hex` instead.
    - `salt.utils.is_bin_str`. Please use :py:func:`salt.utils.stringutils.is_binary` instead.
    - `salt.utils.rand_string`. Please use :py:func:`salt.utils.stringutils.random` instead.
    - `salt.utils.contains_whitespace`. Please use :py:func:`salt.utils.stringutils.contains_whitespace` instead.
    - `salt.utils.build_whitespace_split_regex`. Please use :py:func:`salt.utils.stringutils.build_whitespace_split_regex` instead.
    - `salt.utils.expr_match`. Please use :py:func:`salt.utils.stringutils.expr_match` instead.
    - `salt.utils.check_whitelist_blacklist`. Please use :py:func:`salt.utils.stringutils.check_whitelist_blacklist` instead.
    - `salt.utils.check_include_exclude`.Please use :py:func:`salt.utils.stringutils.check_include_exclude` instead.
    - `salt.utils.print_cli`.Please use :py:func:`salt.utils.stringutils.print_cli` instead.
    - `salt.utils.clean_kwargs`.Please use :py:func:`salt.utils.args.clean_kwargs` instead.
    - `salt.utils.invalid_kwargs`.Please use :py:func:`salt.utils.args.invalid_kwargs` instead.
    - `salt.utils.shlex_split`.Please use :py:func:`salt.utils.args.shlex_split` instead.
    - `salt.utils.arg_lookup`.Please use :py:func:`salt.utils.args.arg_lookup` instead.
    - `salt.utils.argspec_report`.Please use :py:func:`salt.utils.args.argspec_report` instead.
    - `salt.utils.split_input`.Please use :py:func:`salt.utils.args.split_input` instead.
    - `salt.utils.test_mode`.Please use :py:func:`salt.utils.args.test_mode` instead.
    - `salt.utils.format_call`.Please use :py:func:`salt.utils.args.format_call` instead.
    - `salt.utils.which`.Please use :py:func:`salt.utils.path.which` instead.
    - `salt.utils.which_bin`.Please use :py:func:`salt.utils.path.which_bin` instead.
    - `salt.utils.path_join`.Please use :py:func:`salt.utils.path.join` instead.
    - `salt.utils.check_or_die`.Please use :py:func:`salt.utils.path.check_or_die` instead.
    - `salt.utils.sanitize_win_path_string`.Please use :py:func:`salt.utils.path.sanitize_win_path` instead.
    - `salt.utils.rand_str`.Please use :py:func:`salt.utils.hashutils.random_hash` instead.
    - `salt.utils.get_hash`.Please use :py:func:`salt.utils.hashutils.get_hash` instead.
    - `salt.utils.is_windows`.Please use :py:func:`salt.utils.platform.is_windows` instead.
    - `salt.utils.is_proxy`.Please use :py:func:`salt.utils.platform.is_proxy` instead.
    - `salt.utils.is_linux`.Please use :py:func:`salt.utils.platform.is_linux` instead.
    - `salt.utils.is_darwin`.Please use :py:func:`salt.utils.platform.is_darwin` instead.
    - `salt.utils.is_sunos`.Please use :py:func:`salt.utils.platform.is_sunos` instead.
    - `salt.utils.is_smartos`.Please use :py:func:`salt.utils.platform.is_smartos` instead.
    - `salt.utils.is_smartos_globalzone`.Please use :py:func:`salt.utils.platform.is_smartos_globalzone` instead.
    - `salt.utils.is_smartos_zone`.Please use :py:func:`salt.utils.platform.is_smartos_zone` instead.
    - `salt.utils.is_freebsd`.Please use :py:func:`salt.utils.platform.is_freebsd` instead.
    - `salt.utils.is_netbsd`.Please use :py:func:`salt.utils.platform.is_netbsd` instead.
    - `salt.utils.is_openbsd`.Please use :py:func:`salt.utils.platform.is_openbsd` instead.
    - `salt.utils.is_aix`.Please use :py:func:`salt.utils.platform.is_aix` instead.
    - `salt.utils.safe_rm`.Please use :py:func:`salt.utils.files.safe_rm` instead.
    - `salt.utils.is_empty`.Please use :py:func:`salt.utils.files.is_empty` instead.
    - `salt.utils.fopen`.Please use :py:func:`salt.utils.files.fopen` instead.
    - `salt.utils.flopen`.Please use :py:func:`salt.utils.files.flopen` instead.
    - `salt.utils.fpopen`.Please use :py:func:`salt.utils.files.fpopen` instead.
    - `salt.utils.rm_rf`.Please use :py:func:`salt.utils.files.rm_rf` instead.
    - `salt.utils.mkstemp`.Please use :py:func:`salt.utils.files.mkstemp` instead.
    - `salt.utils.istextfile`.Please use :py:func:`salt.utils.files.is_text_file` instead.
    - `salt.utils.is_bin_file`.Please use :py:func:`salt.utils.files.is_binary` instead.
    - `salt.utils.list_files`.Please use :py:func:`salt.utils.files.list_files` instead.
    - `salt.utils.safe_walk`.Please use :py:func:`salt.utils.files.safe_walk` instead.
    - `salt.utils.st_mode_to_octal`.Please use :py:func:`salt.utils.files.st_mode_to_octal` instead.
    - `salt.utils.normalize_mode`.Please use :py:func:`salt.utils.files.normalize_mode` instead.
    - `salt.utils.human_size_to_bytes`.Please use :py:func:`salt.utils.files.human_size_to_bytes` instead.
    - `salt.utils.backup_minion`.Please use :py:func:`salt.utils.files.backup_minion` instead.
    - `salt.utils.str_version_to_evr`.Please use :py:func:`salt.utils.pkg.rpm.version_to_evr` instead.
    - `salt.utils.parse_docstring`.Please use :py:func:`salt.utils.doc.parse_docstring` instead.
    - `salt.utils.compare_versions`.Please use :py:func:`salt.utils.versions.compare` instead.
    - `salt.utils.version_cmp`.Please use :py:func:`salt.utils.versions.version_cmp` instead.
    - `salt.utils.warn_until`.Please use :py:func:`salt.utils.versions.warn_until` instead.
    - `salt.utils.kwargs_warn_until`.Please use :py:func:`salt.utils.versions.kwargs_warn_until` instead.
    - `salt.utils.get_color_theme`.Please use :py:func:`salt.utils.color.get_color_theme` instead.
    - `salt.utils.get_colors`.Please use :py:func:`salt.utils.color.get_colors` instead.
    - `salt.utils.gen_state_tag`.Please use :py:func:`salt.utils.state.gen_tag` instead.
    - `salt.utils.search_onfail_requisites`.Please use :py:func:`salt.utils.state.search_onfail_requisites` instead.
    - `salt.utils.check_onfail_requisites`.Please use :py:func:`salt.utils.state.check_onfail_requisites` instead.
    - `salt.utils.check_state_result`.Please use :py:func:`salt.utils.state.check_result` instead.
    - `salt.utils.get_user`.Please use :py:func:`salt.utils.user.get_user` instead.
    - `salt.utils.get_uid`.Please use :py:func:`salt.utils.user.get_uid` instead.
    - `salt.utils.get_specific_user`.Please use :py:func:`salt.utils.user.get_specific_user` instead.
    - `salt.utils.chugid`.Please use :py:func:`salt.utils.user.chugid` instead.
    - `salt.utils.chugid_and_umask`.Please use :py:func:`salt.utils.user.chugid_and_umask` instead.
    - `salt.utils.get_default_group`.Please use :py:func:`salt.utils.user.get_default_group` instead.
    - `salt.utils.get_group_list`.Please use :py:func:`salt.utils.user.get_group_list` instead.
    - `salt.utils.get_group_dict`.Please use :py:func:`salt.utils.user.get_group_dict` instead.
    - `salt.utils.get_gid_list`.Please use :py:func:`salt.utils.user.get_gid_list` instead.
    - `salt.utils.get_gid`.Please use :py:func:`salt.utils.user.get_gid` instead.
    - `salt.utils.enable_ctrl_logoff_handler`.Please use :py:func:`salt.utils.win_functions.enable_ctrl_logoff_handler` instead.
    - `salt.utils.traverse_dict`.Please use :py:func:`salt.utils.data.traverse_dict` instead.
    - `salt.utils.traverse_dict_and_list`.Please use :py:func:`salt.utils.data.traverse_dict_and_list` instead.
    - `salt.utils.filter_by`.Please use :py:func:`salt.utils.data.filter_by` instead.
    - `salt.utils.subdict_match`.Please use :py:func:`salt.utils.data.subdict_match` instead.
    - `salt.utils.substr_in_list`.Please use :py:func:`salt.utils.data.substr_in_list` instead.
    - `salt.utils.is_dictlist`.Please use :py:func:`salt.utils.data.is_dictlist` instead.
    - `salt.utils.repack_dictlist`.Please use :py:func:`salt.utils.data.repack_dictlist` instead.
    - `salt.utils.compare_dicts`.Please use :py:func:`salt.utils.data.compare_dicts` instead.
    - `salt.utils.compare_lists`.Please use :py:func:`salt.utils.data.compare_lists` instead.
    - `salt.utils.decode_dict`.Please use :py:func:`salt.utils.data.encode_dict` instead.
    - `salt.utils.decode_list`.Please use :py:func:`salt.utils.data.encode_list` instead.
    - `salt.utils.exactly_n`.Please use :py:func:`salt.utils.data.exactly_n` instead.
    - `salt.utils.exactly_one`.Please use :py:func:`salt.utils.data.exactly_one` instead.
    - `salt.utils.is_list`.Please use :py:func:`salt.utils.data.is_list` instead.
    - `salt.utils.is_iter`.Please use :py:func:`salt.utils.data.is_iter` instead.
    - `salt.utils.isorted`.Please use :py:func:`salt.utils.data.sorted_ignorecase` instead.
    - `salt.utils.is_true`.Please use :py:func:`salt.utils.data.is_true` instead.
    - `salt.utils.mysql_to_dict`.Please use :py:func:`salt.utils.data.mysql_to_dict` instead.
    - `salt.utils.simple_types_filter`.Please use :py:func:`salt.utils.data.simple_types_filter` instead.
    - `salt.utils.ip_bracket`.Please use :py:func:`salt.utils.zeromq.ip_bracket` instead.
    - `salt.utils.gen_mac`.Please use :py:func:`salt.utils.network.gen_mac` instead.
    - `salt.utils.mac_str_to_bytes`.Please use :py:func:`salt.utils.network.mac_str_to_bytes` instead.
    - `salt.utils.refresh_dns`.Please use :py:func:`salt.utils.network.refresh_dns` instead.
    - `salt.utils.dns_check`.Please use :py:func:`salt.utils.network.dns_check` instead.
    - `salt.utils.get_context`.Please use :py:func:`salt.utils.stringutils.get_context` instead.
    - `salt.utils.get_master_key`.Please use :py:func:`salt.utils.master.get_master_key` instead.
    - `salt.utils.get_values_of_matching_keys`.Please use :py:func:`salt.utils.master.get_values_of_matching_keys` instead.
    - `salt.utils.date_cast`.Please use :py:func:`salt.utils.dateutils.date_cast` instead.
    - `salt.utils.date_format`.Please use :py:func:`salt.utils.dateutils.strftime` instead.
    - `salt.utils.total_seconds`.Please use :py:func:`salt.utils.dateutils.total_seconds` instead.
    - `salt.utils.find_json`.Please use :py:func:`salt.utils.json.find_json` instead.
    - `salt.utils.import_json`.Please use :py:func:`salt.utils.json.import_json` instead.
    - `salt.utils.namespaced_function`.Please use :py:func:`salt.utils.functools.namespaced_function` instead.
    - `salt.utils.alias_function`.Please use :py:func:`salt.utils.functools.alias_function` instead.
    - `salt.utils.profile_func`.Please use :py:func:`salt.utils.profile.profile_func` instead.
    - `salt.utils.activate_profile`.Please use :py:func:`salt.utils.profile.activate_profile` instead.
    - `salt.utils.output_profile`.Please use :py:func:`salt.utils.profile.output_profile` instead.

salt.auth.Authorize Class Removal
---------------------------------
- The salt.auth.Authorize Class inside of the `salt/auth/__init__.py` file has been removed and
  the `any_auth` method inside of the file `salt/utils/minions.py`. These method and classes were
  not being used inside of the salt code base.
