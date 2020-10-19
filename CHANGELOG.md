All notable changes to Salt will be documented in this file.

This changelog follows [keepachangelog](https://keepachangelog.com/en/1.0.0/) format, and is intended for human consumption.

This project versioning is _similar_ to [Semantic Versioning](https://semver.org), and is documented in [SEP 14](https://github.com/saltstack/salt-enhancement-proposals/pull/20/files).
Versions are `MAJOR.PATCH`.

# Changelog

Salt 3002 (2020-10-19)
======================

Removed
-------

- removed boto_vpc.describe_route_table please use boto_vpc.describe_route_tables (#58636)
- removed show_ipv4 arg from all functions in from salt.runners.manage (#58638)
- removed kwargs from mandrill.send if you use "async" please use "asynchronous" (#58640)
- removed salt/modules/mac_brew_pkg.__fix_cask_namespace (#58641)
- zfs.mount Passing '-a' as name is deprecated please just pass 'None' (#58642)
- Remove include_localhost kwarg for connected_ids method in salt/utils/minions.py (#58224)
- deprecated opts default argument of none and removed deprecation warnings (#58635)


Deprecated
----------

- The `ssh` parameter of `virt.migrate` has been deprecated. Use a libvirt URI `target` value instead. Both `virt.migrate_non_shared` and `virt.migrate_non_shared_inc` have been deprecated. Use the `copy_storage` parameter with `virt.migrate` instead. (#57947)


Changed
-------

- Allow to specify a custom port for Proxmox connection (#50620)
- Changed the lvm.lv_present state to accept a resizefs switch. So, when
  the logical volume is resized, the filesystem will be resized too. (#55265)
- Change the ``enable_fqdns_grains`` setting to default to ``False`` on proxy minions
  as it is generally not needed and just slows down start up time.. (#57676)
- Adds network teaming support to ``network.managed`` state for RHEL-based
  distros. Removes ``ip.get_bond`` and ``ip.build_bond`` for the same, as is
  redundant and not needed for any current RHEL/CentOS/Fedora/etc. release. (#57775)
- The ``serializer`` argument has been added to the :py:func:`file.serialize
  <salt.states.file.serialize>` state, as an alternative to ``formatter``. This
  brings it more in line with the ``serializer_opts`` and ``deserializer_opts``
  arguments. ``formatter`` is still supported, but using both ``serializer`` and
  ``formatter`` will cause the state to fail. (#57858)


Fixed
-----

- `file.read` exec module function no longer fails on binary data. (#58033)
- Remove py2 support from winrepo execution module and runner (#58596)
- Create ini file if does not exist when using ini.options_present state module. (#34236)
- Added an bool "strict" argument to sdb.get module to force module to fail if the sdb uri is not correct. (#39163)
- Fixed issue with postgres.has_privilege breaking on ALL. (#48465)
- check for azurearm username in config before adding username and password to the virtual machine properties (#49063)
- Fixes service.status to return True/False instead of empty strings or PIDs of the service. This brings macOS into parity with the other service modules. (#49237)
- fix frequent rest_tornado non-fatal tracebacks (#49572)
- Do not use reverse DNS of the target used in salt-ssh. Use the target the user provides. (#49840)
- Fixes startup issue where it tried to load the kernalparams grain on Windows (#49901)
- Fixed error in nilrt_ip.get_interfaces_details when loading config. (#50416)
- Doesn't remove underscore when sanitizing hostname in network salt util (#50527)
- permit the use of int/float type for the version in:
   - the state postgres_cluster.present
   - the state postgres_cluster.absent
   - the module postgres.cluster_create
   - the module postgres.cluster_remove (#50899)
- Cleaned up a trackback in lvm.pv_present when the disk doesn't exist. (#52363)
- Fixed UnboundLocalError when using win_network.connect (#53371)
- Add accept_ra 2 option to modules.debian_ip (#54067)
- salt.runner test mode support (#54382)
- Fixed mkpart to allow the creation of a partition without filesystem (#54456)
- Fixes bogus warning message when an empty list is used for an environment in a
  topfile. This allows `[]` to be used as a placeholder in a topfile without
  needing to comment everything out as a workaround. (#54882)
- win_certutil state will no longer fail on non-English systems upon successful additions and deletions of a certificate. (#55024)
- Fixed file.directory state always showing mode change for symlinks. (#55878)
- check for a docker error that the swarm already exists when calling swarm.swarm_init on an existing docker swarm (#55949)
- Fixing stalekey engine so it deletes the keys when they are a list. (#55977)
- An invalid _schedule.conf configuration file is renamed to _schedule.confYAMLError.
  This avoids disabling the minion and busy polling the CPU on Windows. (#56216, #58177)
- Proper calculation of tpldir and related context parameters (#56410)
- Make gpg.encrypt examples work (#56646)
- Artifactory encoding of headers fixed for py3 (#56660)
- Fixed handling of extents extended attribute in file.managed state. (#57189)
- Remove buggy start parameter from virt.pool_running docstring (#57275)
- Fixed saltcheck rendering of map.jinja files from saltenv (#57327)
- Fix for `virt.get_profiles` resolves an error that appears due to new parameters introduced with `_disk_profile()` (#57431)
- Accept nested namespaces in spacewalk.api runner function. (#57442)
- virt.init fix the disk target names (#57477)
- Fix volume name for disk-typed pools in virt.defined (#57497)
- Fixes an issue with filesystems options ordering which kept already
  applied NFS fstab entries being updated. (#57520)
- Do not allow python2 to be added to salt-ssh tar since Salt deprecated Python 2. (#57647)
- Fixed exception on loading custom zipped modules. (#57674)
- corrected support for app_id or local vault configurations (#57705)
- Fix the registration of libvirt pool and nodedev events (#57746)
- Pass cmd.run state arguments to unless and onlyif when they exist (#57760)
- The 2004 release of Windows 10 introduced a bug in the InstallationBehavior COM
  object where you can no longer get properties from that object. Calls to this
  object are now wrapped in a try/except block with sane defaults when it fails to
  read attributes.

  Additionally, some pre-flight checks have been added to the win_wua module to
  make sure Windows Update can actually run. (#57762)
- Changed get_repo in yumpkg.py to use "repo" as first parameter.
  This fixes #57778, a bug were every run of pkgrepo.managed state were
  marked as changed because the get_repo did fail to detect a previously
  applied run. (#57778)
- Raise SaltClientError in parse_host_port insted of ValueError so it is caught and handled properly when the minion is connecting to the master. (#57789)
- Fixed issue with the return dictionary from the workgroup() function in the
  salt.states.win_system module. This resulted in a windows-based minion logging
  an error and could also interfere with a highstate being applied. (#57790)
- Fixes broken block_device_mapping and block_device_mapping_v2 type checks in
  the OpenStack cloud driver. Salt was looking for a dict and the shade library
  was looking for a list of dicts. This made it impossible to use those params. (#57802)
- Fixed incorrect parsing of ``Set-Cookie`` response headers. (#57829)
- When using yumpkg, report stdout when stderr is redirected to stdout. (#57862)
- Fixes an issue on macOS where if you try and restart the macOS using serivce.restart salt-minion it would fail because the service names are different on macOS. (#57878)
- Fixes an issue on macOS where salt would take extra time to run on a service.dead call and the service is missing. (#57907)
- Fixes an issue where a disabled macOS and Windows service would fail to start with service.running. (#57908)
- Use "use_bin_type" to differentiate between bytes and str when writing cache
  for pillar and grains. (#57918)
- Set the comment to "No minions responded" if salt.function fails to find any
  minions (#57920)
- Fix issue with `__utils__` usage in the `__virtual__` functions on a few of the
  execution modules. (#57948)
- remove encoding kwarg for both pack(b)/unpack(b) in msgpack for versions >=1.0.0
  https://github.com/msgpack/msgpack-python/blob/master/ChangeLog.rst#100 (#57965)
- Replace deprecated `cgi.escape()` with `html.escape()` after it was removed from Python 3.8. (#57983)
- Fix btrfs state decorator, that produces exceptions when creating subvolumes. (#58012)
- Fix kubeadm token_list when the list of tokens is empty (#58116)
- Add a fix for the mac_service modules where it would fail to load in some new services and crash on Big Sur. (#58143)
- Fix blank tplfile context parameter when loading top level sls files (#58249)
- Do not include init directory in sls context parameters if explicitly specified (#58250)
- Fixing pillar caching when pillar environments are involved. (#58274)
- Make proxy_config read in the proxy specific configuration which is typically found in /etc/salt/proxy.d/minionid/. (#58307)
- Add timeout kwarg docs for service.running and service.dead (#58311)
- Return empty dict on win_pdh.get_counters rather than raising exception when no data are available (#58327)
- Leave boot parameters untouched if boot parameter is set to None in virt.update (#58331)
- Convert disks of volume type to file or block disks on Xen (#58333)
- Apparently Apple is using both "10.16" and "11" for versioning Big Sur,
  depending on where you look. The mac_softwareupdate module uses a different
  regex depending on OS version, and the determination was based on the
  osrelease_info grain. This results in a Big Sur machine not using the correct
  regex; osrelease_info[1] is 0 for Big Sur.

  This change simply adds an additional clause to the if statement to handle
  osmajorrelease > 10. (#58340)
- Fixed zmq salt-call hang!

  Some objects from the 3rd party module zmq fail to deconstruct if left to the GC when Python exits.
  This is because the objects get destroyed out of order.
  This only happens on some platforms like ubuntu 20.04 and some versions of FreeBSD.
  We fixed this hang by deconstructing all zmq objects in the right order before we exit salt-call. (#58364)
- Reactor runner functions will now ensure reactor system is available before attempting to run and error out if it is not available. (#58384)
- Fix enpoint typos (#58416)
- Make sure we repopulate ``__utils__`` on Windows when a job is run from the scheduler. (#58437)
- Adding a check when a source is an HTTP or FTP URL to do a query to ensure the URL is valid before returning, then we know if we need to move onto to the next source in the list or not. (#58441)
- Improved documentation for the LGPO state module (#58521)
- Remove old documented pending reboot key (#58530)
- On macOS, skip GUI dialog for Developer Command Line Tools when importing gitfs util. (#58575)
- Fixing a use case when multiple inotify beacons are defined but when notifications are fired the configuration from the first beacon are used. (#58655)


Added
-----

- Salt Api
  ========

  salt-api will now work on Windows platforms with limited support. You will be
  able to configure the ``rest_cherrypy`` module, without ``pam`` external
  authentication and without ssl support.

  Example configuration:

  .. code-block:: yaml
      external_auth:
        auto:
          saltuser:
            -.*
      rest_cherrypy:
        host: 127.0.0.1
        port: 8000 (#49949)
- Added `execution_timeout` support to `chocolatey.installed` state (#50449)
- Add new verify_ssl option to file modules. This allows a user to not validate the server certificate for HTTPS source and source hash's. (#52663)
- Added list target type support to the `scan` salt-ssh roster. (#52675)
- Added pvresize and lvextend to linux_lvm (#56089)
- Added COPR option to states.pkgrepo (#57258)
- Add "get_return" key for onlyif and unless requisites to parse deep module results (#57470)
- Allow setting VM boot devices order in virt.running and virt.defined states (#57544)
- Added grains to show the LVM Volume Groups and their Logical Volumes. (#57629)
- Memory Tuning Support which allows much greater control of memory allocation (#57639)
- Add output filter to saltcheck to only display test failures (#57788)
- ### Description
  Add profile block and profiling of import_* jinja calls.

  ### Example
  ```sls
  # cat /srv/salt/example.sls 
  {%- profile as 'local data' %}
    {%- set local_data = {'counter': 0} %}
    {%- for i in range(313377) %}
      {%- do local_data.update({'counter': i}) %}
    {%- endfor %}
  {%- endprofile %}

  test:
    cmd.run:
      - name: |-
          printf 'local data: %s' '{{ local_data['counter'] }}'
  ```

  ### Motivation

  When working with a very large codebase, it becomes more important to trace
  inefficiencies in state and pillar render times.  The `profile` jinja block
  enables the user to get finely detailed information on the most time consuming
  jinja expressions in the codebase.

  Especially as the codebase grows and the amount of minions increases, tracking
  down expensive expressions becomes imperative otherwise the resource burden for
  even just maintaining highstate becomes unmanageable. (#57849)
- - Added an execution module for running idem exec modules
  - Added a state module for running idem states (#57969)
- - Added the ability for states to return `sub_state_run`s -- results frome external state engines (#57993)
- Added salt-cloud support for Linode APIv4 via the ``api_version`` provider configuration parameter. (#58093)
- Added support to manage services in Slackware Linux. (#58206)
- Added list_sources to chocolatey module to have an overview of the repositories present on the minions.  
  Added source_added to chocolatey state in order to add repositories to chocolatey. (#58588)
- Adding tests for changes to virtual function for netmiko module. Adding tests for netmiko proxy minion module. (#58609)
- Added features config option for feature flags. Added a feature flag
  `enable_slsvars_fixes` to enable fixes to tpldir, tplfile and sls_path.
  This flag will be deprecated in the Phosphorus release when this functionality
  becomes the default. (#58652)


Salt 3001.1 (2020-07-27)
========================

Changed
-------

- Change the ``enable_fqdns_grains`` setting to default to ``False`` on Windows
  to address some issues with slowness. (#56296, #57529)
- Handle the UCRT libraries the same way they are handled in the Python 3
  installer (#57594)
- Changes the 'SSDs' grain name to 'ssds' as all grains needs to be 
  resolved in lowered case. (#57612)
- Updated requirement to psutil 5.6.7 due to vulnerability in psutil 5.6.6. (#58018)
- Updated requirement to PyYAML 5.3.1 due to vulnerability in PyYAML 5.2.1. (#58019)


Fixed
-----

- When running scheduled jobs from a proxy minion with multiprocessing turned off (default) a recursive error occurs as __pub_fun_args is repeated over and over again in the kwargs element in the data dictionary.  Now we make a copy of data['kwargs'] instead of using a reference. (#57941)
- The `x509.certificate_managed` state no longer triggers a change because of sorting issues if the certificate being evaluated was previously generated under Python 2. (#56556)
- Added support to lo ip alias in network.managed state by checking if lo inet data
  from network.interfaces contains label with the name of managed interface.
  Return status True if match found. (#56901)
- Redact passwords in the return when setting credentials using
  ``win_iis.container_setting`` (#57285)
- Fixes issue with cmd.powershell. Some powershell commands do not return
  anything in stdout. This causes the JSON parser to fail because an empty string
  is not valid JSON. This changes an empty string to `{}` which is valid JSON and
  will not cause the JSON loader to stacktrace. (#57493)
- Improves performance. Profiling `test.ping` on Windows shows that 13 of 17 
  seconds are wasted when the esxi grain loads vsphere before noting that
  the OS is not a esxi host. (#57529)
- Fixed permissions issue with certain pip/virtualenv states/modules when configured for non-root user. (#57550)
- Allow running nox sessions either using our `nox-py2 fork <https://github.com/s0undt3ch/nox/tree/hotfix/py2-release>`_ or upstream `nox <https://github.com/theacodes/nox>`_. (#57583)
- Fixes issue with lgpo.get when there are unicode characters in the hostname (#57591)
- Fixes issue with virtual block devices, like loopbacks and LVMs, wrongly
  populating the "disks" or "ssds" grains. (#57612)
- Due to some optimization the `virtual` grain was never updated on illumos. Move the fallback in prtdiag output parsing outside the loop that now gets skipped due to the command exiting non-zero. (#57714)
- Grains module delkey and delval methods now support the force option. This is
  needed for deleting grains with complex (nested) values. (#57718)
- Moving import salt.modules.vsphere into `__virtual__` so we have access to test proxytype in opts,
  previously this was causing a traceback when run on proxy minion as `__opts__` does not exist
  outside of any functions. Introducing a new utils function, is_proxytype, to check that the
  device is a proxy minion and also that the proxy type matches. (#57743)
- Fixed fail_with_changes in the test state to use the comment argument when passed. (#57766)
- Adds a fix so salt can run on the latest macOS version Big Sur. (#57787)
- Fixes UnpackValueError when using GPG cache by using atomic open. (#57798)
- The ``gid_from_name`` argument was removed from the ``user.present`` state in
  version 3001, with no deprecation path. It has been restored and put on a
  proper deprecation path. (#57843)
- Fixes dictionary being changed during iteration. (#57845)
- Fixed bug with distro version breaking osrelease on Centos 7. (#57781)
- Fixed macOS build scripts. (#57973)
- Fixed Salt-API startup failure. (#57975)
- Fixed CSR handling in x509 module (#54867)
- Re-allow x509 to manage a certificate based on a CSR


Added
-----

- Added docs demonstrating how to apply an MSI patch with winrepo (#32780)


Salt 3001 (2020-06-17)
======================

Removed
-------

- Removed long-deprecated `repo` option from pip state. (#51060)
- Removed noisy debug logging from config.get. (#54205)
- Removed needless dbus warnings from snapper module. (#56286)
- Removed obsolete MSI functionality from version tools. (#56352)
- Removed deprecated virt functionality. (#56514)
- Dropped requirement for enum34 dependency. (#57108)
- On macOS pkg.installed (using brew) no longer swaps `caskroom/cask/` for `homebrew/cask/` when using outdated package names. (#57361)
- napalm_network.load_template module - removed deprecated arguments
  template_user, template_attrs, template_group, template_mode, and native NAPALM
  template support. Use Salt's rendering pipeline instead. (#57362)
- selinux.fcontext_add_or_delete_policy module removed - use selinux.fcontext_add_policy or selinux.fcontext_delete_pollicy instead. (#57363)
- Deprecated `refresh_db` removed from pkgrepo state. Use `refresh` instead. (#57366)
- Deprecated internal functions salt.utils.locales.sdecode and .sdecode_if_string removed. Use salt.utils.data.decode instead. (#57367)
- Removed deprecated misc. internal Salt functions. See https://github.com/saltstack/salt/issues/57368 for more info. (#57368)
- Remove salt/utils/vt.py duplication from filename map. (#57004)


Changed
-------

- `file.rename` no longer returns False when `force:False`. (#49843)
- Brought localclient command line args functionality into line with regular `salt` calls. (#56853)
- Updated requisites documentation. (#49962)
- Changed eauth "not enabled" log message level from debug to warning. (#50946)
-  (#52546)
- Refactored x509.certificate_managed to be easier to use. (#52935)
- Don't log error when running "alternatives --display" on nonexistant target (#53911)
- Improved logging for user auth issues. (#53990)
- No longer emit extra logs when checking `alternatives.display` and `.check_exists`. (#53991)
- Use lazy loading to get SLS data from master - significantly improves `state.apply` times when using gitfs with many branches. (#54468)
- Changed Salt icon for Windows. (#56194)
- Update `libnacl` to 1.7.1 (#56350)
- Now require pycryptodomex for crypto on all platforms. (#56625)
- Updated to sphinx 3.0.1 when building docs. (#56671)
- Now `__salt__` is automatically refreshed when a package is `pip` installed, allowing pip installing a dependency and using that dependency in the same state run. (#56867)
- Use pygit2>=1.2.0 for Python>=3.8. (#56905)
- Now provides a more meaningful error for `win_groupadd` for unmapped accounts. (#56921)
- Significantly improve call times by only checking one frame in `depends`. (#57062)
- Salt scripts shebang now specifies `python3`. (#57083)
- Upgraded dependency to use boto3>=1.13.5. (#57161)
- Changed to consistent file location handling across APIs for Juniper network devices. (#57399)
- Use Python's hashlib (sha256) instead of shelling out (SipHash24) to generate server_id. (#57415)
- Update `formulas.rst` with new IRC channel and links to IRC logs (#51628)


Fixed
-----

- `pkgrepo.managed` now checks for a changed `key_url`. (#4438)
- Allow passing extra args to `file.rename`. (#29001)
- Fixed issue with overeager recursion detection. (#37646)
- Correctly set DNS search domain in VMware virtual machine. (#37709)
- Fixed trim_output logic in archive.extracted state (#40491)
- Updated documentation on `service` state. (#40819)
- Changed error message on `postgres_database.absent` to report correct error when database is in use. (#42833)
- Fixed issue in `sysctl` when kernel parameters were adjusted via grub. (#45195)
- Added termination protection option to salt-cloud ec2. (#45496)
- Refactored `debian_ip` module. (#46388)
- Log error when reactor tasks go to a full queue instead of silently fail. (#46431)
- Fixed issue with failure on comments in MySQL files. (#47488)
- Properly handle multibyte characters that span blocks of data. (#48473)
- Fixed failure in `user.present` when `gid_from_name` is True. Argument was removed and replaced by the `usergroup` argument. (#48640)
- Properly obtain hostname (#48906)
- Fixed `nilrt_ip` disabled function. (#48971)
- Fixed static configuration in nilrt_ip module. (#48990)
- Added missing ARPCHECK option to rh7_eth template. (#49074)
- Fixed to use the correct LetsEncrypt path on FreeBSD. (#49129)
- Updated docs for netapi logs - log.access_file and log.error_file. (#49247)
- Retry proxmox queries instead of failing immediately. (#49485)
- Fixed AMD GPU vendor detection. (#56837)
- Fixed `aptpkg.normalize_name` to respect architecture. (#49637)
- Add error message for proxmox failures. (#49562)
- Fixed nilrt_ip.enable/disable idempotency. (#56795)
- Fixed issue with file.line doing a partial comparison to determine replacement need, instead compare actual content of lines. (#49855)
- Return actual error message to user or hex code for `win_task.create_task_from_xml`. (#49981)
- Use minion name as ssh_host for saltify cloud provider. (#50135)
- Fixed misconfiguration of syndic. (#50139)
- Re-added `onfail_all`, fixed onfail always triggering with other reqs, and onfail and onchanges not working when both present. (#50264)
- Fixed broken scaleway cloud module. (#50334)
- Fixed issue not cleaning up schedule and beacons. (#50505)
- Fixed opkg install/remove to return potential changes, rather than always an empty dictionary. (#50516)
- Fixed `pycrypto.gen_hash` to use strongest available `algorithm` by default. (#50544)
- Fixed error leaving an empty first line on `.ini` file edits. (#50614)
- Fixes error in tcp transport publish port default value. (#50646)
- Changed internal functionality for deprecated Python `inspect.formatargspec`. (#50911)
- Allows clone_from setting in proxmox salt-cloud to be able to be an integer. (#51001)
- Stopped reading Windows registry value that might not be there. (#51095)
- Fixed complaint about unused variables. (#51196)
- salt-ssh no longer ignores pillar argument on `state.sls_id`. (#51353)
- Stop treating MSI as a hard dependency. (#51470)
- Fixed error handling for route53 to ignore `SignatureDoesNotMatch` errors (which cannot be retried). (#51572)
- Fixed `extract_hash` to use the correct value. (#51670)
- Fixed hard failure if `chocolately.installed` is for a non-existent package. (#51700)
- `fail_with` and `succeed_with` now correctly use `comment` argument. (#51821)
- Updated `is_enabled` to allow optional arguments. (#51823)
- Fixed issue producing an error trying to resolve the unresolvable Capability SIDs. (#51868)
- Additional fixes for using cron state with non-root Minion (#51872)
- Fixed proxy module for Windows by using `__utils__` instead of `__salt__` for code that accesses the registry. (#52013)
- Added support for parsing Gluster cli banner. (#52318)
- Fixed failure to require `target` argument in git states. (#52364)
- Fixed issue failing hard on uninstalled win updates. (#52387)
- Fixed issue with `artifactory` not correctly evaluating `has_classifier` first. (#52517)
- Fixed compound matches with nodegroups. (#52678)
- Removed some noisy logging that have a tendency to fill up the logs on larger installations. (#52763)
- Use `__utils__` for all registry calls. (#52992)
- Added syndic log rotation to RPM. (#53040)
- Use correct output in `zpool.present` when `test=true`. (#53145)
- Fix s3fs cache byte/str mismatch (#53244)
- Fixed `win_system` module to skip unavailable system info. (#53287)
- Ignore invalid product_name files. (#53326)
- Fixed error with `pkg.list_pkgs` to explicitly set `utf-8` encoding when writing, to match when reading. (#53340)
- Fixed issue with encoding/decoding on circular references, discovered with iptables when `state_aggregate` was enabled. (#53353)
- No longer fail when `blkid -o export` does not provide `TYPE` output. (#53447)
- Fixed `guesseed` -> `guessed` typo in `archive` state. (#53480)
- Fixed error with incorrect import statement masking real import error. (#53508)
- Added some error handling around missing results from external returners. (#53517)
- Changed to match repo paramter against repo name on `salt-run git_pillar.update`, so remote name can be used instead of full remote URL. (#56605)
- Changed returner function error message to be useful/less misleading. (#53628)
- Fixed `utils.user` to use correct `chugid` and `umask`. (#53681)
- Fixed SmartOS grains under Python 3. (#53740)
- Fixed error when trying to delete more than one key using `ini.options_absent`. (#53874)
- Fixed error with cmd.run when run in a chroot environment. (#53992)
- Fixed Zabbix configuration.import to use the correct values for the API version. (#54020)
- Fixed salt key management with eauth. (#54078)
- Fixed broken sdb.get_or_set_hash when using Hashicorp's Vault. (#54199)
- Fixed `mac_softwareupdate.list_available` for Catalina. (#54220)
- Fixed bug blocking `user.present` `createhome` on macOS. (#54288)
- Fixed `postfix.show_queue` issue where queue_id, size, timestamp, sender, and recipient must exist before trying to append them. (#54298)
- Fixed issue erroneously adding ssh_interface to DigitalOcean. (#54373)
- Fixed issue not using correct package keys from group info on group install on yum. (#54458)
- Fixed issue breaking state output on `test=true` with retry. (#54501)
- Ignore absent filter.lfs in gitconfig. (#54817)
- Changed to use Salt's CaseInsensitiveDict, so it can be msgpack serialized. (#54899)
- Fixed trying to set too large a queue on AIX. (#54912)
- Fixed issue when Vultr API returns "not supported" as default password during VM setup. (#54933)
- Fixed issue with Jinja renderer ignoring argline. (#55124)
- Fixed osrelease grain for MS Hyper-V 2019 by providing a default year. (#55212)
- Fixed napalm support in bgp and net runners. (#55222)
- Fixed Indefinitely code in win_task. (#55273)
- Fixed `file.replace` idempotency. (#55297)
- Fix incorrectly reported fileserver changes. (#55304)
- Fixed XML RPC-REPLy error in Junos by passing `huge_tree`. (#55318)
- Fixed error trying to treat binary files as text when doing spm install under Python 3. (#55330)
- Correctly determine if Debian repo should be skipped. (#55402)
- Set a hard dependency on `distro` module, for Python 3.8. (#55410)
- Fixed `config_data` parameter when compiling DSC via `win_dsc` module. (#55425)
- Fixed Solaris virtual grain to return better info instead of always LDOM. (#55444)
- Documentation on syncing custom modules slightly inaccurate and missing info on sync to master (#55514)
- Fixed crashes in ansiblegate on Python 3 minions. (#55585)
- Fixed traceback on `http.query` when errors with the URL. (#55586)
- Fixed failure to cache gpg data when `gpg_cache=True`. (#55772)
- Added `__prerequired__` to the state runtime keywords filter, to prevent failures on `file.replace`. (#55775)
- Fixed several Junos-related issues. (#55824)
- Fixed Vault KV version 2 support. (#55842)
- Removed remaning `pchanges` occurrences from state modules. (#55934)
- Fixed issues in Slack webhook returner. (#55968)
- Fixed onlyif/unless requisites being ignored in some cases. (#55974)
- Fixed `skip_files_list_verify` when `keep_source=False` in `archive.extracted` state. (#55975)
- Fixed `seed.apply` not waiting for the disk to be free. (#56002)
- Fixed issue that ignored `trim_output` argument intermittently. (#56041)
- Fixed `shadow.set_password` failing to set password when user isn't in `/etc/shadow`. (#56044)
- Fixed failure in `user` state when moving the user's default group into the `groups` arg. (#56061)
- Fixed issue incorrectly parsing YAML on command line. (#56067)
- Fixed Azure VM creation when using Python3. (#56091)
- Reverted `slspath` changes that broke a lot of states without proper deprecation. (#56119)
- Lack of FQDN for host no longer blocks master startup. (#56179)
- Pillar data is correctly included from `init.sls` file. (#56186)
- Fixed `check_password` for newer RabbitMQ versions. (#56193)
- Fixed timeout parameter not being passed to cmd_subset and cmd_batch, and misnamed (sub -> subset) parameter. (#56203)
- Added support for virtualenv>=20.0.0 `--version` strings. (#56205)
- No longer ignore slots on states when `parallel: true`. (#56221)
- Fix deprecation warnings for imports from collections. (#56225)
- Fixed Napalm beacons failing under Python 3. (#56243)
- Fixed failure in tomcat module. (#56269)
- Added salt-api log file to log rotation to prevent filling up the disk. (#56274)
- Fixed issue using undocumented abbreviation on zypper - now uses the full option. (#56278)
- Fixed issue parsing new `restorecon` output. (#56287)
- Fixed failure for returner only working via cli and not LocalClient. (#56322)
- Fixed version issues with empty minor string. (#56358)
- Upgraded psutil dependency to 5.6.6 due to CVE-2019-18874. (#56363)
- Fixed vendored tornado to use `salt.ext.backports_abc`. (#56369)
- Fixed x509 module incorrectly writing error messages as the cert. (#56372)
- Fixed error doing a `pip install salt` on Windows. (#56376)
- Fixed AzureRM `create_object_model` util. (#56379)
- Fixed issue `toxml` error in `virt.cpu_baseline`. (#56383)
- Fixed issue with exeption being raised on `virt._get_domain` when there's no VM. (#56392)
- Fixed crash in `aptpkg` on long description strings. (#56396)
- Fixed keyword mismatch with `cassandra_cql` and `cassandra_cql_return`. (#56328)
- Now uses the correct zero value for LockoutDuration in `win_lgpo`. (#56406)
- Fixed issue reporting incorrect Salt version. (#56415)
- Corrected documentation for `docker_image.load`. (#56420)
- Fixed `defaults.merge` documentation. (#56432)
- Fixed error always reporting changes with custom index-url for pip. (#56433)
- Matching int keys within nested dictionaries now works. (#56444)
- Fixed failure to support annotated tags when using pygit2. (#56451)
- Better handle virt.pool_rebuild in virt.pool_running and virt.pool_defined states (#56454)
- Fixed gitpython Windows requirements. (#56455)
- Added `grains_cache_expiration` to minion conf documentation. (#56458)
- Fixed incorrect handling of `renew=force` by `acme.cert` function. (#56462)
- Fixed issue with incorrect msgpack version string check. (#56463)
- Fixed infinite recursion in `pkg.group_info`. (#56476)
- Fixed failure to sanitize grains for salt-ssh executions. (#56491)
- Relax version requirements for pdbedit, also handle Debian branding in the version string. (#56553)
- Fixed indentation error on `cmd.run` orchestration output. (#56554)
- Fixed issue with getting incorrect SELinux context. (#56557)
- Fixed bug updating boot parameters with `virt`. (#56562)
- Correctly handle `pymysql.err.InternalError` in `mysql` module. (#56570)
- Fixed `panos` commit example in docs. (#56581)
- Fixed issue with `salt.utils.functools.call_functions` not checking for expected arguments. (#56584)
- Fixed a broken statement when using arbitrary `kwargs` in mine.value. (#56593)
- Fixed support for booting VMs with UEFI on virt. (#56613)
- Fixed postgres.db_remove() execution function if db is still in use. (#56631)
- Updated old redirects and http->https fixes in docs. (#56655)
- Renamed `salt/utils/docker/` to `salt/utils/dockermod/` to avoid clashes with the `docker` package from pypi. (#56669)
- Changed behavior to implicitly ignore package epochs and just use the latest one. (#56681)
- Avoid throwing exception for missing security group in boto under test mode. (#56695)
- Fix some function prompts in myssql module. (#56719)
- Add appropriate comment for `svn export` state. (#56757)
- Updated default master config file and updated the docs (#56053)
- Workaround upstream bug in jinja2 indent filter. (#56833)
- Fixed issue when raid.destroy is called but zero-superblock is not executed (#56838)
- Allow correct failure information to show up when calling `win_interfaces` (#56844)
- Add a note about service.running (#56846)
- Updated Windows installer scripts to use Python 3.7.4. (#56873)
- Nullsoft Salt Install now uninstalls MSI installed salt. (#56883)
- Fallback to ASCII sorting when pillar keys are integers. (#56909)
- Fixed `hwaddr` and `macaddr` not being added to RedHat network config, even if they were provided. (#56910)
- Fixed literal comparisons. (#56931)
- Fixed `win_system` `rawunicodeescape` errors. (#56940)
- Fixed `ps.top` failures with newer `psutil` library. (#56942)
- Provides better stacktrace in `win_pkg` return. (#56955)
- Fixed `reg.present` to respect `(Default)` REG_SZ value of an empty string. (#56959)
- OpenStack driver can now attach to multiple networks, also now respects provided `conn`. (#56960)
- Fixed literal comparsion in `user` state. (#56972)
- Additional fixes for using cron state with non-root Minion (#56973)
- Added ARPCHECK to the template for RHEL8 networking. (#57047)
- Fixed `aptpkg` to use `force-confnew` on it's own, and `force-confold` with `force-confdef`. (#57051)
- Fixed acme.certs state to return /etc/letsencrypt/live subdirectories (#57056)
- Fixed error with `fileserver.update` failing with `gitfs` backend was `git`, and `fileserver.clear_file_list_cache` not clearing gitfs cache when the backend was *not* `git`. (#57063)
- Fixed LazyLoader crashing when using ssh client via salt-api. (#57119)
- Publisher ACL doc fixes (#48915)
- Fixed `acl.present` to properly detect changes for default ACLs and recursive folders. (#57147)
- Fixed Minion/Minon typo in docs. (#57181)
- Fix UnicodeDecodeError when apply file.managed with binary contents in test mode. (#57184)
- Ensure errors are returned for missing pillars. (#57208)
- Fix `ps.top` failures on macOS when iterating over zombie processes. (#57216)
- Add vcredist_2013 (specifically msvcr120.dll) for OpenSSL/M2Crypto support on Windows. Fixes x509 module support. (#57266)
- Fix systemd invocation on latest Linux Arch version. (#57299)
- Updated rpm_lowpkg.version_cmp log messages and unit tests (#57347)
- Added rotation for proxy logs. (#57353)
- Fixed `win_system.join_domain` failures. (#57360)
- Fixed `template_vars` functionality on Junos. (#57388)
- Filter out aliases/duplicates from zypperpkg for <=SLE12SP4. (#57392)
- Fix issue with finding the real python executable during tests (#56686)
- Fix broken link regarding the 1024 character limit for YAML keys (#56540)
- Fix grain.delkey grains.delval for nested keys (#54819)


Added
-----

- Added support for list in `include_pat/exclude_pat` in `file.recurse`. (#2747)
- Added `validate` to tls module. (#7424)
- Pillar relative includes. (#8875)
- Added silent recurse option to `file.directory` state. (#44553)
- Added bhvye support to virt. (#47619)
- Added `kernelparams` grain for Linux. (#48501)
- Added `systempath` PATH grain. (#49049)
- Added appoptics returner. (#49066)
- Added ability to use the minion's region if specified. (#49097)
- Added reactor tuning documentation. (#49214)
- Added support for ipaddr/ipv6ipaddrs, loopback devices, dns_nameservers/dns_serach lists or strings, and multiple addresses per interface. (#49355)
- Added slsutil.banner for creating managed by salt message in files, and `slsutil.boolstr` for converting Pillar bool values to appropriate string representation. (#49396)
- Added `normalize_name` to `pkgin` module. (#49469)
- Added ability to use regex pattern with `ps.pgrep`. (#49565)
- Added `merge` option to `match.filter_by`. (#49845)
- Added ability to disable requisites during state runs. (#49955)
- Add a reactor "leader", especially useful for multimaster hot-hot environments. (#50053)
- Added `method_call` Jinja filter to help reduce boilerplate. (#50152)
- Added ability for async pillar refresh. (#56881)
- Added `shutdown_host` to vmware cloud. (#50177)
- Added `drbd.status` module. (#50410)
- Added `file.keyvalue` state. (#50627)
- Added JID lookup message in case minion times out. (#50704)
- Niceness control options added to the master config, for POSIX platforms. (#50905)
- Added `serial_type` to virt module. (#50930)
- Added RPC process documentation. (#50954)
- Added advanced initdb option support to `postgres_cluster.present`. (#50998)
- Added support for GCE accellerators in Salt Cloud. (#51033)
- Added `broadcast` address to `network.convert_cidr` return. (#51521)
- Added options for gitfs and git_pillar fallback branch. (#51971)
- Add `fat` as a valid `fs_type` for `parted` module. (#52016)
- Added support for comments in the host state/module. (#52185)
- Added offline bootstrap for Chocolatey. (#52233)
- Added support for listing all active running jobs on the master. (#52241)
- Added ability to get expected cache location. (#52305)
- Added ability to pass a timeout value to beacons. (#52314)
- Added support for `btrfs property` command. (#52699)
- Added ability to get minion's network information. (#53100)
- Added support for `not_before` and `not_after` for x509 certificates. (#53148)
- Added support for extra modules that will be loaded before checking the rest of the path. (#53167)
- Added initial execution module to kubeadm. (#53345)
- Added firstboot function to `systemd_service`. (#53381)
- Added ability to pass arbitrary kwargs to zypper pkg. (#53693)
- Added options for multi-use tokens for vault. (#54094)
- Added devinfo module to get hardware information. (#54267)
- Adds versionlock plugin detection for yum/dnf. (#54798)
- Improved nxos support. (#54931)
- Added root and no_recommends parameters for Zypper and RPM. (#54954)
- Added `token` parameter in `blkid`. (#54964)
- Added `cron.get_entry`. (#54985)
- Added support for newer monit versions. (#55140)
- Added btrfs and xfs as valid fstypes for parted and mkfs. (#55209)
- Added functionality for `cmd.run_all` to accept a list when using powershell. (#55213)
- Added Azure Blob Storage as an optional external pillar. (#55493)
- Added ability to turn off FQDNs grains with `enable_fqdns_grains: False`. (#55581)
- Added `virt.*defined` states. (#55814)
- Add towncrier tool to the Salt project to help manage CHANGELOG.md file. (#55836)
- Added Pull Request requirements to documentation (#55862)
- Add selinux support to file.managed (#40703)
- Added hold and unhold support for `mac_brew_pkg`. (#55978)
- States/modules added for managing Helm. (#56081)
- Added parallel run support for saltcheck. (#56097)
- Added multiple asserts against module output for saltcheck. (#56101)
- Added `state.test` as an alias for `state.apply ... test=True`. (#56298)
- Added default argumetn to `vault.read_secret` and `vault.list_secrets`. (#56311)
- Added `fromrepo` to `pkg.upgrade` for `pkgng`. (#56368)
- Added IP filtering by network. (#56394)
- Added more information for `__virtual__` failures. (#56395)
- Added logout functionality to docker. (#56439)
- Added ability to fetch master public key from minion. (#56449)
- Added `pending_reboot` grain for Windows systems. (#56489)
- Added support for forcing refresh in zypper. (#56519)
- Added `refresh_pillar` arg to `grains.setval`. (#56573)
- Added new roster option `ssh_pre_flight`. (#56488)
- Added ability to minions to read pillar files from local filesystem, and get commands from remote master. (#56611)
- Added support for rendering toml states. (#56615)
- Added `set_path` option for salt-ssh shim. (#56627)
- Added `win_wua.installed` to check a list of updates that apply to the current Windows build. (#56640)
- Added ability to compare package versions in Jinja templates. (#56678)
- Add `auto_detect` feature for `ssh_ext_alternatives`. (#56894)
- Add ability to display sys.doc style outputs but without actually loading the module. (#56902)
- Added plist serializer. (#56954)
- Added support for onedir/pop-build Salt in the `pip` module. (#56988)
- Add support for disks volumes in virt.running state (#57005)
- Add virt.all_capabilities helper function (#57009)
- supervisord.status_bool method (#57049)
- Added support for msgpack versions>=1.0 (#57122)
- Added Python 2 deprecation FAQ (#57273)
- Added support for # of hashing rounds when using pycrypto. (#57355)
- `fetchonly` parameter added for `pkg.upgrade` when using `pkgng` (FreeBSD). (#57371)
- Added `efi` parameter to virt module, so `uefi` firmware can be auto selected. (#57397)
- [#56637](https://github.com/saltstack/salt/pull/56637) - Add ``win_wua.installed`` to the ``win_wua`` execution module
- Clarify how to get the master fingerprint (#54699)


## 3000.1
### 3000.3

### Fixed
- [#57100](https://github.com/saltstack/salt/pull/57100) - Address Issues in CVE Release


### Changed
- [#56751](https://github.com/saltstack/salt/pull/56751) - Backport 49981

- [#56731](https://github.com/saltstack/salt/pull/56731) - Backport #53994
- [#56753](https://github.com/saltstack/salt/pull/56753) - Backport 51095

### Fixed
- [#56237](https://github.com/saltstack/salt/pull/56237) - Fix alphabetical ordering and remove duplicates across all documentation indexes - [@myii](https://github.com/myii)
- [#56325](https://github.com/saltstack/salt/pull/56325) - Fix hyperlinks to `salt.serializers` and other documentation issues - [@myii](https://github.com/myii)

### Added
- [#56627](https://github.com/saltstack/salt/pull/56627) - Add new salt-ssh set_path option
- [#51379](https://github.com/saltstack/salt/pull/56792) - Backport 51379 : Adds .set_domain_workgroup to win_system

## 3000.1

### Removed

### Deprecated

### Changed
- [#56730](https://github.com/saltstack/salt/pull/56730) - Backport #52992
### 3000.2

### Fixed
- [#56987](https://github.com/saltstack/salt/pull/56987) - CVE fix


### 3000.1

### Fixed

- [#56082](https://github.com/saltstack/salt/pull/56082) - Fix saltversioninfo grain for new version
- [#56143](https://github.com/saltstack/salt/pull/56143) - Use encoding when caching pillar data
- [#56172](https://github.com/saltstack/salt/pull/56172) - Only change mine data if using new allow_tgt feature
- [#56094](https://github.com/saltstack/salt/pull/56094) - Fix type error in TornadoImporter
- [#56174](https://github.com/saltstack/salt/pull/56174) - MySQL module fixes
- [#56149](https://github.com/saltstack/salt/pull/56149) - Fix to scheduler for use of when and splay
- [#56197](https://github.com/saltstack/salt/pull/56197) - Allows use of inline powershell for cmd.script args
- [#55894](https://github.com/saltstack/salt/pull/55894) - pdbedit module should check for version 4.8.x or newer
- [#55906](https://github.com/saltstack/salt/pull/55906) - smartos.vm_present could not handle nics with vrrp_vrid property
- [#56218](https://github.com/saltstack/salt/pull/56218) - Changed StrictVersion checking of setuptools to LooseVersion
- [#56099](https://github.com/saltstack/salt/pull/56099) - Fix Windows and macOS requirements handling in setup.py
- [#56068](https://github.com/saltstack/salt/pull/56068) - Update the bootstrap script to latest version, v2020.02.24
- [#56185](https://github.com/saltstack/salt/pull/56185) - Fix regression in service states with reload argument
- [#56341](https://github.com/saltstack/salt/pull/56341) - Revert "Don't remove one directory level from slspath"
- [#56290](https://github.com/saltstack/salt/pull/56290) - Ensures popping lgpo.secedit_data does not throw KeyError
- [#56339](https://github.com/saltstack/salt/pull/56339) - Fix win_dns_client when used with scheduler
- [#56215](https://github.com/saltstack/salt/pull/56215) - Fix for unless requisite when pip is not installed
- [#56060](https://github.com/saltstack/salt/pull/56060) - Fix regex string for Del and DelVals
- [#56337](https://github.com/saltstack/salt/pull/56337) - Handle Adapter Type 53 and Undefined Types
- [#56160](https://github.com/saltstack/salt/pull/56160) - Fix issue with existing reg_dword entries
- [#56358](https://github.com/saltstack/salt/pull/56358) - Fix version instantiation when minor is an empty string
- [#56272](https://github.com/saltstack/salt/pull/56272) - Properly resolve the policy name
- [#56310](https://github.com/saltstack/salt/pull/56310) - Only process ADMX files when loading policies
- [#56327](https://github.com/saltstack/salt/pull/56327) - keep cache_copied_files variable a list
- [#56360](https://github.com/saltstack/salt/pull/56360) - dont require virtualenv.virtualenv_version call, removed in 20.0.10
- [#56378](https://github.com/saltstack/salt/pull/56378) - Include _version.py if building wheel
- [#56376](https://github.com/saltstack/salt/pull/56376) - Fix win deps
- [#56418](https://github.com/saltstack/salt/pull/56418) - Ensure version.py included before we install
- [#56435](https://github.com/saltstack/salt/pull/56435) - Update mac build scripts


### Added

### 3000 - Neon [2020-02-10]

### Removed

- [#54474](https://github.com/saltstack/salt/issues/54474) via [#54475](https://github.com/saltstack/salt/pull/54475) - `virt.pool_delete` fast parameter removed. - [@cbosdo](https://github.com/cbosdo)
- [#54943](https://github.com/saltstack/salt/pull/54943) - Removed RAET transport method per the deprecation schedule - [@s0undt3ch](https://github.com/s0undt3ch)
- [#54983](https://github.com/saltstack/salt/pull/54983) - Removed Hipchat module, due to Hipchat discontinuation - [@mchugh19](https://github.com/mchugh19)
- [#55197](https://github.com/saltstack/salt/pull/55197) - Removed Google+ link since Google+ is gone - [@sramkrishna](https://github.com/sramkrishna)
- [#55539](https://github.com/saltstack/salt/pull/55539) - Removed salt.auth.Authorize class and the `any_auth` method
- [#55552](https://github.com/saltstack/salt/pull/55552) - Removed the config options `hgfs_env_whitelist`, `hgfs_env_blacklist`, `svnfs_env_whitelist`, and `svnfs_env_whitelist` in favor of `hgfs_saltenv_whitelist`, `hgfs_saltenv_blacklist`, `svnfs_saltenv_whitelist`, `svnfs_saltenv_blacklist`.
- [#55569](https://github.com/saltstack/salt/pull/55569) - Removed nova cloud driver in favor of the openstack driver.
- [#55573](https://github.com/saltstack/salt/pull/55573) - Removed `quiet` kwarg in cmd.run state module. Please set `output_loglevel` to `quiet` instead.
- [#55609](https://github.com/saltstack/salt/pull/55609) - Removed smartos grains `hypervisor_uuid` and `datacenter` in favor of `mdata:sdc:server_uuid` and `mdata:sdc:datacenter_name`.
- [#55641](https://github.com/saltstack/salt/pull/55641) - Removed `enviroment` kwarg from heat state and execution module. Please use correct spelling `environment`.
- [#55680](https://github.com/saltstack/salt/pull/55680) - Removed deprecated args from several `dockermod` functions - [@Ch3LL](https://github.com/Ch3LL)
- [#55682](https://github.com/saltstack/salt/pull/55682) - Removed `get_known_host` and `recv_known_host` functions from ssh module.
- [#55722](https://github.com/saltstack/salt/pull/55722) - Removed all functions in salt/utils/__init__.py.
- [#55725](https://github.com/saltstack/salt/pull/55725) - Removed `gitfs_env_whitelist` and `gitfs_env_blacklist` in favor of `gitfs_saltenv_whitelist` and `gitfs_saltenv_blacklist`.

### Deprecated

- [#55592](https://github.com/saltstack/salt/pull/55592) - Add deprecation warning for `glance` state and execution module  - [@Ch3LL](https://github.com/Ch3LL)
- [#55612](https://github.com/saltstack/salt/pull/55612) - Bump keystone deprecation to Sodium - [@Ch3LL](https://github.com/Ch3LL)
- [#55614](https://github.com/saltstack/salt/pull/55614) - Deprecate jinja filters for Neon - [@Ch3LL](https://github.com/Ch3LL)
- [#55664](https://github.com/saltstack/salt/pull/55664) - Bump deprecation warning to Aluminium for neutron module - [@Ch3LL](https://github.com/Ch3LL)
- [#55679](https://github.com/saltstack/salt/pull/55679) - Deprecate `boto_vpc.describe_route_table` in Magnesium - [@Ch3LL](https://github.com/Ch3LL)
- [#55726](https://github.com/saltstack/salt/pull/55726) - Deprecate `override_name` in Sodium - [@Ch3LL](https://github.com/Ch3LL)

### Changed

- [SEP 1](https://github.com/saltstack/salt-enhancement-proposals/blob/master/accepted/0001-changelog-format.md), [SEP 14](https://github.com/saltstack/salt-enhancement-proposals/pull/20) - Adopted keepachangelog format.
- [SEP 14](https://github.com/saltstack/salt-enhancement-proposals/pull/20) - Changed to numeric versions.
- [#49078](https://github.com/saltstack/salt/issues/49078) via [#54572](https://github.com/saltstack/salt/pull/54572) - Use `ip link set iface up/down` instead of `ifup/ifdown` - [@dmurphy18](https://github.com/dmurphy18)
- [#50023](https://github.com/saltstack/salt/pull/50023) via [#54620](https://github.com/saltstack/salt/pull/54620) - Change to reduce `roster_matcher` internal complexity - [@kojiromike](https://github.com/kojiromike)
- [#50579](https://github.com/saltstack/salt/pull/50579) via [#55389](https://github.com/saltstack/salt/pull/55389) - Update kafka returner to use confluent kafka - [@justindesilets](https://github.com/justindesilets)
- [#52749](https://github.com/saltstack/salt/pull/52749) - Padding change in versions report output - [@dwoz](https://github.com/dwoz)
- [#54013](https://github.com/saltstack/salt/pull/54103) - Set `session_id` cookie in the `rest_tornado` backend.
- [#55002](https://github.com/saltstack/salt/pull/55002) - Changed `mdadm_raid` metadata to text to allow float pillar data - [@aplanas](https://github.com/aplanas)
- [#55354](https://github.com/saltstack/salt/pull/55354) - Changed naive usage to use wrapped msgpack - [@Akm0d](https://github.com/Akm0d)
- [#55423](https://github.com/saltstack/salt/pull/55423) - Changed default configs to be immutable - [@s0undt3ch](https://github.com/s0undt3ch)
- [#55464](https://github.com/saltstack/salt/pull/55464) - Changed to name subprocesses - [@s0undt3ch](https://github.com/s0undt3ch)
- [#55500](https://github.com/saltstack/salt/pull/55500) - Start Linting Under Py3 - [@s0undt3ch](https://github.com/s0undt3ch)
- [#55643](https://github.com/saltstack/salt/pull/55643) - Remove deprecation for `refresh_db` in aptpkg - [@Ch3LL](https://github.com/Ch3LL)
- [#55660](https://github.com/saltstack/salt/pull/55660) - Use wrapped json module for ThreadsafeProxy - [@Akm0d](https://github.com/Akm0d)
- [#55683](https://github.com/saltstack/salt/pull/55683) - Changed `prune_services` in the firewall state module to be False by default. And update `force_masquerade` to be False by default in the firewall execution module.
- [#55739](https://github.com/saltstack/salt/pull/55739) - Microoptimized the command to set FreeBSD's virtual grain - [@asomers](https://github.com/asomers)

### Fixed

- [#6922](https://github.com/saltstack/salt/pull/6922) via [#51343](https://github.com/saltstack/salt/pull/51343) - Fixed errors when producing network errors - [@waynew](https://github.com/waynew)
- [#13971](https://github.com/saltstack/salt/issues/13971) via [#53462](https://github.com/saltstack/salt/pull/53462) - Support all valid protos for remote sources - []
- [#37646](https://github.com/saltstack/salt/pull/37646) - Fixed recursion error during msgpack serialization - [@waynew](https://github.com/waynew)
- [#39875](https://github.com/saltstack/salt/pull/39875) via [#52710](https://github.com/saltstack/salt/pull/52710) and [#54665](https://github.com/saltstack/salt/pull/54665) - Fixed complex grain comparison - [@mickenordin](https://github.com/mickenordin)
- [#41818](https://github.com/saltstack/salt/pull/41818) via [#51988](https://github.com/saltstack/salt/pull/51988) and [#54664](https://github.com/saltstack/salt/pull/54664) - Fixed `file.comment` and `file.uncomment` for when the pattern existed in both forms - [@mbunkus](https://github.com/mbunkus)
- [#49222](https://github.com/saltstack/salt/pull/49222) via [#49223](https://github.com/saltstack/salt/pull/49223) and [#54668](https://github.com/saltstack/salt/pull/54668) - Fixed salt-key `token_file` creation when using external auth - [@msciciel](https://github.com/msciciel)
- [#49256](https://github.com/saltstack/salt/pull/49256) via [#55060](https://github.com/saltstack/salt/pull/55060) - Fixed proxmox failure to apply settings - [@BrianSidebotham](https://github.com/BrianSidebotham)
- [#49490](https://github.com/saltstack/salt/pull/49490) via [#55404](https://github.com/saltstack/salt/pull/55404) - Fixed misleading cmdmod error message - [@rares-pop](https://github.com/rares-pop) and [@joechainz](https://github.com/joechainz)
- [#49748](https://github.com/saltstack/salt/pull/49748) via [#49843](https://github.com/saltstack/salt/pull/49843) and [#54546](https://github.com/saltstack/salt/pull/54546) - Fixed `file.rename` to be successful when target exists and force not set - [@MTecknology](https://github.com/MTecknology)
- [#49903](https://github.com/saltstack/salt/pull/49903) via [#54625](https://github.com/saltstack/salt/pull/54625) - Fixed inconsistencies with `consul_pillar` configuration parsing - [@FraaJad](https://github.com/FraaJad)
- [#49977](https://github.com/saltstack/salt/pull/49977) via [#55050](https://github.com/saltstack/salt/pull/55050) - [#4997]Fix novaclient api - [@slivik](https://github.com/slivik)
- [#50041](https://github.com/saltstack/salt/pull/50041) via [#54566](https://github.com/saltstack/salt/pull/54566) - Actually use `extra_install_flags` in `win_pkg` module - [@cmcmarrow](https://github.com/cmcmarrow)
- [#50374](https://github.com/saltstack/salt/pull/50374) via [#54616](https://github.com/saltstack/salt/pull/54616) - Fixed `local_cache` returner to report proper path in error message - [@isbm](https://github.com/isbm)
- [#50523](https://github.com/saltstack/salt/pull/50523) via [#54605](https://github.com/saltstack/salt/pull/54605) - Fixed OS arch fallback when no `rpm` is installed - [@isbm](https://github.com/isbm)
- [#50757](https://github.com/saltstack/salt/pull/50757) via [#54638](https://github.com/saltstack/salt/pull/54638) - Fixed restartcheck bytestring bug - [@10ne1](https://github.com/10ne1)
- [#50938](https://github.com/saltstack/salt/pull/50938) via [#54642](https://github.com/saltstack/salt/pull/54642) - Fixed performance issue with undefined opkg functions - [@andzn](https://github.com/andzn)
- [#50970](https://github.com/saltstack/salt/pull/50970) via [#54631](https://github.com/saltstack/salt/pull/54631) - Fix `win_path` index checks to allow for 0 - [@jalandis](https://github.com/jalandis)
- [#51038](https://github.com/saltstack/salt/pull/51038) via [#55706](https://github.com/saltstack/salt/pull/55706) - Fixed zabbix module failure on boolean return - [@thechile](https://github.com/thechile)
- [#51537](https://github.com/saltstack/salt/pull/51537) via [#51538](https://github.com/saltstack/salt/pull/51538) and [#54650](https://github.com/saltstack/salt/pull/54650) - Fixed directory vs. file issue in `salt.utils.etcd_util` - [@arizvisa](https://github.com/arizvisa)
- [#51711](https://github.com/saltstack/salt/issues/52788) via [#51718](https://github.com/saltstack/salt/pull/51718) - Fix Cheetah template renderer - [@arizvisa](https://github.com/arizvisa)
- [#51785](https://github.com/saltstack/salt/pull/51785) via [#54645](https://github.com/saltstack/salt/pull/54645) - Fixed POSIX vs. Windows inconsistencies in `salt.utils.path.which` - [@arizvisa](https://github.com/arizvisa)
- [#51795](https://github.com/saltstack/salt/issues/51795) via [#51801](https://github.com/saltstack/salt/pull/51801) - Fix netbox execution module cannot be loaded - [@misch42](https://github.com/misch42)
- [#51811](https://github.com/saltstack/salt/pull/51811) via [#51813](https://github.com/saltstack/salt/pull/51813) and [#54647](https://github.com/saltstack/salt/pull/54647) - Fixed `npm` version check on Windows - [@arizvisa](https://github.com/arizvisa)
- [#51915](https://github.com/saltstack/salt/pull/51915) via [#54685](https://github.com/saltstack/salt/pull/54685) - Changed nulls to empty strings to prevent Zabbix API errors - [@timdufrane](https://github.com/timdufrane)
- [#51929](https://github.com/saltstack/salt/pull/51929) via [#54611](https://github.com/saltstack/salt/pull/54611) - Fixed lvm to not show errors when pv, lv, or vg is not expected - [@aplanas](https://github.com/aplanas)
- [#51954](https://github.com/saltstack/salt/pull/51954) via [#54603](https://github.com/saltstack/salt/pull/54603) - Ignore misleading errors during `linuxlvm.pvcreate` and `.pvremove` - [@aplanas](https://github.com/aplanas)
- [#52230](https://github.com/saltstack/salt/pull/52230) via [#52352](https://github.com/saltstack/salt/pull/52352) and [#54640](https://github.com/saltstack/salt/pull/54640) - Fixed salt failing on missing `_syspaths` variables - [@alan-cugler](https://github.com/alan-cugler)
- [#52265](http://www.github.com/saltstack/salt/issues/52265) via [#54569](https://github.com/saltstack/salt/pull/54569) - Stop the Windows installer from hanging - [@twangboy](https://github.com/twangboy)
- [#52431](https://github.com/saltstack/salt/pull/52431) via [#52574](https://github.com/saltstack/salt/pull/52574) and [#54687](https://github.com/saltstack/salt/pull/54687) - Fix inconsistent `virt.get_xml` usage - [@zer0def](https://github.com/zer0def)
- [#52538](https://github.com/saltstack/salt/pull/52538) via [#52747](https://github.com/saltstack/salt/pull/52747) and [#54678](https://github.com/saltstack/salt/pull/54678) - Fix issue on Python3 when reading csv pillar with binary format - [@que5o](https://github.com/que5o)
- [#52589](https://github.com/saltstack/salt/pull/52589) via [#54536](https://github.com/saltstack/salt/pull/54536) - Ignore retcode when checking filesystem type - [@terminalmage](https://github.com/terminalmage)
- [#52786](https://github.com/saltstack/salt/pull/52786) via [#54588](https://github.com/saltstack/salt/pull/54588) - Fixed setting homedrive, profile, logonscript, and description for `user.present` under Windows- [@twangboy](https://github.com/twangboy)
- [#52788](https://github.com/saltstack/salt/issues/52788) via [#51706](https://github.com/saltstack/salt/pull/51706) - Ignore `HOST_NOT_FOUND` and `NO_DATA` when resolving FQDN - [@aplanas](https://github.com/aplanas)
- [#53017](https://github.com/saltstack/salt/issues/53401) via [#54196](https://github.com/saltstack/salt/pull/54196) - Fixed virt state on stopped VMs, virt.running's use of virt.vm_state, virt.pool_running, and virt.network_define - [@cbosdo](https://github.com/cbosdo)
- [#53401](https://github.com/saltstack/salt/issues/53401) via [#54166](https://github.com/saltstack/salt/pull/54166) - Fixed Docker image grains and pillar - [@waynew](https://github.com/waynew)
- [#53600](https://github.com/saltstack/salt/issues/53600) via [#54480](https://github.com/saltstack/salt/pull/54480) - Allow Windows minion to manage a binary file from `ext_pillar` - [@xeacott](https://github.com/xeacott)
- [#53935](https://github.com/saltstack/salt/pull/53935) - Poweroff when shutting down FreeBSD, NetBSD, and OpenBSD - [@morganwillcock](https://github.com/morganwillcock)
- [#54072](https://github.com/saltstack/salt/pull/54072) - Check for Windows registry key before trying to list it - [@twangboy](https://github.com/twangboy)
- [#54177](https://github.com/saltstack/salt/issues/54177) - Fixed `file.managed` bug with `contents_newline` flag - [@xeacott](https://github.com/xeacott)
- [#54197](https://github.com/saltstack/salt/pull/54197) - `virt.network_define` can now create NAT networks - [@cbosdo](https://github.com/cbosdo)
- [#54216](https://github.com/saltstack/salt/pull/54216) - Fixed Homebrew cask namespace support - [@cdalvaro](https://github.com/cdalvaro)
- [#54335](https://github.com/saltstack/salt/pull/54335) - Fixed `virt.full_info` output - [@cbosdo](https://github.com/cbosdo)
- [#54402](https://github.com/saltstack/salt/pull/54402) via [#54900](https://github.com/saltstack/salt/pull/54900) - Fix gitfs to use bytes when using gitpython with python3.x - [@vin01](https://github.com/vin01)
- [#54411](https://github.com/saltstack/salt/pull/54411) - Correctly handle `wusa` 3010 return code - [@tlemarchand](https://github.com/tlemarchand)
- [#54653](https://github.com/saltstack/salt/pull/54653) via [#55403](https://github.com/saltstack/salt/pull/55403) - Fixed issue with `publish.publish` trim mods after comma split - [@bmiguel-teixeira](https://github.com/bmiguel-teixeira) and [@saltybaker](https://github.com/saltybaker)
- [#54769](https://github.com/saltstack/salt/pull/54769) - Fixed `cmd.run` to call bash only when necessary on macOS - [@cdalvaro](https://github.com/cdalvaro)
- [#54896](https://github.com/saltstack/salt/pull/54896) - Fix multiple LGPO issues - [@twangboy](https://github.com/twangboy)
- [#55003](https://github.com/saltstack/salt/pull/55003) - Fix `collections` ABC warning - [@aplanas](https://github.com/aplanas)
- [#55005](https://github.com/saltstack/salt/pull/55005) - Fixed `mount.remount` when fstype was unset - [@aplanas](https://github.com/aplanas)
- [#55006](https://github.com/saltstack/salt/pull/55006) - Fixed args/kwargs bug in loop state - [@aplanas](https://github.com/aplanas)
- [#55052](https://github.com/saltstack/salt/pull/55052) - Fixed fileclient for ftp connections - [@garethgreenaway](https://github.com/garethgreenaway)
- [#55065](https://github.com/saltstack/salt/pull/55065) - Fixed multiprocessing process after fork and finalize regression - [@s0undt3ch](https://github.com/s0undt3ch)
- [#55083](https://github.com/saltstack/salt/pull/55083) - Fixed iLo module to use proper tempfile settings - [@garethgreenaway](https://github.com/garethgreenaway)
- [#55137](https://github.com/saltstack/salt/pull/55137) - Fixed `smartos_imgadm` to correctly handle orphan images - [@sjorge](https://github.com/sjorge)
- [#55149](https://github.com/saltstack/salt/pull/55149) via [#55497](https://github.com/saltstack/salt/pull/55497) - Removed incorrect pass of opts to `compound_match.match` - [@Akm0d](https://github.com/Akm0d)
- [#55165](https://github.com/saltstack/salt/pull/55165) - Fixed `virt.volume_infos` to handle volumes missing since last refresh - [@cbosdo](https://github.com/cbosdo)
- [#55190](https://github.com/saltstack/salt/pull/55190) - Fixed missing lazyloader functionality - [@max-arnold](https://github.com/max-arnold) and [@mattp-](https://github.com/mattp-)
- [#55191](https://github.com/saltstack/salt/pull/55191) - Fixed missing `list_downloaded` for apt module - [@brejoc](https://github.com/brejoc)
- [#55196](https://github.com/saltstack/salt/pull/55196) - Fixed `schedule.modify` to use function from current job - [@garethgreenaway](https://github.com/garethgreenaway)
- [#55207](https://github.com/saltstack/salt/pull/55207) - Fixed complex CORS option on CherryPy - [@niflostancu](https://github.com/niflostancu)
- [#55216](https://github.com/saltstack/salt/pull/55216) - Fixed failure to check for jid before returning data - [@brejoc](https://github.com/brejoc)
- [#55258](https://github.com/saltstack/salt/pull/55258) - Fixed aptpkg.info to return only installed packages - [@mateiw](https://github.com/mateiw)
- [#55271](https://github.com/saltstack/salt/pull/55271) - Fixed Py3 compatability issue in upstart - [@s0undt3ch](https://github.com/s0undt3ch)
- [#55336](https://github.com/saltstack/salt/pull/55336) - Fixed grains to allow `__utils__` in grains modules - [@max-arnold](https://github.com/max-arnold)
- [#55351](https://github.com/saltstack/salt/pull/55351) - Fixed `virt.get_hypervisor()` - [@cbosdo](https://github.com/cbosdo)
- [#55374](https://github.com/saltstack/salt/pull/55374) - Fixed issue with `zfs.filesystem_present` under Python3 - [@silenius](https://github.com/silenius)
- [#55434](https://github.com/saltstack/salt/pull/55434) - Stopped removing a directory level from slspath in templates - [@terminalmage](https://github.com/terminalmage)
- [#55441](https://github.com/saltstack/salt/pull/55441) - Fixed bug in logging - [@s0undt3ch](https://github.com/s0undt3ch)
- [#55452](https://github.com/saltstack/salt/pull/55452) - Fixed missing service.reload alias in `gentoo_service` module - [@vulnbe](https://github.com/vulnbe)
- [#55472](https://github.com/saltstack/salt/pull/55472) - Fixed several Py2/Py3 Unicode issues - [@s0undt3ch](https://github.com/s0undt3ch)
- [#55501](https://github.com/saltstack/salt/pull/55501) - Fixed slowdown by using ss filter to match TCP connections on Linux - [@cifvts](https://github.com/cifvts)
- [#55510](https://github.com/saltstack/salt/pull/55510) - Corrected `num_cpus` and `cpu_model` grains for IBM/S390 - [@FerrySchuller](https://github.com/FerrySchuller)
- [#55532](https://github.com/saltstack/salt/pull/55532) - Fixed missing beacons timeout error handling - [@s0undt3ch](https://github.com/s0undt3ch)
- [#55534](https://github.com/saltstack/salt/pull/55534) - Stopped `_virtual` from hard coding the 'virtual' key. - [@cmcmarrow](https://github.com/cmcmarrow)
- [#55540](https://github.com/saltstack/salt/pull/55540) - Fixed race condition in service.running on systemd - [@terminalmage](https://github.com/terminalmage)
- [#55557](https://github.com/saltstack/salt/pull/55557) - Changed to use UTC times for jids - [@dwoz](https://github.com/dwoz)
- [#55578](https://github.com/saltstack/salt/pull/55578) - Fixed `postgres.datadir_init` to use `checksums` arg - [@meaksh](https://github.com/meaksh)
- [#55580](https://github.com/saltstack/salt/pull/55580) - Fixed inconsistency with `pkg.list_pkgs` when using `attr` on RHEL systems - [@meaksh](https://github.com/meaksh)
- [#55582](https://github.com/saltstack/salt/pull/55582) - Do not report patches as installed when not all the related pkgs are installed (yumpkg) - [@meaksh](https://github.com/meaksh)
- [#55583](https://github.com/saltstack/salt/pull/55583) - Fixed `utils.network` issue with IPv6 that could cause a crash - [@meaksh](https://github.com/meaksh)
- [#55584](https://github.com/saltstack/salt/pull/55584) - Stopped breaking multiline repo files in `yumpkg` - [@meaksh](https://github.com/meaksh)
- [#55589](https://github.com/saltstack/salt/pull/55589) - Acme state fixes - [@github-abcde](https://github.com/github-abcde)
- [#55607](https://github.com/saltstack/salt/pull/55607) - Fixed failure to fire events to all syndics from MoM when using tcp transport - [@lukasraska](https://github.com/lukasraska)
- [#55616](https://github.com/saltstack/salt/pull/55616) - Fixed jboss `run_operation` and `datasource_exists` - [@cmcmarrow](https://github.com/cmcmarrow)
- [#55624](https://github.com/saltstack/salt/pull/55624) - Fixed issue with matchers, fallback to `ext_pillar` if there is no pillar in __opts__ - [@vquiering](https://github.com/vquiering)
- [#55635](https://github.com/saltstack/salt/pull/55635) - Fixed issue with minion signing during/after job execution - [@lukasraska](https://github.com/lukasraska)
- [#55651](https://github.com/saltstack/salt/pull/55651) - Fixed `ldap.managed` errors - [@sathieu](https://github.com/sathieu)
- [#55655](https://github.com/saltstack/salt/pull/55655) - Fixed using password hashes with MariaDB - [@pprkut](https://github.com/pprkut)
- [#55672](https://github.com/saltstack/salt/pull/55672) - Fixed issue with busy guestfs mount folders - [@cbosdo](https://github.com/cbosdo)
- [#55694](https://github.com/saltstack/salt/pull/55694) - Fixed S3 pillar pagination - [@garethgreenaway](https://github.com/garethgreenaway)
- [#55705](https://github.com/saltstack/salt/pull/55705) - Fixed zypper upgrade fromrepo - [@pkwestm](https://github.com/pkwestm)
- [#55730](https://github.com/saltstack/salt/pull/55730) - Restored original minion configured `publish_port` behavior - [@mattp-](https://github.com/mattp-) and [@Ch3LL](https://github.com/Ch3LL)
- [#55780](https://github.com/saltstack/salt/pull/55780) - Fallback to disabled `LG_INCLUDE_INDIRECT` when DC is unavailable - [@lukasraska](https://github.com/lukasraska)
- [#55795](https://github.com/saltstack/salt/pull/55795) - Fixed issue with whitespace in ADML data - [@twangboy](https://github.com/twangboy)
- [#55796](https://github.com/saltstack/salt/pull/55796) - Fixed cached `osrelease_info` grain type - [@srg91](https://github.com/srg91)
- [#55817](https://github.com/saltstack/salt/pull/55817) - Bring #51372 to Master Branch - [@twangboy](https://github.com/twangboy)
- [#55823](https://github.com/saltstack/salt/pull/55823) - Fix issue with overly long names in the LGPO module - [@twangboy](https://github.com/twangboy)
- [#55843](https://github.com/saltstack/salt/pull/55843) - Fixed `file.mkdir` to respect `test=True` - [@mchugh19](https://github.com/mchugh19)
- [#55845](https://github.com/saltstack/salt/pull/55845) - Fixed logging to return multiprocessing queue if it's already set - [@s0undt3ch](https://github.com/s0undt3ch)

### Added

- [#16674](https://github.com/saltstack/salt/pull/16674) via [#50083](https://github.com/saltstack/salt/pull/50083) and [#54632](https://github.com/saltstack/salt/pull/54632) - Added `migrate` support for Django module - [@jrbeilke](https://github.com/jrbeilke)
- [#39475](https://github.com/saltstack/salt/issues/39475) - Added `hardlink` for `file` state and module - [@arizvisa](https://github.com/arizvisa)
- [#48792](https://github.com/saltstack/salt/pull/48792) via [#49399](https://github.com/saltstack/salt/pull/49399) and [#54879](https://github.com/saltstack/salt/pull/54879) - Add IIS webconfiguration - [@tlemarchand](https://github.com/tlemarchand)
- [#49212](https://github.com/saltstack/salt/pull/49212) via [#49378](https://github.com/saltstack/salt/pull/49378) - Added `minion_id_remove_domain`- [@markuskramerIgitt](https://github.com/markuskramerIgitt)
- [#49250](https://github.com/saltstack/salt/pull/49250) via [#54657](https://github.com/saltstack/salt/pull/54657) - Add capability `jboss7` to keep unchanged deployments - [@garethgreenaway](https://github.com/garethgreenaway)
- [#49481](https://github.com/saltstack/salt/pull/49481) via [#54532](https://github.com/saltstack/salt/pull/54532) - Added `grains_blacklist` to block specific grains - [@rongzeng54](https://github.com/rongzeng54)
- [#50005](https://github.com/saltstack/salt/pull/50005) via [#54651](https://github.com/saltstack/salt/pull/54651) - Added ability to create events based on an arbitrary script's output - [@austinpapp](https://github.com/austinpapp)
- [#50306](https://github.com/saltstack/salt/pull/50306) via [#54542](https://github.com/saltstack/salt/pull/54542) - Added `noaction` flag for opkg execution module - [@rares-pop](https://github.com/rares-pop)
- [#50706](https://github.com/saltstack/salt/pull/50706) via [#54604](https://github.com/saltstack/salt/pull/54604) - Added `token` to `disk.blkid` to allow extended search - [@aplanas](https://github.com/aplanas)
- [#50953](https://github.com/saltstack/salt/pull/50953) via [#54548](https://github.com/saltstack/salt/pull/54548) - Add `nvme_nqn` grain - [@sdodsley](https://github.com/sdodsley)
- [#51047](https://github.com/saltstack/salt/pull/51047) via [#55253](https://github.com/saltstack/salt/pull/55253) - Added new execution module for troubleshooting Jinja map files- [@terminalmage](https://github.com/terminalmage) and [@max-arnold](https://github.com/max-arnold)
- [#51074](https://github.com/saltstack/salt/pull/51074) via [#54613](https://github.com/saltstack/salt/pull/54613) - Added `fat` parameter to disk module to allow specifying FAT sizes - [@aplanas](https://github.com/aplanas)
- [#51385](https://github.com/saltstack/salt/pull/51385) via [#54656](https://github.com/saltstack/salt/pull/54656) - Added support for directories and checking for free space in the `disk` state - [@maxim-sermin](https://github.com/maxim-sermin)
- [#51758](https://github.com/saltstack/salt/pull/51758) via [#55400](https://github.com/saltstack/salt/pull/55400) - Added cwd grain - [@theskabeater](https://github.com/theskabeater) and [@dwoz](https://github.com/dwoz)
- [#52293](https://github.com/saltstack/salt/pull/52293) via [#55723](https://github.com/saltstack/salt/pull/55723) - Added saltenv support in slsutil.renderer - [@afischer-opentext-com](https://github.com/afischer-opentext-com)
- [#52458](https://github.com/saltstack/salt/pull/52458) via [#54623](https://github.com/saltstack/salt/pull/54623) - Added `camel_to_snake_case` and `snake_to_camel_case` to stringutils - [@github-abcde](https://github.com/github-abcde)
- [#52715](https://github.com/saltstack/salt/pull/52715) via [#54577](https://github.com/saltstack/salt/pull/54577) - Added webhook support to Slack state - [@garethgreenaway](https://github.com/garethgreenaway)
- [#52764](https://github.com/saltstack/salt/pull/52764) via [#54058](https://github.com/saltstack/salt/pull/54058) - Added vSphere tagging ability - [@xeacott](https://github.com/xeacott)
- [#53307](https://github.com/saltstack/salt/pull/53307) - Added slot parsing inside nested state data structures - [@max-arnold](https://github.com/max-arnold)
- [#53621](https://github.com/saltstack/salt/pull/53621) - Added support for `git_pillar_update_interval` - [@sathieu](https://github.com/sathieu)
- [#53736](https://github.com/saltstack/salt/issues/53736) - Added index get_settings, put_settings methods for Elasticsearch module. - [@Oloremo](https://github.com/Oloremo)
- [#53738](https://github.com/saltstack/salt/pull/53738) - Added `request_interval` feature to `http.wait_for_successful_query` module - [@Oloremo](https://github.com/Oloremo)
- [#53959](https://github.com/saltstack/salt/pull/53959) - Added additional optional `warnings` to `test` module - [@max-arnold](https://github.com/max-arnold)
- [#54505](https://github.com/saltstack/salt/issues/54505) - Added cluster get_settings, put_settings and flush_synced methods for Elasticsearch module. - [@Oloremo](https://github.com/Oloremo)
- [#54518](https://github.com/saltstack/salt/pull/54518) via [#54526](https://github.com/saltstack/salt/pull/54526) - Add salt-cloud support for Tencent Cloud - [@likexian](https://github.com/likexian)
- [#54902](https://github.com/saltstack/salt/pull/54902) - Added `cert_info` beacon to get cert information from local files - [@nicholasmhughes](https://github.com/nicholasmhughes)
- [#54903](https://github.com/saltstack/salt/pull/54903) - Added multipart/form-data file posting to `http.query` util - [@nicholasmhughes](https://github.com/nicholasmhughes)
- [#54948](https://github.com/saltstack/salt/pull/54948) - Added ability to pass grains on minion startup event - [@admd](https://github.com/admd)
- [#54955](https://github.com/saltstack/salt/pull/54955) - Added root parameter to useradd, shadow and groupadd - [@aplanas](https://github.com/aplanas)
- [#54956](https://github.com/saltstack/salt/pull/54956) - Added root parameter for wait and run states - [@aplanas](https://github.com/aplanas)
- [#54958](https://github.com/saltstack/salt/pull/54958) - Added optional root parameter for systemd - [@aplanas](https://github.com/aplanas)
- [#54959](https://github.com/saltstack/salt/pull/54959) - Added new chroot module - [@aplanas](https://github.com/aplanas)
- [#54960](https://github.com/saltstack/salt/pull/54960) - Added new freezer module - [@aplanas](https://github.com/aplanas)
- [#54961](https://github.com/saltstack/salt/pull/54961) - Added all subvolume commands to btrfs - [@aplanas](https://github.com/aplanas)
- [#54965](https://github.com/saltstack/salt/pull/54965) - Added fstab present/absent to mount state - [@aplanas](https://github.com/aplanas)
- [#54977](https://github.com/saltstack/salt/pull/54977) - Added xml state & module - [@mchugh19](https://github.com/mchugh19)
- [#54981](https://github.com/saltstack/salt/pull/54981) - Added `ssh_auth.manage` to both add _and_ remove ssh keys - [@mchugh19](https://github.com/mchugh19)
- [#54982](https://github.com/saltstack/salt/pull/54982) - Added new AWS SSM module - [@mchugh19](https://github.com/mchugh19)
- [#54984](https://github.com/saltstack/salt/pull/54984) - Added saltutil states to match saltutil modules - [@mchugh19](https://github.com/mchugh19) and [@max-arnold](https://github.com/max-arnold)
- [#54991](https://github.com/saltstack/salt/pull/54991) - Added keystore state and modules for Java keystore files - [@mchugh19](https://github.com/mchugh19)
- [#54992](https://github.com/saltstack/salt/pull/54992) - Added ability to use salt modules in onlyif and unless - [@mchugh19](https://github.com/mchugh19) and [@gtmanfred](https://github.com/gtmanfred)
- [#54993](https://github.com/saltstack/salt/pull/54993) - Added support for parsing slot results - [@mchugh19](https://github.com/mchugh19)
- [#54996](https://github.com/saltstack/salt/pull/54996) - Added `binds` parameter for `run_chroot` - [@aplanas](https://github.com/aplanas)
- [#55001](https://github.com/saltstack/salt/pull/55001) - Added ability to ignore errors on `mdadm_raid.examine` - [@aplanas](https://github.com/aplanas)
- [#55047](https://github.com/saltstack/salt/pull/55047) - Added ability to deprecate by date - [@s0undt3ch](https://github.com/s0undt3ch)
- [#55145](https://github.com/saltstack/salt/pull/55145) and [#50150](https://github.com/saltstack/salt/pull/50150) - Added status code lists and status regex for `http.query` state - [@Ajnbro](https://github.com/Ajnbro) and [@mchugh19](https://github.com/mchugh19)
- [#55150](https://github.com/saltstack/salt/pull/55150) - Added 'ppc64le' as a valid RPM package architecture - [@meaksh](https://github.com/meaksh)
- [#55195](https://github.com/saltstack/salt/pull/55195) - Added `salt_version` module - [@rallytime](https://github.com/rallytime) and [@max-arnold](https://github.com/max-arnold)
- [#55200](https://github.com/saltstack/salt/pull/55200) - Added `virt.pool_deleted` state - [@cbosdo](https://github.com/cbosdo)
- [#55202](https://github.com/saltstack/salt/pull/55202) - Added test ability and pool editing to `virt.pool_running` - [@cbosdo](https://github.com/cbosdo)
- [#55203](https://github.com/saltstack/salt/pull/55203) - Adds enabled kwarg to `aptpkg` module - [@brejoc](https://github.com/brejoc)
- [#55245](https://github.com/saltstack/salt/pull/55245) - Adding kernel boot parameters to libvirt xml - [@ldeweysuse](https://github.com/ldeweysuse)
- [#55256](https://github.com/saltstack/salt/pull/55256) - Added status to dpkg.info response - [@mateiw](https://github.com/mateiw)
- [#55342](https://github.com/saltstack/salt/pull/55342) - Added Slack webhook returner - [@cdalvaro](https://github.com/cdalvaro)
- [#55345](https://github.com/saltstack/salt/pull/55345) - Add chroot apply_, sls, and highstate for state execution - [@aplanas](https://github.com/aplanas)
- [#55346](https://github.com/saltstack/salt/pull/55346) - Added `virt.pool_capabilities` module - [@cbosdo](https://github.com/cbosdo)
- [#55418](https://github.com/saltstack/salt/pull/55418) - Added clean_parent argument for the archive state. - [@Oloremo](https://github.com/Oloremo)
- [#55420](https://github.com/saltstack/salt/pull/55420) - Added performance tracing/logging to gitfs file_list cache rebuild - [@duckfez](https://github.com/duckfez)
- [#55424](https://github.com/saltstack/salt/pull/55424) - Added Azure DNS modules and states - [@nicholasmhughes](https://github.com/nicholasmhughes)
- [#55432](https://github.com/saltstack/salt/pull/55432) - Add null to YAML dumper for threadsafe loader - [@Akm0d](https://github.com/Akm0d)
- [#55443](https://github.com/saltstack/salt/issues/55443) - Added a skip_files_list_verify argument to archive.extracted state. - [@Oloremo](https://github.com/Oloremo)
- [#55448](https://github.com/saltstack/salt/pull/55448) - Adds `downloadonly/download_only` alias for aptpkg module - [@brejoc](https://github.com/brejoc)
- [#55480](https://github.com/saltstack/salt/pull/55480) - Add lint pre-commit hooks - [@s0undt3ch](https://github.com/s0undt3ch)
- [#55492](https://github.com/saltstack/salt/pull/55492) - Allow arbitrary arguments to be passed through the pip module - [@Akm0d](https://github.com/Akm0d)
- [#55506](https://github.com/saltstack/salt/pull/55506) - Added `hashutil.hmac_compute` - [@Ajnbro](https://github.com/Ajnbro)
- [#55515](https://github.com/saltstack/salt/pull/55515) - Added `disk_set` and `disk_toggle` to parted module - [@aplanas](https://github.com/aplanas)
- [#55516](https://github.com/saltstack/salt/pull/55516) - Added `not_change` to several functions in the mount module, `set_fstab` & others - [@aplanas](https://github.com/aplanas)
- [#55565](https://github.com/saltstack/salt/pull/55565) - Added ability to pass the context dictionary to Sminion and Runner - [@s0undt3ch](https://github.com/s0undt3ch)
- [#55590](https://github.com/saltstack/salt/pull/55590) - Added `version` to depends decorator - [@github-abcde](https://github.com/github-abcde)
- [#55593](https://github.com/saltstack/salt/issues/55593) - Added a support for a global proxy to pip module. - [@Oloremo](https://github.com/Oloremo)
- [#55613](https://github.com/saltstack/salt/pull/55613) - Added saltcheck updates for Neon - [@mchugh19](https://github.com/mchugh19)
- [#55636](https://github.com/saltstack/salt/pull/55636) - Added DSON outputter - [@terminalmage](https://github.com/terminalmage)
- [#55637](https://github.com/saltstack/salt/pull/55637) - Added wildcard matches and grains matching to `config.option` - [@terminalmage](https://github.com/terminalmage)
- [#55639](https://github.com/saltstack/salt/pull/55639) - Added `loop.until_no_eval` - [@github-abcde](https://github.com/github-abcde)
- [#55666](https://github.com/saltstack/salt/pull/55666) - Added the `internal` flag to openvswitch - [@Akm0d](https://github.com/Akm0d)
- [#55711](https://github.com/saltstack/salt/pull/55711) - Added `fluentd` engine - [@mchugh19](https://github.com/mchugh19)
- [#55733](https://github.com/saltstack/salt/pull/55733) - Added `salt.utils.data.filter_falsey` - [@github-abcde](https://github.com/github-abcde)
- [#55749](https://github.com/saltstack/salt/pull/55749) - Added port of `json_query` Jinja filter from Ansible - [@max-arnold](https://github.com/max-arnold)
- [#55751](https://github.com/saltstack/salt/pull/55751) - Added the osfullname grain on FreeBSD - [@asomers](https://github.com/asomers)
- [#55759](https://github.com/saltstack/salt/pull/55759) - Added `salt.utils.data.recursive_diff` - [@github-abcde](https://github.com/github-abcde)
- [#55760](https://github.com/saltstack/salt/pull/55760) - Add minion-side access control - [@github-abcde](https://github.com/github-abcde)
- [#55762](https://github.com/saltstack/salt/pull/55762) - Added `virt.(pool|network)_get_xml` functions - [@cbosdo](https://github.com/cbosdo)
- [#55767](https://github.com/saltstack/salt/pull/55767) - Added ability to manipulate RabbitMQ upstream definitions - [@github-abcde](https://github.com/github-abcde)
- [#55768](https://github.com/saltstack/salt/pull/55768) - Added `boto3_elasticsearch` module and state - [@github-abcde](https://github.com/github-abcde)
- [#55844](https://github.com/saltstack/salt/pull/55844) - Allow multiple running instances of Salt engine - [@garethgreenaway](https://github.com/garethgreenaway)

---

## [2019.2.2]

### Changed

- [#54758](https://github.com/saltstack/salt/issues/54758) - Missing sls file during `state.show_states` displays message instead of failing - [@Ch3LL](https://github.com/Ch3LL)

### Fixed

- [#54521](https://github.com/saltstack/salt/issues/54521) - `failhard` during orchestration now fails as expected - [@mattp-](https://github.com/mattp-) / [@Oloremo](https://github.com/Oloremo)
- [#54741](https://github.com/saltstack/salt/issues/54741) - `schedule.run_job` without time element now works as expected - [@garethgreenaway](https://github.com/garethgreenaway)
- [#54755](https://github.com/saltstack/salt/issues/54755) - Pip state ensures pip was imported before trying to remove - [@dwoz](https://github.com/dwoz)
- [#54760](https://github.com/saltstack/salt/issues/54760) - Fix `salt-cloud -Q` for OpenStack driver - [@vdloo](https://github.com/vdloo) / [@Akm0d](https://github.com/Akm0d)
- [#54762](https://github.com/saltstack/salt/issues/54762) - IPv6 addresses with brackets no longer break master/minion communication - [@dhiltonp](https://github.com/dhiltonp)
- [#54765](https://github.com/saltstack/salt/issues/54765) - Masterless jinja imports - [@dwoz](https://github.com/dwoz)
- [#54776](https://github.com/saltstack/salt/issues/54776) - `ping_interval` in minion config no longer prevents startup - [@dwoz](https://github.com/dwoz)
- [#54820](https://github.com/saltstack/salt/issues/54820) - `scheduler.present` no longer always reports changes when scheduler is disabled - [@garethgreenaway](https://github.com/garethgreenaway)
- [#54941](https://github.com/saltstack/salt/issues/54941) - Pillar data is no longer refreshed on every call - [@dwoz](https://github.com/dwoz)


### Added

- [#54919](https://github.com/saltstack/salt/pull/54919) - Added missing `win_wusa` state and module docs - [@twangboy](https://github.com/twangboy)

## [2019.2.1] - 2019-09-25 [YANKED]


- See [old release notes](https://docs.saltstack.com/en/latest/topics/releases/2019.2.1.html)
