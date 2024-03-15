All notable changes to Salt will be documented in this file.

This changelog follows [keepachangelog](https://keepachangelog.com/en/1.0.0/) format, and is intended for human consumption.

This project versioning is _similar_ to [Semantic Versioning](https://semver.org), and is documented in [SEP 14](https://github.com/saltstack/salt-enhancement-proposals/pull/20/files).
Versions are `MAJOR.PATCH`.

# Changelog

## 3007.0 (2024-03-03)


### Removed

- Removed RHEL 5 support since long since end-of-lifed [#62520](https://github.com/saltstack/salt/issues/62520)
- Removing Azure-Cloud modules from the code base. [#64322](https://github.com/saltstack/salt/issues/64322)
- Dropped Python 3.7 support since it's EOL in 27 Jun 2023 [#64417](https://github.com/saltstack/salt/issues/64417)
- Remove salt.payload.Serial [#64459](https://github.com/saltstack/salt/issues/64459)
- Remove netmiko_conn and pyeapi_conn from salt.modules.napalm_mod [#64460](https://github.com/saltstack/salt/issues/64460)
- Removed 'transport' arg from salt.utils.event.get_event [#64461](https://github.com/saltstack/salt/issues/64461)
- Removed the usage of retired Linode API v3 from Salt Cloud [#64517](https://github.com/saltstack/salt/issues/64517)


### Deprecated

- Deprecate all Proxmox cloud modules [#64224](https://github.com/saltstack/salt/issues/64224)
- Deprecate all the Vault modules in favor of the Vault Salt Extension https://github.com/salt-extensions/saltext-vault. The Vault modules will be removed in Salt core in 3009.0. [#64893](https://github.com/saltstack/salt/issues/64893)
- Deprecate all the Docker modules in favor of the Docker Salt Extension https://github.com/saltstack/saltext-docker. The Docker modules will be removed in Salt core in 3009.0. [#64894](https://github.com/saltstack/salt/issues/64894)
- Deprecate all the Zabbix modules in favor of the Zabbix Salt Extension https://github.com/salt-extensions/saltext-zabbix. The Zabbix modules will be removed in Salt core in 3009.0. [#64896](https://github.com/saltstack/salt/issues/64896)
- Deprecate all the Apache modules in favor of the Apache Salt Extension https://github.com/salt-extensions/saltext-apache. The Apache modules will be removed in Salt core in 3009.0. [#64909](https://github.com/saltstack/salt/issues/64909)
- Deprecation warning for Salt's backport of ``OrderedDict`` class which will be removed in 3009 [#65542](https://github.com/saltstack/salt/issues/65542)
- Deprecate Kubernetes modules for move to saltext-kubernetes in version 3009 [#65565](https://github.com/saltstack/salt/issues/65565)
- Deprecated all Pushover modules in favor of the Salt Extension at https://github.com/salt-extensions/saltext-pushover. The Pushover modules will be removed from Salt core in 3009.0 [#65567](https://github.com/saltstack/salt/issues/65567)
- Removed deprecated code:

  * All of ``salt/log/`` which has been on a deprecation path for a long time.
  * Some of the logging handlers found in ``salt/_logging/handlers`` have been removed since the standard library provides
    them.
  * Removed the deprecated ``salt/modules/cassandra_mod.py`` module and any tests for it.
  * Removed the deprecated ``salt/returners/cassandra_return.py`` module and any tests for it.
  * Removed the deprecated ``salt/returners/django_return.py`` module and any tests for it. [#65986](https://github.com/saltstack/salt/issues/65986)


### Changed

- Masquerade property will not default to false turning off masquerade if not specified. [#53120](https://github.com/saltstack/salt/issues/53120)
- Addressed Python 3.11 deprecations:

  * Switch to `FullArgSpec` since Py 3.11 no longer has `ArgSpec`, deprecated since Py 3.0
  * Stopped using the deprecated `cgi` module.
  * Stopped using the deprecated `pipes` module
  * Stopped using the deprecated `imp` module [#64457](https://github.com/saltstack/salt/issues/64457)
- changed 'gpg_decrypt_must_succeed' default from False to True [#64462](https://github.com/saltstack/salt/issues/64462)


### Fixed

- When an NFS or FUSE mount fails to unmount when mount options have changed, try again with a lazy umount before mounting again. [#18907](https://github.com/saltstack/salt/issues/18907)
- fix autoaccept gpg keys by supporting it in refresh_db module [#42039](https://github.com/saltstack/salt/issues/42039)
- Made cmd.script work with files from the fileserver via salt-ssh [#48067](https://github.com/saltstack/salt/issues/48067)
- Made slsutil.renderer work with salt-ssh [#50196](https://github.com/saltstack/salt/issues/50196)
- Fixed defaults.merge is not available when using salt-ssh [#51605](https://github.com/saltstack/salt/issues/51605)
- Fix extfs.mkfs missing parameter handling for -C, -d, and -e [#51858](https://github.com/saltstack/salt/issues/51858)
- Fixed Salt master does not renew token [#51986](https://github.com/saltstack/salt/issues/51986)
- Fixed salt-ssh continues state/pillar rendering with incorrect data when an exception is raised by a module on the target [#52452](https://github.com/saltstack/salt/issues/52452)
- Fix extfs.tune has 'reserved' documented twice and is missing the 'reserved_percentage' keyword argument [#54426](https://github.com/saltstack/salt/issues/54426)
- Fix the ability of the 'selinux.port_policy_present' state to modify. [#55687](https://github.com/saltstack/salt/issues/55687)
- Fixed config.get does not support merge option with salt-ssh [#56441](https://github.com/saltstack/salt/issues/56441)
- Removed an unused assignment in file.patch [#57204](https://github.com/saltstack/salt/issues/57204)
- Fixed vault module fetching more than one secret in one run with single-use tokens [#57561](https://github.com/saltstack/salt/issues/57561)
- Use brew path from which in mac_brew_pkg module and rely on _homebrew_bin() everytime [#57946](https://github.com/saltstack/salt/issues/57946)
- Fixed Vault verify option to work on minions when only specified in master config [#58174](https://github.com/saltstack/salt/issues/58174)
- Fixed vault command errors configured locally [#58580](https://github.com/saltstack/salt/issues/58580)
- Fixed issue with basic auth causing invalid header error and 401 Bad Request, by using HTTPBasicAuthHandler instead of header. [#58936](https://github.com/saltstack/salt/issues/58936)
- Make the LXD module work with pyLXD > 2.10 [#59514](https://github.com/saltstack/salt/issues/59514)
- Return error if patch file passed to state file.patch is malformed. [#59806](https://github.com/saltstack/salt/issues/59806)
- Handle failure and error information from tuned module/state [#60500](https://github.com/saltstack/salt/issues/60500)
- Fixed sdb.get_or_set_hash with Vault single-use tokens [#60779](https://github.com/saltstack/salt/issues/60779)
- Fixed state.test does not work with salt-ssh [#61100](https://github.com/saltstack/salt/issues/61100)
- Made slsutil.findup work with salt-ssh [#61143](https://github.com/saltstack/salt/issues/61143)
- Allow all primitive grain types for autosign_grains [#61416](https://github.com/saltstack/salt/issues/61416), [#63708](https://github.com/saltstack/salt/issues/63708)
- `ipset.new_set` no longer fails when creating a set type that uses the `family` create option [#61620](https://github.com/saltstack/salt/issues/61620)
- Fixed Vault session storage to allow unlimited use tokens [#62380](https://github.com/saltstack/salt/issues/62380)
- fix the efi grain on FreeBSD [#63052](https://github.com/saltstack/salt/issues/63052)
- Fixed gpg.receive_keys returns success on failed import [#63144](https://github.com/saltstack/salt/issues/63144)
- Fixed GPG state module always reports success without changes [#63153](https://github.com/saltstack/salt/issues/63153)
- Fixed GPG state module does not respect test mode [#63156](https://github.com/saltstack/salt/issues/63156)
- Fixed gpg.absent with gnupghome/user, fixed gpg.delete_key with gnupghome [#63159](https://github.com/saltstack/salt/issues/63159)
- Fixed service module does not handle enable/disable if systemd service is an alias [#63214](https://github.com/saltstack/salt/issues/63214)
- Made x509_v2 compound match detection use new runner instead of peer publishing [#63278](https://github.com/saltstack/salt/issues/63278)
- Need to make sure we update __pillar__ during a pillar refresh to ensure that process_beacons has the updated beacons loaded from pillar. [#63583](https://github.com/saltstack/salt/issues/63583)
- This implements the vpc_uuid parameter when creating a droplet. This parameter selects the correct virtual private cloud (private network interface). [#63714](https://github.com/saltstack/salt/issues/63714)
- pkg.installed no longer reports failure when installing packages that are installed via the task manager [#63767](https://github.com/saltstack/salt/issues/63767)
- mac_xattr.list and mac_xattr.read will replace undecode-able bytes to avoid raising CommandExecutionError. [#63779](https://github.com/saltstack/salt/issues/63779) [#63779](https://github.com/saltstack/salt/issues/63779)
- Fix aptpkg.latest_version performance, reducing number of times to 'shell out' [#63982](https://github.com/saltstack/salt/issues/63982)
- Added option to use a fresh connection for mysql cache [#63991](https://github.com/saltstack/salt/issues/63991)
- [lxd] Fixed a bug in `container_create` which prevented devices which are not of type `disk` to be correctly created and added to the container when passed via the `devices` parameter. [#63996](https://github.com/saltstack/salt/issues/63996)
- Skipped the `isfile` check to greatly increase speed of reading minion keys for systems with a large number of minions on slow file storage [#64260](https://github.com/saltstack/salt/issues/64260)
- Fix utf8 handling in 'pass' renderer [#64300](https://github.com/saltstack/salt/issues/64300)
- Upgade tornado to 6.3.2 [#64305](https://github.com/saltstack/salt/issues/64305)
- Prevent errors due missing 'transactional_update.apply' on SLE Micro and MicroOS. [#64369](https://github.com/saltstack/salt/issues/64369)
- Fix 'unable to unmount' failure to return False result instead of None [#64420](https://github.com/saltstack/salt/issues/64420)
- Fixed issue uninstalling duplicate packages in ``win_appx`` execution module [#64450](https://github.com/saltstack/salt/issues/64450)
- Clean up tech debt, IPC now uses tcp transport. [#64488](https://github.com/saltstack/salt/issues/64488)
- Made salt-ssh more strict when handling unexpected situations and state.* wrappers treat a remote exception as failure, excluded salt-ssh error returns from mine [#64531](https://github.com/saltstack/salt/issues/64531)
- Fix flaky test for LazyLoader with isolated mocking of threading.RLock [#64567](https://github.com/saltstack/salt/issues/64567)
- Fix possible `KeyError` exceptions in `salt.utils.user.get_group_dict`
  while reading improper duplicated GID assigned for the user. [#64599](https://github.com/saltstack/salt/issues/64599)
- changed vm_config() to deep-merge vm_overrides of specific VM, instead of simple-merging the whole vm_overrides [#64610](https://github.com/saltstack/salt/issues/64610)
- Fix the way Salt tries to get the Homebrew's prefix

  The first attempt to get the Homebrew's prefix is to look for
  the `HOMEBREW_PREFIX` environment variable. If it's not set, then
  Salt tries to get the prefix from the `brew` command. However, the
  `brew` command can fail. So a last attempt is made to get the
  prefix by guessing the installation path. [#64924](https://github.com/saltstack/salt/issues/64924)
- Add missing MySQL Grant SERVICE_CONNECTION_ADMIN to mysql module. [#64934](https://github.com/saltstack/salt/issues/64934)
- Fixed slsutil.update with salt-ssh during template rendering [#65067](https://github.com/saltstack/salt/issues/65067)
- Keep track when an included file only includes sls files but is a requisite. [#65080](https://github.com/saltstack/salt/issues/65080)
- Fixed `gpg.present` succeeds when the keyserver is unreachable [#65169](https://github.com/saltstack/salt/issues/65169)
- Fix typo in nftables module to ensure unique nft family values [#65295](https://github.com/saltstack/salt/issues/65295)
- Dereference symlinks to set proper __cli opt [#65435](https://github.com/saltstack/salt/issues/65435)
- Made salt-ssh merge master top returns for the same environment [#65480](https://github.com/saltstack/salt/issues/65480)
- Account for situation where the metadata grain fails because the AWS environment requires an authentication token to query the metadata URL. [#65513](https://github.com/saltstack/salt/issues/65513)
- Improve the condition of overriding target for pip with VENV_PIP_TARGET environment variable. [#65562](https://github.com/saltstack/salt/issues/65562)
- Added SSH wrapper for logmod [#65630](https://github.com/saltstack/salt/issues/65630)
- Include changes in the results when schedule.present state is run with test=True. [#65652](https://github.com/saltstack/salt/issues/65652)
- Fix extfs.tune doesn't pass retcode to module.run [#65686](https://github.com/saltstack/salt/issues/65686)
- Return an error message when the DNS plugin is not supported [#65739](https://github.com/saltstack/salt/issues/65739)
- Execution modules have access to regular fileclient durring pillar rendering. [#66124](https://github.com/saltstack/salt/issues/66124)
- Fixed a issue with server channel where a minion's public key
  would be rejected if it contained a final newline character. [#66126](https://github.com/saltstack/salt/issues/66126)


### Added

- Allowed publishing to regular minions from the SSH wrapper [#40943](https://github.com/saltstack/salt/issues/40943)
- Added syncing of custom salt-ssh wrappers [#45450](https://github.com/saltstack/salt/issues/45450)
- Made salt-ssh sync custom utils [#53666](https://github.com/saltstack/salt/issues/53666)
- Add ability to use file.managed style check_cmd in file.serialize [#53982](https://github.com/saltstack/salt/issues/53982)
- Revised use of deprecated net-tools and added support for ip neighbour with IPv4 ip_neighs, IPv6 ip_neighs6 [#57541](https://github.com/saltstack/salt/issues/57541)
- Added password support to Redis returner. [#58044](https://github.com/saltstack/salt/issues/58044)
- Added a state (win_task) for managing scheduled tasks on Windows [#59037](https://github.com/saltstack/salt/issues/59037)
- Added keyring param to gpg modules [#59783](https://github.com/saltstack/salt/issues/59783)
- Added new grain to detect the Salt package type: onedir, pip or system [#62589](https://github.com/saltstack/salt/issues/62589)
- Added Vault AppRole and identity issuance to minions [#62823](https://github.com/saltstack/salt/issues/62823)
- Added Vault AppRole auth mount path configuration option [#62825](https://github.com/saltstack/salt/issues/62825)
- Added distribution of Vault authentication details via response wrapping [#62828](https://github.com/saltstack/salt/issues/62828)
- Add salt package type information. Either onedir, pip or system. [#62961](https://github.com/saltstack/salt/issues/62961)
- Added signature verification to file.managed/archive.extracted [#63143](https://github.com/saltstack/salt/issues/63143)
- Added signed_by_any/signed_by_all parameters to gpg.verify [#63166](https://github.com/saltstack/salt/issues/63166)
- Added match runner [#63278](https://github.com/saltstack/salt/issues/63278)
- Added Vault token lifecycle management [#63406](https://github.com/saltstack/salt/issues/63406)
- adding new call for openscap xccdf eval supporting new parameters [#63416](https://github.com/saltstack/salt/issues/63416)
- Added Vault lease management utility [#63440](https://github.com/saltstack/salt/issues/63440)
- implement removal of ptf packages in zypper pkg module [#63442](https://github.com/saltstack/salt/issues/63442)
- add JUnit output for saltcheck [#63463](https://github.com/saltstack/salt/issues/63463)
- Add ability for file.keyvalue to create a file if it doesn't exist [#63545](https://github.com/saltstack/salt/issues/63545)
- added cleanup of temporary mountpoint dir for macpackage installed state [#63905](https://github.com/saltstack/salt/issues/63905)
- Add pkg.installed show installable version in test mode [#63985](https://github.com/saltstack/salt/issues/63985)
- Added patch option to Vault SDB driver [#64096](https://github.com/saltstack/salt/issues/64096)
- Added flags to create local users and groups [#64256](https://github.com/saltstack/salt/issues/64256)
- Added inline specification of trusted CA root certificate for Vault [#64379](https://github.com/saltstack/salt/issues/64379)
- Add ability to return False result in test mode of configurable_test_state [#64418](https://github.com/saltstack/salt/issues/64418)
- Switched Salt's onedir Python version to 3.11 [#64457](https://github.com/saltstack/salt/issues/64457)
- Added support for dnf5 and its new command syntax [#64532](https://github.com/saltstack/salt/issues/64532)
- Adding a new decorator to indicate when a module is deprecated in favor of a Salt extension. [#64569](https://github.com/saltstack/salt/issues/64569)
- Add jq-esque to_entries and from_entries functions [#64600](https://github.com/saltstack/salt/issues/64600)
- Added ability to use PYTHONWARNINGS=ignore to silence deprecation warnings. [#64660](https://github.com/saltstack/salt/issues/64660)
- Add follow_symlinks to file.symlink exec module to switch to os.path.lexists when False [#64665](https://github.com/saltstack/salt/issues/64665)
- Strenghten Salt's HA capabilities with master clustering. [#64939](https://github.com/saltstack/salt/issues/64939)
- Added win_appx state and execution modules for managing Microsoft Store apps and deprovisioning them from systems [#64978](https://github.com/saltstack/salt/issues/64978)
- Add support for show_jid to salt-run

  Adds support for show_jid master config option to salt-run, so its behaviour matches the salt cli command. [#65008](https://github.com/saltstack/salt/issues/65008)
- Add ability to remove packages by wildcard via apt execution module [#65220](https://github.com/saltstack/salt/issues/65220)
- Added support for master top modules on masterless minions [#65479](https://github.com/saltstack/salt/issues/65479)
- Allowed accessing the regular mine from the SSH wrapper [#65645](https://github.com/saltstack/salt/issues/65645)
- Allow enabling backup for Linode in Salt Cloud [#65697](https://github.com/saltstack/salt/issues/65697)
- Add a backup schedule setter fFunction for Linode VMs [#65713](https://github.com/saltstack/salt/issues/65713)
- Add acme support for manual plugin hooks [#65744](https://github.com/saltstack/salt/issues/65744)


### Security

- Upgrade to `tornado>=6.3.3` due to https://github.com/advisories/GHSA-qppv-j76h-2rpx [#64989](https://github.com/saltstack/salt/issues/64989)
- Update to `gitpython>=3.1.35` due to https://github.com/advisories/GHSA-wfm5-v35h-vwf4 and https://github.com/advisories/GHSA-cwvm-v4w8-q58c [#65137](https://github.com/saltstack/salt/issues/65137)


## 3007.0rc1 (2024-01-02)


### Removed

- Removed RHEL 5 support since long since end-of-lifed [#62520](https://github.com/saltstack/salt/issues/62520)
- Removing Azure-Cloud modules from the code base. [#64322](https://github.com/saltstack/salt/issues/64322)
- Dropped Python 3.7 support since it's EOL in 27 Jun 2023 [#64417](https://github.com/saltstack/salt/issues/64417)
- Remove salt.payload.Serial [#64459](https://github.com/saltstack/salt/issues/64459)
- Remove netmiko_conn and pyeapi_conn from salt.modules.napalm_mod [#64460](https://github.com/saltstack/salt/issues/64460)
- Removed 'transport' arg from salt.utils.event.get_event [#64461](https://github.com/saltstack/salt/issues/64461)
- Removed the usage of retired Linode API v3 from Salt Cloud [#64517](https://github.com/saltstack/salt/issues/64517)


### Deprecated

- Deprecate all Proxmox cloud modules [#64224](https://github.com/saltstack/salt/issues/64224)
- Deprecate all the Vault modules in favor of the Vault Salt Extension https://github.com/salt-extensions/saltext-vault. The Vault modules will be removed in Salt core in 3009.0. [#64893](https://github.com/saltstack/salt/issues/64893)
- Deprecate all the Docker modules in favor of the Docker Salt Extension https://github.com/saltstack/saltext-docker. The Docker modules will be removed in Salt core in 3009.0. [#64894](https://github.com/saltstack/salt/issues/64894)
- Deprecate all the Zabbix modules in favor of the Zabbix Salt Extension https://github.com/salt-extensions/saltext-zabbix. The Zabbix modules will be removed in Salt core in 3009.0. [#64896](https://github.com/saltstack/salt/issues/64896)
- Deprecate all the Apache modules in favor of the Apache Salt Extension https://github.com/salt-extensions/saltext-apache. The Apache modules will be removed in Salt core in 3009.0. [#64909](https://github.com/saltstack/salt/issues/64909)
- Deprecation warning for Salt's backport of ``OrderedDict`` class which will be removed in 3009 [#65542](https://github.com/saltstack/salt/issues/65542)
- Deprecate Kubernetes modules for move to saltext-kubernetes in version 3009 [#65565](https://github.com/saltstack/salt/issues/65565)
- Deprecated all Pushover modules in favor of the Salt Extension at https://github.com/salt-extensions/saltext-pushover. The Pushover modules will be removed from Salt core in 3009.0 [#65567](https://github.com/saltstack/salt/issues/65567)


### Changed

- Masquerade property will not default to false turning off masquerade if not specified. [#53120](https://github.com/saltstack/salt/issues/53120)
- Addressed Python 3.11 deprecations:

  * Switch to `FullArgSpec` since Py 3.11 no longer has `ArgSpec`, deprecated since Py 3.0
  * Stopped using the deprecated `cgi` module.
  * Stopped using the deprecated `pipes` module
  * Stopped using the deprecated `imp` module [#64457](https://github.com/saltstack/salt/issues/64457)
- changed 'gpg_decrypt_must_succeed' default from False to True [#64462](https://github.com/saltstack/salt/issues/64462)


### Fixed

- When an NFS or FUSE mount fails to unmount when mount options have changed, try again with a lazy umount before mounting again. [#18907](https://github.com/saltstack/salt/issues/18907)
- fix autoaccept gpg keys by supporting it in refresh_db module [#42039](https://github.com/saltstack/salt/issues/42039)
- Made cmd.script work with files from the fileserver via salt-ssh [#48067](https://github.com/saltstack/salt/issues/48067)
- Made slsutil.renderer work with salt-ssh [#50196](https://github.com/saltstack/salt/issues/50196)
- Fixed defaults.merge is not available when using salt-ssh [#51605](https://github.com/saltstack/salt/issues/51605)
- Fix extfs.mkfs missing parameter handling for -C, -d, and -e [#51858](https://github.com/saltstack/salt/issues/51858)
- Fixed Salt master does not renew token [#51986](https://github.com/saltstack/salt/issues/51986)
- Fixed salt-ssh continues state/pillar rendering with incorrect data when an exception is raised by a module on the target [#52452](https://github.com/saltstack/salt/issues/52452)
- Fix extfs.tune has 'reserved' documented twice and is missing the 'reserved_percentage' keyword argument [#54426](https://github.com/saltstack/salt/issues/54426)
- Fix the ability of the 'selinux.port_policy_present' state to modify. [#55687](https://github.com/saltstack/salt/issues/55687)
- Fixed config.get does not support merge option with salt-ssh [#56441](https://github.com/saltstack/salt/issues/56441)
- Removed an unused assignment in file.patch [#57204](https://github.com/saltstack/salt/issues/57204)
- Fixed vault module fetching more than one secret in one run with single-use tokens [#57561](https://github.com/saltstack/salt/issues/57561)
- Use brew path from which in mac_brew_pkg module and rely on _homebrew_bin() everytime [#57946](https://github.com/saltstack/salt/issues/57946)
- Fixed Vault verify option to work on minions when only specified in master config [#58174](https://github.com/saltstack/salt/issues/58174)
- Fixed vault command errors configured locally [#58580](https://github.com/saltstack/salt/issues/58580)
- Fixed issue with basic auth causing invalid header error and 401 Bad Request, by using HTTPBasicAuthHandler instead of header. [#58936](https://github.com/saltstack/salt/issues/58936)
- Make the LXD module work with pyLXD > 2.10 [#59514](https://github.com/saltstack/salt/issues/59514)
- Return error if patch file passed to state file.patch is malformed. [#59806](https://github.com/saltstack/salt/issues/59806)
- Handle failure and error information from tuned module/state [#60500](https://github.com/saltstack/salt/issues/60500)
- Fixed sdb.get_or_set_hash with Vault single-use tokens [#60779](https://github.com/saltstack/salt/issues/60779)
- Fixed state.test does not work with salt-ssh [#61100](https://github.com/saltstack/salt/issues/61100)
- Made slsutil.findup work with salt-ssh [#61143](https://github.com/saltstack/salt/issues/61143)
- Allow all primitive grain types for autosign_grains [#61416](https://github.com/saltstack/salt/issues/61416), [#63708](https://github.com/saltstack/salt/issues/63708)
- `ipset.new_set` no longer fails when creating a set type that uses the `family` create option [#61620](https://github.com/saltstack/salt/issues/61620)
- Fixed Vault session storage to allow unlimited use tokens [#62380](https://github.com/saltstack/salt/issues/62380)
- fix the efi grain on FreeBSD [#63052](https://github.com/saltstack/salt/issues/63052)
- Fixed gpg.receive_keys returns success on failed import [#63144](https://github.com/saltstack/salt/issues/63144)
- Fixed GPG state module always reports success without changes [#63153](https://github.com/saltstack/salt/issues/63153)
- Fixed GPG state module does not respect test mode [#63156](https://github.com/saltstack/salt/issues/63156)
- Fixed gpg.absent with gnupghome/user, fixed gpg.delete_key with gnupghome [#63159](https://github.com/saltstack/salt/issues/63159)
- Fixed service module does not handle enable/disable if systemd service is an alias [#63214](https://github.com/saltstack/salt/issues/63214)
- Made x509_v2 compound match detection use new runner instead of peer publishing [#63278](https://github.com/saltstack/salt/issues/63278)
- Need to make sure we update __pillar__ during a pillar refresh to ensure that process_beacons has the updated beacons loaded from pillar. [#63583](https://github.com/saltstack/salt/issues/63583)
- This implements the vpc_uuid parameter when creating a droplet. This parameter selects the correct virtual private cloud (private network interface). [#63714](https://github.com/saltstack/salt/issues/63714)
- pkg.installed no longer reports failure when installing packages that are installed via the task manager [#63767](https://github.com/saltstack/salt/issues/63767)
- mac_xattr.list and mac_xattr.read will replace undecode-able bytes to avoid raising CommandExecutionError. [#63779](https://github.com/saltstack/salt/issues/63779) [#63779](https://github.com/saltstack/salt/issues/63779)
- Fix aptpkg.latest_version performance, reducing number of times to 'shell out' [#63982](https://github.com/saltstack/salt/issues/63982)
- Added option to use a fresh connection for mysql cache [#63991](https://github.com/saltstack/salt/issues/63991)
- [lxd] Fixed a bug in `container_create` which prevented devices which are not of type `disk` to be correctly created and added to the container when passed via the `devices` parameter. [#63996](https://github.com/saltstack/salt/issues/63996)
- Skipped the `isfile` check to greatly increase speed of reading minion keys for systems with a large number of minions on slow file storage [#64260](https://github.com/saltstack/salt/issues/64260)
- Fix utf8 handling in 'pass' renderer [#64300](https://github.com/saltstack/salt/issues/64300)
- Upgade tornado to 6.3.2 [#64305](https://github.com/saltstack/salt/issues/64305)
- Prevent errors due missing 'transactional_update.apply' on SLE Micro and MicroOS. [#64369](https://github.com/saltstack/salt/issues/64369)
- Fix 'unable to unmount' failure to return False result instead of None [#64420](https://github.com/saltstack/salt/issues/64420)
- Fixed issue uninstalling duplicate packages in ``win_appx`` execution module [#64450](https://github.com/saltstack/salt/issues/64450)
- Clean up tech debt, IPC now uses tcp transport. [#64488](https://github.com/saltstack/salt/issues/64488)
- Made salt-ssh more strict when handling unexpected situations and state.* wrappers treat a remote exception as failure, excluded salt-ssh error returns from mine [#64531](https://github.com/saltstack/salt/issues/64531)
- Fix flaky test for LazyLoader with isolated mocking of threading.RLock [#64567](https://github.com/saltstack/salt/issues/64567)
- Fix possible `KeyError` exceptions in `salt.utils.user.get_group_dict`
  while reading improper duplicated GID assigned for the user. [#64599](https://github.com/saltstack/salt/issues/64599)
- changed vm_config() to deep-merge vm_overrides of specific VM, instead of simple-merging the whole vm_overrides [#64610](https://github.com/saltstack/salt/issues/64610)
- Fix the way Salt tries to get the Homebrew's prefix

  The first attempt to get the Homebrew's prefix is to look for
  the `HOMEBREW_PREFIX` environment variable. If it's not set, then
  Salt tries to get the prefix from the `brew` command. However, the
  `brew` command can fail. So a last attempt is made to get the
  prefix by guessing the installation path. [#64924](https://github.com/saltstack/salt/issues/64924)
- Add missing MySQL Grant SERVICE_CONNECTION_ADMIN to mysql module. [#64934](https://github.com/saltstack/salt/issues/64934)
- Fixed slsutil.update with salt-ssh during template rendering [#65067](https://github.com/saltstack/salt/issues/65067)
- Keep track when an included file only includes sls files but is a requisite. [#65080](https://github.com/saltstack/salt/issues/65080)
- Fixed `gpg.present` succeeds when the keyserver is unreachable [#65169](https://github.com/saltstack/salt/issues/65169)
- Fix issue with openscap when the error was outside the expected scope. It now
  returns failed with the error code and the error [#65193](https://github.com/saltstack/salt/issues/65193)
- Fix typo in nftables module to ensure unique nft family values [#65295](https://github.com/saltstack/salt/issues/65295)
- Dereference symlinks to set proper __cli opt [#65435](https://github.com/saltstack/salt/issues/65435)
- Made salt-ssh merge master top returns for the same environment [#65480](https://github.com/saltstack/salt/issues/65480)
- Account for situation where the metadata grain fails because the AWS environment requires an authentication token to query the metadata URL. [#65513](https://github.com/saltstack/salt/issues/65513)
- Improve the condition of overriding target for pip with VENV_PIP_TARGET environment variable. [#65562](https://github.com/saltstack/salt/issues/65562)
- Added SSH wrapper for logmod [#65630](https://github.com/saltstack/salt/issues/65630)
- Include changes in the results when schedule.present state is run with test=True. [#65652](https://github.com/saltstack/salt/issues/65652)
- Fixed Salt-SSH pillar rendering and state rendering with nested SSH calls when called via saltutil.cmd or in an orchestration [#65670](https://github.com/saltstack/salt/issues/65670)
- Fix extfs.tune doesn't pass retcode to module.run [#65686](https://github.com/saltstack/salt/issues/65686)
- Fix boto execution module loading [#65691](https://github.com/saltstack/salt/issues/65691)
- Removed PR 65185 changes since incomplete solution [#65692](https://github.com/saltstack/salt/issues/65692)
- Return an error message when the DNS plugin is not supported [#65739](https://github.com/saltstack/salt/issues/65739)


### Added

- Allowed publishing to regular minions from the SSH wrapper [#40943](https://github.com/saltstack/salt/issues/40943)
- Added syncing of custom salt-ssh wrappers [#45450](https://github.com/saltstack/salt/issues/45450)
- Made salt-ssh sync custom utils [#53666](https://github.com/saltstack/salt/issues/53666)
- Add ability to use file.managed style check_cmd in file.serialize [#53982](https://github.com/saltstack/salt/issues/53982)
- Revised use of deprecated net-tools and added support for ip neighbour with IPv4 ip_neighs, IPv6 ip_neighs6 [#57541](https://github.com/saltstack/salt/issues/57541)
- Added password support to Redis returner. [#58044](https://github.com/saltstack/salt/issues/58044)
- Added keyring param to gpg modules [#59783](https://github.com/saltstack/salt/issues/59783)
- Added new grain to detect the Salt package type: onedir, pip or system [#62589](https://github.com/saltstack/salt/issues/62589)
- Added Vault AppRole and identity issuance to minions [#62823](https://github.com/saltstack/salt/issues/62823)
- Added Vault AppRole auth mount path configuration option [#62825](https://github.com/saltstack/salt/issues/62825)
- Added distribution of Vault authentication details via response wrapping [#62828](https://github.com/saltstack/salt/issues/62828)
- Add salt package type information. Either onedir, pip or system. [#62961](https://github.com/saltstack/salt/issues/62961)
- Added signature verification to file.managed/archive.extracted [#63143](https://github.com/saltstack/salt/issues/63143)
- Added signed_by_any/signed_by_all parameters to gpg.verify [#63166](https://github.com/saltstack/salt/issues/63166)
- Added match runner [#63278](https://github.com/saltstack/salt/issues/63278)
- Added Vault token lifecycle management [#63406](https://github.com/saltstack/salt/issues/63406)
- adding new call for openscap xccdf eval supporting new parameters [#63416](https://github.com/saltstack/salt/issues/63416)
- Added Vault lease management utility [#63440](https://github.com/saltstack/salt/issues/63440)
- implement removal of ptf packages in zypper pkg module [#63442](https://github.com/saltstack/salt/issues/63442)
- add JUnit output for saltcheck [#63463](https://github.com/saltstack/salt/issues/63463)
- Add ability for file.keyvalue to create a file if it doesn't exist [#63545](https://github.com/saltstack/salt/issues/63545)
- added cleanup of temporary mountpoint dir for macpackage installed state [#63905](https://github.com/saltstack/salt/issues/63905)
- Add pkg.installed show installable version in test mode [#63985](https://github.com/saltstack/salt/issues/63985)
- Added patch option to Vault SDB driver [#64096](https://github.com/saltstack/salt/issues/64096)
- Added flags to create local users and groups [#64256](https://github.com/saltstack/salt/issues/64256)
- Added inline specification of trusted CA root certificate for Vault [#64379](https://github.com/saltstack/salt/issues/64379)
- Add ability to return False result in test mode of configurable_test_state [#64418](https://github.com/saltstack/salt/issues/64418)
- Switched Salt's onedir Python version to 3.11 [#64457](https://github.com/saltstack/salt/issues/64457)
- Added support for dnf5 and its new command syntax [#64532](https://github.com/saltstack/salt/issues/64532)
- Adding a new decorator to indicate when a module is deprecated in favor of a Salt extension. [#64569](https://github.com/saltstack/salt/issues/64569)
- Add jq-esque to_entries and from_entries functions [#64600](https://github.com/saltstack/salt/issues/64600)
- Added ability to use PYTHONWARNINGS=ignore to silence deprecation warnings. [#64660](https://github.com/saltstack/salt/issues/64660)
- Add follow_symlinks to file.symlink exec module to switch to os.path.lexists when False [#64665](https://github.com/saltstack/salt/issues/64665)
- Added win_appx state and execution modules for managing Microsoft Store apps and deprovisioning them from systems [#64978](https://github.com/saltstack/salt/issues/64978)
- Add support for show_jid to salt-run

  Adds support for show_jid master config option to salt-run, so its behaviour matches the salt cli command. [#65008](https://github.com/saltstack/salt/issues/65008)
- Add ability to remove packages by wildcard via apt execution module [#65220](https://github.com/saltstack/salt/issues/65220)
- Added support for master top modules on masterless minions [#65479](https://github.com/saltstack/salt/issues/65479)
- Allowed accessing the regular mine from the SSH wrapper [#65645](https://github.com/saltstack/salt/issues/65645)
- Allow enabling backup for Linode in Salt Cloud [#65697](https://github.com/saltstack/salt/issues/65697)
- Add a backup schedule setter fFunction for Linode VMs [#65713](https://github.com/saltstack/salt/issues/65713)
- Add acme support for manual plugin hooks [#65744](https://github.com/saltstack/salt/issues/65744)


### Security

- Upgrade to `tornado>=6.3.3` due to https://github.com/advisories/GHSA-qppv-j76h-2rpx [#64989](https://github.com/saltstack/salt/issues/64989)
- Update to `gitpython>=3.1.35` due to https://github.com/advisories/GHSA-wfm5-v35h-vwf4 and https://github.com/advisories/GHSA-cwvm-v4w8-q58c [#65137](https://github.com/saltstack/salt/issues/65137)


## 3006.7 (2024-02-20)


### Deprecated

- Deprecate and stop using ``salt.features`` [#65951](https://github.com/saltstack/salt/issues/65951)


### Changed

- Change module search path priority, so Salt extensions can be overridden by syncable modules and module_dirs. You can switch back to the old logic by setting features.enable_deprecated_module_search_path_priority to true, but it will be removed in Salt 3008. [#65938](https://github.com/saltstack/salt/issues/65938)


### Fixed

- Fix an issue with mac_shadow that was causing a command execution error when
  retrieving values that were not yet set. For example, retrieving last login
  before the user had logged in. [#34658](https://github.com/saltstack/salt/issues/34658)
- Fixed an issue when keys didn't match because of line endings [#52289](https://github.com/saltstack/salt/issues/52289)
- Corrected encoding of credentials for use with Artifactory [#63063](https://github.com/saltstack/salt/issues/63063)
- Use `send_multipart` instead of `send` when sending multipart message. [#65018](https://github.com/saltstack/salt/issues/65018)
- Fix an issue where the minion would crash on Windows if some of the grains
  failed to resolve [#65154](https://github.com/saltstack/salt/issues/65154)
- Fix issue with openscap when the error was outside the expected scope. It now
  returns failed with the error code and the error [#65193](https://github.com/saltstack/salt/issues/65193)
- Upgrade relenv to 0.15.0 to fix namespaced packages installed by salt-pip [#65433](https://github.com/saltstack/salt/issues/65433)
- Fix regression of fileclient re-use when rendering sls pillars and states [#65450](https://github.com/saltstack/salt/issues/65450)
- Fixes the s3fs backend computing the local cache's files with the wrong hash type [#65589](https://github.com/saltstack/salt/issues/65589)
- Fixed Salt-SSH pillar rendering and state rendering with nested SSH calls when called via saltutil.cmd or in an orchestration [#65670](https://github.com/saltstack/salt/issues/65670)
- Fix boto execution module loading [#65691](https://github.com/saltstack/salt/issues/65691)
- Removed PR 65185 changes since incomplete solution [#65692](https://github.com/saltstack/salt/issues/65692)
- catch only ret/ events not all returning events. [#65727](https://github.com/saltstack/salt/issues/65727)
- Fix nonsensical time in fileclient timeout error. [#65752](https://github.com/saltstack/salt/issues/65752)
- Fixes an issue when reading/modifying ini files that contain unicode characters [#65777](https://github.com/saltstack/salt/issues/65777)
- added https proxy to the list of proxies so that requests knows what to do with https based proxies [#65824](https://github.com/saltstack/salt/issues/65824)
- Ensure minion channels are closed on any master connection error. [#65932](https://github.com/saltstack/salt/issues/65932)
- Fixed issue where Salt can't find libcrypto when pip installed from a cloned repo [#65954](https://github.com/saltstack/salt/issues/65954)
- Fix RPM package systemd scriptlets to make RPM packages more universal [#65987](https://github.com/saltstack/salt/issues/65987)
- Fixed an issue where fileclient requests during Pillar rendering cause
  fileserver backends to be needlessly refreshed. [#65990](https://github.com/saltstack/salt/issues/65990)
- Fix exceptions being set on futures that are already done in ZeroMQ transport [#66006](https://github.com/saltstack/salt/issues/66006)
- Use hmac compare_digest method in hashutil module to mitigate potential timing attacks [#66041](https://github.com/saltstack/salt/issues/66041)
- Fix request channel default timeout regression. In 3006.5 it was changed from
  60 to 30 and is now set back to 60 by default. [#66061](https://github.com/saltstack/salt/issues/66061)
- Upgrade relenv to 0.15.1 to fix debugpy support. [#66094](https://github.com/saltstack/salt/issues/66094)


### Security

- Bump to ``cryptography==42.0.0`` due to https://github.com/advisories/GHSA-3ww4-gg4f-jr7f

  In the process, we were also required to update to ``pyOpenSSL==24.0.0`` [#66004](https://github.com/saltstack/salt/issues/66004)
- Bump to `cryptography==42.0.3` due to https://github.com/advisories/GHSA-3ww4-gg4f-jr7f [#66090](https://github.com/saltstack/salt/issues/66090)


## 3006.6 (2024-01-26)


### Changed

- Salt no longer time bombs user installations on code using `salt.utils.versions.warn_until_date` [#665924](https://github.com/saltstack/salt/issues/665924)


### Fixed

- Fix un-closed transport in tornado netapi [#65759](https://github.com/saltstack/salt/issues/65759)


### Security

- CVE-2024-22231 Prevent directory traversal when creating syndic cache directory on the master
  CVE-2024-22232 Prevent directory traversal attacks in the master's serve_file method.
  These vulerablities were discovered and reported by:
  Yudi Zhao(Huawei Nebula Security Lab),Chenwei Jiang(Huawei Nebula Security Lab) [#565](https://github.com/saltstack/salt/issues/565)
- Update some requirements which had some security issues:

  * Bump to `pycryptodome==3.19.1` and `pycryptodomex==3.19.1` due to https://github.com/advisories/GHSA-j225-cvw7-qrx7
  * Bump to `gitpython==3.1.41` due to https://github.com/advisories/GHSA-2mqj-m65w-jghx
  * Bump to `jinja2==3.1.3` due to https://github.com/advisories/GHSA-h5c8-rqwp-cp95 [#65830](https://github.com/saltstack/salt/issues/65830)


## 3006.5 (2023-12-12)
Salt 3005.5 (2024-01-19)
========================

Security
--------

- Fix CVE-2024-22231 Prevent directory traversal when creating syndic cache directory on the master.
- Fix CVE-2024-22232 Prevent directory traversal attacks in the master's serve_file method.

These vulnerablities were discovered and reported by:
Yudi Zhao(Huawei Nebula Security Lab),Chenwei Jiang(Huawei Nebula Security Lab) (#565)


Salt v3005.4 (2023-10-16)
=========================


### Removed

- Tech Debt - support for pysss removed due to functionality addition in Python 3.3 [#65029](https://github.com/saltstack/salt/issues/65029)


### Fixed

- Improved error message when state arguments are accidentally passed as a string [#38098](https://github.com/saltstack/salt/issues/38098)
- Allow `pip.install` to create a log file that is passed in if the parent directory is writeable [#44722](https://github.com/saltstack/salt/issues/44722)
- Fixed merging of complex pillar overrides with salt-ssh states [#59802](https://github.com/saltstack/salt/issues/59802)
- Fixed gpg pillar rendering with salt-ssh [#60002](https://github.com/saltstack/salt/issues/60002)
- Made salt-ssh states not re-render pillars unnecessarily [#62230](https://github.com/saltstack/salt/issues/62230)
- Made Salt maintain options in Debian package repo definitions [#64130](https://github.com/saltstack/salt/issues/64130)
- Migrated all [`invoke`](https://www.pyinvoke.org/) tasks to [`python-tools-scripts`](https://github.com/s0undt3ch/python-tools-scripts).

  * `tasks/docs.py` -> `tools/precommit/docs.py`
  * `tasks/docstrings.py` -> `tools/precommit/docstrings.py`
  * `tasks/loader.py` -> `tools/precommit/loader.py`
  * `tasks/filemap.py` -> `tools/precommit/filemap.py` [#64374](https://github.com/saltstack/salt/issues/64374)
- Fix salt user login shell path in Debian packages [#64377](https://github.com/saltstack/salt/issues/64377)
- Fill out lsb_distrib_xxxx (best estimate) grains if problems with retrieving lsb_release data [#64473](https://github.com/saltstack/salt/issues/64473)
- Fixed an issue in the ``file.directory`` state where the ``children_only`` keyword
  argument was not being respected. [#64497](https://github.com/saltstack/salt/issues/64497)
- Move salt.ufw to correct location /etc/ufw/applications.d/ [#64572](https://github.com/saltstack/salt/issues/64572)
- Fixed salt-ssh stacktrace when retcode is not an integer [#64575](https://github.com/saltstack/salt/issues/64575)
- Fixed SSH shell seldomly fails to report any exit code [#64588](https://github.com/saltstack/salt/issues/64588)
- Fixed some issues in x509_v2 execution module private key functions [#64597](https://github.com/saltstack/salt/issues/64597)
- Fixed grp.getgrall() in utils/user.py causing performance issues [#64888](https://github.com/saltstack/salt/issues/64888)
- Fix user.list_groups omits remote groups via sssd, etc. [#64953](https://github.com/saltstack/salt/issues/64953)
- Ensure sync from _grains occurs before attempting pillar compilation in case custom grain used in pillar file [#65027](https://github.com/saltstack/salt/issues/65027)
- Moved gitfs locks to salt working dir to avoid lock wipes [#65086](https://github.com/saltstack/salt/issues/65086)
- Only attempt to create a keys directory when `--gen-keys` is passed to the `salt-key` CLI [#65093](https://github.com/saltstack/salt/issues/65093)
- Fix nonce verification, request server replies do not stomp on eachother. [#65114](https://github.com/saltstack/salt/issues/65114)
- speed up yumpkg list_pkgs by not requiring digest or signature verification on lookup. [#65152](https://github.com/saltstack/salt/issues/65152)
- Fix pkg.latest failing on windows for winrepo packages where the package is already up to date [#65165](https://github.com/saltstack/salt/issues/65165)
- Ensure __kwarg__ is preserved when checking for kwargs.  This change affects proxy minions when used with Deltaproxy, which had kwargs popped when targeting multiple minions id. [#65179](https://github.com/saltstack/salt/issues/65179)
- Fixes traceback when state id is an int in a reactor SLS file. [#65210](https://github.com/saltstack/salt/issues/65210)
- Install logrotate config as /etc/logrotate.d/salt-common for Debian packages
  Remove broken /etc/logrotate.d/salt directory from 3006.3 if it exists. [#65231](https://github.com/saltstack/salt/issues/65231)
- Use ``sha256`` as the default ``hash_type``. It has been the default since Salt v2016.9 [#65287](https://github.com/saltstack/salt/issues/65287)
- Preserve ownership on log rotation [#65288](https://github.com/saltstack/salt/issues/65288)
- Ensure that the correct value of jid_inclue is passed if the argument is included in the passed keyword arguments. [#65302](https://github.com/saltstack/salt/issues/65302)
- Uprade relenv to 0.14.2
   - Update openssl to address CVE-2023-5363.
   - Fix bug in openssl setup when openssl binary can't be found.
   - Add M1 mac support. [#65316](https://github.com/saltstack/salt/issues/65316)
- Fix regex for filespec adding/deleting fcontext policy in selinux [#65340](https://github.com/saltstack/salt/issues/65340)
- Ensure CLI options take priority over Saltfile options [#65358](https://github.com/saltstack/salt/issues/65358)
- Test mode for state function `saltmod.wheel` no longer set's `result` to `(None,)` [#65372](https://github.com/saltstack/salt/issues/65372)
- Client only process events which tag conforms to an event return. [#65400](https://github.com/saltstack/salt/issues/65400)
- Fixes an issue setting user or machine policy on Windows when the Group Policy
  directory is missing [#65411](https://github.com/saltstack/salt/issues/65411)
- Fix regression in file module which was not re-using a file client. [#65450](https://github.com/saltstack/salt/issues/65450)
- pip.installed state will now properly fail when a specified user does not exists [#65458](https://github.com/saltstack/salt/issues/65458)
- Publish channel connect callback method properly closes it's request channel. [#65464](https://github.com/saltstack/salt/issues/65464)
- Ensured the pillar in SSH wrapper modules is the same as the one used in template rendering when overrides are passed [#65483](https://github.com/saltstack/salt/issues/65483)
- Fix file.comment ignore_missing not working with multiline char [#65501](https://github.com/saltstack/salt/issues/65501)
- Warn when an un-closed transport client is being garbage collected. [#65554](https://github.com/saltstack/salt/issues/65554)
- Only generate the HMAC's for ``libssl.so.1.1`` and ``libcrypto.so.1.1`` if those files exist. [#65581](https://github.com/saltstack/salt/issues/65581)
- Fixed an issue where Salt Cloud would fail if it could not delete lingering
  PAexec binaries [#65584](https://github.com/saltstack/salt/issues/65584)


### Added

- Added Salt support for Debian 12 [#64223](https://github.com/saltstack/salt/issues/64223)
- Added Salt support for Amazon Linux 2023 [#64455](https://github.com/saltstack/salt/issues/64455)


### Security

- Bump to `cryptography==41.0.4` due to https://github.com/advisories/GHSA-v8gr-m533-ghj9 [#65268](https://github.com/saltstack/salt/issues/65268)
- Bump to `cryptography==41.0.7` due to https://github.com/advisories/GHSA-jfhm-5ghh-2f97 [#65643](https://github.com/saltstack/salt/issues/65643)


## 3006.4 (2023-10-16)

### Security

- Fix CVE-2023-34049 by ensuring we do not use a predictable name for the script and correctly check returncode of scp command.
  This only impacts salt-ssh users using the pre-flight option. [#cve-2023-34049](https://github.com/saltstack/salt/issues/cve-2023-34049)
- Update to `gitpython>=3.1.35` due to https://github.com/advisories/GHSA-wfm5-v35h-vwf4 and https://github.com/advisories/GHSA-cwvm-v4w8-q58c [#65163](https://github.com/saltstack/salt/issues/65163)
- Bump to `cryptography==41.0.4` due to https://github.com/advisories/GHSA-v8gr-m533-ghj9 [#65268](https://github.com/saltstack/salt/issues/65268)
- Upgrade relenv to 0.13.12 to address CVE-2023-4807 [#65316](https://github.com/saltstack/salt/issues/65316)
- Bump to `urllib3==1.26.17` or `urllib3==2.0.6` due to https://github.com/advisories/GHSA-v845-jxx5-vc9f [#65334](https://github.com/saltstack/salt/issues/65334)
- Bump to `gitpython==3.1.37` due to https://github.com/advisories/GHSA-cwvm-v4w8-q58c [#65383](https://github.com/saltstack/salt/issues/65383)


## 3005.4 (2023-10-16)

### Security

- Fix CVE-2023-34049 by ensuring we do not use a predictable name for the script and correctly check returncode of scp command.
  This only impacts salt-ssh users using the pre-flight option. (cve-2023-34049)
- Bump to `cryptography==41.0.4` due to https://github.com/advisories/GHSA-v8gr-m533-ghj9 (#65267)
- Bump to `urllib3==1.26.17` or `urllib3==2.0.6` due to https://github.com/advisories/GHSA-v845-jxx5-vc9f (#65334)
- Bump to `gitpython==3.1.37` due to https://github.com/advisories/GHSA-cwvm-v4w8-q58c (#65383)


## Salt v3005.3 (2023-09-14)

### Fixed

- Fix __env__ and improve cache cleaning see more info at pull #65017. (#65002)


### Security

- Update to `gitpython>=3.1.35` due to https://github.com/advisories/GHSA-wfm5-v35h-vwf4 and https://github.com/advisories/GHSA-cwvm-v4w8-q58c (#65167)


## 3006.3 (2023-09-06)


### Removed

- Fedora 36 support was removed because it reached EOL [#64315](https://github.com/saltstack/salt/issues/64315)
- Handle deprecation warnings:

  * Switch to `FullArgSpec` since Py 3.11 no longer has `ArgSpec`, deprecated since Py 3.0
  * Stop using the deprecated `cgi` module
  * Stop using the deprecated `pipes` module
  * Stop using the deprecated `imp` module [#64553](https://github.com/saltstack/salt/issues/64553)


### Changed

- Replace libnacl with PyNaCl [#64372](https://github.com/saltstack/salt/issues/64372)
- Don't hardcode the python version on the Salt Package tests and on the `pkg/debian/salt-cloud.postinst` file [#64553](https://github.com/saltstack/salt/issues/64553)
- Some more deprecated code fixes:

  * Stop using the deprecated `locale.getdefaultlocale()` function
  * Stop accessing deprecated attributes
  * `pathlib.Path.__enter__()` usage is deprecated and not required, a no-op [#64565](https://github.com/saltstack/salt/issues/64565)
- Bump to `pyyaml==6.0.1` due to https://github.com/yaml/pyyaml/issues/601 and address lint issues [#64657](https://github.com/saltstack/salt/issues/64657)


### Fixed

- Fix for assume role when used salt-cloud to create aws ec2. [#52501](https://github.com/saltstack/salt/issues/52501)
- fixes aptpkg module by checking for blank comps. [#58667](https://github.com/saltstack/salt/issues/58667)
- `wheel.file_roots.find` is now able to find files in subdirectories of the roots. [#59800](https://github.com/saltstack/salt/issues/59800)
- pkg.latest no longer fails when multiple versions are reported to be installed (e.g. updating the kernel) [#60931](https://github.com/saltstack/salt/issues/60931)
- Do not update the credentials dictionary in `utils/aws.py` while iterating over it, and use the correct delete functionality [#61049](https://github.com/saltstack/salt/issues/61049)
- fixed runner not having a proper exit code when runner modules throw an exception. [#61173](https://github.com/saltstack/salt/issues/61173)
- `pip.list_all_versions` now works with `index_url` and `extra_index_url` [#61610](https://github.com/saltstack/salt/issues/61610)
- speed up file.recurse by using prefix with cp.list_master_dir and remove an un-needed loop. [#61998](https://github.com/saltstack/salt/issues/61998)
- Preserve test=True condition while running sub states. [#62590](https://github.com/saltstack/salt/issues/62590)
- Job returns are only sent to originating master [#62834](https://github.com/saltstack/salt/issues/62834)
- Fixes an issue with failing subsequent state runs with the lgpo state module.
  The ``lgpo.get_polcy`` function now returns all boolean settings. [#63296](https://github.com/saltstack/salt/issues/63296)
- Fix SELinux get policy with trailing whitespace [#63336](https://github.com/saltstack/salt/issues/63336)
- Fixes an issue with boolean settings not being reported after being set. The
  ``lgpo.get_polcy`` function now returns all boolean settings. [#63473](https://github.com/saltstack/salt/issues/63473)
- Ensure body is returned when salt.utils.http returns something other than 200 with tornado backend. [#63557](https://github.com/saltstack/salt/issues/63557)
- Allow long running pillar and file client requests to finish using request_channel_timeout and request_channel_tries minion config. [#63824](https://github.com/saltstack/salt/issues/63824)
- Fix state_queue type checking to allow int values [#64122](https://github.com/saltstack/salt/issues/64122)
- Call global logger when catching pip.list exceptions in states.pip.installed
  Rename global logger `log` to `logger` inside pip_state [#64169](https://github.com/saltstack/salt/issues/64169)
- Fixes permissions created by the Debian and RPM packages for the salt user.

  The salt user created by the Debian and RPM packages to run the salt-master process, was previously given ownership of various directories in a way which compromised the benefits of running the salt-master process as a non-root user.

  This fix sets the salt user to only have write access to those files and
  directories required for the salt-master process to run. [#64193](https://github.com/saltstack/salt/issues/64193)
- Fix user.present state when groups is unset to ensure the groups are unchanged, as documented. [#64211](https://github.com/saltstack/salt/issues/64211)
- Fixes issue with MasterMinion class loading configuration from `/etc/salt/minion.d/*.conf.

  The MasterMinion class (used for running orchestraions on master and other functionality) was incorrectly loading configuration from `/etc/salt/minion.d/*.conf`, when it should only load configuration from `/etc/salt/master` and `/etc/salt/master.d/*.conf`. [#64219](https://github.com/saltstack/salt/issues/64219)
- Fixed issue in mac_user.enable_auto_login that caused the user's keychain to be reset at each boot [#64226](https://github.com/saltstack/salt/issues/64226)
- Fixed KeyError in logs when running a state that fails. [#64231](https://github.com/saltstack/salt/issues/64231)
- Fixed x509_v2 `create_private_key`/`create_crl` unknown kwargs: __pub_fun... [#64232](https://github.com/saltstack/salt/issues/64232)
- remove the hard coded python version in error. [#64237](https://github.com/saltstack/salt/issues/64237)
- `salt-pip` now properly errors out when being called from a non `onedir` environment. [#64249](https://github.com/saltstack/salt/issues/64249)
- Ensure we return an error when adding the key fails in the pkgrepo state for debian hosts. [#64253](https://github.com/saltstack/salt/issues/64253)
- Fixed file client private attribute reference on `SaltMakoTemplateLookup` [#64280](https://github.com/saltstack/salt/issues/64280)
- Fix pkgrepo.absent failures on apt-based systems when repo either a) contains a
  trailing slash, or b) there is an arch mismatch. [#64286](https://github.com/saltstack/salt/issues/64286)
- Fix detection of Salt codename by "salt_version" execution module [#64306](https://github.com/saltstack/salt/issues/64306)
- Ensure selinux values are handled lowercase [#64318](https://github.com/saltstack/salt/issues/64318)
- Remove the `clr.AddReference`, it is causing an `Illegal characters in path` exception [#64339](https://github.com/saltstack/salt/issues/64339)
- Update `pkg.group_installed` state to support repo options [#64348](https://github.com/saltstack/salt/issues/64348)
- Fix salt user login shell path in Debian packages [#64377](https://github.com/saltstack/salt/issues/64377)
- Allow for multiple user's keys presented when authenticating, for example: root, salt, etc. [#64398](https://github.com/saltstack/salt/issues/64398)
- Fixed an issue with ``lgpo_reg`` where existing entries for the same key in
  ``Registry.pol`` were being overwritten in subsequent runs if the value name in
  the subesequent run was contained in the existing value name. For example, a
  key named ``SetUpdateNotificationLevel`` would be overwritten by a subsequent
  run attempting to set ``UpdateNotificationLevel`` [#64401](https://github.com/saltstack/salt/issues/64401)
- Add search for %ProgramData%\Chocolatey\choco.exe to determine if Chocolatey is installed or not [#64427](https://github.com/saltstack/salt/issues/64427)
- Fix regression for user.present on handling groups with dupe GIDs [#64430](https://github.com/saltstack/salt/issues/64430)
- Fix inconsistent use of args in ssh_auth.managed [#64442](https://github.com/saltstack/salt/issues/64442)
- Ensure we raise an error when the name argument is invalid in pkgrepo.managed state for systems using apt. [#64451](https://github.com/saltstack/salt/issues/64451)
- Fix file.symlink will not replace/update existing symlink [#64477](https://github.com/saltstack/salt/issues/64477)
- Fixed salt-ssh state.* commands returning retcode 0 when state/pillar rendering fails [#64514](https://github.com/saltstack/salt/issues/64514)
- Fix pkg.install when using a port in the url. [#64516](https://github.com/saltstack/salt/issues/64516)
- `win_pkg` Fixes an issue runing `pkg.install` with `version=latest` where the
  new installer would not be cached if there was already an installer present
  with the same name. [#64519](https://github.com/saltstack/salt/issues/64519)
- Added a `test:full` label in the salt repository, which, when selected, will force a full test run. [#64539](https://github.com/saltstack/salt/issues/64539)
- Syndic's async_req_channel uses the asynchornous version of request channel [#64552](https://github.com/saltstack/salt/issues/64552)
- Ensure runners properly save information to job cache. [#64570](https://github.com/saltstack/salt/issues/64570)
- Added salt.ufw to salt-master install on Debian and Ubuntu [#64572](https://github.com/saltstack/salt/issues/64572)
- Added support for Chocolatey 2.0.0+ while maintaining support for older versions [#64622](https://github.com/saltstack/salt/issues/64622)
- Updated semanage fcontext to use --modify if context already exists when adding context [#64625](https://github.com/saltstack/salt/issues/64625)
- Preserve request client socket between requests. [#64627](https://github.com/saltstack/salt/issues/64627)
- Show user friendly message when pillars timeout [#64651](https://github.com/saltstack/salt/issues/64651)
- File client timeouts durring jobs show user friendly errors instead of tracbacks [#64653](https://github.com/saltstack/salt/issues/64653)
- SaltClientError does not log a traceback on minions, we expect these to happen so a user friendly log is shown. [#64729](https://github.com/saltstack/salt/issues/64729)
- Look in location salt is running from, this accounts for running from an unpacked onedir file that has not been installed. [#64877](https://github.com/saltstack/salt/issues/64877)
- Preserve credentials on spawning platforms, minions no longer re-authenticate
  with every job when using `multiprocessing=True`. [#64914](https://github.com/saltstack/salt/issues/64914)
- Fixed uninstaller to not remove the `salt` directory by default. This allows
  the `extras-3.##` folder to persist so salt-pip dependencies are not wiped out
  during an upgrade. [#64957](https://github.com/saltstack/salt/issues/64957)
- fix msteams by adding the missing header that Microsoft is now enforcing. [#64973](https://github.com/saltstack/salt/issues/64973)
- Fix __env__ and improve cache cleaning see more info at pull #65017. [#65002](https://github.com/saltstack/salt/issues/65002)
- Better error message on inconsistent decoded payload [#65020](https://github.com/saltstack/salt/issues/65020)
- Handle permissions access error when calling `lsb_release` with the salt user [#65024](https://github.com/saltstack/salt/issues/65024)
- Allow schedule state module to update schedule when the minion is offline. [#65033](https://github.com/saltstack/salt/issues/65033)
- Fixed creation of wildcard DNS in SAN in `x509_v2` [#65072](https://github.com/saltstack/salt/issues/65072)
- The macOS installer no longer removes the extras directory [#65073](https://github.com/saltstack/salt/issues/65073)


### Added

- Added a script to automate setting up a 2nd minion in a user context on Windows [#64439](https://github.com/saltstack/salt/issues/64439)
- Several fixes to the CI workflow:

  * Don't override the `on` Jinja block on the `ci.yaml` template. This enables reacting to labels getting added/removed
    to/from pull requests.
  * Switch to using `tools` and re-use the event payload available instead of querying the GH API again to get the pull
    request labels
  * Concentrate test selection by labels to a single place
  * Enable code coverage on pull-requests by setting the `test:coverage` label [#64547](https://github.com/saltstack/salt/issues/64547)


### Security

- Upgrade to `cryptography==41.0.3`(and therefor `pyopenssl==23.2.0` due to https://github.com/advisories/GHSA-jm77-qphf-c4w8)

  This only really impacts pip installs of Salt and the windows onedir since the linux and macos onedir build every package dependency from source, not from pre-existing wheels.

  Also resolves the following cryptography advisories:

  Due to:
    * https://github.com/advisories/GHSA-5cpq-8wj7-hf2v
    * https://github.com/advisories/GHSA-x4qr-2fvf-3mr5
    * https://github.com/advisories/GHSA-w7pp-m8wf-vj6r [#64595](https://github.com/saltstack/salt/issues/64595)
- Bump to `aiohttp==3.8.5` due to https://github.com/advisories/GHSA-45c4-8wx5-qw6w [#64687](https://github.com/saltstack/salt/issues/64687)
- Bump to `certifi==2023.07.22` due to https://github.com/advisories/GHSA-xqr8-7jwr-rhp7 [#64718](https://github.com/saltstack/salt/issues/64718)
- Upgrade `relenv` to `0.13.2` and Python to `3.10.12`

  Addresses multiple CVEs in Python's dependencies: https://docs.python.org/release/3.10.12/whatsnew/changelog.html#python-3-10-12 [#64719](https://github.com/saltstack/salt/issues/64719)
- Update to `gitpython>=3.1.32` due to https://github.com/advisories/GHSA-pr76-5cm5-w9cj [#64988](https://github.com/saltstack/salt/issues/64988)


## 3006.2 (2023-08-09)


### Fixed

- In scenarios where PythonNet fails to load, Salt will now fall back to WMI for
  gathering grains information [#64897](https://github.com/saltstack/salt/issues/64897)


### Security

- fix CVE-2023-20897 by catching exception instead of letting exception disrupt connection [#cve-2023-20897](https://github.com/saltstack/salt/issues/cve-2023-20897)
- Fixed gitfs cachedir_basename to avoid hash collisions. Added MP Lock to gitfs. These changes should stop race conditions. [#cve-2023-20898](https://github.com/saltstack/salt/issues/cve-2023-20898)
- Upgrade to `requests==2.31.0`

  Due to:
    * https://github.com/advisories/GHSA-j8r2-6x86-q33q [#64336](https://github.com/saltstack/salt/issues/64336)
- Upgrade to `cryptography==41.0.3`(and therefor `pyopenssl==23.2.0` due to https://github.com/advisories/GHSA-jm77-qphf-c4w8)

  This only really impacts pip installs of Salt and the windows onedir since the linux and macos onedir build every package dependency from source, not from pre-existing wheels.

  Also resolves the following cryptography advisories:

  Due to:
    * https://github.com/advisories/GHSA-5cpq-8wj7-hf2v
    * https://github.com/advisories/GHSA-x4qr-2fvf-3mr5
    * https://github.com/advisories/GHSA-w7pp-m8wf-vj6r

  There is no security upgrade available for Py3.5 [#64595](https://github.com/saltstack/salt/issues/64595)
- Bump to `certifi==2023.07.22` due to https://github.com/advisories/GHSA-xqr8-7jwr-rhp7 [#64718](https://github.com/saltstack/salt/issues/64718)
- Upgrade `relenv` to `0.13.2` and Python to `3.10.12`

  Addresses multiple CVEs in Python's dependencies: https://docs.python.org/release/3.10.12/whatsnew/changelog.html#python-3-10-12 [#64719](https://github.com/saltstack/salt/issues/64719)


## Salt v3005.2 (2023-07-31)

### Changed

- Additional required package upgrades

  * It's now `pyzmq>=20.0.0` on all platforms, and `<=22.0.3` just for windows.
  * Upgrade to `pyopenssl==23.0.0` due to the cryptography upgrade. (#63757)


### Security

- fix CVE-2023-20897 by catching exception instead of letting exception disrupt connection (cve-2023-20897)
- Fixed gitfs cachedir_basename to avoid hash collisions. Added MP Lock to gitfs. These changes should stop race conditions. (cve-2023-20898)
- Upgrade to `requests==2.31.0`

  Due to:
    * https://github.com/advisories/GHSA-j8r2-6x86-q33q (#64336)
- Upgrade to `cryptography==41.0.3`(and therefor `pyopenssl==23.2.0` due to https://github.com/advisories/GHSA-jm77-qphf-c4w8)

  Also resolves the following cryptography advisories:

  Due to:
    * https://github.com/advisories/GHSA-5cpq-8wj7-hf2v
    * https://github.com/advisories/GHSA-x4qr-2fvf-3mr5
    * https://github.com/advisories/GHSA-w7pp-m8wf-vj6r

  There is no security upgrade available for Py3.5 (#64595)
- Bump to `certifi==2023.07.22` due to https://github.com/advisories/GHSA-xqr8-7jwr-rhp7

  Python 3.5 cannot get the updated requirements since certifi no longer supports this python version (#64720)


## 3006.1 (2023-05-05)


### Fixed

- Check that the return data from the cloud create function is a dictionary before attempting to pull values out. [#61236](https://github.com/saltstack/salt/issues/61236)
- Ensure NamedLoaderContext's have their value() used if passing to other modules [#62477](https://github.com/saltstack/salt/issues/62477)
- add documentation note about reactor state ids. [#63589](https://github.com/saltstack/salt/issues/63589)
- Added support for ``test=True`` to the ``file.cached`` state module [#63785](https://github.com/saltstack/salt/issues/63785)
- Updated `source_hash` documentation and added a log warning when `source_hash` is used with a source other than `http`, `https` and `ftp`. [#63810](https://github.com/saltstack/salt/issues/63810)
- Fixed clear pillar cache on every highstate and added clean_pillar_cache=False to saltutil functions. [#64081](https://github.com/saltstack/salt/issues/64081)
- Fix dmsetup device names with hyphen being picked up. [#64082](https://github.com/saltstack/salt/issues/64082)
- Update all the scheduler functions to include a fire_event argument which will determine whether to fire the completion event onto the event bus.
  This event is only used when these functions are called via the schedule execution modules.
  Update all the calls to the schedule related functions in the deltaproxy proxy minion to include fire_event=False, as the event bus is not available when these functions are called. [#64102](https://github.com/saltstack/salt/issues/64102), [#64103](https://github.com/saltstack/salt/issues/64103)
- Default to a 0 timeout if none is given for the terraform roster to avoid `-o ConnectTimeout=None` when using `salt-ssh` [#64109](https://github.com/saltstack/salt/issues/64109)
- Disable class level caching of the file client on `SaltCacheLoader` and properly use context managers to take care of initialization and termination of the file client. [#64111](https://github.com/saltstack/salt/issues/64111)
- Fixed several file client uses which were not properly terminating it by switching to using it as a context manager
  whenever possible or making sure `.destroy()` was called when using a context manager was not possible. [#64113](https://github.com/saltstack/salt/issues/64113)
- Fix running setup.py when passing in --salt-config-dir and --salt-cache-dir arguments. [#64114](https://github.com/saltstack/salt/issues/64114)
- Moved /etc/salt/proxy and /lib/systemd/system/salt-proxy@.service to the salt-minion DEB package [#64117](https://github.com/saltstack/salt/issues/64117)
- Stop passing `**kwargs` and be explicit about the keyword arguments to pass, namely, to `cp.cache_file` call in `salt.states.pkg` [#64118](https://github.com/saltstack/salt/issues/64118)
- lgpo_reg.set_value now returns ``True`` on success instead of ``None`` [#64126](https://github.com/saltstack/salt/issues/64126)
- Make salt user's home /opt/saltstack/salt [#64141](https://github.com/saltstack/salt/issues/64141)
- Fix cmd.run doesn't output changes in test mode [#64150](https://github.com/saltstack/salt/issues/64150)
- Move salt user and group creation to common package [#64158](https://github.com/saltstack/salt/issues/64158)
- Fixed issue in salt-cloud so that multiple masters specified in the cloud
  are written to the minion config properly [#64170](https://github.com/saltstack/salt/issues/64170)
- Make sure the `salt-ssh` CLI calls it's `fsclient.destroy()` method when done. [#64184](https://github.com/saltstack/salt/issues/64184)
- Stop using the deprecated `salt.transport.client` imports. [#64186](https://github.com/saltstack/salt/issues/64186)
- Add a `.pth` to the Salt onedir env to ensure packages in extras are importable. Bump relenv to 0.12.3. [#64192](https://github.com/saltstack/salt/issues/64192)
- Fix ``lgpo_reg`` state to work with User policy [#64200](https://github.com/saltstack/salt/issues/64200)
- Cloud deployment directories are owned by salt user and group [#64204](https://github.com/saltstack/salt/issues/64204)
- ``lgpo_reg`` state now enforces and reports changes to the registry [#64222](https://github.com/saltstack/salt/issues/64222)

## 3006.0 (2023-04-18)


### Removed

- Remove and deprecate the __orchestration__ key from salt.runner and salt.wheel return data. To get it back, set features.enable_deprecated_orchestration_flag master configuration option to True. The flag will be completely removed in Salt 3008 Argon. [#59917](https://github.com/saltstack/salt/issues/59917)
- Removed distutils and replaced with setuptools, given distutils is deprecated and removed in Python 3.12 [#60476](https://github.com/saltstack/salt/issues/60476)
- Removed ``runtests`` targets from ``noxfile.py`` [#62239](https://github.com/saltstack/salt/issues/62239)
- Removed the PyObjC dependency.

  This addresses problems with building a one dir build for macOS.
  It became problematic because depending on the macOS version, it pulls different dependencies, and we would either have to build a macos onedir for each macOS supported release, or ship a crippled onedir(because it would be tied to the macOS version where the onedir was built).
  Since it's currently not being used, it's removed. [#62432](https://github.com/saltstack/salt/issues/62432)
- Removed `SixRedirectImporter` from Salt. Salt hasn't shipped `six` since Salt 3004. [#63874](https://github.com/saltstack/salt/issues/63874)


### Deprecated

- renamed `keep_jobs`, specifying job cache TTL in hours, to `keep_jobs_seconds`, specifying TTL in seconds.
  `keep_jobs` will be removed in the Argon release [#55295](https://github.com/saltstack/salt/issues/55295)
- Removing all references to napalm-base which is no longer supported. [#61542](https://github.com/saltstack/salt/issues/61542)
- The 'ip_bracket' function has been moved from salt/utils/zeromq.py in salt/utils/network.py [#62009](https://github.com/saltstack/salt/issues/62009)
- The `expand_repo_def` function in `salt.modules.aptpkg` is now deprecated. It's only used in `salt.states.pkgrepo` and it has no use of being exposed to the CLI. [#62485](https://github.com/saltstack/salt/issues/62485)
- Deprecated defunct Django returner [#62644](https://github.com/saltstack/salt/issues/62644)
- Deprecate core ESXi and associated states and modules, vcenter and vsphere support in favor of Salt VMware Extensions [#62754](https://github.com/saltstack/salt/issues/62754)
- Removing manufacture grain which has been deprecated. [#62914](https://github.com/saltstack/salt/issues/62914)
- Removing deprecated utils/boto3_elasticsearch.py [#62915](https://github.com/saltstack/salt/issues/62915)
- Removing support for the now deprecated _ext_nodes from salt/master.py. [#62917](https://github.com/saltstack/salt/issues/62917)
- Deprecating the Salt Slack engine in favor of the Salt Slack Bolt Engine. [#63095](https://github.com/saltstack/salt/issues/63095)
- `salt.utils.version.StrictVersion` is now deprecated and it's use should be replaced with `salt.utils.version.Version`. [#63383](https://github.com/saltstack/salt/issues/63383)


### Changed

- More intelligent diffing in changes of file.serialize state. [#48609](https://github.com/saltstack/salt/issues/48609)
- Move deprecation of the neutron module to Argon. Please migrate to the neutronng module instead. [#49430](https://github.com/saltstack/salt/issues/49430)
- ``umask`` is now a global state argument, instead of only applying to ``cmd``
  states. [#57803](https://github.com/saltstack/salt/issues/57803)
- Update pillar.obfuscate to accept kwargs in addition to args.  This is useful when passing in keyword arguments like saltenv that are then passed along to pillar.items. [#58971](https://github.com/saltstack/salt/issues/58971)
- Improve support for listing macOS brew casks [#59439](https://github.com/saltstack/salt/issues/59439)
- Add missing MariaDB Grants to mysql module.
  MariaDB has added some grants in 10.4.x and 10.5.x that are not present here, which results in an error when creating.
  Also improved exception handling in `grant_add` which did not log the original error message and replaced it with a generic error. [#61409](https://github.com/saltstack/salt/issues/61409)
- Use VENV_PIP_TARGET environment variable as a default target for pip if present. [#62089](https://github.com/saltstack/salt/issues/62089)
- Disabled FQDNs grains on macOS by default [#62168](https://github.com/saltstack/salt/issues/62168)
- Replaced pyroute2.IPDB with pyroute2.NDB, as the former is deprecated [#62218](https://github.com/saltstack/salt/issues/62218)
- Enhance capture of error messages for Zypper calls in zypperpkg module. [#62346](https://github.com/saltstack/salt/issues/62346)
- Removed GPG_1_3_1 check [#62895](https://github.com/saltstack/salt/issues/62895)
- Requisite state chunks now all consistently contain `__id__`, `__sls__` and `name`. [#63012](https://github.com/saltstack/salt/issues/63012)
- netapi_enable_clients option to allow enabling/disabling of clients in salt-api.
  By default all clients will now be disabled. Users of salt-api will need
  to update their master config to enable the clients that they use. Not adding
  the netapi_enable_clients option with required clients to the master config will
  disable salt-api. [#63050](https://github.com/saltstack/salt/issues/63050)
- Stop relying on `salt/_version.py` to write Salt's version. Instead use `salt/_version.txt` which only contains the version string. [#63383](https://github.com/saltstack/salt/issues/63383)
- Set enable_fqdns_grains to be False by default. [#63595](https://github.com/saltstack/salt/issues/63595)
- Changelog snippet files must now have a `.md` file extension to be more explicit on what type of rendering is done when they are included in the main `CHANGELOG.md` file. [#63710](https://github.com/saltstack/salt/issues/63710)
- Upgraded to `relenv==0.9.0` [#63883](https://github.com/saltstack/salt/issues/63883)


### Fixed

- Add kwargs to handle extra parameters for http.query [#36138](https://github.com/saltstack/salt/issues/36138)
- Fix mounted bind mounts getting active mount options added [#39292](https://github.com/saltstack/salt/issues/39292)
- Fix `sysctl.present` converts spaces to tabs. [#40054](https://github.com/saltstack/salt/issues/40054)
- Fixes state pkg.purged to purge removed packages on Debian family systems [#42306](https://github.com/saltstack/salt/issues/42306)
- Fix fun_args missing from syndic returns [#45823](https://github.com/saltstack/salt/issues/45823)
- Fix mount.mounted with 'mount: False' reports unmounted file system as unchanged when running with test=True [#47201](https://github.com/saltstack/salt/issues/47201)
- Issue #49310: Allow users to touch a file with Unix date of birth [#49310](https://github.com/saltstack/salt/issues/49310)
- Do not raise an exception in pkg.info_installed on nonzero return code [#51620](https://github.com/saltstack/salt/issues/51620)
- Passes the value of the force parameter from file.copy to its call to file.remove so that files with the read-only attribute are handled. [#51739](https://github.com/saltstack/salt/issues/51739)
- Fixed x509.certificate_managed creates new certificate every run in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#52167](https://github.com/saltstack/salt/issues/52167)
- Don't check for cached pillar errors on state.apply [#52354](https://github.com/saltstack/salt/issues/52354), [#57180](https://github.com/saltstack/salt/issues/57180), [#59339](https://github.com/saltstack/salt/issues/59339)
- Swapping out args and kwargs for arg and kwarg respectively in the Slack engine when the command passed is a runner. [#52400](https://github.com/saltstack/salt/issues/52400)
- Ensure when we're adding chunks to the rules when running aggregation with the iptables state module we use a copy of the chunk otherwise we end up with a recursive mess. [#53353](https://github.com/saltstack/salt/issues/53353)
- When user_create or user_remove fail, return False instead of returning the error. [#53377](https://github.com/saltstack/salt/issues/53377)
- Include sync_roster when sync_all is called. [#53914](https://github.com/saltstack/salt/issues/53914)
- Avoid warning noise in lograte.get [#53988](https://github.com/saltstack/salt/issues/53988)
- Fixed listing revoked keys with gpg.list_keys [#54347](https://github.com/saltstack/salt/issues/54347)
- Fix mount.mounted does not handle blanks properly [#54508](https://github.com/saltstack/salt/issues/54508)
- Fixed grain num_cpus get wrong CPUs count in case of inconsistent CPU numbering. [#54682](https://github.com/saltstack/salt/issues/54682)
- Fix spelling error for python_shell argument in dpkg_lower module [#54907](https://github.com/saltstack/salt/issues/54907)
- Cleaned up bytes response data before sending to non-bytes compatible returners (postgres, mysql) [#55226](https://github.com/saltstack/salt/issues/55226)
- Fixed malformed state return when testing file.managed with unavailable source file [#55269](https://github.com/saltstack/salt/issues/55269)
- Included stdout in error message for Zypper calls in zypperpkg module. [#56016](https://github.com/saltstack/salt/issues/56016)
- Fixed pillar.filter_by with salt-ssh [#56093](https://github.com/saltstack/salt/issues/56093)
- Fix boto_route53 issue with (multiple) VPCs. [#57139](https://github.com/saltstack/salt/issues/57139)
- Remove log from mine runner which was not used. [#57463](https://github.com/saltstack/salt/issues/57463)
- Fixed x509.read_certificate error when reading a Microsoft CA issued certificate in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#57535](https://github.com/saltstack/salt/issues/57535)
- Updating Slack engine to use slack_bolt library. [#57842](https://github.com/saltstack/salt/issues/57842)
- Fixed warning about replace=True with x509.certificate_managed in the new cryptography x509 module. [#58165](https://github.com/saltstack/salt/issues/58165)
- Fix salt.modules.pip:is_installed doesn't handle locally installed packages [#58202](https://github.com/saltstack/salt/issues/58202)
- Add missing MariaDB Grants to mysql module. MariaDB has added some grants in 10.4.x and 10.5.x that are not present here, which results in an error when creating. [#58297](https://github.com/saltstack/salt/issues/58297)
- linux_shadow: Fix cases where malformed shadow entries cause `user.present`
  states to fail. [#58423](https://github.com/saltstack/salt/issues/58423)
- Fixed salt.utils.compat.cmp to work with dictionaries [#58729](https://github.com/saltstack/salt/issues/58729)
- Fixed formatting for terse output mode [#58953](https://github.com/saltstack/salt/issues/58953)
- Fixed RecursiveDictDiffer with added nested dicts [#59017](https://github.com/saltstack/salt/issues/59017)
- Fixed x509.certificate_managed has DoS effect on master in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#59169](https://github.com/saltstack/salt/issues/59169)
- Fixed saltnado websockets disconnecting immediately [#59183](https://github.com/saltstack/salt/issues/59183)
- Fixed x509.certificate_managed rolls certificates every now and then in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#59315](https://github.com/saltstack/salt/issues/59315)
- Fix postgres_privileges.present not idempotent for functions [#59585](https://github.com/saltstack/salt/issues/59585)
- Fixed influxdb_continuous_query.present state to provide the client args to the underlying module on create. [#59766](https://github.com/saltstack/salt/issues/59766)
- Warn when using insecure (http:// based) key_urls for apt-based systems in pkgrepo.managed, and add a kwarg that determines the validity of such a url. [#59786](https://github.com/saltstack/salt/issues/59786)
- add load balancing policy default option and ensure the module can be executed with arguments from CLI [#59909](https://github.com/saltstack/salt/issues/59909)
- Fix salt-ssh when using imports with extra-filerefs. [#60003](https://github.com/saltstack/salt/issues/60003)
- Fixed cache directory corruption startup error [#60170](https://github.com/saltstack/salt/issues/60170)
- Update docs remove dry_run in docstring of file.blockreplace state. [#60227](https://github.com/saltstack/salt/issues/60227)
- Adds Parrot to OS_Family_Map in grains. [#60249](https://github.com/saltstack/salt/issues/60249)
- Fixed stdout and stderr being empty sometimes when use_vt=True for the cmd.run[*] functions [#60365](https://github.com/saltstack/salt/issues/60365)
- Use return code in iptables --check to verify rule exists. [#60467](https://github.com/saltstack/salt/issues/60467)
- Fix regression pip.installed does not pass env_vars when calling pip.list [#60557](https://github.com/saltstack/salt/issues/60557)
- Fix xfs module when additional output included in mkfs.xfs command. [#60853](https://github.com/saltstack/salt/issues/60853)
- Fixed parsing new format of terraform states in roster.terraform [#60915](https://github.com/saltstack/salt/issues/60915)
- Fixed recognizing installed ARMv7 rpm packages in compatible architectures. [#60994](https://github.com/saltstack/salt/issues/60994)
- Fixing changes dict in pkg state to be consistent when installing and test=True. [#60995](https://github.com/saltstack/salt/issues/60995)
- Fix cron.present duplicating entries when changing timespec to special. [#60997](https://github.com/saltstack/salt/issues/60997)
- Made salt-ssh respect --wipe again [#61083](https://github.com/saltstack/salt/issues/61083)
- state.orchestrate_single only passes a pillar if it is set to the state
  function. This allows it to be used with state functions that don't accept a
  pillar keyword argument. [#61092](https://github.com/saltstack/salt/issues/61092)
- Fix ipset state when the comment kwarg is set. [#61122](https://github.com/saltstack/salt/issues/61122)
- Fix issue with archive.unzip where the password was not being encoded for the extract function [#61422](https://github.com/saltstack/salt/issues/61422)
- Some Linux distributions (like AlmaLinux, Astra Linux, Debian, Mendel, Linux
  Mint, Pop!_OS, Rocky Linux) report different `oscodename`, `osfullname`,
  `osfinger` grains if lsb-release is installed or not. They have been changed to
  only derive these OS grains from `/etc/os-release`. [#61618](https://github.com/saltstack/salt/issues/61618)
- Pop!_OS uses the full version (YY.MM) in the osfinger grain now, not just the year. This allows differentiating for example between 20.04 and 20.10. [#61619](https://github.com/saltstack/salt/issues/61619)
- Fix ssh config roster to correctly parse the ssh config files that contain spaces. [#61650](https://github.com/saltstack/salt/issues/61650)
- Fix SoftLayer configuration not raising an exception when a domain is missing [#61727](https://github.com/saltstack/salt/issues/61727)
- Allow the minion to start or salt-call to run even if the user doesn't have permissions to read the root_dir value from the registry [#61789](https://github.com/saltstack/salt/issues/61789)
- Need to move the creation of the proxy object for the ProxyMinion further down in the initialization for sub proxies to ensure that all modules, especially any custom proxy modules, are available before attempting to run the init function. [#61805](https://github.com/saltstack/salt/issues/61805)
- Fixed malformed state return when merge-serializing to an improperly formatted file [#61814](https://github.com/saltstack/salt/issues/61814)
- Made cmdmod._run[_all]_quiet work during minion startup on MacOS with runas specified (which fixed mac_service) [#61816](https://github.com/saltstack/salt/issues/61816)
- When deleting the vault cache, also delete from the session cache [#61821](https://github.com/saltstack/salt/issues/61821)
- Ignore errors on reading license info with dpkg_lowpkg to prevent tracebacks on getting package information. [#61827](https://github.com/saltstack/salt/issues/61827)
- win_lgpo: Display conflicting policy names when more than one policy is found [#61859](https://github.com/saltstack/salt/issues/61859)
- win_lgpo: Fixed intermittent KeyError when getting policy setting using lgpo.get_policy [#61860](https://github.com/saltstack/salt/issues/61860)
- Fixed listing minions on OpenBSD [#61966](https://github.com/saltstack/salt/issues/61966)
- Make Salt to return an error on "pkg" modules and states when targeting duplicated package names [#62019](https://github.com/saltstack/salt/issues/62019)
- Fix return of REST-returned permissions when auth_list is set [#62022](https://github.com/saltstack/salt/issues/62022)
- Normalize package names once on using pkg.installed/removed with yum to make it possible to install packages with the name containing a part similar to a name of architecture. [#62029](https://github.com/saltstack/salt/issues/62029)
- Fix inconsitency regarding name and pkgs parameters between zypperpkg.upgrade() and yumpkg.upgrade() [#62030](https://github.com/saltstack/salt/issues/62030)
- Fix attr=all handling in pkg.list_pkgs() (yum/zypper). [#62032](https://github.com/saltstack/salt/issues/62032)
- Fixed the humanname being ignored in pkgrepo.managed on openSUSE Leap [#62053](https://github.com/saltstack/salt/issues/62053)
- Fixed issue with some LGPO policies having whitespace at the beginning or end of the element alias [#62058](https://github.com/saltstack/salt/issues/62058)
- Fix ordering of args to libcloud_storage.download_object module [#62074](https://github.com/saltstack/salt/issues/62074)
- Ignore extend declarations in sls files that are excluded. [#62082](https://github.com/saltstack/salt/issues/62082)
- Remove leftover usage of impacket [#62101](https://github.com/saltstack/salt/issues/62101)
- Pass executable path from _get_path_exec() is used when calling the program.
  The $HOME env is no longer modified globally.
  Only trailing newlines are stripped from the fetched secret.
  Pass process arguments are handled in a secure way. [#62120](https://github.com/saltstack/salt/issues/62120)
- Ignore some command return codes in openbsdrcctl_service to prevent spurious errors [#62131](https://github.com/saltstack/salt/issues/62131)
- Fixed extra period in filename output in tls module. Instead of "server.crt." it will now be "server.crt". [#62139](https://github.com/saltstack/salt/issues/62139)
- Make sure lingering PAexec-*.exe files in the Windows directory are cleaned up [#62152](https://github.com/saltstack/salt/issues/62152)
- Restored Salt's DeprecationWarnings [#62185](https://github.com/saltstack/salt/issues/62185)
- Fixed issue with forward slashes on Windows with file.recurse and clean=True [#62197](https://github.com/saltstack/salt/issues/62197)
- Recognize OSMC as Debian-based [#62198](https://github.com/saltstack/salt/issues/62198)
- Fixed Zypper module failing on RPM lock file being temporarily unavailable. [#62204](https://github.com/saltstack/salt/issues/62204)
- Improved error handling and diagnostics in the proxmox salt-cloud driver [#62211](https://github.com/saltstack/salt/issues/62211)
- Added EndeavourOS to the Arch os_family. [#62220](https://github.com/saltstack/salt/issues/62220)
- Fix salt-ssh not detecting `platform-python` as a valid interpreter on EL8 [#62235](https://github.com/saltstack/salt/issues/62235)
- Fix pkg.version_cmp on openEuler and a few other os flavors. [#62248](https://github.com/saltstack/salt/issues/62248)
- Fix localhost detection in glusterfs.peers [#62273](https://github.com/saltstack/salt/issues/62273)
- Fix Salt Package Manager (SPM) exception when calling spm create_repo . [#62281](https://github.com/saltstack/salt/issues/62281)
- Fix matcher slowness due to loader invocation [#62283](https://github.com/saltstack/salt/issues/62283)
- Fixes the Puppet module for non-aio Puppet packages for example running the Puppet module on FreeBSD. [#62323](https://github.com/saltstack/salt/issues/62323)
- Issue 62334: Displays a debug log message instead of an error log message when the publisher fails to connect [#62334](https://github.com/saltstack/salt/issues/62334)
- Fix pyobjects renderer access to opts and sls [#62336](https://github.com/saltstack/salt/issues/62336)
- Fix use of random shuffle and sample functions as Jinja filters [#62372](https://github.com/saltstack/salt/issues/62372)
- Fix groups with duplicate GIDs are not returned by get_group_list [#62377](https://github.com/saltstack/salt/issues/62377)
- Fix the "zpool.present" state when enabling zpool features that are already active. [#62390](https://github.com/saltstack/salt/issues/62390)
- Fix ability to execute remote file client methods in saltcheck [#62398](https://github.com/saltstack/salt/issues/62398)
- Update all platforms to use pycparser 2.21 or greater for Py 3.9 or higher, fixes fips fault with openssl v3.x [#62400](https://github.com/saltstack/salt/issues/62400)
- Due to changes in the Netmiko library for the exception paths, need to check the version of Netmiko python library and then import the exceptions from different locations depending on the result. [#62405](https://github.com/saltstack/salt/issues/62405)
- When using preq on a state, then prereq state will first be run with test=True to determine if there are changes.  When there are changes, the state with the prereq option will be run prior to the prereq state.  If this state fails then the prereq state will not run and the state output uses the test=True run.  However, the proposed changes are included for the prereq state are included from the test=True run.  We should pull those out as there weren't actually changes since the prereq state did not run. [#62408](https://github.com/saltstack/salt/issues/62408)
- Added directory mode for file.copy with makedirs [#62426](https://github.com/saltstack/salt/issues/62426)
- Provide better error handling in the various napalm proxy minion functions when the device is not accessible. [#62435](https://github.com/saltstack/salt/issues/62435)
- When handling aggregation, change the order to ensure that the requisites are aggregated first and then the state functions are aggregated.  Caching whether aggregate functions are available for particular states so we don't need to attempt to load them everytime. [#62439](https://github.com/saltstack/salt/issues/62439)
- The patch allows to boostrap kubernetes clusters in the version above 1.13 via salt module [#62451](https://github.com/saltstack/salt/issues/62451)
- sysctl.persist now updates the in-memory value on FreeBSD even if the on-disk value was already correct. [#62461](https://github.com/saltstack/salt/issues/62461)
- Fixed parsing CDROM apt sources [#62474](https://github.com/saltstack/salt/issues/62474)
- Update sanitizing masking for Salt SSH to include additional password like strings. [#62483](https://github.com/saltstack/salt/issues/62483)
- Fix user/group checking on file state functions in the test mode. [#62499](https://github.com/saltstack/salt/issues/62499)
- Fix user.present to allow removing groups using optional_groups parameter and enforcing idempotent group membership. [#62502](https://github.com/saltstack/salt/issues/62502)
- Fix possible tracebacks if there is a package with '------' or '======' in the description is installed on the Debian based minion. [#62519](https://github.com/saltstack/salt/issues/62519)
- Fixed the omitted "pool" parameter when cloning a VM with the proxmox salt-cloud driver [#62521](https://github.com/saltstack/salt/issues/62521)
- Fix rendering of pyobjects states in saltcheck [#62523](https://github.com/saltstack/salt/issues/62523)
- Fixes pillar where a corrupted CacheDisk file forces the pillar to be rebuilt [#62527](https://github.com/saltstack/salt/issues/62527)
- Use str() method instead of repo_line for when python3-apt is installed or not in aptpkg.py. [#62546](https://github.com/saltstack/salt/issues/62546)
- Remove the connection_timeout from netmiko_connection_args before netmiko_connection_args is added to __context__["netmiko_device"]["args"] which is passed along to the Netmiko library. [#62547](https://github.com/saltstack/salt/issues/62547)
- Fix order specific mount.mounted options for persist [#62556](https://github.com/saltstack/salt/issues/62556)
- Fixed salt-cloud cloning a proxmox VM with a specified new vmid. [#62558](https://github.com/saltstack/salt/issues/62558)
- Fix runas with cmd module when using the onedir bundled packages [#62565](https://github.com/saltstack/salt/issues/62565)
- Update setproctitle version for all platforms [#62576](https://github.com/saltstack/salt/issues/62576)
- Fixed missing parameters when cloning a VM with the proxmox salt-cloud driver [#62580](https://github.com/saltstack/salt/issues/62580)
- Handle PermissionError when importing crypt when FIPS is enabled. [#62587](https://github.com/saltstack/salt/issues/62587)
- Correctly reraise exceptions in states.http [#62595](https://github.com/saltstack/salt/issues/62595)
- Fixed syndic eauth. Now jobs will be published when a valid eauth user is targeting allowed minions/functions. [#62618](https://github.com/saltstack/salt/issues/62618)
- updated rest_cherry/app to properly detect arg sent as a string as curl will do when only one arg is supplied. [#62624](https://github.com/saltstack/salt/issues/62624)
- Prevent possible tracebacks in core grains module by ignoring non utf8 characters in /proc/1/environ, /proc/1/cmdline, /proc/cmdline [#62633](https://github.com/saltstack/salt/issues/62633)
- Fixed vault ext pillar return data for KV v2 [#62651](https://github.com/saltstack/salt/issues/62651)
- Fix saltcheck _get_top_states doesn't pass saltenv to state.show_top [#62654](https://github.com/saltstack/salt/issues/62654)
- Fix groupadd.* functions hard code relative command name [#62657](https://github.com/saltstack/salt/issues/62657)
- Fixed pdbedit.create trying to use a bytes-like hash as string. [#62670](https://github.com/saltstack/salt/issues/62670)
- Fix depenency on legacy boto module in boto3 modules [#62672](https://github.com/saltstack/salt/issues/62672)
- Modified "_get_flags" function so that it returns regex flags instead of integers [#62676](https://github.com/saltstack/salt/issues/62676)
- Change startup ReqServer log messages from error to info level. [#62728](https://github.com/saltstack/salt/issues/62728)
- Fix kmod.* functions hard code relative command name [#62772](https://github.com/saltstack/salt/issues/62772)
- Remove mako as a dependency in Windows and macOS. [#62785](https://github.com/saltstack/salt/issues/62785)
- Fix mac_brew_pkg to work with null taps [#62793](https://github.com/saltstack/salt/issues/62793)
- Fixing a bug when listing the running schedule if "schedule.enable" and/or "schedule.disable" has been run, where the "enabled" items is being treated as a schedule item. [#62795](https://github.com/saltstack/salt/issues/62795)
- Prevent annoying RuntimeWarning message about line buffering (buffering=1) not being supported in binary mode [#62817](https://github.com/saltstack/salt/issues/62817)
- Include UID and GID checks in modules.file.check_perms as well as comparing
  ownership by username and group name. [#62818](https://github.com/saltstack/salt/issues/62818)
- Fix presence events on TCP transport by removing a client's presence when minion disconnects from publish channel correctly [#62826](https://github.com/saltstack/salt/issues/62826)
- Remove Azure deprecation messages from functions that always run w/ salt-cloud [#62845](https://github.com/saltstack/salt/issues/62845)
- Use select instead of iterating over entrypoints as a dictionary for importlib_metadata>=5.0.0 [#62854](https://github.com/saltstack/salt/issues/62854)
- Fixed master job scheduler using when [#62858](https://github.com/saltstack/salt/issues/62858)
- LGPO: Added support for missing domain controller policies: VulnerableChannelAllowList and LdapEnforceChannelBinding [#62873](https://github.com/saltstack/salt/issues/62873)
- Fix unnecessarily complex gce metadata grains code to use googles metadata service more effectively. [#62878](https://github.com/saltstack/salt/issues/62878)
- Fixed dockermod version_info function for docker-py 6.0.0+ [#62882](https://github.com/saltstack/salt/issues/62882)
- Moving setting the LOAD_BALANCING_POLICY_MAP dictionary into the try except block that determines if the cassandra_cql module should be made available. [#62886](https://github.com/saltstack/salt/issues/62886)
- Updating various MongoDB module functions to work with latest version of pymongo. [#62900](https://github.com/saltstack/salt/issues/62900)
- Restored channel for Syndic minions to send job returns to the Salt master. [#62933](https://github.com/saltstack/salt/issues/62933)
- removed _resolve_deps as it required a library that is not generally avalible. and switched to apt-get for everything as that can auto resolve dependencies. [#62934](https://github.com/saltstack/salt/issues/62934)
- Updated pyzmq to version 22.0.3 on Windows builds because the old version was causing salt-minion/salt-call to hang [#62937](https://github.com/saltstack/salt/issues/62937)
- Allow root user to modify crontab lines for non-root users (except AIX and Solaris). Align crontab line changes with the file ones and also with listing crontab. [#62940](https://github.com/saltstack/salt/issues/62940)
- Fix systemd_service.* functions hard code relative command name [#62942](https://github.com/saltstack/salt/issues/62942)
- Fix file.symlink backupname operation can copy remote contents to local disk [#62953](https://github.com/saltstack/salt/issues/62953)
- Issue #62968: Fix issue where cloud deployments were putting the keys in the wrong location on Windows hosts [#62968](https://github.com/saltstack/salt/issues/62968)
- Fixed gpg_passphrase issue with gpg decrypt/encrypt functions [#62977](https://github.com/saltstack/salt/issues/62977)
- Fix file.tidied FileNotFoundError [#62986](https://github.com/saltstack/salt/issues/62986)
- Fixed bug where module.wait states were detected as running legacy module.run syntax [#62988](https://github.com/saltstack/salt/issues/62988)
- Fixed issue with win_wua module where it wouldn't load if the CryptSvc was set to Manual start [#62993](https://github.com/saltstack/salt/issues/62993)
- The `__opts__` dunder dictionary is now added to the loader's `pack` if not
  already present, which makes it accessible via the
  `salt.loader.context.NamedLoaderContext` class. [#63013](https://github.com/saltstack/salt/issues/63013)
- Issue #63024: Fix issue where grains and config data were being place in the wrong location on Windows hosts [#63024](https://github.com/saltstack/salt/issues/63024)
- Fix btrfs.subvolume_snapshot command failing [#63025](https://github.com/saltstack/salt/issues/63025)
- Fix file.retention_schedule always reports changes [#63033](https://github.com/saltstack/salt/issues/63033)
- Fix mongo authentication for mongo ext_pillar and mongo returner

  This fix also include the ability to use the mongo connection string for mongo ext_pillar [#63058](https://github.com/saltstack/salt/issues/63058)
- Fixed x509.create_csr creates invalid CSR by default in the new cryptography x509 module. [#63103](https://github.com/saltstack/salt/issues/63103)
- TCP transport documentation now contains proper master/minion-side filtering information [#63120](https://github.com/saltstack/salt/issues/63120)
- Fixed gpg.verify does not respect gnupghome [#63145](https://github.com/saltstack/salt/issues/63145)
- User responsible for the runner is now correctly reported in the events on the event bus for the runner. [#63148](https://github.com/saltstack/salt/issues/63148)
- Made pillar cache pass extra minion data as well [#63208](https://github.com/saltstack/salt/issues/63208)
- Fix serious performance issues with the file.tidied module [#63231](https://github.com/saltstack/salt/issues/63231)
- Fix rpm_lowpkg version comparison logic when using rpm-vercmp and only one version has a release number. [#63317](https://github.com/saltstack/salt/issues/63317)
- Import StrictVersion and LooseVersion from setuptools.distutils.verison or setuptools._distutils.version, if first not available [#63350](https://github.com/saltstack/salt/issues/63350)
- ``service.status`` on Windows does no longer throws a CommandExecutionError if
  the service is not found on the system. It now returns "Not Found" instead. [#63577](https://github.com/saltstack/salt/issues/63577)
- When the shell is passed as powershell or pwsh, only wrapper the shell in quotes if cmd.run is running on Windows.  When quoted on Linux hosts, this results in an error when the keyword arguments are appended. [#63590](https://github.com/saltstack/salt/issues/63590)
- LGPO: Added support for "Relax minimum password length limits" [#63596](https://github.com/saltstack/salt/issues/63596)
- Fixed the ability to set a scheduled task to auto delete if not scheduled to run again (``delete_after``) [#63650](https://github.com/saltstack/salt/issues/63650)
- When a job is disabled only increase it's _next_fire_time value if the job would have run at the current time, eg. the current _next_fire_time == now. [#63699](https://github.com/saltstack/salt/issues/63699)
- have salt.template.compile_template_str cleanup its temp files. [#63724](https://github.com/saltstack/salt/issues/63724)
- Check file is not empty before attempting to read pillar disk cache file [#63729](https://github.com/saltstack/salt/issues/63729)
- Fixed an issue with generating fingerprints for public keys with different line endings [#63742](https://github.com/saltstack/salt/issues/63742)
- Add `fileserver_interval` and `maintenance_interval` master configuration options. These options control how often to restart the FileServerUpdate and Maintenance processes. Some file server and pillar configurations are known to cause memory leaks over time. A notable example of this are configurations that use pygit2. Salt can not guarantee dependency libraries like pygit2 won't leak memory. Restarting any long running processes that use pygit2 guarantees we can keep the master's memory usage in check. [#63747](https://github.com/saltstack/salt/issues/63747)
- mac_xattr.list and mac_xattr.read will replace undecode-able bytes to avoid raising CommandExecutionError. [#63779](https://github.com/saltstack/salt/issues/63779) [#63779](https://github.com/saltstack/salt/issues/63779)
- Change default GPG keyserver from pgp.mit.edu to keys.openpgp.org. [#63806](https://github.com/saltstack/salt/issues/63806)
- fix cherrypy 400 error output to be less generic. [#63835](https://github.com/saltstack/salt/issues/63835)
- Ensure kwargs is passed along to _call_apt when passed into install function. [#63847](https://github.com/saltstack/salt/issues/63847)
- remove eval and update logging to be more informative on bad config [#63879](https://github.com/saltstack/salt/issues/63879)
- add linux_distribution to util to stop dep warning [#63904](https://github.com/saltstack/salt/issues/63904)
- Fix valuerror when trying to close fileclient. Remove usage of __del__ and close the filclient properly. [#63920](https://github.com/saltstack/salt/issues/63920)
- Handle the situation when a sub proxy minion does not init properly, eg. an exception happens, and the sub proxy object is not available. [#63923](https://github.com/saltstack/salt/issues/63923)
- Clarifying documentation for extension_modules configuration option. [#63929](https://github.com/saltstack/salt/issues/63929)
- Windows pkg module now properly handles versions containing strings [#63935](https://github.com/saltstack/salt/issues/63935)
- Handle the scenario when the check_cmd requisite is used with a state function when the state has a local check_cmd function but that function isn't used by that function. [#63948](https://github.com/saltstack/salt/issues/63948)
- Issue #63981: Allow users to pass verify_ssl to pkg.install/pkg.installed on Windows [#63981](https://github.com/saltstack/salt/issues/63981)
- Hardened permissions on workers.ipc and master_event_pub.ipc. [#64063](https://github.com/saltstack/salt/issues/64063)


### Added

- Introduce a `LIB_STATE_DIR` syspaths variable which defaults to `CONFIG_DIR`,
  but can be individually customized during installation by specifying
  `--salt-lib-state-dir` during installation. Change the default `pki_dir` to
  `<LIB_STATE_DIR>/pki/master` (for the master) and `<LIB_STATE_DIR>/pki/minion`
  (for the minion). [#3396](https://github.com/saltstack/salt/issues/3396)
- Allow users to enable 'queue=True' for all state runs via config file [#31468](https://github.com/saltstack/salt/issues/31468)
- Added pillar templating to vault policies [#43287](https://github.com/saltstack/salt/issues/43287)
- Add support for NVMeF as a transport protocol for hosts in a Pure Storage FlashArray [#51088](https://github.com/saltstack/salt/issues/51088)
- A new salt-ssh roster that generates a roster by parses a known_hosts file. [#54679](https://github.com/saltstack/salt/issues/54679)
- Added Windows Event Viewer support [#54713](https://github.com/saltstack/salt/issues/54713)
- Added the win_lgpo_reg state and execution modules which will allow registry based group policy to be set directly in the Registry.pol file [#56013](https://github.com/saltstack/salt/issues/56013)
- Added resource tagging functions to boto_dynamodb execution module [#57500](https://github.com/saltstack/salt/issues/57500)
- Added `openvswitch_db` state module and functions `bridge_to_parent`,
  `bridge_to_vlan`, `db_get`, and `db_set` to the `openvswitch` execution module.
  Also added optional `parent` and `vlan` parameters to the
  `openvswitch_bridge.present` state module function and the
  `openvswitch.bridge_create` execution module function. [#58986](https://github.com/saltstack/salt/issues/58986)
- State module to manage SysFS attributes [#60154](https://github.com/saltstack/salt/issues/60154)
- Added ability for `salt.wait_for_event` to handle `event_id`s that have a list value. [#60430](https://github.com/saltstack/salt/issues/60430)
- Added suport for Linux ppc64le core grains (cpu_model, virtual, productname, manufacturer, serialnumber) and arm core grains (serialnumber, productname) [#60518](https://github.com/saltstack/salt/issues/60518)
- Added autostart option to virt.defined and virt.running states, along with virt.update execution modules. [#60700](https://github.com/saltstack/salt/issues/60700)
- Added .0 back to our versioning scheme for future versions (e.g. 3006.0) [#60722](https://github.com/saltstack/salt/issues/60722)
- Initial work to allow parallel startup of proxy minions when used as sub proxies with Deltaproxy. [#61153](https://github.com/saltstack/salt/issues/61153)
- Added node label support for GCE [#61245](https://github.com/saltstack/salt/issues/61245)
- Support the --priority flag when adding sources to Chocolatey. [#61319](https://github.com/saltstack/salt/issues/61319)
- Add namespace option to ext_pillar.http_json [#61335](https://github.com/saltstack/salt/issues/61335)
- Added a filter function to ps module to get a list of processes on a minion according to their state. [#61420](https://github.com/saltstack/salt/issues/61420)
- Add postgres.timeout option to postgres module for limiting postgres query times [#61433](https://github.com/saltstack/salt/issues/61433)
- Added new optional vault option, ``config_location``. This can be either ``master`` or ``local`` and defines where vault will look for connection details, either requesting them from the master or using the local config. [#61857](https://github.com/saltstack/salt/issues/61857)
- Add ipwrap() jinja filter to wrap IPv6 addresses with brackets. [#61931](https://github.com/saltstack/salt/issues/61931)
- 'tcp' transport is now available in ipv6-only network [#62009](https://github.com/saltstack/salt/issues/62009)
- Add `diff_attr` parameter to pkg.upgrade() (zypper/yum). [#62031](https://github.com/saltstack/salt/issues/62031)
- Config option pass_variable_prefix allows to distinguish variables that contain paths to pass secrets.
  Config option pass_strict_fetch allows to error out when a secret cannot be fetched from pass.
  Config option pass_dir allows setting the PASSWORD_STORE_DIR env for pass.
  Config option pass_gnupghome allows setting the $GNUPGHOME env for pass. [#62120](https://github.com/saltstack/salt/issues/62120)
- Add file.pruned state and expanded file.rmdir exec module functionality [#62178](https://github.com/saltstack/salt/issues/62178)
- Added "dig.PTR" function to resolve PTR records for IPs, as well as tests and documentation [#62275](https://github.com/saltstack/salt/issues/62275)
- Added the ability to remove a KB using the DISM state/execution modules [#62366](https://github.com/saltstack/salt/issues/62366)
- Add "<tiamat> python" subcommand to allow execution or arbitrary scripts via bundled Python runtime [#62381](https://github.com/saltstack/salt/issues/62381)
- Add ability to provide conditions which convert normal state actions to no-op when true [#62446](https://github.com/saltstack/salt/issues/62446)
- Added debug log messages displaying the command being run when installing packages on Windows [#62480](https://github.com/saltstack/salt/issues/62480)
- Add biosvendor grain [#62496](https://github.com/saltstack/salt/issues/62496)
- Add ifelse Jinja function as found in CFEngine [#62508](https://github.com/saltstack/salt/issues/62508)
- Implementation of Amazon EC2 instance detection and setting `virtual_subtype` grain accordingly including the product if possible to identify. [#62539](https://github.com/saltstack/salt/issues/62539)
- Adds __env__substitution to ext_pillar.stack; followup of #61531, improved exception handling for stacked template (jinja) template rendering and yaml parsing in ext_pillar.stack [#62578](https://github.com/saltstack/salt/issues/62578)
- Increase file.tidied flexibility with regard to age and size [#62678](https://github.com/saltstack/salt/issues/62678)
- Added "connected_devices" feature to netbox pillar module. It contains extra information about devices connected to the minion [#62761](https://github.com/saltstack/salt/issues/62761)
- Add atomic file operation for symlink changes [#62768](https://github.com/saltstack/salt/issues/62768)
- Add password/account locking/unlocking in user.present state on supported operating systems [#62856](https://github.com/saltstack/salt/issues/62856)
- Added onchange configuration for script engine [#62867](https://github.com/saltstack/salt/issues/62867)
- Added output and bare functionality to export_key gpg module function [#62978](https://github.com/saltstack/salt/issues/62978)
- Add keyvalue serializer for environment files [#62983](https://github.com/saltstack/salt/issues/62983)
- Add ability to ignore symlinks in file.tidied [#63042](https://github.com/saltstack/salt/issues/63042)
- salt-cloud support IMDSv2 tokens when using 'use-instance-role-credentials' [#63067](https://github.com/saltstack/salt/issues/63067)
- Fix running fast tests twice and add git labels to suite. [#63081](https://github.com/saltstack/salt/issues/63081)
- Add ability for file.symlink to not set ownership on existing links [#63093](https://github.com/saltstack/salt/issues/63093)
- Restore the previous slack engine and deprecate it, rename replace the slack engine to slack_bolt until deprecation [#63095](https://github.com/saltstack/salt/issues/63095)
- Add functions that will return the underlying block device, mount point, and filesystem type for a given path [#63098](https://github.com/saltstack/salt/issues/63098)
- Add ethtool execution and state module functions for pause [#63128](https://github.com/saltstack/salt/issues/63128)
- Add boardname grain [#63131](https://github.com/saltstack/salt/issues/63131)
- Added management of ECDSA/EdDSA private keys with x509 modules in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#63248](https://github.com/saltstack/salt/issues/63248)
- Added x509 modules support for different output formats in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#63249](https://github.com/saltstack/salt/issues/63249)
- Added deprecation_warning test state for ensuring that deprecation warnings are correctly emitted. [#63315](https://github.com/saltstack/salt/issues/63315)
- Adds a state_events option to state.highstate, state.apply, state.sls, state.sls_id.
  This allows users to enable state_events on a per use basis rather than having to
  enable them globally for all state runs. [#63316](https://github.com/saltstack/salt/issues/63316)
- Allow max queue size setting for state runs to prevent performance problems from queue growth [#63356](https://github.com/saltstack/salt/issues/63356)
- Add support of exposing meta_server_grains for Azure VMs [#63606](https://github.com/saltstack/salt/issues/63606)
- Include the version of `relenv` in the versions report. [#63827](https://github.com/saltstack/salt/issues/63827)
- Added debug log messages displaying the command being run when removing packages on Windows [#63866](https://github.com/saltstack/salt/issues/63866)
- Adding the ability to exclude arguments from a state that end up passed to cmd.retcode when requisites such as onlyif or unless are used. [#63956](https://github.com/saltstack/salt/issues/63956)
- Add --next-release argument to salt/version.py, which prints the next upcoming release. [#64023](https://github.com/saltstack/salt/issues/64023)


### Security

- Upgrade Requirements Due to Security Issues.

  * Upgrade to `cryptography>=39.0.1` due to:
    * https://github.com/advisories/GHSA-x4qr-2fvf-3mr5
    * https://github.com/advisories/GHSA-w7pp-m8wf-vj6r
  * Upgrade to `pyopenssl==23.0.0` due to the cryptography upgrade.
  * Update to `markdown-it-py==2.2.0` due to:
    * https://github.com/advisories/GHSA-jrwr-5x3p-hvc3
    * https://github.com/advisories/GHSA-vrjv-mxr7-vjf8 [#63882](https://github.com/saltstack/salt/issues/63882)


## 3006.0rc3 (2023-03-29)


### Removed

- Remove and deprecate the __orchestration__ key from salt.runner and salt.wheel return data. To get it back, set features.enable_deprecated_orchestration_flag master configuration option to True. The flag will be completely removed in Salt 3008 Argon. [#59917](https://github.com/saltstack/salt/issues/59917)
- Removed distutils and replaced with setuptools, given distutils is deprecated and removed in Python 3.12 [#60476](https://github.com/saltstack/salt/issues/60476)
- Removed ``runtests`` targets from ``noxfile.py`` [#62239](https://github.com/saltstack/salt/issues/62239)
- Removed the PyObjC dependency.

  This addresses problems with building a one dir build for macOS.
  It became problematic because depending on the macOS version, it pulls different dependencies, and we would either have to build a macos onedir for each macOS supported release, or ship a crippled onedir(because it would be tied to the macOS version where the onedir was built).
  Since it's currently not being used, it's removed. [#62432](https://github.com/saltstack/salt/issues/62432)
- Removed `SixRedirectImporter` from Salt. Salt hasn't shipped `six` since Salt 3004. [#63874](https://github.com/saltstack/salt/issues/63874)


### Deprecated

- renamed `keep_jobs`, specifying job cache TTL in hours, to `keep_jobs_seconds`, specifying TTL in seconds.
  `keep_jobs` will be removed in the Argon release [#55295](https://github.com/saltstack/salt/issues/55295)
- Removing all references to napalm-base which is no longer supported. [#61542](https://github.com/saltstack/salt/issues/61542)
- The 'ip_bracket' function has been moved from salt/utils/zeromq.py in salt/utils/network.py [#62009](https://github.com/saltstack/salt/issues/62009)
- The `expand_repo_def` function in `salt.modules.aptpkg` is now deprecated. It's only used in `salt.states.pkgrepo` and it has no use of being exposed to the CLI. [#62485](https://github.com/saltstack/salt/issues/62485)
- Deprecated defunct Django returner [#62644](https://github.com/saltstack/salt/issues/62644)
- Deprecate core ESXi and associated states and modules, vcenter and vsphere support in favor of Salt VMware Extensions [#62754](https://github.com/saltstack/salt/issues/62754)
- Removing manufacture grain which has been deprecated. [#62914](https://github.com/saltstack/salt/issues/62914)
- Removing deprecated utils/boto3_elasticsearch.py [#62915](https://github.com/saltstack/salt/issues/62915)
- Removing support for the now deprecated _ext_nodes from salt/master.py. [#62917](https://github.com/saltstack/salt/issues/62917)
- Deprecating the Salt Slack engine in favor of the Salt Slack Bolt Engine. [#63095](https://github.com/saltstack/salt/issues/63095)
- `salt.utils.version.StrictVersion` is now deprecated and it's use should be replaced with `salt.utils.version.Version`. [#63383](https://github.com/saltstack/salt/issues/63383)


### Changed

- More intelligent diffing in changes of file.serialize state. [#48609](https://github.com/saltstack/salt/issues/48609)
- Move deprecation of the neutron module to Argon. Please migrate to the neutronng module instead. [#49430](https://github.com/saltstack/salt/issues/49430)
- ``umask`` is now a global state argument, instead of only applying to ``cmd``
  states. [#57803](https://github.com/saltstack/salt/issues/57803)
- Update pillar.obfuscate to accept kwargs in addition to args.  This is useful when passing in keyword arguments like saltenv that are then passed along to pillar.items. [#58971](https://github.com/saltstack/salt/issues/58971)
- Improve support for listing macOS brew casks [#59439](https://github.com/saltstack/salt/issues/59439)
- Add missing MariaDB Grants to mysql module.
  MariaDB has added some grants in 10.4.x and 10.5.x that are not present here, which results in an error when creating.
  Also improved exception handling in `grant_add` which did not log the original error message and replaced it with a generic error. [#61409](https://github.com/saltstack/salt/issues/61409)
- Use VENV_PIP_TARGET environment variable as a default target for pip if present. [#62089](https://github.com/saltstack/salt/issues/62089)
- Disabled FQDNs grains on macOS by default [#62168](https://github.com/saltstack/salt/issues/62168)
- Replaced pyroute2.IPDB with pyroute2.NDB, as the former is deprecated [#62218](https://github.com/saltstack/salt/issues/62218)
- Enhance capture of error messages for Zypper calls in zypperpkg module. [#62346](https://github.com/saltstack/salt/issues/62346)
- Removed GPG_1_3_1 check [#62895](https://github.com/saltstack/salt/issues/62895)
- Requisite state chunks now all consistently contain `__id__`, `__sls__` and `name`. [#63012](https://github.com/saltstack/salt/issues/63012)
- netapi_enable_clients option to allow enabling/disabling of clients in salt-api.
  By default all clients will now be disabled. Users of salt-api will need
  to update their master config to enable the clients that they use. Not adding
  the netapi_enable_clients option with required clients to the master config will
  disable salt-api. [#63050](https://github.com/saltstack/salt/issues/63050)
- Stop relying on `salt/_version.py` to write Salt's version. Instead use `salt/_version.txt` which only contains the version string. [#63383](https://github.com/saltstack/salt/issues/63383)
- Set enable_fqdns_grains to be False by default. [#63595](https://github.com/saltstack/salt/issues/63595)
- Changelog snippet files must now have a `.md` file extension to be more explicit on what type of rendering is done when they are included in the main `CHANGELOG.md` file. [#63710](https://github.com/saltstack/salt/issues/63710)
- Upgraded to `relenv==0.9.0` [#63883](https://github.com/saltstack/salt/issues/63883)


### Fixed

- Add kwargs to handle extra parameters for http.query [#36138](https://github.com/saltstack/salt/issues/36138)
- Fix mounted bind mounts getting active mount options added [#39292](https://github.com/saltstack/salt/issues/39292)
- Fix `sysctl.present` converts spaces to tabs. [#40054](https://github.com/saltstack/salt/issues/40054)
- Fixes state pkg.purged to purge removed packages on Debian family systems [#42306](https://github.com/saltstack/salt/issues/42306)
- Fix fun_args missing from syndic returns [#45823](https://github.com/saltstack/salt/issues/45823)
- Fix mount.mounted with 'mount: False' reports unmounted file system as unchanged when running with test=True [#47201](https://github.com/saltstack/salt/issues/47201)
- Issue #49310: Allow users to touch a file with Unix date of birth [#49310](https://github.com/saltstack/salt/issues/49310)
- Do not raise an exception in pkg.info_installed on nonzero return code [#51620](https://github.com/saltstack/salt/issues/51620)
- Passes the value of the force parameter from file.copy to its call to file.remove so that files with the read-only attribute are handled. [#51739](https://github.com/saltstack/salt/issues/51739)
- Fixed x509.certificate_managed creates new certificate every run in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#52167](https://github.com/saltstack/salt/issues/52167)
- Don't check for cached pillar errors on state.apply [#52354](https://github.com/saltstack/salt/issues/52354), [#57180](https://github.com/saltstack/salt/issues/57180), [#59339](https://github.com/saltstack/salt/issues/59339)
- Swapping out args and kwargs for arg and kwarg respectively in the Slack engine when the command passed is a runner. [#52400](https://github.com/saltstack/salt/issues/52400)
- Ensure when we're adding chunks to the rules when running aggregation with the iptables state module we use a copy of the chunk otherwise we end up with a recursive mess. [#53353](https://github.com/saltstack/salt/issues/53353)
- When user_create or user_remove fail, return False instead of returning the error. [#53377](https://github.com/saltstack/salt/issues/53377)
- Include sync_roster when sync_all is called. [#53914](https://github.com/saltstack/salt/issues/53914)
- Avoid warning noise in lograte.get [#53988](https://github.com/saltstack/salt/issues/53988)
- Fixed listing revoked keys with gpg.list_keys [#54347](https://github.com/saltstack/salt/issues/54347)
- Fix mount.mounted does not handle blanks properly [#54508](https://github.com/saltstack/salt/issues/54508)
- Fixed grain num_cpus get wrong CPUs count in case of inconsistent CPU numbering. [#54682](https://github.com/saltstack/salt/issues/54682)
- Fix spelling error for python_shell argument in dpkg_lower module [#54907](https://github.com/saltstack/salt/issues/54907)
- Cleaned up bytes response data before sending to non-bytes compatible returners (postgres, mysql) [#55226](https://github.com/saltstack/salt/issues/55226)
- Fixed malformed state return when testing file.managed with unavailable source file [#55269](https://github.com/saltstack/salt/issues/55269)
- Included stdout in error message for Zypper calls in zypperpkg module. [#56016](https://github.com/saltstack/salt/issues/56016)
- Fixed pillar.filter_by with salt-ssh [#56093](https://github.com/saltstack/salt/issues/56093)
- Fix boto_route53 issue with (multiple) VPCs. [#57139](https://github.com/saltstack/salt/issues/57139)
- Remove log from mine runner which was not used. [#57463](https://github.com/saltstack/salt/issues/57463)
- Fixed x509.read_certificate error when reading a Microsoft CA issued certificate in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#57535](https://github.com/saltstack/salt/issues/57535)
- Updating Slack engine to use slack_bolt library. [#57842](https://github.com/saltstack/salt/issues/57842)
- Fixed warning about replace=True with x509.certificate_managed in the new cryptography x509 module. [#58165](https://github.com/saltstack/salt/issues/58165)
- Fix salt.modules.pip:is_installed doesn't handle locally installed packages [#58202](https://github.com/saltstack/salt/issues/58202)
- Add missing MariaDB Grants to mysql module. MariaDB has added some grants in 10.4.x and 10.5.x that are not present here, which results in an error when creating. [#58297](https://github.com/saltstack/salt/issues/58297)
- linux_shadow: Fix cases where malformed shadow entries cause `user.present`
  states to fail. [#58423](https://github.com/saltstack/salt/issues/58423)
- Fixed salt.utils.compat.cmp to work with dictionaries [#58729](https://github.com/saltstack/salt/issues/58729)
- Fixed formatting for terse output mode [#58953](https://github.com/saltstack/salt/issues/58953)
- Fixed RecursiveDictDiffer with added nested dicts [#59017](https://github.com/saltstack/salt/issues/59017)
- Fixed x509.certificate_managed has DoS effect on master in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#59169](https://github.com/saltstack/salt/issues/59169)
- Fixed saltnado websockets disconnecting immediately [#59183](https://github.com/saltstack/salt/issues/59183)
- Fixed x509.certificate_managed rolls certificates every now and then in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#59315](https://github.com/saltstack/salt/issues/59315)
- Fix postgres_privileges.present not idempotent for functions [#59585](https://github.com/saltstack/salt/issues/59585)
- Fixed influxdb_continuous_query.present state to provide the client args to the underlying module on create. [#59766](https://github.com/saltstack/salt/issues/59766)
- Warn when using insecure (http:// based) key_urls for apt-based systems in pkgrepo.managed, and add a kwarg that determines the validity of such a url. [#59786](https://github.com/saltstack/salt/issues/59786)
- add load balancing policy default option and ensure the module can be executed with arguments from CLI [#59909](https://github.com/saltstack/salt/issues/59909)
- Fix salt-ssh when using imports with extra-filerefs. [#60003](https://github.com/saltstack/salt/issues/60003)
- Fixed cache directory corruption startup error [#60170](https://github.com/saltstack/salt/issues/60170)
- Update docs remove dry_run in docstring of file.blockreplace state. [#60227](https://github.com/saltstack/salt/issues/60227)
- Adds Parrot to OS_Family_Map in grains. [#60249](https://github.com/saltstack/salt/issues/60249)
- Fixed stdout and stderr being empty sometimes when use_vt=True for the cmd.run[*] functions [#60365](https://github.com/saltstack/salt/issues/60365)
- Use return code in iptables --check to verify rule exists. [#60467](https://github.com/saltstack/salt/issues/60467)
- Fix regression pip.installed does not pass env_vars when calling pip.list [#60557](https://github.com/saltstack/salt/issues/60557)
- Fix xfs module when additional output included in mkfs.xfs command. [#60853](https://github.com/saltstack/salt/issues/60853)
- Fixed parsing new format of terraform states in roster.terraform [#60915](https://github.com/saltstack/salt/issues/60915)
- Fixed recognizing installed ARMv7 rpm packages in compatible architectures. [#60994](https://github.com/saltstack/salt/issues/60994)
- Fixing changes dict in pkg state to be consistent when installing and test=True. [#60995](https://github.com/saltstack/salt/issues/60995)
- Fix cron.present duplicating entries when changing timespec to special. [#60997](https://github.com/saltstack/salt/issues/60997)
- Made salt-ssh respect --wipe again [#61083](https://github.com/saltstack/salt/issues/61083)
- state.orchestrate_single only passes a pillar if it is set to the state
  function. This allows it to be used with state functions that don't accept a
  pillar keyword argument. [#61092](https://github.com/saltstack/salt/issues/61092)
- Fix ipset state when the comment kwarg is set. [#61122](https://github.com/saltstack/salt/issues/61122)
- Fix issue with archive.unzip where the password was not being encoded for the extract function [#61422](https://github.com/saltstack/salt/issues/61422)
- Some Linux distributions (like AlmaLinux, Astra Linux, Debian, Mendel, Linux
  Mint, Pop!_OS, Rocky Linux) report different `oscodename`, `osfullname`,
  `osfinger` grains if lsb-release is installed or not. They have been changed to
  only derive these OS grains from `/etc/os-release`. [#61618](https://github.com/saltstack/salt/issues/61618)
- Pop!_OS uses the full version (YY.MM) in the osfinger grain now, not just the year. This allows differentiating for example between 20.04 and 20.10. [#61619](https://github.com/saltstack/salt/issues/61619)
- Fix ssh config roster to correctly parse the ssh config files that contain spaces. [#61650](https://github.com/saltstack/salt/issues/61650)
- Fix SoftLayer configuration not raising an exception when a domain is missing [#61727](https://github.com/saltstack/salt/issues/61727)
- Allow the minion to start or salt-call to run even if the user doesn't have permissions to read the root_dir value from the registry [#61789](https://github.com/saltstack/salt/issues/61789)
- Need to move the creation of the proxy object for the ProxyMinion further down in the initialization for sub proxies to ensure that all modules, especially any custom proxy modules, are available before attempting to run the init function. [#61805](https://github.com/saltstack/salt/issues/61805)
- Fixed malformed state return when merge-serializing to an improperly formatted file [#61814](https://github.com/saltstack/salt/issues/61814)
- Made cmdmod._run[_all]_quiet work during minion startup on MacOS with runas specified (which fixed mac_service) [#61816](https://github.com/saltstack/salt/issues/61816)
- When deleting the vault cache, also delete from the session cache [#61821](https://github.com/saltstack/salt/issues/61821)
- Ignore errors on reading license info with dpkg_lowpkg to prevent tracebacks on getting package information. [#61827](https://github.com/saltstack/salt/issues/61827)
- win_lgpo: Display conflicting policy names when more than one policy is found [#61859](https://github.com/saltstack/salt/issues/61859)
- win_lgpo: Fixed intermittent KeyError when getting policy setting using lgpo.get_policy [#61860](https://github.com/saltstack/salt/issues/61860)
- Fixed listing minions on OpenBSD [#61966](https://github.com/saltstack/salt/issues/61966)
- Make Salt to return an error on "pkg" modules and states when targeting duplicated package names [#62019](https://github.com/saltstack/salt/issues/62019)
- Fix return of REST-returned permissions when auth_list is set [#62022](https://github.com/saltstack/salt/issues/62022)
- Normalize package names once on using pkg.installed/removed with yum to make it possible to install packages with the name containing a part similar to a name of architecture. [#62029](https://github.com/saltstack/salt/issues/62029)
- Fix inconsitency regarding name and pkgs parameters between zypperpkg.upgrade() and yumpkg.upgrade() [#62030](https://github.com/saltstack/salt/issues/62030)
- Fix attr=all handling in pkg.list_pkgs() (yum/zypper). [#62032](https://github.com/saltstack/salt/issues/62032)
- Fixed the humanname being ignored in pkgrepo.managed on openSUSE Leap [#62053](https://github.com/saltstack/salt/issues/62053)
- Fixed issue with some LGPO policies having whitespace at the beginning or end of the element alias [#62058](https://github.com/saltstack/salt/issues/62058)
- Fix ordering of args to libcloud_storage.download_object module [#62074](https://github.com/saltstack/salt/issues/62074)
- Ignore extend declarations in sls files that are excluded. [#62082](https://github.com/saltstack/salt/issues/62082)
- Remove leftover usage of impacket [#62101](https://github.com/saltstack/salt/issues/62101)
- Pass executable path from _get_path_exec() is used when calling the program.
  The $HOME env is no longer modified globally.
  Only trailing newlines are stripped from the fetched secret.
  Pass process arguments are handled in a secure way. [#62120](https://github.com/saltstack/salt/issues/62120)
- Ignore some command return codes in openbsdrcctl_service to prevent spurious errors [#62131](https://github.com/saltstack/salt/issues/62131)
- Fixed extra period in filename output in tls module. Instead of "server.crt." it will now be "server.crt". [#62139](https://github.com/saltstack/salt/issues/62139)
- Make sure lingering PAexec-*.exe files in the Windows directory are cleaned up [#62152](https://github.com/saltstack/salt/issues/62152)
- Restored Salt's DeprecationWarnings [#62185](https://github.com/saltstack/salt/issues/62185)
- Fixed issue with forward slashes on Windows with file.recurse and clean=True [#62197](https://github.com/saltstack/salt/issues/62197)
- Recognize OSMC as Debian-based [#62198](https://github.com/saltstack/salt/issues/62198)
- Fixed Zypper module failing on RPM lock file being temporarily unavailable. [#62204](https://github.com/saltstack/salt/issues/62204)
- Improved error handling and diagnostics in the proxmox salt-cloud driver [#62211](https://github.com/saltstack/salt/issues/62211)
- Added EndeavourOS to the Arch os_family. [#62220](https://github.com/saltstack/salt/issues/62220)
- Fix salt-ssh not detecting `platform-python` as a valid interpreter on EL8 [#62235](https://github.com/saltstack/salt/issues/62235)
- Fix pkg.version_cmp on openEuler and a few other os flavors. [#62248](https://github.com/saltstack/salt/issues/62248)
- Fix localhost detection in glusterfs.peers [#62273](https://github.com/saltstack/salt/issues/62273)
- Fix Salt Package Manager (SPM) exception when calling spm create_repo . [#62281](https://github.com/saltstack/salt/issues/62281)
- Fix matcher slowness due to loader invocation [#62283](https://github.com/saltstack/salt/issues/62283)
- Fixes the Puppet module for non-aio Puppet packages for example running the Puppet module on FreeBSD. [#62323](https://github.com/saltstack/salt/issues/62323)
- Issue 62334: Displays a debug log message instead of an error log message when the publisher fails to connect [#62334](https://github.com/saltstack/salt/issues/62334)
- Fix pyobjects renderer access to opts and sls [#62336](https://github.com/saltstack/salt/issues/62336)
- Fix use of random shuffle and sample functions as Jinja filters [#62372](https://github.com/saltstack/salt/issues/62372)
- Fix groups with duplicate GIDs are not returned by get_group_list [#62377](https://github.com/saltstack/salt/issues/62377)
- Fix the "zpool.present" state when enabling zpool features that are already active. [#62390](https://github.com/saltstack/salt/issues/62390)
- Fix ability to execute remote file client methods in saltcheck [#62398](https://github.com/saltstack/salt/issues/62398)
- Update all platforms to use pycparser 2.21 or greater for Py 3.9 or higher, fixes fips fault with openssl v3.x [#62400](https://github.com/saltstack/salt/issues/62400)
- Due to changes in the Netmiko library for the exception paths, need to check the version of Netmiko python library and then import the exceptions from different locations depending on the result. [#62405](https://github.com/saltstack/salt/issues/62405)
- When using preq on a state, then prereq state will first be run with test=True to determine if there are changes.  When there are changes, the state with the prereq option will be run prior to the prereq state.  If this state fails then the prereq state will not run and the state output uses the test=True run.  However, the proposed changes are included for the prereq state are included from the test=True run.  We should pull those out as there weren't actually changes since the prereq state did not run. [#62408](https://github.com/saltstack/salt/issues/62408)
- Added directory mode for file.copy with makedirs [#62426](https://github.com/saltstack/salt/issues/62426)
- Provide better error handling in the various napalm proxy minion functions when the device is not accessible. [#62435](https://github.com/saltstack/salt/issues/62435)
- When handling aggregation, change the order to ensure that the requisites are aggregated first and then the state functions are aggregated.  Caching whether aggregate functions are available for particular states so we don't need to attempt to load them everytime. [#62439](https://github.com/saltstack/salt/issues/62439)
- The patch allows to boostrap kubernetes clusters in the version above 1.13 via salt module [#62451](https://github.com/saltstack/salt/issues/62451)
- sysctl.persist now updates the in-memory value on FreeBSD even if the on-disk value was already correct. [#62461](https://github.com/saltstack/salt/issues/62461)
- Fixed parsing CDROM apt sources [#62474](https://github.com/saltstack/salt/issues/62474)
- Update sanitizing masking for Salt SSH to include additional password like strings. [#62483](https://github.com/saltstack/salt/issues/62483)
- Fix user/group checking on file state functions in the test mode. [#62499](https://github.com/saltstack/salt/issues/62499)
- Fix user.present to allow removing groups using optional_groups parameter and enforcing idempotent group membership. [#62502](https://github.com/saltstack/salt/issues/62502)
- Fix possible tracebacks if there is a package with '------' or '======' in the description is installed on the Debian based minion. [#62519](https://github.com/saltstack/salt/issues/62519)
- Fixed the omitted "pool" parameter when cloning a VM with the proxmox salt-cloud driver [#62521](https://github.com/saltstack/salt/issues/62521)
- Fix rendering of pyobjects states in saltcheck [#62523](https://github.com/saltstack/salt/issues/62523)
- Fixes pillar where a corrupted CacheDisk file forces the pillar to be rebuilt [#62527](https://github.com/saltstack/salt/issues/62527)
- Use str() method instead of repo_line for when python3-apt is installed or not in aptpkg.py. [#62546](https://github.com/saltstack/salt/issues/62546)
- Remove the connection_timeout from netmiko_connection_args before netmiko_connection_args is added to __context__["netmiko_device"]["args"] which is passed along to the Netmiko library. [#62547](https://github.com/saltstack/salt/issues/62547)
- Fix order specific mount.mounted options for persist [#62556](https://github.com/saltstack/salt/issues/62556)
- Fixed salt-cloud cloning a proxmox VM with a specified new vmid. [#62558](https://github.com/saltstack/salt/issues/62558)
- Fix runas with cmd module when using the onedir bundled packages [#62565](https://github.com/saltstack/salt/issues/62565)
- Update setproctitle version for all platforms [#62576](https://github.com/saltstack/salt/issues/62576)
- Fixed missing parameters when cloning a VM with the proxmox salt-cloud driver [#62580](https://github.com/saltstack/salt/issues/62580)
- Handle PermissionError when importing crypt when FIPS is enabled. [#62587](https://github.com/saltstack/salt/issues/62587)
- Correctly reraise exceptions in states.http [#62595](https://github.com/saltstack/salt/issues/62595)
- Fixed syndic eauth. Now jobs will be published when a valid eauth user is targeting allowed minions/functions. [#62618](https://github.com/saltstack/salt/issues/62618)
- updated rest_cherry/app to properly detect arg sent as a string as curl will do when only one arg is supplied. [#62624](https://github.com/saltstack/salt/issues/62624)
- Prevent possible tracebacks in core grains module by ignoring non utf8 characters in /proc/1/environ, /proc/1/cmdline, /proc/cmdline [#62633](https://github.com/saltstack/salt/issues/62633)
- Fixed vault ext pillar return data for KV v2 [#62651](https://github.com/saltstack/salt/issues/62651)
- Fix saltcheck _get_top_states doesn't pass saltenv to state.show_top [#62654](https://github.com/saltstack/salt/issues/62654)
- Fix groupadd.* functions hard code relative command name [#62657](https://github.com/saltstack/salt/issues/62657)
- Fixed pdbedit.create trying to use a bytes-like hash as string. [#62670](https://github.com/saltstack/salt/issues/62670)
- Fix depenency on legacy boto module in boto3 modules [#62672](https://github.com/saltstack/salt/issues/62672)
- Modified "_get_flags" function so that it returns regex flags instead of integers [#62676](https://github.com/saltstack/salt/issues/62676)
- Change startup ReqServer log messages from error to info level. [#62728](https://github.com/saltstack/salt/issues/62728)
- Fix kmod.* functions hard code relative command name [#62772](https://github.com/saltstack/salt/issues/62772)
- Fix mac_brew_pkg to work with null taps [#62793](https://github.com/saltstack/salt/issues/62793)
- Fixing a bug when listing the running schedule if "schedule.enable" and/or "schedule.disable" has been run, where the "enabled" items is being treated as a schedule item. [#62795](https://github.com/saltstack/salt/issues/62795)
- Prevent annoying RuntimeWarning message about line buffering (buffering=1) not being supported in binary mode [#62817](https://github.com/saltstack/salt/issues/62817)
- Include UID and GID checks in modules.file.check_perms as well as comparing
  ownership by username and group name. [#62818](https://github.com/saltstack/salt/issues/62818)
- Fix presence events on TCP transport by removing a client's presence when minion disconnects from publish channel correctly [#62826](https://github.com/saltstack/salt/issues/62826)
- Remove Azure deprecation messages from functions that always run w/ salt-cloud [#62845](https://github.com/saltstack/salt/issues/62845)
- Use select instead of iterating over entrypoints as a dictionary for importlib_metadata>=5.0.0 [#62854](https://github.com/saltstack/salt/issues/62854)
- Fixed master job scheduler using when [#62858](https://github.com/saltstack/salt/issues/62858)
- LGPO: Added support for missing domain controller policies: VulnerableChannelAllowList and LdapEnforceChannelBinding [#62873](https://github.com/saltstack/salt/issues/62873)
- Fix unnecessarily complex gce metadata grains code to use googles metadata service more effectively. [#62878](https://github.com/saltstack/salt/issues/62878)
- Fixed dockermod version_info function for docker-py 6.0.0+ [#62882](https://github.com/saltstack/salt/issues/62882)
- Moving setting the LOAD_BALANCING_POLICY_MAP dictionary into the try except block that determines if the cassandra_cql module should be made available. [#62886](https://github.com/saltstack/salt/issues/62886)
- Updating various MongoDB module functions to work with latest version of pymongo. [#62900](https://github.com/saltstack/salt/issues/62900)
- Restored channel for Syndic minions to send job returns to the Salt master. [#62933](https://github.com/saltstack/salt/issues/62933)
- removed _resolve_deps as it required a library that is not generally avalible. and switched to apt-get for everything as that can auto resolve dependencies. [#62934](https://github.com/saltstack/salt/issues/62934)
- Updated pyzmq to version 22.0.3 on Windows builds because the old version was causing salt-minion/salt-call to hang [#62937](https://github.com/saltstack/salt/issues/62937)
- Allow root user to modify crontab lines for non-root users (except AIX and Solaris). Align crontab line changes with the file ones and also with listing crontab. [#62940](https://github.com/saltstack/salt/issues/62940)
- Fix systemd_service.* functions hard code relative command name [#62942](https://github.com/saltstack/salt/issues/62942)
- Fix file.symlink backupname operation can copy remote contents to local disk [#62953](https://github.com/saltstack/salt/issues/62953)
- Issue #62968: Fix issue where cloud deployments were putting the keys in the wrong location on Windows hosts [#62968](https://github.com/saltstack/salt/issues/62968)
- Fixed gpg_passphrase issue with gpg decrypt/encrypt functions [#62977](https://github.com/saltstack/salt/issues/62977)
- Fix file.tidied FileNotFoundError [#62986](https://github.com/saltstack/salt/issues/62986)
- Fixed bug where module.wait states were detected as running legacy module.run syntax [#62988](https://github.com/saltstack/salt/issues/62988)
- Fixed issue with win_wua module where it wouldn't load if the CryptSvc was set to Manual start [#62993](https://github.com/saltstack/salt/issues/62993)
- The `__opts__` dunder dictionary is now added to the loader's `pack` if not
  already present, which makes it accessible via the
  `salt.loader.context.NamedLoaderContext` class. [#63013](https://github.com/saltstack/salt/issues/63013)
- Issue #63024: Fix issue where grains and config data were being place in the wrong location on Windows hosts [#63024](https://github.com/saltstack/salt/issues/63024)
- Fix btrfs.subvolume_snapshot command failing [#63025](https://github.com/saltstack/salt/issues/63025)
- Fix file.retention_schedule always reports changes [#63033](https://github.com/saltstack/salt/issues/63033)
- Fix mongo authentication for mongo ext_pillar and mongo returner

  This fix also include the ability to use the mongo connection string for mongo ext_pillar [#63058](https://github.com/saltstack/salt/issues/63058)
- Fixed x509.create_csr creates invalid CSR by default in the new cryptography x509 module. [#63103](https://github.com/saltstack/salt/issues/63103)
- TCP transport documentation now contains proper master/minion-side filtering information [#63120](https://github.com/saltstack/salt/issues/63120)
- Fixed gpg.verify does not respect gnupghome [#63145](https://github.com/saltstack/salt/issues/63145)
- Made pillar cache pass extra minion data as well [#63208](https://github.com/saltstack/salt/issues/63208)
- Fix serious performance issues with the file.tidied module [#63231](https://github.com/saltstack/salt/issues/63231)
- Fix rpm_lowpkg version comparison logic when using rpm-vercmp and only one version has a release number. [#63317](https://github.com/saltstack/salt/issues/63317)
- Import StrictVersion and LooseVersion from setuptools.distutils.verison or setuptools._distutils.version, if first not available [#63350](https://github.com/saltstack/salt/issues/63350)
- When the shell is passed as powershell or pwsh, only wrapper the shell in quotes if cmd.run is running on Windows.  When quoted on Linux hosts, this results in an error when the keyword arguments are appended. [#63590](https://github.com/saltstack/salt/issues/63590)
- LGPO: Added support for "Relax minimum password length limits" [#63596](https://github.com/saltstack/salt/issues/63596)
- Fixed the ability to set a scheduled task to auto delete if not scheduled to run again (``delete_after``) [#63650](https://github.com/saltstack/salt/issues/63650)
- When a job is disabled only increase it's _next_fire_time value if the job would have run at the current time, eg. the current _next_fire_time == now. [#63699](https://github.com/saltstack/salt/issues/63699)
- have salt.template.compile_template_str cleanup its temp files. [#63724](https://github.com/saltstack/salt/issues/63724)
- Check file is not empty before attempting to read pillar disk cache file [#63729](https://github.com/saltstack/salt/issues/63729)
- Fixed an issue with generating fingerprints for public keys with different line endings [#63742](https://github.com/saltstack/salt/issues/63742)
- Change default GPG keyserver from pgp.mit.edu to keys.openpgp.org. [#63806](https://github.com/saltstack/salt/issues/63806)
- fix cherrypy 400 error output to be less generic. [#63835](https://github.com/saltstack/salt/issues/63835)
- Ensure kwargs is passed along to _call_apt when passed into install function. [#63847](https://github.com/saltstack/salt/issues/63847)
- remove eval and update logging to be more informative on bad config [#63879](https://github.com/saltstack/salt/issues/63879)
- add linux_distribution to util to stop dep warning [#63904](https://github.com/saltstack/salt/issues/63904)
- Handle the situation when a sub proxy minion does not init properly, eg. an exception happens, and the sub proxy object is not available. [#63923](https://github.com/saltstack/salt/issues/63923)
- Clarifying documentation for extension_modules configuration option. [#63929](https://github.com/saltstack/salt/issues/63929)
- Windows pkg module now properly handles versions containing strings [#63935](https://github.com/saltstack/salt/issues/63935)
- Handle the scenario when the check_cmd requisite is used with a state function when the state has a local check_cmd function but that function isn't used by that function. [#63948](https://github.com/saltstack/salt/issues/63948)
- Issue #63981: Allow users to pass verify_ssl to pkg.install/pkg.installed on Windows [#63981](https://github.com/saltstack/salt/issues/63981)


### Added

- Introduce a `LIB_STATE_DIR` syspaths variable which defaults to `CONFIG_DIR`,
  but can be individually customized during installation by specifying
  `--salt-lib-state-dir` during installation. Change the default `pki_dir` to
  `<LIB_STATE_DIR>/pki/master` (for the master) and `<LIB_STATE_DIR>/pki/minion`
  (for the minion). [#3396](https://github.com/saltstack/salt/issues/3396)
- Allow users to enable 'queue=True' for all state runs via config file [#31468](https://github.com/saltstack/salt/issues/31468)
- Added pillar templating to vault policies [#43287](https://github.com/saltstack/salt/issues/43287)
- Add support for NVMeF as a transport protocol for hosts in a Pure Storage FlashArray [#51088](https://github.com/saltstack/salt/issues/51088)
- A new salt-ssh roster that generates a roster by parses a known_hosts file. [#54679](https://github.com/saltstack/salt/issues/54679)
- Added Windows Event Viewer support [#54713](https://github.com/saltstack/salt/issues/54713)
- Added the win_lgpo_reg state and execution modules which will allow registry based group policy to be set directly in the Registry.pol file [#56013](https://github.com/saltstack/salt/issues/56013)
- Added resource tagging functions to boto_dynamodb execution module [#57500](https://github.com/saltstack/salt/issues/57500)
- Added `openvswitch_db` state module and functions `bridge_to_parent`,
  `bridge_to_vlan`, `db_get`, and `db_set` to the `openvswitch` execution module.
  Also added optional `parent` and `vlan` parameters to the
  `openvswitch_bridge.present` state module function and the
  `openvswitch.bridge_create` execution module function. [#58986](https://github.com/saltstack/salt/issues/58986)
- State module to manage SysFS attributes [#60154](https://github.com/saltstack/salt/issues/60154)
- Added ability for `salt.wait_for_event` to handle `event_id`s that have a list value. [#60430](https://github.com/saltstack/salt/issues/60430)
- Added suport for Linux ppc64le core grains (cpu_model, virtual, productname, manufacturer, serialnumber) and arm core grains (serialnumber, productname) [#60518](https://github.com/saltstack/salt/issues/60518)
- Added autostart option to virt.defined and virt.running states, along with virt.update execution modules. [#60700](https://github.com/saltstack/salt/issues/60700)
- Added .0 back to our versioning scheme for future versions (e.g. 3006.0) [#60722](https://github.com/saltstack/salt/issues/60722)
- Initial work to allow parallel startup of proxy minions when used as sub proxies with Deltaproxy. [#61153](https://github.com/saltstack/salt/issues/61153)
- Added node label support for GCE [#61245](https://github.com/saltstack/salt/issues/61245)
- Support the --priority flag when adding sources to Chocolatey. [#61319](https://github.com/saltstack/salt/issues/61319)
- Add namespace option to ext_pillar.http_json [#61335](https://github.com/saltstack/salt/issues/61335)
- Added a filter function to ps module to get a list of processes on a minion according to their state. [#61420](https://github.com/saltstack/salt/issues/61420)
- Add postgres.timeout option to postgres module for limiting postgres query times [#61433](https://github.com/saltstack/salt/issues/61433)
- Added new optional vault option, ``config_location``. This can be either ``master`` or ``local`` and defines where vault will look for connection details, either requesting them from the master or using the local config. [#61857](https://github.com/saltstack/salt/issues/61857)
- Add ipwrap() jinja filter to wrap IPv6 addresses with brackets. [#61931](https://github.com/saltstack/salt/issues/61931)
- 'tcp' transport is now available in ipv6-only network [#62009](https://github.com/saltstack/salt/issues/62009)
- Add `diff_attr` parameter to pkg.upgrade() (zypper/yum). [#62031](https://github.com/saltstack/salt/issues/62031)
- Config option pass_variable_prefix allows to distinguish variables that contain paths to pass secrets.
  Config option pass_strict_fetch allows to error out when a secret cannot be fetched from pass.
  Config option pass_dir allows setting the PASSWORD_STORE_DIR env for pass.
  Config option pass_gnupghome allows setting the $GNUPGHOME env for pass. [#62120](https://github.com/saltstack/salt/issues/62120)
- Add file.pruned state and expanded file.rmdir exec module functionality [#62178](https://github.com/saltstack/salt/issues/62178)
- Added "dig.PTR" function to resolve PTR records for IPs, as well as tests and documentation [#62275](https://github.com/saltstack/salt/issues/62275)
- Added the ability to remove a KB using the DISM state/execution modules [#62366](https://github.com/saltstack/salt/issues/62366)
- Add "<tiamat> python" subcommand to allow execution or arbitrary scripts via bundled Python runtime [#62381](https://github.com/saltstack/salt/issues/62381)
- Add ability to provide conditions which convert normal state actions to no-op when true [#62446](https://github.com/saltstack/salt/issues/62446)
- Added debug log messages displaying the command being run when installing packages on Windows [#62480](https://github.com/saltstack/salt/issues/62480)
- Add biosvendor grain [#62496](https://github.com/saltstack/salt/issues/62496)
- Add ifelse Jinja function as found in CFEngine [#62508](https://github.com/saltstack/salt/issues/62508)
- Implementation of Amazon EC2 instance detection and setting `virtual_subtype` grain accordingly including the product if possible to identify. [#62539](https://github.com/saltstack/salt/issues/62539)
- Adds __env__substitution to ext_pillar.stack; followup of #61531, improved exception handling for stacked template (jinja) template rendering and yaml parsing in ext_pillar.stack [#62578](https://github.com/saltstack/salt/issues/62578)
- Increase file.tidied flexibility with regard to age and size [#62678](https://github.com/saltstack/salt/issues/62678)
- Added "connected_devices" feature to netbox pillar module. It contains extra information about devices connected to the minion [#62761](https://github.com/saltstack/salt/issues/62761)
- Add atomic file operation for symlink changes [#62768](https://github.com/saltstack/salt/issues/62768)
- Add password/account locking/unlocking in user.present state on supported operating systems [#62856](https://github.com/saltstack/salt/issues/62856)
- Added onchange configuration for script engine [#62867](https://github.com/saltstack/salt/issues/62867)
- Added output and bare functionality to export_key gpg module function [#62978](https://github.com/saltstack/salt/issues/62978)
- Add keyvalue serializer for environment files [#62983](https://github.com/saltstack/salt/issues/62983)
- Add ability to ignore symlinks in file.tidied [#63042](https://github.com/saltstack/salt/issues/63042)
- salt-cloud support IMDSv2 tokens when using 'use-instance-role-credentials' [#63067](https://github.com/saltstack/salt/issues/63067)
- Add ability for file.symlink to not set ownership on existing links [#63093](https://github.com/saltstack/salt/issues/63093)
- Restore the previous slack engine and deprecate it, rename replace the slack engine to slack_bolt until deprecation [#63095](https://github.com/saltstack/salt/issues/63095)
- Add functions that will return the underlying block device, mount point, and filesystem type for a given path [#63098](https://github.com/saltstack/salt/issues/63098)
- Add ethtool execution and state module functions for pause [#63128](https://github.com/saltstack/salt/issues/63128)
- Add boardname grain [#63131](https://github.com/saltstack/salt/issues/63131)
- Added management of ECDSA/EdDSA private keys with x509 modules in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#63248](https://github.com/saltstack/salt/issues/63248)
- Added x509 modules support for different output formats in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#63249](https://github.com/saltstack/salt/issues/63249)
- Added deprecation_warning test state for ensuring that deprecation warnings are correctly emitted. [#63315](https://github.com/saltstack/salt/issues/63315)
- Adds a state_events option to state.highstate, state.apply, state.sls, state.sls_id.
  This allows users to enable state_events on a per use basis rather than having to
  enable them globally for all state runs. [#63316](https://github.com/saltstack/salt/issues/63316)
- Allow max queue size setting for state runs to prevent performance problems from queue growth [#63356](https://github.com/saltstack/salt/issues/63356)
- Add support of exposing meta_server_grains for Azure VMs [#63606](https://github.com/saltstack/salt/issues/63606)
- Include the version of `relenv` in the versions report. [#63827](https://github.com/saltstack/salt/issues/63827)
- Added debug log messages displaying the command being run when removing packages on Windows [#63866](https://github.com/saltstack/salt/issues/63866)


### Security

- Upgrade Requirements Due to Security Issues.

  * Upgrade to `cryptography>=39.0.1` due to:
    * https://github.com/advisories/GHSA-x4qr-2fvf-3mr5
    * https://github.com/advisories/GHSA-w7pp-m8wf-vj6r
  * Upgrade to `pyopenssl==23.0.0` due to the cryptography upgrade.
  * Update to `markdown-it-py==2.2.0` due to:
    * https://github.com/advisories/GHSA-jrwr-5x3p-hvc3
    * https://github.com/advisories/GHSA-vrjv-mxr7-vjf8 [#63882](https://github.com/saltstack/salt/issues/63882)


## 3006.0rc2 (2023-03-19)


### Removed

- Remove and deprecate the __orchestration__ key from salt.runner and salt.wheel return data. To get it back, set features.enable_deprecated_orchestration_flag master configuration option to True. The flag will be completely removed in Salt 3008 Argon. [#59917](https://github.com/saltstack/salt/issues/59917)
- Removed distutils and replaced with setuptools, given distutils is deprecated and removed in Python 3.12 [#60476](https://github.com/saltstack/salt/issues/60476)
- Removed ``runtests`` targets from ``noxfile.py`` [#62239](https://github.com/saltstack/salt/issues/62239)
- Removed the PyObjC dependency.

  This addresses problems with building a one dir build for macOS.
  It became problematic because depending on the macOS version, it pulls different dependencies, and we would either have to build a macos onedir for each macOS supported release, or ship a crippled onedir(because it would be tied to the macOS version where the onedir was built).
  Since it's currently not being used, it's removed. [#62432](https://github.com/saltstack/salt/issues/62432)
- Removed `SixRedirectImporter` from Salt. Salt hasn't shipped `six` since Salt 3004. [#63874](https://github.com/saltstack/salt/issues/63874)


### Deprecated

- renamed `keep_jobs`, specifying job cache TTL in hours, to `keep_jobs_seconds`, specifying TTL in seconds.
  `keep_jobs` will be removed in the Argon release [#55295](https://github.com/saltstack/salt/issues/55295)
- Removing all references to napalm-base which is no longer supported. [#61542](https://github.com/saltstack/salt/issues/61542)
- The 'ip_bracket' function has been moved from salt/utils/zeromq.py in salt/utils/network.py [#62009](https://github.com/saltstack/salt/issues/62009)
- The `expand_repo_def` function in `salt.modules.aptpkg` is now deprecated. It's only used in `salt.states.pkgrepo` and it has no use of being exposed to the CLI. [#62485](https://github.com/saltstack/salt/issues/62485)
- Deprecated defunct Django returner [#62644](https://github.com/saltstack/salt/issues/62644)
- Deprecate core ESXi and associated states and modules, vcenter and vsphere support in favor of Salt VMware Extensions [#62754](https://github.com/saltstack/salt/issues/62754)
- Removing manufacture grain which has been deprecated. [#62914](https://github.com/saltstack/salt/issues/62914)
- Removing deprecated utils/boto3_elasticsearch.py [#62915](https://github.com/saltstack/salt/issues/62915)
- Removing support for the now deprecated _ext_nodes from salt/master.py. [#62917](https://github.com/saltstack/salt/issues/62917)
- Deprecating the Salt Slack engine in favor of the Salt Slack Bolt Engine. [#63095](https://github.com/saltstack/salt/issues/63095)
- `salt.utils.version.StrictVersion` is now deprecated and it's use should be replaced with `salt.utils.version.Version`. [#63383](https://github.com/saltstack/salt/issues/63383)


### Changed

- More intelligent diffing in changes of file.serialize state. [#48609](https://github.com/saltstack/salt/issues/48609)
- Move deprecation of the neutron module to Argon. Please migrate to the neutronng module instead. [#49430](https://github.com/saltstack/salt/issues/49430)
- ``umask`` is now a global state argument, instead of only applying to ``cmd``
  states. [#57803](https://github.com/saltstack/salt/issues/57803)
- Update pillar.obfuscate to accept kwargs in addition to args.  This is useful when passing in keyword arguments like saltenv that are then passed along to pillar.items. [#58971](https://github.com/saltstack/salt/issues/58971)
- Improve support for listing macOS brew casks [#59439](https://github.com/saltstack/salt/issues/59439)
- Add missing MariaDB Grants to mysql module.
  MariaDB has added some grants in 10.4.x and 10.5.x that are not present here, which results in an error when creating.
  Also improved exception handling in `grant_add` which did not log the original error message and replaced it with a generic error. [#61409](https://github.com/saltstack/salt/issues/61409)
- Use VENV_PIP_TARGET environment variable as a default target for pip if present. [#62089](https://github.com/saltstack/salt/issues/62089)
- Disabled FQDNs grains on macOS by default [#62168](https://github.com/saltstack/salt/issues/62168)
- Replaced pyroute2.IPDB with pyroute2.NDB, as the former is deprecated [#62218](https://github.com/saltstack/salt/issues/62218)
- Enhance capture of error messages for Zypper calls in zypperpkg module. [#62346](https://github.com/saltstack/salt/issues/62346)
- Removed GPG_1_3_1 check [#62895](https://github.com/saltstack/salt/issues/62895)
- Requisite state chunks now all consistently contain `__id__`, `__sls__` and `name`. [#63012](https://github.com/saltstack/salt/issues/63012)
- netapi_enable_clients option to allow enabling/disabling of clients in salt-api.
  By default all clients will now be disabled. Users of salt-api will need
  to update their master config to enable the clients that they use. Not adding
  the netapi_enable_clients option with required clients to the master config will
  disable salt-api. [#63050](https://github.com/saltstack/salt/issues/63050)
- Stop relying on `salt/_version.py` to write Salt's version. Instead use `salt/_version.txt` which only contains the version string. [#63383](https://github.com/saltstack/salt/issues/63383)
- Set enable_fqdns_grains to be False by default. [#63595](https://github.com/saltstack/salt/issues/63595)
- Changelog snippet files must now have a `.md` file extension to be more explicit on what type of rendering is done when they are included in the main `CHANGELOG.md` file. [#63710](https://github.com/saltstack/salt/issues/63710)


### Fixed

- Add kwargs to handle extra parameters for http.query [#36138](https://github.com/saltstack/salt/issues/36138)
- Fix mounted bind mounts getting active mount options added [#39292](https://github.com/saltstack/salt/issues/39292)
- Fix `sysctl.present` converts spaces to tabs. [#40054](https://github.com/saltstack/salt/issues/40054)
- Fixes state pkg.purged to purge removed packages on Debian family systems [#42306](https://github.com/saltstack/salt/issues/42306)
- Fix fun_args missing from syndic returns [#45823](https://github.com/saltstack/salt/issues/45823)
- Fix mount.mounted with 'mount: False' reports unmounted file system as unchanged when running with test=True [#47201](https://github.com/saltstack/salt/issues/47201)
- Issue #49310: Allow users to touch a file with Unix date of birth [#49310](https://github.com/saltstack/salt/issues/49310)
- Do not raise an exception in pkg.info_installed on nonzero return code [#51620](https://github.com/saltstack/salt/issues/51620)
- Passes the value of the force parameter from file.copy to its call to file.remove so that files with the read-only attribute are handled. [#51739](https://github.com/saltstack/salt/issues/51739)
- Fixed x509.certificate_managed creates new certificate every run in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#52167](https://github.com/saltstack/salt/issues/52167)
- Don't check for cached pillar errors on state.apply [#52354](https://github.com/saltstack/salt/issues/52354), [#57180](https://github.com/saltstack/salt/issues/57180), [#59339](https://github.com/saltstack/salt/issues/59339)
- Swapping out args and kwargs for arg and kwarg respectively in the Slack engine when the command passed is a runner. [#52400](https://github.com/saltstack/salt/issues/52400)
- Ensure when we're adding chunks to the rules when running aggregation with the iptables state module we use a copy of the chunk otherwise we end up with a recursive mess. [#53353](https://github.com/saltstack/salt/issues/53353)
- When user_create or user_remove fail, return False instead of returning the error. [#53377](https://github.com/saltstack/salt/issues/53377)
- Include sync_roster when sync_all is called. [#53914](https://github.com/saltstack/salt/issues/53914)
- Avoid warning noise in lograte.get [#53988](https://github.com/saltstack/salt/issues/53988)
- Fixed listing revoked keys with gpg.list_keys [#54347](https://github.com/saltstack/salt/issues/54347)
- Fix mount.mounted does not handle blanks properly [#54508](https://github.com/saltstack/salt/issues/54508)
- Fixed grain num_cpus get wrong CPUs count in case of inconsistent CPU numbering. [#54682](https://github.com/saltstack/salt/issues/54682)
- Fix spelling error for python_shell argument in dpkg_lower module [#54907](https://github.com/saltstack/salt/issues/54907)
- Cleaned up bytes response data before sending to non-bytes compatible returners (postgres, mysql) [#55226](https://github.com/saltstack/salt/issues/55226)
- Fixed malformed state return when testing file.managed with unavailable source file [#55269](https://github.com/saltstack/salt/issues/55269)
- Included stdout in error message for Zypper calls in zypperpkg module. [#56016](https://github.com/saltstack/salt/issues/56016)
- Fixed pillar.filter_by with salt-ssh [#56093](https://github.com/saltstack/salt/issues/56093)
- Fix boto_route53 issue with (multiple) VPCs. [#57139](https://github.com/saltstack/salt/issues/57139)
- Remove log from mine runner which was not used. [#57463](https://github.com/saltstack/salt/issues/57463)
- Fixed x509.read_certificate error when reading a Microsoft CA issued certificate in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#57535](https://github.com/saltstack/salt/issues/57535)
- Updating Slack engine to use slack_bolt library. [#57842](https://github.com/saltstack/salt/issues/57842)
- Fixed warning about replace=True with x509.certificate_managed in the new cryptography x509 module. [#58165](https://github.com/saltstack/salt/issues/58165)
- Fix salt.modules.pip:is_installed doesn't handle locally installed packages [#58202](https://github.com/saltstack/salt/issues/58202)
- Add missing MariaDB Grants to mysql module. MariaDB has added some grants in 10.4.x and 10.5.x that are not present here, which results in an error when creating. [#58297](https://github.com/saltstack/salt/issues/58297)
- linux_shadow: Fix cases where malformed shadow entries cause `user.present`
  states to fail. [#58423](https://github.com/saltstack/salt/issues/58423)
- Fixed salt.utils.compat.cmp to work with dictionaries [#58729](https://github.com/saltstack/salt/issues/58729)
- Fixed formatting for terse output mode [#58953](https://github.com/saltstack/salt/issues/58953)
- Fixed RecursiveDictDiffer with added nested dicts [#59017](https://github.com/saltstack/salt/issues/59017)
- Fixed x509.certificate_managed has DoS effect on master in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#59169](https://github.com/saltstack/salt/issues/59169)
- Fixed saltnado websockets disconnecting immediately [#59183](https://github.com/saltstack/salt/issues/59183)
- Fixed x509.certificate_managed rolls certificates every now and then in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#59315](https://github.com/saltstack/salt/issues/59315)
- Fix postgres_privileges.present not idempotent for functions [#59585](https://github.com/saltstack/salt/issues/59585)
- Fixed influxdb_continuous_query.present state to provide the client args to the underlying module on create. [#59766](https://github.com/saltstack/salt/issues/59766)
- Warn when using insecure (http:// based) key_urls for apt-based systems in pkgrepo.managed, and add a kwarg that determines the validity of such a url. [#59786](https://github.com/saltstack/salt/issues/59786)
- add load balancing policy default option and ensure the module can be executed with arguments from CLI [#59909](https://github.com/saltstack/salt/issues/59909)
- Fix salt-ssh when using imports with extra-filerefs. [#60003](https://github.com/saltstack/salt/issues/60003)
- Fixed cache directory corruption startup error [#60170](https://github.com/saltstack/salt/issues/60170)
- Update docs remove dry_run in docstring of file.blockreplace state. [#60227](https://github.com/saltstack/salt/issues/60227)
- Adds Parrot to OS_Family_Map in grains. [#60249](https://github.com/saltstack/salt/issues/60249)
- Fixed stdout and stderr being empty sometimes when use_vt=True for the cmd.run[*] functions [#60365](https://github.com/saltstack/salt/issues/60365)
- Use return code in iptables --check to verify rule exists. [#60467](https://github.com/saltstack/salt/issues/60467)
- Fix regression pip.installed does not pass env_vars when calling pip.list [#60557](https://github.com/saltstack/salt/issues/60557)
- Fix xfs module when additional output included in mkfs.xfs command. [#60853](https://github.com/saltstack/salt/issues/60853)
- Fixed parsing new format of terraform states in roster.terraform [#60915](https://github.com/saltstack/salt/issues/60915)
- Fixed recognizing installed ARMv7 rpm packages in compatible architectures. [#60994](https://github.com/saltstack/salt/issues/60994)
- Fixing changes dict in pkg state to be consistent when installing and test=True. [#60995](https://github.com/saltstack/salt/issues/60995)
- Fix cron.present duplicating entries when changing timespec to special. [#60997](https://github.com/saltstack/salt/issues/60997)
- Made salt-ssh respect --wipe again [#61083](https://github.com/saltstack/salt/issues/61083)
- state.orchestrate_single only passes a pillar if it is set to the state
  function. This allows it to be used with state functions that don't accept a
  pillar keyword argument. [#61092](https://github.com/saltstack/salt/issues/61092)
- Fix ipset state when the comment kwarg is set. [#61122](https://github.com/saltstack/salt/issues/61122)
- Fix issue with archive.unzip where the password was not being encoded for the extract function [#61422](https://github.com/saltstack/salt/issues/61422)
- Some Linux distributions (like AlmaLinux, Astra Linux, Debian, Mendel, Linux
  Mint, Pop!_OS, Rocky Linux) report different `oscodename`, `osfullname`,
  `osfinger` grains if lsb-release is installed or not. They have been changed to
  only derive these OS grains from `/etc/os-release`. [#61618](https://github.com/saltstack/salt/issues/61618)
- Pop!_OS uses the full version (YY.MM) in the osfinger grain now, not just the year. This allows differentiating for example between 20.04 and 20.10. [#61619](https://github.com/saltstack/salt/issues/61619)
- Fix ssh config roster to correctly parse the ssh config files that contain spaces. [#61650](https://github.com/saltstack/salt/issues/61650)
- Fix SoftLayer configuration not raising an exception when a domain is missing [#61727](https://github.com/saltstack/salt/issues/61727)
- Allow the minion to start or salt-call to run even if the user doesn't have permissions to read the root_dir value from the registry [#61789](https://github.com/saltstack/salt/issues/61789)
- Need to move the creation of the proxy object for the ProxyMinion further down in the initialization for sub proxies to ensure that all modules, especially any custom proxy modules, are available before attempting to run the init function. [#61805](https://github.com/saltstack/salt/issues/61805)
- Fixed malformed state return when merge-serializing to an improperly formatted file [#61814](https://github.com/saltstack/salt/issues/61814)
- Made cmdmod._run[_all]_quiet work during minion startup on MacOS with runas specified (which fixed mac_service) [#61816](https://github.com/saltstack/salt/issues/61816)
- When deleting the vault cache, also delete from the session cache [#61821](https://github.com/saltstack/salt/issues/61821)
- Ignore errors on reading license info with dpkg_lowpkg to prevent tracebacks on getting package information. [#61827](https://github.com/saltstack/salt/issues/61827)
- win_lgpo: Display conflicting policy names when more than one policy is found [#61859](https://github.com/saltstack/salt/issues/61859)
- win_lgpo: Fixed intermittent KeyError when getting policy setting using lgpo.get_policy [#61860](https://github.com/saltstack/salt/issues/61860)
- Fixed listing minions on OpenBSD [#61966](https://github.com/saltstack/salt/issues/61966)
- Make Salt to return an error on "pkg" modules and states when targeting duplicated package names [#62019](https://github.com/saltstack/salt/issues/62019)
- Fix return of REST-returned permissions when auth_list is set [#62022](https://github.com/saltstack/salt/issues/62022)
- Normalize package names once on using pkg.installed/removed with yum to make it possible to install packages with the name containing a part similar to a name of architecture. [#62029](https://github.com/saltstack/salt/issues/62029)
- Fix inconsitency regarding name and pkgs parameters between zypperpkg.upgrade() and yumpkg.upgrade() [#62030](https://github.com/saltstack/salt/issues/62030)
- Fix attr=all handling in pkg.list_pkgs() (yum/zypper). [#62032](https://github.com/saltstack/salt/issues/62032)
- Fixed the humanname being ignored in pkgrepo.managed on openSUSE Leap [#62053](https://github.com/saltstack/salt/issues/62053)
- Fixed issue with some LGPO policies having whitespace at the beginning or end of the element alias [#62058](https://github.com/saltstack/salt/issues/62058)
- Fix ordering of args to libcloud_storage.download_object module [#62074](https://github.com/saltstack/salt/issues/62074)
- Ignore extend declarations in sls files that are excluded. [#62082](https://github.com/saltstack/salt/issues/62082)
- Remove leftover usage of impacket [#62101](https://github.com/saltstack/salt/issues/62101)
- Pass executable path from _get_path_exec() is used when calling the program.
  The $HOME env is no longer modified globally.
  Only trailing newlines are stripped from the fetched secret.
  Pass process arguments are handled in a secure way. [#62120](https://github.com/saltstack/salt/issues/62120)
- Ignore some command return codes in openbsdrcctl_service to prevent spurious errors [#62131](https://github.com/saltstack/salt/issues/62131)
- Fixed extra period in filename output in tls module. Instead of "server.crt." it will now be "server.crt". [#62139](https://github.com/saltstack/salt/issues/62139)
- Make sure lingering PAexec-*.exe files in the Windows directory are cleaned up [#62152](https://github.com/saltstack/salt/issues/62152)
- Restored Salt's DeprecationWarnings [#62185](https://github.com/saltstack/salt/issues/62185)
- Fixed issue with forward slashes on Windows with file.recurse and clean=True [#62197](https://github.com/saltstack/salt/issues/62197)
- Recognize OSMC as Debian-based [#62198](https://github.com/saltstack/salt/issues/62198)
- Fixed Zypper module failing on RPM lock file being temporarily unavailable. [#62204](https://github.com/saltstack/salt/issues/62204)
- Improved error handling and diagnostics in the proxmox salt-cloud driver [#62211](https://github.com/saltstack/salt/issues/62211)
- Added EndeavourOS to the Arch os_family. [#62220](https://github.com/saltstack/salt/issues/62220)
- Fix salt-ssh not detecting `platform-python` as a valid interpreter on EL8 [#62235](https://github.com/saltstack/salt/issues/62235)
- Fix pkg.version_cmp on openEuler and a few other os flavors. [#62248](https://github.com/saltstack/salt/issues/62248)
- Fix localhost detection in glusterfs.peers [#62273](https://github.com/saltstack/salt/issues/62273)
- Fix Salt Package Manager (SPM) exception when calling spm create_repo . [#62281](https://github.com/saltstack/salt/issues/62281)
- Fix matcher slowness due to loader invocation [#62283](https://github.com/saltstack/salt/issues/62283)
- Fixes the Puppet module for non-aio Puppet packages for example running the Puppet module on FreeBSD. [#62323](https://github.com/saltstack/salt/issues/62323)
- Issue 62334: Displays a debug log message instead of an error log message when the publisher fails to connect [#62334](https://github.com/saltstack/salt/issues/62334)
- Fix pyobjects renderer access to opts and sls [#62336](https://github.com/saltstack/salt/issues/62336)
- Fix use of random shuffle and sample functions as Jinja filters [#62372](https://github.com/saltstack/salt/issues/62372)
- Fix groups with duplicate GIDs are not returned by get_group_list [#62377](https://github.com/saltstack/salt/issues/62377)
- Fix the "zpool.present" state when enabling zpool features that are already active. [#62390](https://github.com/saltstack/salt/issues/62390)
- Fix ability to execute remote file client methods in saltcheck [#62398](https://github.com/saltstack/salt/issues/62398)
- Update all platforms to use pycparser 2.21 or greater for Py 3.9 or higher, fixes fips fault with openssl v3.x [#62400](https://github.com/saltstack/salt/issues/62400)
- Due to changes in the Netmiko library for the exception paths, need to check the version of Netmiko python library and then import the exceptions from different locations depending on the result. [#62405](https://github.com/saltstack/salt/issues/62405)
- When using preq on a state, then prereq state will first be run with test=True to determine if there are changes.  When there are changes, the state with the prereq option will be run prior to the prereq state.  If this state fails then the prereq state will not run and the state output uses the test=True run.  However, the proposed changes are included for the prereq state are included from the test=True run.  We should pull those out as there weren't actually changes since the prereq state did not run. [#62408](https://github.com/saltstack/salt/issues/62408)
- Added directory mode for file.copy with makedirs [#62426](https://github.com/saltstack/salt/issues/62426)
- Provide better error handling in the various napalm proxy minion functions when the device is not accessible. [#62435](https://github.com/saltstack/salt/issues/62435)
- When handling aggregation, change the order to ensure that the requisites are aggregated first and then the state functions are aggregated.  Caching whether aggregate functions are available for particular states so we don't need to attempt to load them everytime. [#62439](https://github.com/saltstack/salt/issues/62439)
- The patch allows to boostrap kubernetes clusters in the version above 1.13 via salt module [#62451](https://github.com/saltstack/salt/issues/62451)
- sysctl.persist now updates the in-memory value on FreeBSD even if the on-disk value was already correct. [#62461](https://github.com/saltstack/salt/issues/62461)
- Fixed parsing CDROM apt sources [#62474](https://github.com/saltstack/salt/issues/62474)
- Update sanitizing masking for Salt SSH to include additional password like strings. [#62483](https://github.com/saltstack/salt/issues/62483)
- Fix user/group checking on file state functions in the test mode. [#62499](https://github.com/saltstack/salt/issues/62499)
- Fix user.present to allow removing groups using optional_groups parameter and enforcing idempotent group membership. [#62502](https://github.com/saltstack/salt/issues/62502)
- Fix possible tracebacks if there is a package with '------' or '======' in the description is installed on the Debian based minion. [#62519](https://github.com/saltstack/salt/issues/62519)
- Fixed the omitted "pool" parameter when cloning a VM with the proxmox salt-cloud driver [#62521](https://github.com/saltstack/salt/issues/62521)
- Fix rendering of pyobjects states in saltcheck [#62523](https://github.com/saltstack/salt/issues/62523)
- Fixes pillar where a corrupted CacheDisk file forces the pillar to be rebuilt [#62527](https://github.com/saltstack/salt/issues/62527)
- Use str() method instead of repo_line for when python3-apt is installed or not in aptpkg.py. [#62546](https://github.com/saltstack/salt/issues/62546)
- Remove the connection_timeout from netmiko_connection_args before netmiko_connection_args is added to __context__["netmiko_device"]["args"] which is passed along to the Netmiko library. [#62547](https://github.com/saltstack/salt/issues/62547)
- Fix order specific mount.mounted options for persist [#62556](https://github.com/saltstack/salt/issues/62556)
- Fixed salt-cloud cloning a proxmox VM with a specified new vmid. [#62558](https://github.com/saltstack/salt/issues/62558)
- Fix runas with cmd module when using the onedir bundled packages [#62565](https://github.com/saltstack/salt/issues/62565)
- Update setproctitle version for all platforms [#62576](https://github.com/saltstack/salt/issues/62576)
- Fixed missing parameters when cloning a VM with the proxmox salt-cloud driver [#62580](https://github.com/saltstack/salt/issues/62580)
- Handle PermissionError when importing crypt when FIPS is enabled. [#62587](https://github.com/saltstack/salt/issues/62587)
- Correctly reraise exceptions in states.http [#62595](https://github.com/saltstack/salt/issues/62595)
- Fixed syndic eauth. Now jobs will be published when a valid eauth user is targeting allowed minions/functions. [#62618](https://github.com/saltstack/salt/issues/62618)
- updated rest_cherry/app to properly detect arg sent as a string as curl will do when only one arg is supplied. [#62624](https://github.com/saltstack/salt/issues/62624)
- Prevent possible tracebacks in core grains module by ignoring non utf8 characters in /proc/1/environ, /proc/1/cmdline, /proc/cmdline [#62633](https://github.com/saltstack/salt/issues/62633)
- Fixed vault ext pillar return data for KV v2 [#62651](https://github.com/saltstack/salt/issues/62651)
- Fix saltcheck _get_top_states doesn't pass saltenv to state.show_top [#62654](https://github.com/saltstack/salt/issues/62654)
- Fix groupadd.* functions hard code relative command name [#62657](https://github.com/saltstack/salt/issues/62657)
- Fixed pdbedit.create trying to use a bytes-like hash as string. [#62670](https://github.com/saltstack/salt/issues/62670)
- Fix depenency on legacy boto module in boto3 modules [#62672](https://github.com/saltstack/salt/issues/62672)
- Modified "_get_flags" function so that it returns regex flags instead of integers [#62676](https://github.com/saltstack/salt/issues/62676)
- Change startup ReqServer log messages from error to info level. [#62728](https://github.com/saltstack/salt/issues/62728)
- Fix kmod.* functions hard code relative command name [#62772](https://github.com/saltstack/salt/issues/62772)
- Fix mac_brew_pkg to work with null taps [#62793](https://github.com/saltstack/salt/issues/62793)
- Fixing a bug when listing the running schedule if "schedule.enable" and/or "schedule.disable" has been run, where the "enabled" items is being treated as a schedule item. [#62795](https://github.com/saltstack/salt/issues/62795)
- Prevent annoying RuntimeWarning message about line buffering (buffering=1) not being supported in binary mode [#62817](https://github.com/saltstack/salt/issues/62817)
- Include UID and GID checks in modules.file.check_perms as well as comparing
  ownership by username and group name. [#62818](https://github.com/saltstack/salt/issues/62818)
- Fix presence events on TCP transport by removing a client's presence when minion disconnects from publish channel correctly [#62826](https://github.com/saltstack/salt/issues/62826)
- Remove Azure deprecation messages from functions that always run w/ salt-cloud [#62845](https://github.com/saltstack/salt/issues/62845)
- Use select instead of iterating over entrypoints as a dictionary for importlib_metadata>=5.0.0 [#62854](https://github.com/saltstack/salt/issues/62854)
- Fixed master job scheduler using when [#62858](https://github.com/saltstack/salt/issues/62858)
- LGPO: Added support for missing domain controller policies: VulnerableChannelAllowList and LdapEnforceChannelBinding [#62873](https://github.com/saltstack/salt/issues/62873)
- Fix unnecessarily complex gce metadata grains code to use googles metadata service more effectively. [#62878](https://github.com/saltstack/salt/issues/62878)
- Fixed dockermod version_info function for docker-py 6.0.0+ [#62882](https://github.com/saltstack/salt/issues/62882)
- Moving setting the LOAD_BALANCING_POLICY_MAP dictionary into the try except block that determines if the cassandra_cql module should be made available. [#62886](https://github.com/saltstack/salt/issues/62886)
- Updating various MongoDB module functions to work with latest version of pymongo. [#62900](https://github.com/saltstack/salt/issues/62900)
- Restored channel for Syndic minions to send job returns to the Salt master. [#62933](https://github.com/saltstack/salt/issues/62933)
- removed _resolve_deps as it required a library that is not generally avalible. and switched to apt-get for everything as that can auto resolve dependencies. [#62934](https://github.com/saltstack/salt/issues/62934)
- Updated pyzmq to version 22.0.3 on Windows builds because the old version was causing salt-minion/salt-call to hang [#62937](https://github.com/saltstack/salt/issues/62937)
- Allow root user to modify crontab lines for non-root users (except AIX and Solaris). Align crontab line changes with the file ones and also with listing crontab. [#62940](https://github.com/saltstack/salt/issues/62940)
- Fix systemd_service.* functions hard code relative command name [#62942](https://github.com/saltstack/salt/issues/62942)
- Fix file.symlink backupname operation can copy remote contents to local disk [#62953](https://github.com/saltstack/salt/issues/62953)
- Issue #62968: Fix issue where cloud deployments were putting the keys in the wrong location on Windows hosts [#62968](https://github.com/saltstack/salt/issues/62968)
- Fixed gpg_passphrase issue with gpg decrypt/encrypt functions [#62977](https://github.com/saltstack/salt/issues/62977)
- Fix file.tidied FileNotFoundError [#62986](https://github.com/saltstack/salt/issues/62986)
- Fixed bug where module.wait states were detected as running legacy module.run syntax [#62988](https://github.com/saltstack/salt/issues/62988)
- Fixed issue with win_wua module where it wouldn't load if the CryptSvc was set to Manual start [#62993](https://github.com/saltstack/salt/issues/62993)
- The `__opts__` dunder dictionary is now added to the loader's `pack` if not
  already present, which makes it accessible via the
  `salt.loader.context.NamedLoaderContext` class. [#63013](https://github.com/saltstack/salt/issues/63013)
- Issue #63024: Fix issue where grains and config data were being place in the wrong location on Windows hosts [#63024](https://github.com/saltstack/salt/issues/63024)
- Fix btrfs.subvolume_snapshot command failing [#63025](https://github.com/saltstack/salt/issues/63025)
- Fix file.retention_schedule always reports changes [#63033](https://github.com/saltstack/salt/issues/63033)
- Fix mongo authentication for mongo ext_pillar and mongo returner

  This fix also include the ability to use the mongo connection string for mongo ext_pillar [#63058](https://github.com/saltstack/salt/issues/63058)
- Fixed x509.create_csr creates invalid CSR by default in the new cryptography x509 module. [#63103](https://github.com/saltstack/salt/issues/63103)
- TCP transport documentation now contains proper master/minion-side filtering information [#63120](https://github.com/saltstack/salt/issues/63120)
- Fixed gpg.verify does not respect gnupghome [#63145](https://github.com/saltstack/salt/issues/63145)
- Made pillar cache pass extra minion data as well [#63208](https://github.com/saltstack/salt/issues/63208)
- Fix serious performance issues with the file.tidied module [#63231](https://github.com/saltstack/salt/issues/63231)
- Fix rpm_lowpkg version comparison logic when using rpm-vercmp and only one version has a release number. [#63317](https://github.com/saltstack/salt/issues/63317)
- Import StrictVersion and LooseVersion from setuptools.distutils.verison or setuptools._distutils.version, if first not available [#63350](https://github.com/saltstack/salt/issues/63350)
- When the shell is passed as powershell or pwsh, only wrapper the shell in quotes if cmd.run is running on Windows.  When quoted on Linux hosts, this results in an error when the keyword arguments are appended. [#63590](https://github.com/saltstack/salt/issues/63590)
- LGPO: Added support for "Relax minimum password length limits" [#63596](https://github.com/saltstack/salt/issues/63596)
- When a job is disabled only increase it's _next_fire_time value if the job would have run at the current time, eg. the current _next_fire_time == now. [#63699](https://github.com/saltstack/salt/issues/63699)
- Check file is not empty before attempting to read pillar disk cache file [#63729](https://github.com/saltstack/salt/issues/63729)
- fix cherrypy 400 error output to be less generic. [#63835](https://github.com/saltstack/salt/issues/63835)
- remove eval and update logging to be more informative on bad config [#63879](https://github.com/saltstack/salt/issues/63879)


### Added

- Introduce a `LIB_STATE_DIR` syspaths variable which defaults to `CONFIG_DIR`,
  but can be individually customized during installation by specifying
  `--salt-lib-state-dir` during installation. Change the default `pki_dir` to
  `<LIB_STATE_DIR>/pki/master` (for the master) and `<LIB_STATE_DIR>/pki/minion`
  (for the minion). [#3396](https://github.com/saltstack/salt/issues/3396)
- Allow users to enable 'queue=True' for all state runs via config file [#31468](https://github.com/saltstack/salt/issues/31468)
- Added pillar templating to vault policies [#43287](https://github.com/saltstack/salt/issues/43287)
- Add support for NVMeF as a transport protocol for hosts in a Pure Storage FlashArray [#51088](https://github.com/saltstack/salt/issues/51088)
- A new salt-ssh roster that generates a roster by parses a known_hosts file. [#54679](https://github.com/saltstack/salt/issues/54679)
- Added Windows Event Viewer support [#54713](https://github.com/saltstack/salt/issues/54713)
- Added the win_lgpo_reg state and execution modules which will allow registry based group policy to be set directly in the Registry.pol file [#56013](https://github.com/saltstack/salt/issues/56013)
- Added resource tagging functions to boto_dynamodb execution module [#57500](https://github.com/saltstack/salt/issues/57500)
- Added `openvswitch_db` state module and functions `bridge_to_parent`,
  `bridge_to_vlan`, `db_get`, and `db_set` to the `openvswitch` execution module.
  Also added optional `parent` and `vlan` parameters to the
  `openvswitch_bridge.present` state module function and the
  `openvswitch.bridge_create` execution module function. [#58986](https://github.com/saltstack/salt/issues/58986)
- State module to manage SysFS attributes [#60154](https://github.com/saltstack/salt/issues/60154)
- Added ability for `salt.wait_for_event` to handle `event_id`s that have a list value. [#60430](https://github.com/saltstack/salt/issues/60430)
- Added suport for Linux ppc64le core grains (cpu_model, virtual, productname, manufacturer, serialnumber) and arm core grains (serialnumber, productname) [#60518](https://github.com/saltstack/salt/issues/60518)
- Added autostart option to virt.defined and virt.running states, along with virt.update execution modules. [#60700](https://github.com/saltstack/salt/issues/60700)
- Added .0 back to our versioning scheme for future versions (e.g. 3006.0) [#60722](https://github.com/saltstack/salt/issues/60722)
- Initial work to allow parallel startup of proxy minions when used as sub proxies with Deltaproxy. [#61153](https://github.com/saltstack/salt/issues/61153)
- Added node label support for GCE [#61245](https://github.com/saltstack/salt/issues/61245)
- Support the --priority flag when adding sources to Chocolatey. [#61319](https://github.com/saltstack/salt/issues/61319)
- Add namespace option to ext_pillar.http_json [#61335](https://github.com/saltstack/salt/issues/61335)
- Added a filter function to ps module to get a list of processes on a minion according to their state. [#61420](https://github.com/saltstack/salt/issues/61420)
- Add postgres.timeout option to postgres module for limiting postgres query times [#61433](https://github.com/saltstack/salt/issues/61433)
- Added new optional vault option, ``config_location``. This can be either ``master`` or ``local`` and defines where vault will look for connection details, either requesting them from the master or using the local config. [#61857](https://github.com/saltstack/salt/issues/61857)
- Add ipwrap() jinja filter to wrap IPv6 addresses with brackets. [#61931](https://github.com/saltstack/salt/issues/61931)
- 'tcp' transport is now available in ipv6-only network [#62009](https://github.com/saltstack/salt/issues/62009)
- Add `diff_attr` parameter to pkg.upgrade() (zypper/yum). [#62031](https://github.com/saltstack/salt/issues/62031)
- Config option pass_variable_prefix allows to distinguish variables that contain paths to pass secrets.
  Config option pass_strict_fetch allows to error out when a secret cannot be fetched from pass.
  Config option pass_dir allows setting the PASSWORD_STORE_DIR env for pass.
  Config option pass_gnupghome allows setting the $GNUPGHOME env for pass. [#62120](https://github.com/saltstack/salt/issues/62120)
- Add file.pruned state and expanded file.rmdir exec module functionality [#62178](https://github.com/saltstack/salt/issues/62178)
- Added "dig.PTR" function to resolve PTR records for IPs, as well as tests and documentation [#62275](https://github.com/saltstack/salt/issues/62275)
- Added the ability to remove a KB using the DISM state/execution modules [#62366](https://github.com/saltstack/salt/issues/62366)
- Add "<tiamat> python" subcommand to allow execution or arbitrary scripts via bundled Python runtime [#62381](https://github.com/saltstack/salt/issues/62381)
- Add ability to provide conditions which convert normal state actions to no-op when true [#62446](https://github.com/saltstack/salt/issues/62446)
- Added debug log messages displaying the command being run when installing packages on Windows [#62480](https://github.com/saltstack/salt/issues/62480)
- Add biosvendor grain [#62496](https://github.com/saltstack/salt/issues/62496)
- Add ifelse Jinja function as found in CFEngine [#62508](https://github.com/saltstack/salt/issues/62508)
- Implementation of Amazon EC2 instance detection and setting `virtual_subtype` grain accordingly including the product if possible to identify. [#62539](https://github.com/saltstack/salt/issues/62539)
- Adds __env__substitution to ext_pillar.stack; followup of #61531, improved exception handling for stacked template (jinja) template rendering and yaml parsing in ext_pillar.stack [#62578](https://github.com/saltstack/salt/issues/62578)
- Increase file.tidied flexibility with regard to age and size [#62678](https://github.com/saltstack/salt/issues/62678)
- Added "connected_devices" feature to netbox pillar module. It contains extra information about devices connected to the minion [#62761](https://github.com/saltstack/salt/issues/62761)
- Add atomic file operation for symlink changes [#62768](https://github.com/saltstack/salt/issues/62768)
- Add password/account locking/unlocking in user.present state on supported operating systems [#62856](https://github.com/saltstack/salt/issues/62856)
- Added onchange configuration for script engine [#62867](https://github.com/saltstack/salt/issues/62867)
- Added output and bare functionality to export_key gpg module function [#62978](https://github.com/saltstack/salt/issues/62978)
- Add keyvalue serializer for environment files [#62983](https://github.com/saltstack/salt/issues/62983)
- Add ability to ignore symlinks in file.tidied [#63042](https://github.com/saltstack/salt/issues/63042)
- salt-cloud support IMDSv2 tokens when using 'use-instance-role-credentials' [#63067](https://github.com/saltstack/salt/issues/63067)
- Add ability for file.symlink to not set ownership on existing links [#63093](https://github.com/saltstack/salt/issues/63093)
- Restore the previous slack engine and deprecate it, rename replace the slack engine to slack_bolt until deprecation [#63095](https://github.com/saltstack/salt/issues/63095)
- Add functions that will return the underlying block device, mount point, and filesystem type for a given path [#63098](https://github.com/saltstack/salt/issues/63098)
- Add ethtool execution and state module functions for pause [#63128](https://github.com/saltstack/salt/issues/63128)
- Add boardname grain [#63131](https://github.com/saltstack/salt/issues/63131)
- Added management of ECDSA/EdDSA private keys with x509 modules in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#63248](https://github.com/saltstack/salt/issues/63248)
- Added x509 modules support for different output formats in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#63249](https://github.com/saltstack/salt/issues/63249)
- Added deprecation_warning test state for ensuring that deprecation warnings are correctly emitted. [#63315](https://github.com/saltstack/salt/issues/63315)
- Adds a state_events option to state.highstate, state.apply, state.sls, state.sls_id.
  This allows users to enable state_events on a per use basis rather than having to
  enable them globally for all state runs. [#63316](https://github.com/saltstack/salt/issues/63316)
- Allow max queue size setting for state runs to prevent performance problems from queue growth [#63356](https://github.com/saltstack/salt/issues/63356)
- Add support of exposing meta_server_grains for Azure VMs [#63606](https://github.com/saltstack/salt/issues/63606)
- Include the version of `relenv` in the versions report. [#63827](https://github.com/saltstack/salt/issues/63827)
- Added debug log messages displaying the command being run when removing packages on Windows [#63866](https://github.com/saltstack/salt/issues/63866)


## 3006.0rc1 (2023-03-01)


### Removed

- Remove and deprecate the __orchestration__ key from salt.runner and salt.wheel return data. To get it back, set features.enable_deprecated_orchestration_flag master configuration option to True. The flag will be completely removed in Salt 3008 Argon. [#59917](https://github.com/saltstack/salt/issues/59917)
- Removed distutils and replaced with setuptools, given distutils is deprecated and removed in Python 3.12 [#60476](https://github.com/saltstack/salt/issues/60476)
- Removed ``runtests`` targets from ``noxfile.py`` [#62239](https://github.com/saltstack/salt/issues/62239)
- Removed the PyObjC dependency.

  This addresses problems with building a one dir build for macOS.
  It became problematic because depending on the macOS version, it pulls different dependencies, and we would either have to build a macos onedir for each macOS supported release, or ship a crippled onedir(because it would be tied to the macOS version where the onedir was built).
  Since it's currently not being used, it's removed. [#62432](https://github.com/saltstack/salt/issues/62432)


### Deprecated

- renamed `keep_jobs`, specifying job cache TTL in hours, to `keep_jobs_seconds`, specifying TTL in seconds.
  `keep_jobs` will be removed in the Argon release [#55295](https://github.com/saltstack/salt/issues/55295)
- Removing all references to napalm-base which is no longer supported. [#61542](https://github.com/saltstack/salt/issues/61542)
- The 'ip_bracket' function has been moved from salt/utils/zeromq.py in salt/utils/network.py [#62009](https://github.com/saltstack/salt/issues/62009)
- The `expand_repo_def` function in `salt.modules.aptpkg` is now deprecated. It's only used in `salt.states.pkgrepo` and it has no use of being exposed to the CLI. [#62485](https://github.com/saltstack/salt/issues/62485)
- Deprecated defunct Django returner [#62644](https://github.com/saltstack/salt/issues/62644)
- Deprecate core ESXi and associated states and modules, vcenter and vsphere support in favor of Salt VMware Extensions [#62754](https://github.com/saltstack/salt/issues/62754)
- Removing manufacture grain which has been deprecated. [#62914](https://github.com/saltstack/salt/issues/62914)
- Removing deprecated utils/boto3_elasticsearch.py [#62915](https://github.com/saltstack/salt/issues/62915)
- Removing support for the now deprecated _ext_nodes from salt/master.py. [#62917](https://github.com/saltstack/salt/issues/62917)
- Deprecating the Salt Slack engine in favor of the Salt Slack Bolt Engine. [#63095](https://github.com/saltstack/salt/issues/63095)
- `salt.utils.version.StrictVersion` is now deprecated and it's use should be replaced with `salt.utils.version.Version`. [#63383](https://github.com/saltstack/salt/issues/63383)


### Changed

- More intelligent diffing in changes of file.serialize state. [#48609](https://github.com/saltstack/salt/issues/48609)
- Move deprecation of the neutron module to Argon. Please migrate to the neutronng module instead. [#49430](https://github.com/saltstack/salt/issues/49430)
- ``umask`` is now a global state argument, instead of only applying to ``cmd``
  states. [#57803](https://github.com/saltstack/salt/issues/57803)
- Update pillar.obfuscate to accept kwargs in addition to args.  This is useful when passing in keyword arguments like saltenv that are then passed along to pillar.items. [#58971](https://github.com/saltstack/salt/issues/58971)
- Improve support for listing macOS brew casks [#59439](https://github.com/saltstack/salt/issues/59439)
- Add missing MariaDB Grants to mysql module.
  MariaDB has added some grants in 10.4.x and 10.5.x that are not present here, which results in an error when creating.
  Also improved exception handling in `grant_add` which did not log the original error message and replaced it with a generic error. [#61409](https://github.com/saltstack/salt/issues/61409)
- Use VENV_PIP_TARGET environment variable as a default target for pip if present. [#62089](https://github.com/saltstack/salt/issues/62089)
- Disabled FQDNs grains on macOS by default [#62168](https://github.com/saltstack/salt/issues/62168)
- Replaced pyroute2.IPDB with pyroute2.NDB, as the former is deprecated [#62218](https://github.com/saltstack/salt/issues/62218)
- Enhance capture of error messages for Zypper calls in zypperpkg module. [#62346](https://github.com/saltstack/salt/issues/62346)
- Removed GPG_1_3_1 check [#62895](https://github.com/saltstack/salt/issues/62895)
- Requisite state chunks now all consistently contain `__id__`, `__sls__` and `name`. [#63012](https://github.com/saltstack/salt/issues/63012)
- netapi_enable_clients option to allow enabling/disabling of clients in salt-api.
  By default all clients will now be disabled. Users of salt-api will need
  to update their master config to enable the clients that they use. Not adding
  the netapi_enable_clients option with required clients to the master config will
  disable salt-api. [#63050](https://github.com/saltstack/salt/issues/63050)
- Stop relying on `salt/_version.py` to write Salt's version. Instead use `salt/_version.txt` which only contains the version string. [#63383](https://github.com/saltstack/salt/issues/63383)
- Set enable_fqdns_grains to be False by default. [#63595](https://github.com/saltstack/salt/issues/63595)
- Changelog snippet files must now have a `.md` file extension to be more explicit on what type of rendering is done when they are included in the main `CHANGELOG.md` file. [#63710](https://github.com/saltstack/salt/issues/63710)


### Fixed

- Add kwargs to handle extra parameters for http.query [#36138](https://github.com/saltstack/salt/issues/36138)
- Fix mounted bind mounts getting active mount options added [#39292](https://github.com/saltstack/salt/issues/39292)
- Fix `sysctl.present` converts spaces to tabs. [#40054](https://github.com/saltstack/salt/issues/40054)
- Fixes state pkg.purged to purge removed packages on Debian family systems [#42306](https://github.com/saltstack/salt/issues/42306)
- Fix fun_args missing from syndic returns [#45823](https://github.com/saltstack/salt/issues/45823)
- Fix mount.mounted with 'mount: False' reports unmounted file system as unchanged when running with test=True [#47201](https://github.com/saltstack/salt/issues/47201)
- Issue #49310: Allow users to touch a file with Unix date of birth [#49310](https://github.com/saltstack/salt/issues/49310)
- Do not raise an exception in pkg.info_installed on nonzero return code [#51620](https://github.com/saltstack/salt/issues/51620)
- Passes the value of the force parameter from file.copy to its call to file.remove so that files with the read-only attribute are handled. [#51739](https://github.com/saltstack/salt/issues/51739)
- Fixed x509.certificate_managed creates new certificate every run in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#52167](https://github.com/saltstack/salt/issues/52167)
- Don't check for cached pillar errors on state.apply [#52354](https://github.com/saltstack/salt/issues/52354), [#57180](https://github.com/saltstack/salt/issues/57180), [#59339](https://github.com/saltstack/salt/issues/59339)
- Swapping out args and kwargs for arg and kwarg respectively in the Slack engine when the command passed is a runner. [#52400](https://github.com/saltstack/salt/issues/52400)
- Ensure when we're adding chunks to the rules when running aggregation with the iptables state module we use a copy of the chunk otherwise we end up with a recursive mess. [#53353](https://github.com/saltstack/salt/issues/53353)
- When user_create or user_remove fail, return False instead of returning the error. [#53377](https://github.com/saltstack/salt/issues/53377)
- Include sync_roster when sync_all is called. [#53914](https://github.com/saltstack/salt/issues/53914)
- Avoid warning noise in lograte.get [#53988](https://github.com/saltstack/salt/issues/53988)
- Fixed listing revoked keys with gpg.list_keys [#54347](https://github.com/saltstack/salt/issues/54347)
- Fix mount.mounted does not handle blanks properly [#54508](https://github.com/saltstack/salt/issues/54508)
- Fixed grain num_cpus get wrong CPUs count in case of inconsistent CPU numbering. [#54682](https://github.com/saltstack/salt/issues/54682)
- Fix spelling error for python_shell argument in dpkg_lower module [#54907](https://github.com/saltstack/salt/issues/54907)
- Cleaned up bytes response data before sending to non-bytes compatible returners (postgres, mysql) [#55226](https://github.com/saltstack/salt/issues/55226)
- Fixed malformed state return when testing file.managed with unavailable source file [#55269](https://github.com/saltstack/salt/issues/55269)
- Included stdout in error message for Zypper calls in zypperpkg module. [#56016](https://github.com/saltstack/salt/issues/56016)
- Fixed pillar.filter_by with salt-ssh [#56093](https://github.com/saltstack/salt/issues/56093)
- Fix boto_route53 issue with (multiple) VPCs. [#57139](https://github.com/saltstack/salt/issues/57139)
- Remove log from mine runner which was not used. [#57463](https://github.com/saltstack/salt/issues/57463)
- Fixed x509.read_certificate error when reading a Microsoft CA issued certificate in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#57535](https://github.com/saltstack/salt/issues/57535)
- Updating Slack engine to use slack_bolt library. [#57842](https://github.com/saltstack/salt/issues/57842)
- Fixed warning about replace=True with x509.certificate_managed in the new cryptography x509 module. [#58165](https://github.com/saltstack/salt/issues/58165)
- Fix salt.modules.pip:is_installed doesn't handle locally installed packages [#58202](https://github.com/saltstack/salt/issues/58202)
- Add missing MariaDB Grants to mysql module. MariaDB has added some grants in 10.4.x and 10.5.x that are not present here, which results in an error when creating. [#58297](https://github.com/saltstack/salt/issues/58297)
- linux_shadow: Fix cases where malformed shadow entries cause `user.present`
  states to fail. [#58423](https://github.com/saltstack/salt/issues/58423)
- Fixed salt.utils.compat.cmp to work with dictionaries [#58729](https://github.com/saltstack/salt/issues/58729)
- Fixed formatting for terse output mode [#58953](https://github.com/saltstack/salt/issues/58953)
- Fixed RecursiveDictDiffer with added nested dicts [#59017](https://github.com/saltstack/salt/issues/59017)
- Fixed x509.certificate_managed has DoS effect on master in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#59169](https://github.com/saltstack/salt/issues/59169)
- Fixed saltnado websockets disconnecting immediately [#59183](https://github.com/saltstack/salt/issues/59183)
- Fixed x509.certificate_managed rolls certificates every now and then in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#59315](https://github.com/saltstack/salt/issues/59315)
- Fix postgres_privileges.present not idempotent for functions [#59585](https://github.com/saltstack/salt/issues/59585)
- Fixed influxdb_continuous_query.present state to provide the client args to the underlying module on create. [#59766](https://github.com/saltstack/salt/issues/59766)
- Warn when using insecure (http:// based) key_urls for apt-based systems in pkgrepo.managed, and add a kwarg that determines the validity of such a url. [#59786](https://github.com/saltstack/salt/issues/59786)
- add load balancing policy default option and ensure the module can be executed with arguments from CLI [#59909](https://github.com/saltstack/salt/issues/59909)
- Fix salt-ssh when using imports with extra-filerefs. [#60003](https://github.com/saltstack/salt/issues/60003)
- Fixed cache directory corruption startup error [#60170](https://github.com/saltstack/salt/issues/60170)
- Update docs remove dry_run in docstring of file.blockreplace state. [#60227](https://github.com/saltstack/salt/issues/60227)
- Adds Parrot to OS_Family_Map in grains. [#60249](https://github.com/saltstack/salt/issues/60249)
- Fixed stdout and stderr being empty sometimes when use_vt=True for the cmd.run[*] functions [#60365](https://github.com/saltstack/salt/issues/60365)
- Use return code in iptables --check to verify rule exists. [#60467](https://github.com/saltstack/salt/issues/60467)
- Fix regression pip.installed does not pass env_vars when calling pip.list [#60557](https://github.com/saltstack/salt/issues/60557)
- Fix xfs module when additional output included in mkfs.xfs command. [#60853](https://github.com/saltstack/salt/issues/60853)
- Fixed parsing new format of terraform states in roster.terraform [#60915](https://github.com/saltstack/salt/issues/60915)
- Fixed recognizing installed ARMv7 rpm packages in compatible architectures. [#60994](https://github.com/saltstack/salt/issues/60994)
- Fixing changes dict in pkg state to be consistent when installing and test=True. [#60995](https://github.com/saltstack/salt/issues/60995)
- Fix cron.present duplicating entries when changing timespec to special. [#60997](https://github.com/saltstack/salt/issues/60997)
- Made salt-ssh respect --wipe again [#61083](https://github.com/saltstack/salt/issues/61083)
- state.orchestrate_single only passes a pillar if it is set to the state
  function. This allows it to be used with state functions that don't accept a
  pillar keyword argument. [#61092](https://github.com/saltstack/salt/issues/61092)
- Fix ipset state when the comment kwarg is set. [#61122](https://github.com/saltstack/salt/issues/61122)
- Fix issue with archive.unzip where the password was not being encoded for the extract function [#61422](https://github.com/saltstack/salt/issues/61422)
- Some Linux distributions (like AlmaLinux, Astra Linux, Debian, Mendel, Linux
  Mint, Pop!_OS, Rocky Linux) report different `oscodename`, `osfullname`,
  `osfinger` grains if lsb-release is installed or not. They have been changed to
  only derive these OS grains from `/etc/os-release`. [#61618](https://github.com/saltstack/salt/issues/61618)
- Pop!_OS uses the full version (YY.MM) in the osfinger grain now, not just the year. This allows differentiating for example between 20.04 and 20.10. [#61619](https://github.com/saltstack/salt/issues/61619)
- Fix ssh config roster to correctly parse the ssh config files that contain spaces. [#61650](https://github.com/saltstack/salt/issues/61650)
- Fix SoftLayer configuration not raising an exception when a domain is missing [#61727](https://github.com/saltstack/salt/issues/61727)
- Allow the minion to start or salt-call to run even if the user doesn't have permissions to read the root_dir value from the registry [#61789](https://github.com/saltstack/salt/issues/61789)
- Need to move the creation of the proxy object for the ProxyMinion further down in the initialization for sub proxies to ensure that all modules, especially any custom proxy modules, are available before attempting to run the init function. [#61805](https://github.com/saltstack/salt/issues/61805)
- Fixed malformed state return when merge-serializing to an improperly formatted file [#61814](https://github.com/saltstack/salt/issues/61814)
- Made cmdmod._run[_all]_quiet work during minion startup on MacOS with runas specified (which fixed mac_service) [#61816](https://github.com/saltstack/salt/issues/61816)
- When deleting the vault cache, also delete from the session cache [#61821](https://github.com/saltstack/salt/issues/61821)
- Ignore errors on reading license info with dpkg_lowpkg to prevent tracebacks on getting package information. [#61827](https://github.com/saltstack/salt/issues/61827)
- win_lgpo: Display conflicting policy names when more than one policy is found [#61859](https://github.com/saltstack/salt/issues/61859)
- win_lgpo: Fixed intermittent KeyError when getting policy setting using lgpo.get_policy [#61860](https://github.com/saltstack/salt/issues/61860)
- Fixed listing minions on OpenBSD [#61966](https://github.com/saltstack/salt/issues/61966)
- Make Salt to return an error on "pkg" modules and states when targeting duplicated package names [#62019](https://github.com/saltstack/salt/issues/62019)
- Fix return of REST-returned permissions when auth_list is set [#62022](https://github.com/saltstack/salt/issues/62022)
- Normalize package names once on using pkg.installed/removed with yum to make it possible to install packages with the name containing a part similar to a name of architecture. [#62029](https://github.com/saltstack/salt/issues/62029)
- Fix inconsitency regarding name and pkgs parameters between zypperpkg.upgrade() and yumpkg.upgrade() [#62030](https://github.com/saltstack/salt/issues/62030)
- Fix attr=all handling in pkg.list_pkgs() (yum/zypper). [#62032](https://github.com/saltstack/salt/issues/62032)
- Fixed the humanname being ignored in pkgrepo.managed on openSUSE Leap [#62053](https://github.com/saltstack/salt/issues/62053)
- Fixed issue with some LGPO policies having whitespace at the beginning or end of the element alias [#62058](https://github.com/saltstack/salt/issues/62058)
- Fix ordering of args to libcloud_storage.download_object module [#62074](https://github.com/saltstack/salt/issues/62074)
- Ignore extend declarations in sls files that are excluded. [#62082](https://github.com/saltstack/salt/issues/62082)
- Remove leftover usage of impacket [#62101](https://github.com/saltstack/salt/issues/62101)
- Pass executable path from _get_path_exec() is used when calling the program.
  The $HOME env is no longer modified globally.
  Only trailing newlines are stripped from the fetched secret.
  Pass process arguments are handled in a secure way. [#62120](https://github.com/saltstack/salt/issues/62120)
- Ignore some command return codes in openbsdrcctl_service to prevent spurious errors [#62131](https://github.com/saltstack/salt/issues/62131)
- Fixed extra period in filename output in tls module. Instead of "server.crt." it will now be "server.crt". [#62139](https://github.com/saltstack/salt/issues/62139)
- Make sure lingering PAexec-*.exe files in the Windows directory are cleaned up [#62152](https://github.com/saltstack/salt/issues/62152)
- Restored Salt's DeprecationWarnings [#62185](https://github.com/saltstack/salt/issues/62185)
- Fixed issue with forward slashes on Windows with file.recurse and clean=True [#62197](https://github.com/saltstack/salt/issues/62197)
- Recognize OSMC as Debian-based [#62198](https://github.com/saltstack/salt/issues/62198)
- Fixed Zypper module failing on RPM lock file being temporarily unavailable. [#62204](https://github.com/saltstack/salt/issues/62204)
- Improved error handling and diagnostics in the proxmox salt-cloud driver [#62211](https://github.com/saltstack/salt/issues/62211)
- Added EndeavourOS to the Arch os_family. [#62220](https://github.com/saltstack/salt/issues/62220)
- Fix salt-ssh not detecting `platform-python` as a valid interpreter on EL8 [#62235](https://github.com/saltstack/salt/issues/62235)
- Fix pkg.version_cmp on openEuler and a few other os flavors. [#62248](https://github.com/saltstack/salt/issues/62248)
- Fix localhost detection in glusterfs.peers [#62273](https://github.com/saltstack/salt/issues/62273)
- Fix Salt Package Manager (SPM) exception when calling spm create_repo . [#62281](https://github.com/saltstack/salt/issues/62281)
- Fix matcher slowness due to loader invocation [#62283](https://github.com/saltstack/salt/issues/62283)
- Fixes the Puppet module for non-aio Puppet packages for example running the Puppet module on FreeBSD. [#62323](https://github.com/saltstack/salt/issues/62323)
- Issue 62334: Displays a debug log message instead of an error log message when the publisher fails to connect [#62334](https://github.com/saltstack/salt/issues/62334)
- Fix pyobjects renderer access to opts and sls [#62336](https://github.com/saltstack/salt/issues/62336)
- Fix use of random shuffle and sample functions as Jinja filters [#62372](https://github.com/saltstack/salt/issues/62372)
- Fix groups with duplicate GIDs are not returned by get_group_list [#62377](https://github.com/saltstack/salt/issues/62377)
- Fix the "zpool.present" state when enabling zpool features that are already active. [#62390](https://github.com/saltstack/salt/issues/62390)
- Fix ability to execute remote file client methods in saltcheck [#62398](https://github.com/saltstack/salt/issues/62398)
- Update all platforms to use pycparser 2.21 or greater for Py 3.9 or higher, fixes fips fault with openssl v3.x [#62400](https://github.com/saltstack/salt/issues/62400)
- Due to changes in the Netmiko library for the exception paths, need to check the version of Netmiko python library and then import the exceptions from different locations depending on the result. [#62405](https://github.com/saltstack/salt/issues/62405)
- When using preq on a state, then prereq state will first be run with test=True to determine if there are changes.  When there are changes, the state with the prereq option will be run prior to the prereq state.  If this state fails then the prereq state will not run and the state output uses the test=True run.  However, the proposed changes are included for the prereq state are included from the test=True run.  We should pull those out as there weren't actually changes since the prereq state did not run. [#62408](https://github.com/saltstack/salt/issues/62408)
- Added directory mode for file.copy with makedirs [#62426](https://github.com/saltstack/salt/issues/62426)
- Provide better error handling in the various napalm proxy minion functions when the device is not accessible. [#62435](https://github.com/saltstack/salt/issues/62435)
- When handling aggregation, change the order to ensure that the requisites are aggregated first and then the state functions are aggregated.  Caching whether aggregate functions are available for particular states so we don't need to attempt to load them everytime. [#62439](https://github.com/saltstack/salt/issues/62439)
- The patch allows to boostrap kubernetes clusters in the version above 1.13 via salt module [#62451](https://github.com/saltstack/salt/issues/62451)
- sysctl.persist now updates the in-memory value on FreeBSD even if the on-disk value was already correct. [#62461](https://github.com/saltstack/salt/issues/62461)
- Fixed parsing CDROM apt sources [#62474](https://github.com/saltstack/salt/issues/62474)
- Update sanitizing masking for Salt SSH to include additional password like strings. [#62483](https://github.com/saltstack/salt/issues/62483)
- Fix user/group checking on file state functions in the test mode. [#62499](https://github.com/saltstack/salt/issues/62499)
- Fix user.present to allow removing groups using optional_groups parameter and enforcing idempotent group membership. [#62502](https://github.com/saltstack/salt/issues/62502)
- Fix possible tracebacks if there is a package with '------' or '======' in the description is installed on the Debian based minion. [#62519](https://github.com/saltstack/salt/issues/62519)
- Fixed the omitted "pool" parameter when cloning a VM with the proxmox salt-cloud driver [#62521](https://github.com/saltstack/salt/issues/62521)
- Fix rendering of pyobjects states in saltcheck [#62523](https://github.com/saltstack/salt/issues/62523)
- Fixes pillar where a corrupted CacheDisk file forces the pillar to be rebuilt [#62527](https://github.com/saltstack/salt/issues/62527)
- Use str() method instead of repo_line for when python3-apt is installed or not in aptpkg.py. [#62546](https://github.com/saltstack/salt/issues/62546)
- Remove the connection_timeout from netmiko_connection_args before netmiko_connection_args is added to __context__["netmiko_device"]["args"] which is passed along to the Netmiko library. [#62547](https://github.com/saltstack/salt/issues/62547)
- Fix order specific mount.mounted options for persist [#62556](https://github.com/saltstack/salt/issues/62556)
- Fixed salt-cloud cloning a proxmox VM with a specified new vmid. [#62558](https://github.com/saltstack/salt/issues/62558)
- Fix runas with cmd module when using the onedir bundled packages [#62565](https://github.com/saltstack/salt/issues/62565)
- Update setproctitle version for all platforms [#62576](https://github.com/saltstack/salt/issues/62576)
- Fixed missing parameters when cloning a VM with the proxmox salt-cloud driver [#62580](https://github.com/saltstack/salt/issues/62580)
- Handle PermissionError when importing crypt when FIPS is enabled. [#62587](https://github.com/saltstack/salt/issues/62587)
- Correctly reraise exceptions in states.http [#62595](https://github.com/saltstack/salt/issues/62595)
- Fixed syndic eauth. Now jobs will be published when a valid eauth user is targeting allowed minions/functions. [#62618](https://github.com/saltstack/salt/issues/62618)
- updated rest_cherry/app to properly detect arg sent as a string as curl will do when only one arg is supplied. [#62624](https://github.com/saltstack/salt/issues/62624)
- Prevent possible tracebacks in core grains module by ignoring non utf8 characters in /proc/1/environ, /proc/1/cmdline, /proc/cmdline [#62633](https://github.com/saltstack/salt/issues/62633)
- Fixed vault ext pillar return data for KV v2 [#62651](https://github.com/saltstack/salt/issues/62651)
- Fix saltcheck _get_top_states doesn't pass saltenv to state.show_top [#62654](https://github.com/saltstack/salt/issues/62654)
- Fix groupadd.* functions hard code relative command name [#62657](https://github.com/saltstack/salt/issues/62657)
- Fixed pdbedit.create trying to use a bytes-like hash as string. [#62670](https://github.com/saltstack/salt/issues/62670)
- Fix depenency on legacy boto module in boto3 modules [#62672](https://github.com/saltstack/salt/issues/62672)
- Modified "_get_flags" function so that it returns regex flags instead of integers [#62676](https://github.com/saltstack/salt/issues/62676)
- Change startup ReqServer log messages from error to info level. [#62728](https://github.com/saltstack/salt/issues/62728)
- Fix kmod.* functions hard code relative command name [#62772](https://github.com/saltstack/salt/issues/62772)
- Fix mac_brew_pkg to work with null taps [#62793](https://github.com/saltstack/salt/issues/62793)
- Fixing a bug when listing the running schedule if "schedule.enable" and/or "schedule.disable" has been run, where the "enabled" items is being treated as a schedule item. [#62795](https://github.com/saltstack/salt/issues/62795)
- Prevent annoying RuntimeWarning message about line buffering (buffering=1) not being supported in binary mode [#62817](https://github.com/saltstack/salt/issues/62817)
- Include UID and GID checks in modules.file.check_perms as well as comparing
  ownership by username and group name. [#62818](https://github.com/saltstack/salt/issues/62818)
- Fix presence events on TCP transport by removing a client's presence when minion disconnects from publish channel correctly [#62826](https://github.com/saltstack/salt/issues/62826)
- Remove Azure deprecation messages from functions that always run w/ salt-cloud [#62845](https://github.com/saltstack/salt/issues/62845)
- Use select instead of iterating over entrypoints as a dictionary for importlib_metadata>=5.0.0 [#62854](https://github.com/saltstack/salt/issues/62854)
- Fixed master job scheduler using when [#62858](https://github.com/saltstack/salt/issues/62858)
- LGPO: Added support for missing domain controller policies: VulnerableChannelAllowList and LdapEnforceChannelBinding [#62873](https://github.com/saltstack/salt/issues/62873)
- Fix unnecessarily complex gce metadata grains code to use googles metadata service more effectively. [#62878](https://github.com/saltstack/salt/issues/62878)
- Fixed dockermod version_info function for docker-py 6.0.0+ [#62882](https://github.com/saltstack/salt/issues/62882)
- Moving setting the LOAD_BALANCING_POLICY_MAP dictionary into the try except block that determines if the cassandra_cql module should be made available. [#62886](https://github.com/saltstack/salt/issues/62886)
- Updating various MongoDB module functions to work with latest version of pymongo. [#62900](https://github.com/saltstack/salt/issues/62900)
- Restored channel for Syndic minions to send job returns to the Salt master. [#62933](https://github.com/saltstack/salt/issues/62933)
- removed _resolve_deps as it required a library that is not generally avalible. and switched to apt-get for everything as that can auto resolve dependencies. [#62934](https://github.com/saltstack/salt/issues/62934)
- Updated pyzmq to version 22.0.3 on Windows builds because the old version was causing salt-minion/salt-call to hang [#62937](https://github.com/saltstack/salt/issues/62937)
- Allow root user to modify crontab lines for non-root users (except AIX and Solaris). Align crontab line changes with the file ones and also with listing crontab. [#62940](https://github.com/saltstack/salt/issues/62940)
- Fix systemd_service.* functions hard code relative command name [#62942](https://github.com/saltstack/salt/issues/62942)
- Fix file.symlink backupname operation can copy remote contents to local disk [#62953](https://github.com/saltstack/salt/issues/62953)
- Issue #62968: Fix issue where cloud deployments were putting the keys in the wrong location on Windows hosts [#62968](https://github.com/saltstack/salt/issues/62968)
- Fixed gpg_passphrase issue with gpg decrypt/encrypt functions [#62977](https://github.com/saltstack/salt/issues/62977)
- Fix file.tidied FileNotFoundError [#62986](https://github.com/saltstack/salt/issues/62986)
- Fixed bug where module.wait states were detected as running legacy module.run syntax [#62988](https://github.com/saltstack/salt/issues/62988)
- Fixed issue with win_wua module where it wouldn't load if the CryptSvc was set to Manual start [#62993](https://github.com/saltstack/salt/issues/62993)
- The `__opts__` dunder dictionary is now added to the loader's `pack` if not
  already present, which makes it accessible via the
  `salt.loader.context.NamedLoaderContext` class. [#63013](https://github.com/saltstack/salt/issues/63013)
- Issue #63024: Fix issue where grains and config data were being place in the wrong location on Windows hosts [#63024](https://github.com/saltstack/salt/issues/63024)
- Fix btrfs.subvolume_snapshot command failing [#63025](https://github.com/saltstack/salt/issues/63025)
- Fix file.retention_schedule always reports changes [#63033](https://github.com/saltstack/salt/issues/63033)
- Fix mongo authentication for mongo ext_pillar and mongo returner

  This fix also include the ability to use the mongo connection string for mongo ext_pillar [#63058](https://github.com/saltstack/salt/issues/63058)
- Fixed x509.create_csr creates invalid CSR by default in the new cryptography x509 module. [#63103](https://github.com/saltstack/salt/issues/63103)
- TCP transport documentation now contains proper master/minion-side filtering information [#63120](https://github.com/saltstack/salt/issues/63120)
- Fixed gpg.verify does not respect gnupghome [#63145](https://github.com/saltstack/salt/issues/63145)
- Made pillar cache pass extra minion data as well [#63208](https://github.com/saltstack/salt/issues/63208)
- Fix serious performance issues with the file.tidied module [#63231](https://github.com/saltstack/salt/issues/63231)
- Import StrictVersion and LooseVersion from setuptools.distutils.verison or setuptools._distutils.version, if first not available [#63350](https://github.com/saltstack/salt/issues/63350)
- When the shell is passed as powershell or pwsh, only wrapper the shell in quotes if cmd.run is running on Windows.  When quoted on Linux hosts, this results in an error when the keyword arguments are appended. [#63590](https://github.com/saltstack/salt/issues/63590)
- LGPO: Added support for "Relax minimum password length limits" [#63596](https://github.com/saltstack/salt/issues/63596)
- Check file is not empty before attempting to read pillar disk cache file [#63729](https://github.com/saltstack/salt/issues/63729)


### Added

- Introduce a `LIB_STATE_DIR` syspaths variable which defaults to `CONFIG_DIR`,
  but can be individually customized during installation by specifying
  `--salt-lib-state-dir` during installation. Change the default `pki_dir` to
  `<LIB_STATE_DIR>/pki/master` (for the master) and `<LIB_STATE_DIR>/pki/minion`
  (for the minion). [#3396](https://github.com/saltstack/salt/issues/3396)
- Allow users to enable 'queue=True' for all state runs via config file [#31468](https://github.com/saltstack/salt/issues/31468)
- Added pillar templating to vault policies [#43287](https://github.com/saltstack/salt/issues/43287)
- Add support for NVMeF as a transport protocol for hosts in a Pure Storage FlashArray [#51088](https://github.com/saltstack/salt/issues/51088)
- A new salt-ssh roster that generates a roster by parses a known_hosts file. [#54679](https://github.com/saltstack/salt/issues/54679)
- Added Windows Event Viewer support [#54713](https://github.com/saltstack/salt/issues/54713)
- Added the win_lgpo_reg state and execution modules which will allow registry based group policy to be set directly in the Registry.pol file [#56013](https://github.com/saltstack/salt/issues/56013)
- Added resource tagging functions to boto_dynamodb execution module [#57500](https://github.com/saltstack/salt/issues/57500)
- Added `openvswitch_db` state module and functions `bridge_to_parent`,
  `bridge_to_vlan`, `db_get`, and `db_set` to the `openvswitch` execution module.
  Also added optional `parent` and `vlan` parameters to the
  `openvswitch_bridge.present` state module function and the
  `openvswitch.bridge_create` execution module function. [#58986](https://github.com/saltstack/salt/issues/58986)
- State module to manage SysFS attributes [#60154](https://github.com/saltstack/salt/issues/60154)
- Added ability for `salt.wait_for_event` to handle `event_id`s that have a list value. [#60430](https://github.com/saltstack/salt/issues/60430)
- Added suport for Linux ppc64le core grains (cpu_model, virtual, productname, manufacturer, serialnumber) and arm core grains (serialnumber, productname) [#60518](https://github.com/saltstack/salt/issues/60518)
- Added autostart option to virt.defined and virt.running states, along with virt.update execution modules. [#60700](https://github.com/saltstack/salt/issues/60700)
- Added .0 back to our versioning scheme for future versions (e.g. 3006.0) [#60722](https://github.com/saltstack/salt/issues/60722)
- Initial work to allow parallel startup of proxy minions when used as sub proxies with Deltaproxy. [#61153](https://github.com/saltstack/salt/issues/61153)
- Added node label support for GCE [#61245](https://github.com/saltstack/salt/issues/61245)
- Support the --priority flag when adding sources to Chocolatey. [#61319](https://github.com/saltstack/salt/issues/61319)
- Add namespace option to ext_pillar.http_json [#61335](https://github.com/saltstack/salt/issues/61335)
- Added a filter function to ps module to get a list of processes on a minion according to their state. [#61420](https://github.com/saltstack/salt/issues/61420)
- Add postgres.timeout option to postgres module for limiting postgres query times [#61433](https://github.com/saltstack/salt/issues/61433)
- Added new optional vault option, ``config_location``. This can be either ``master`` or ``local`` and defines where vault will look for connection details, either requesting them from the master or using the local config. [#61857](https://github.com/saltstack/salt/issues/61857)
- Add ipwrap() jinja filter to wrap IPv6 addresses with brackets. [#61931](https://github.com/saltstack/salt/issues/61931)
- 'tcp' transport is now available in ipv6-only network [#62009](https://github.com/saltstack/salt/issues/62009)
- Add `diff_attr` parameter to pkg.upgrade() (zypper/yum). [#62031](https://github.com/saltstack/salt/issues/62031)
- Config option pass_variable_prefix allows to distinguish variables that contain paths to pass secrets.
  Config option pass_strict_fetch allows to error out when a secret cannot be fetched from pass.
  Config option pass_dir allows setting the PASSWORD_STORE_DIR env for pass.
  Config option pass_gnupghome allows setting the $GNUPGHOME env for pass. [#62120](https://github.com/saltstack/salt/issues/62120)
- Add file.pruned state and expanded file.rmdir exec module functionality [#62178](https://github.com/saltstack/salt/issues/62178)
- Added "dig.PTR" function to resolve PTR records for IPs, as well as tests and documentation [#62275](https://github.com/saltstack/salt/issues/62275)
- Added the ability to remove a KB using the DISM state/execution modules [#62366](https://github.com/saltstack/salt/issues/62366)
- Add "<tiamat> python" subcommand to allow execution or arbitrary scripts via bundled Python runtime [#62381](https://github.com/saltstack/salt/issues/62381)
- Add ability to provide conditions which convert normal state actions to no-op when true [#62446](https://github.com/saltstack/salt/issues/62446)
- Added debug log messages displaying the command being run when installing packages on Windows [#62480](https://github.com/saltstack/salt/issues/62480)
- Add biosvendor grain [#62496](https://github.com/saltstack/salt/issues/62496)
- Add ifelse Jinja function as found in CFEngine [#62508](https://github.com/saltstack/salt/issues/62508)
- Implementation of Amazon EC2 instance detection and setting `virtual_subtype` grain accordingly including the product if possible to identify. [#62539](https://github.com/saltstack/salt/issues/62539)
- Adds __env__substitution to ext_pillar.stack; followup of #61531, improved exception handling for stacked template (jinja) template rendering and yaml parsing in ext_pillar.stack [#62578](https://github.com/saltstack/salt/issues/62578)
- Increase file.tidied flexibility with regard to age and size [#62678](https://github.com/saltstack/salt/issues/62678)
- Added "connected_devices" feature to netbox pillar module. It contains extra information about devices connected to the minion [#62761](https://github.com/saltstack/salt/issues/62761)
- Add atomic file operation for symlink changes [#62768](https://github.com/saltstack/salt/issues/62768)
- Add password/account locking/unlocking in user.present state on supported operating systems [#62856](https://github.com/saltstack/salt/issues/62856)
- Added onchange configuration for script engine [#62867](https://github.com/saltstack/salt/issues/62867)
- Added output and bare functionality to export_key gpg module function [#62978](https://github.com/saltstack/salt/issues/62978)
- Add keyvalue serializer for environment files [#62983](https://github.com/saltstack/salt/issues/62983)
- Add ability to ignore symlinks in file.tidied [#63042](https://github.com/saltstack/salt/issues/63042)
- salt-cloud support IMDSv2 tokens when using 'use-instance-role-credentials' [#63067](https://github.com/saltstack/salt/issues/63067)
- Add ability for file.symlink to not set ownership on existing links [#63093](https://github.com/saltstack/salt/issues/63093)
- Restore the previous slack engine and deprecate it, rename replace the slack engine to slack_bolt until deprecation [#63095](https://github.com/saltstack/salt/issues/63095)
- Add functions that will return the underlying block device, mount point, and filesystem type for a given path [#63098](https://github.com/saltstack/salt/issues/63098)
- Add ethtool execution and state module functions for pause [#63128](https://github.com/saltstack/salt/issues/63128)
- Add boardname grain [#63131](https://github.com/saltstack/salt/issues/63131)
- Added management of ECDSA/EdDSA private keys with x509 modules in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#63248](https://github.com/saltstack/salt/issues/63248)
- Added x509 modules support for different output formats in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#63249](https://github.com/saltstack/salt/issues/63249)
- Added deprecation_warning test state for ensuring that deprecation warnings are correctly emitted. [#63315](https://github.com/saltstack/salt/issues/63315)
- Adds a state_events option to state.highstate, state.apply, state.sls, state.sls_id.
  This allows users to enable state_events on a per use basis rather than having to
  enable them globally for all state runs. [#63316](https://github.com/saltstack/salt/issues/63316)
- Allow max queue size setting for state runs to prevent performance problems from queue growth [#63356](https://github.com/saltstack/salt/issues/63356)
- Add support of exposing meta_server_grains for Azure VMs [#63606](https://github.com/saltstack/salt/issues/63606)


## Salt v3005.1-2 (2022-11-04)

Note: This release is only impacting the packages not the Salt code base.

### Fixed

- Updated pyzmq to version 22.0.3 on Windows builds because the old version was causing salt-minion/salt-call to hang (#62937)
- Onedir Package Fix: Fix "No such file or directory" error on Rhel installs. (#62948)

### Security

- Update the onedir packages Python version to 3.8.15 for Windows and 3.9.15 for Linux and Mac


## Salt 3005.1 (2022-09-26)

### Fixed

- Fix arch parsing issue in apt source files (#62247)
- Fixed parsing CDROM apt sources (#62474)
- Use str() method instead of repo_line for when python3-apt is installed or not in aptpkg.py. (#62546)
- Remove the connection_timeout from netmiko_connection_args before netmiko_connection_args is added to __context__["netmiko_device"]["args"] which is passed along to the Netmiko library. (#62547)
- fixes #62553 by checking for disabled master_type before starting master connection and skipping it if set. (#62553)
- Fix runas with cmd module when using the onedir bundled packages (#62565)
- Fix the Pyinstaller hooks to preserve the environment if None is passed. (#62567, #62628)
- pkgrepo.managed sets wrong permissions on keys installed to /etc/apt/keyring (#62569)
- pkgrepo.managed creates zero byte gpg files when dearmoring contents to the same filename (#62570)
- Ensure default values for IPC Buffers are correct type (#62591)
- Fix a hang on salt-ssh when using sudo. (#62603)
- Renderers now have access to the correct set of salt functions. (#62610, #62620)
- Fix including Jinja template from absolute path (#62611)
- include jmespath in package requirements (#62613)
- Fix pkgrepo.managed signed-by in test=true mode (#62662)
- Ensure the status of the service is captured when the beacon function is called, even when the event is not being emitted. (#62675)
- The sub proxies controlled by Deltaproxy need to have their own req_channel otherwise there are timeout exceptions when the __master_req_channel_payload is fired and reacted on. (#62708)


## Salt 3005 (2022-08-22)

### Removed

- Deprecating and removing salt-unity. (#56055)
- Removed support for macos mojave (#61130)
- Removed `salt.utils.MultiprocessingProcess` and `salt.utils.SignalHandlingMultiprocessingProcess`. Please use `salt.utils.Process` and `salt.utils.SignalHandlingProcess` instead. (#61573)
- Remove the grains.get_or_set_hash function. Please reference pillar and SDB documentation for secure ways to manage sensitive information. Grains are an insecure way to store secrets. (#61691)
- Removed the `telnet_port`, `serial_type` and `console` parameters in salt/modules/virt.py. Use the `serials` and `consoles` parameters instead. Use the `serials` parameter with a value like ``{{{{'type': 'tcp', 'protocol': 'telnet', 'port': {}}}}}`` instead and a similar `consoles` parameter. (#61693)
- Remove remove_lock in zypperpkg.py in favor of unhold.
  Remove add_lock in zypperpkg.py in favor of hold. (#61694)
- Removed support for old-style Windows Group Policy names
  Recommended policy names will be displayed in comments (#61696)
- Remove the feature flag feature.enable_slsvars_fixes and enable the fixes for `sls_path`, `tpl_file`, and `tpldir` by default.
  Enabling this behavior by default will fix the following:
    - tpldir: If your directory name and your SLS file name are the same tpldir used to return a ., now it returns the correct directory name.
    - slspath,slsdotpath,slscolonpath,sls_path: If an init.sls file is accessed by its explicit name path.to.init instead of path.to, init shows up as a directory for in various sls context parameters, now it will only show as a file.
    - tplfile: When using tplfile in a SLS file in the root directory of file roots it returns empty. Now it returns the filename. (#61697)
- Remove SaltMessageServer.shutdown in favor of close.
  Remove LoadBalancerWorker.stop in favor of close. (#61698)
- Removed the PyObjC dependency.

  This addresses problems with building a one dir build for macOS.
  It became problematic because depending on the macOS version, it pulls different dependencies, and we would either have to build a macos onedir for each macOS supported release, or ship a crippled onedir(because it would be tied to the macOS version where the onedir was built).
  Since it's currently not being used, it's removed. (#62432)


### Deprecated

- In etcd_util, the recursive kwarg in the read and delete methods has been deprecated in favor of recurse for both client versions.
  In etcd_util, the index kwarg in the watch method has been deprecated in favor of start_revision for both client versions.
  In etcd_util, the waitIndex kwarg in the read method has been deprecated in favor of start_revision for both client versions.
  The etcd API v2 implementation has been deprecated in favor of etcd API v3. (#60325)
- Deprecated transport kwarg inside salt.utils.event.get_event (#61275)
- Deprecated netmiko_conn and pyeapi_conn in napalm_mod.py as these function should not be called from the CLI (#61566)
- Deprecate all Azure cloud modules (#62183)
- Deprecated ``defaults`` and ``preserve_context`` for ``salt.utils.functools.namespaced_function``.
  Additionally, the behavior when ``preserve_namespace=True`` was passed is now the default in order not to require duplicating imports on the modules that are namespacing functions. (#62272)
- Deprecated the cassandra module in favor of the cassandra_cql module/returner. (#62327)


### Changed

- alternatives: Do not access /var/lib/dpkg/alternatives directly (#58745)
- Enhance logging when there are errors at loading beacons (#60402)
- Updated mysql cache module to also store updated timestamp, making it consistent with default cache module. Users of mysql cache should ensure database size before updating, as ALTER TABLE will add the timestamp column. (#61081)
- Changed linux_shadow to test success of commands using cmd.retcode instead of cmd.run (#61932)
- `zabbix.user_get` returns full user info with groups and medias
  `zabbix.user_addmedia` returns error for Zabbix 4.0+ due to `user.addmedia` method removal
  `zabbix.user_deletemedia` returns error for Zabbix 4.0+ due to `user.deletemedia` method removal (#62012)
- "Sign before ending the testrun in x509.create_certificate" (#62100)


### Fixed

- Fix salt-ssh using sudo with a password (#8882)
- Fix SSH password regex to not search for content after password:. (#25721)
- Addressing a few issues when having keep_symlinks set to True with file.recurse.  Also allow symlinks that are outside the salt fileserver root to be discoverable as symlinks when fileserver_followsymlinks is set to False. (#29562)
- serialize to JSON only non string objects. (#35215)
- Fix archive.extracted doesn't set user/group ownership correctly (#38605)
- Make sys.argspec work on functions with annotations (#48735)
- Fixed pdbedit.list_users with Samba 4.8 (#49648)
- Fixes a scenario where ipv6 is enabled but the master is configured as an ipv4 IP address. (#49835)
- Ensure that NOTIFY_SOCKET is not passed to child processes created with cmdmod unless it's set explicitly for such call. (#50851)
- remove escaping of dbname in mysql.alter_db function. (#51559)
- Fix runit module failing to find service if it is not symlinked. (#52759)
- Changed manage.versions to report minions offline if minion call fails. (#53513)
- Fixed events stream from /events endpoint not halting when auth token has expired. (#53742)
- Fixed user.present which was breaking when updating workphone,homephone, fullname and "other" fields in case int was passed instead of string (#53961)
- Fix error in webutil state module when attempting to grep a file that does not exist. (#53977)
- Fixed ability to modify the "Audit: Force audit policy subcategory settings..." policy (#54301)
- Fix timeout handling in netapi/saltnado. (#55394)
- Fixing REST auth so that we actually support using ACLs from the REST server like we said in the documentation. (#55654)
- Salt now correctly handles macOS after Py3.8 where python defaults to spawn instead of fork. (#55847)
- Factor out sum and sorting of permissions into separate functions.
  Additionally, the same logic was applied to the rest_cherrypy netapi (#56495)
- Display packages that are marked NoRemove in pkg.list_pkgs for Windows platforms (#56864)
- Attempt to fix 56957 by detecting the broken recusion and stopping it. (#56957)
- Fixed bytes vs. text issue when using sqlite for sdb backend. (#57133)
- Ensure test is added to opts when using the state module with salt-ssh. (#57144)
- Fixed RuntimeError OrderedDict mutated in network.managed for Debian systems. (#57721)
- Improved the multiprocessing classes to better handle spawning platforms (#57742)
- Config options are enforced according to config type (#57873)
- fixed 57992 fix multi item kv v2 items read. (#57992)
- Fixed thread leak during FQDN lookup when DNS entries had malformed PTR records, or other similar issues. (#58141)
- Remove unnecessary dot in template that cause the bridge interface to fail on debian. Fixes #58195 (#58195)
- update salt.module.schedule to check the job_args and job_kwargs for valid formatting. (#58329)
- Allowe use of `roster` in salt.function state when using the SSH client. (#58662)
- Detect new and legacy styles of calling module.run and support them both. (#58763)
- Clean repo uri before checking if it's present, avoiding ghost change. (#58807)
- Fix error "'__opts__' is not defined" when using the boto v2 modules (#58934)
- hgfs: fix bytes vs str issues within hgfs. (#58963)
- Fixes salt-ssh error when targetting IPs or hostnames directly. (#59033)
- Allow for multiple configuration entries with keyword strict_config=False on yum-based systems (#59090)
- Fixed error when running legacy code in winrepo.update_git_repos (#59101)
- Clarify the persist argument in the scheduler module. Adding code in the list function to indicate if the schedule job is saved or not. (#59102)
- Swap ret["retcode"] for ret.get("retcode") in the event that there is no retcode, eg. when a function is not passed with a module. (#59331)
- Fix race condition when caching vault tokens (#59361)
- The ssh module now accepts all ssh public key types as of openssh server version 8.7. (#59429)
- Set default transport and port settings for Napalm NXOS, if not set. (#59448)
- Use __salt_system_encoding__ when retrieving keystore certificate SHA1 str (#59503)
- Fix error being thrown on empty flags list given to file.replace (#59554)
- Update url for ez_setup.py script in virtualenv_mod.py (#59604)
- Changed yumpkg module to normalize versions to strings when they were ambiguously floats (example version=3005.0). (#59705)
- Fix pillar_roots.write on subdirectories broken after CVE-2021-25282 patch. (#59935)
- Improved performance of zfs.filesystem_present and zfs.volume_present.  When
  applying these states, only query specified ZFS properties rather than all
  properties. (#59970)
- Fixed highstate outputter not displaying with salt.function in orchestration when module returns a dictionary. (#60029)
- Update docs where python-dateutil is required for schedule. (#60070)
- Send un-parsed username to LookupAccountName function (#60076)
- Fix ability to set propagation on a folder to "this_folder_only" (#60103)
- Fix name attribute access error in spm. (#60106)
- Fix zeromq stream.send exception message (#60228)
- Exit gracefully on ctrl+c. (#60242)
- Corrected import statement for redis_cache in cluster mode. (#60272)
- loader: Fix loading grains with annotations (#60285)
- fix docker_network.present when com.docker.network.bridge.name is being used as the unixes can not have a bridge of the same name (#60316)
- Fix exception in yumpkg.remove for not installed package on calling pkg.remove or pkg.removed (#60356)
- Batch runs now return proper retcodes in a tuple of the form (result, retcode) (#60361)
- Fixed issue with ansible roster __virtual__ when ansible is not installed. (#60370)
- Fixed error being thrown when None was passed as src/defaults or dest to defaults.update and defaults.merge (#60431)
- Allow for additional options for xmit hash policy in mode 4 NIC bonding on Redhat (#60583)
- Properly detect VMware grains on Windows Server 2019+ (#60593)
- Allow for minion failure to respond to job sent in batch mode (#60724)
- The mac assistive execution module no longer shells out to change the database. (#60819)
- Fix regression in win_timezone.get_zone which failed to resolve specific timezones that begin or end with d/s/t/o/f/_ characters (#60829)
- The TCP transport resets it's unpacker on stream disconnects (#60831)
- Moving the call to the validate function earlier to ensure that beacons are in the right format before we attempt to do anything to the configuration.  Adding a generic validation to ensure the beacon configuration is in the wrong format when a validation function does not exist. (#60838)
- Update the mac installer welcome and conclusion page, add docs for the salt-config tool (#60858)
- Fixed external node classifier not callable due to wrong parameter (#60872)
- Adjust Debian/Ubuntu package use of name 'ifenslave-2.6' to 'ifenslave' (#60876)
- Clear and update the Pillar Cache when running saltutil.refresh_pillar. This only affects users
  that have `pillar_cache` set to True. If you do not want to clear the cache you can pass the kwarg
  `clean_cache=False` to `saltutil.refresh_pillar`. (#60897)
- Handle the situation when apt repo lines have or do not have trailing slashes properly. (#60907)
- Fixed Python 2 syntax for Python 3, allow for view objects returned by dictionary keys() function (#60909)
- Fix REST CherryPY append the default permissions every request (#60955)
- Do not consider "skipped" targets as failed for "ansible.playbooks" states (#60983)
- Fix behavior for internal "_netlink_tool_remote_on" to filter results based on requested end (#61017)
- schedule.job_status module: Convert datetime objects into formatted strings (#61043)
- virt: don't crash if console doesn't have service or type attribute (#61054)
- Fixed conflict between importlib_metada from Salt and importlib.metadata from Python 3.10 (#61062)
- sys.argspec now works with pillar.get, vault.read_secret, and vault.list_secrets (#61084)
- Set virtual grain on FreeBSD EC2 instances (#61094)
- Fixed v3004 windows minion failing to open log file at C:\ProgramData\Salt Project\Salt\var\log\salt\minion (#61113)
- Correct returned result to False when an error exception occurs for pip.installed (#61117)
- fixed extend being too strict and wanting the system_type to exist when it is only needed for requisites. (#61121)
- Fixed bug where deserialization in script engine would throw an error after all output was read. (#61124)
- Adding missing import for salt.utils.beacons into beacons that were updated to use it. (#61135)
- added exception catch to salt.utils.vt.terminal.isalive(). (#61160)
- Re-factor transport to make them more plug-able (#61161)
- Remove max zeromq pinned version due to issues on FreeBSD (#61163)
- Fixing deltaproxy code to handle the situation where the control proxy is configured to control a proxy minion whose pillar data could not be loaded. (#61172)
- Prevent get_tops from performing a Set operation on a List (#61176)
- Make "state.highstate" to acts on concurrent flag.
  Simplify "transactional_update" module to not use SSH wrapper and allow more flexible execution (#61188)
- Fix a failure with salt.utils.vault.make_request when namespace is not defined in the connection. (#61191)
- Fix race condition in `salt.utils.verify.verify_env` and ignore directories starting with dot (#61192)
- LGPO: Search for policies in a case-sensitive manner first, then fall back to non case-sensitive names (#61198)
- Fixed state includes in dynamic environments (#61200)
- Minimize the number of network connections minions to the master (#61247)
- Fix salt-call event.event with pillar or grains (#61252)
- Fixed failing dcs.compile_config where a successful compile errored with `AttributeError: 'list' object has no attribute 'get'`. (#61261)
- Make the salt.utils.win_dacl.get_name() function include the "NT Security" prefix for Virtual Accounts. Virtual Accounts can only be added with the fully qualified name. (#61271)
- Fixed tracebacks and print helpful error message when proxy_return = True but no platform or primary_ip set in NetBox pillar. (#61277)
- Ensure opts is included in pack for minion_mods and config loads opts from the named_context. (#61297)
- Added prefix length info for IPv6 addresses in Windows (#61316)
- Handle MariaDB 10.5+ SLAVE MONITOR grant (#61331)
- Fix secondary ip addresses being added to ip4_interfaces and ip6_interfaces at the same time (#61370)
- Do not block the deltaproxy startup.  Wrap the call to the individual proxy initialization functions in a try...except, catching the exception, logging an error and moving onto the next proxy minion. (#61377)
- show_instance of hetzner cloud provider should enforce an action like the other ones (#61392)
- Fix Hetzner Cloud config loading mechanism (#61399)
- Sets correctly the lvm grain even when lvm's command execution outputs a WARNING (#61412)
- Use net instead of sc in salt cloud when restarting the salt service (#61413)
- Fix use_etag support in fileclient by removing case sensitivity of expected header (#61440)
- Expand environment variables in the root_dir registry key (#61445)
- Use salt.utils.path.readlink everywhere instead of os.readlink (#61458)
- Fix state_aggregate minion option not respected (#61478)
- Fixed wua.installed and wua.uptodate to return all changes, failures, and supersedences (#61479)
- When running with test=True and there are no changes, don't show that there are changes. (#61483)
- Fix issue with certutil when there's a space in the path to the certificate (#61494)
- Fix cmdmod not respecting config for saltenv (#61507)
- Convert Py 2'isms to Python 3, and add tests for set_filesystems on AIX (#61509)
- Fix tracebacks caused by missing block device type and wrong mode used for gzip.open while calling inspector.export (#61530)
- win_wua: Titles no longer limited to 40 characters (#61533)
- Fixed error when using network module on RHEL 8 due to the name of the service changing from "network" to "NetworkManager". (#61538)
- Allow symlink to be created even if source is missing on Windows (#61544)
- Print jinja error context on `UndefinedError`.  Previously `jinja2.exceptions.UndefinedError` resulted in a `SaltRenderError` without source file context, unlike all of the other Jinja exceptions handled in `salt/utils/templates.py`. (#61553)
- Fix uptime on AIX systems when less than 24 hours (#61557)
- Fix issue with state.show_state_usage when a saltenv is not referenced in any topfile (#61614)
- Making the retry state system feature available when parallel is set to True. (#61630)
- modules/aptpkg.SourceEntry: fix parsing lines with arbitrary comments in case HAS_APT=False (#61632)
- Fix file.comment incorrectly reports changes in test mode (#61662)
- Fix improper master caching of file listing in multiple dynamic environments (#61738)
- When configured beacons are empty write an empty beacon configuration file. (#61741)
- Fix file.replace updating mtime with no changes (#61743)
- Fixed etcd_return being out of sync with the underlying etcd_util. (#61756)
- Fixing items, values, and keys functions in the data module. (#61812)
- Ensure that `salt://` URIs never contain backslashes, converting them to forward slashes instead.  A specific situation to handle is caching files on Windows minions, where Jinja relative imports introduce a backslash into the path. (#61829)
- Do not raise a UnicodeDecodeError when pillar cache cannot decode binary data. (#61836)
- Don't rely on ``importlib.metadata``, even on Py3.10, use ``importlib_metadata`` instead. (#61839)
- Fix the reporting of errors for file.directory in test mode (#61846)
- Update Markup and contextfunction imports for jinja versions >=3.1. (#61848)
- Update states.chef for version 16.x and 17.x Chef Infra Client output. (#61891)
- Fixed some whitespace and ``pathlib.Path`` issues when not using the sytem ``aptsources`` package. (#61936)
- fixed error when using backslash literal in file.replace (#61944)
- Fix an issue where under spawning platforms, one could exhaust the available multiprocessing semaphores. (#61945)
- Fix salt-cloud sync_after_install functionality (#61946)
- Ensure that `common_prefix` matching only occurs if a directory name is identified (in the `archive.list` execution module function, which affects the `archive.extracted` state). (#61968)
- When states are running in parallel, ensure that the total run time produced by the highstate outputter takes that into account. (#61999)
- Temporary logging is now shutdown when logging has been configured. (#62005)
- modules/lxd.FilesManager: fix memory leak through pylxd.modules.container.Container.FilesManager (#62006)
- utils/jinja.SaltCacheLoader: fix leaking SaltCacheLoader through atexit.register (#62007)
- Fixed errors on calling `zabbix_user.admin_password_present` state, due to changed error message in Zabbix 6.0
  Fixed `zabbix.host_update` not mapping group ids list to list of dicts in format `[{"groupid": groupid}, ...]`
  Fixed `zabbix.user_update` not mapping usergroup id list to list of dicts in format `[{"usrgrpid": usrgrpid}, ...]` (#62012)
- utils/yamlloader and yamlloader_old: fix leaking DuplicateKeyWarning through a warnings module (#62021)
- Fix cache checking for Jinja templates (#62042)
- Fixed salt.states.file.managed() for follow_symlinks=True and test=True (#62066)
- Stop trigering the `GLIBC race condition <https://sourceware.org/bugzilla/show_bug.cgi?id=19329>`_ when parallelizing the resolution of the fqnds. (#62071)
- Fix useradd functions hard-coded relative command name (#62087)
- Fix #62092: Catch zmq.error.ZMQError to set HWM for zmq >= 3.

  Run ``git show 0be0941`` for more info. (#62092)
- Allow emitatstartup to work when delay option is setup. (#62095)
- Fix broken relative jinja includes in local mode bug introduced in #62043 (#62117)
- Fix broken file.comment functionality introduced in #62045 (#62121)
- Fixed an incompatibility preventing salt-cloud from deploying VMs on Proxmox VE 7 (#62154)
- Fix sysctl functions hard-coded relative command name (#62164)
- All of Salt's loaders now accept ``loaded_base_name`` as a keyword argument, allowing different namespacing the loaded modules. (#62186)
- Only functions defined on the modules being loaded will be added to the lazy loader, functions imported from other modules, unless they are properly namespaced, are not included. (#62190)
- Fixes issue in postgresql privileges detection: privileges on views were never retrieved and always recreated. (#57690)
- Fix service.enabled error for unavailable service in test mode (#62258)
- Fix variable reuse causing requisite_in problems (#62264)
- Adding -G option to pkgdd cmd_prefix list when current_zone_only is True. (#62206)
- Don't expect ``lsof`` to be installed when trying check which minions are connected. (#62303)
- Added a pyinstaller hook that traverses the python used on the tiamat package to add all possible modules as hidden imports. (#62362)
- Fix use of random shuffle and sample functions as Jinja filters (#62372)
- All of the requirements provided in the requirements files are now included. The job of evaluating platform markers is not Salt's it's pip's. (#62392)
- Update all platforms to use pycparser 2.21 or greater for Py 3.9 or higher, fixes fips fault with openssl v3.x (#62400)
- Due to changes in the Netmiko library for the exception paths, need to check the version of Netmiko python library and then import the exceptions from different locations depending on the result. (#62405)
- Fixed urlparse typo in rpmbuild_pkgbuild.py (#62442)
- Fixing changes dict in pkg state to be consistent when installing and test=True. (#60995)
- Use fire_event_async when expecting a coroutine (#62453)
- Fixes import error under windows. (#62459)
- account for revision number in formulas to account for difference between bottle and formula (#62466)
- Fixed stacktrace on Windows when running pkg.list_pkgs (#62479)
- Update sanitizing masking for Salt SSH to include additional password like strings. (#62483)
- Fixes an issue where the minion could not connect to a master after 2 failed attempts (#62489)


Added
-----

- Added ability to request VPC peering connections in different AWS regions (boto_vpc). (#50394)
- Added event return capability to Splunk returner (#50815)
- Added allow downgrades support to apt upgrade (#52977)
- added new grain for metadata to handle googles metadata differences (#53223)
- Added win_shortcut execution and state module that does not prepend the current working directory to paths. Use shortcut.create and shortcut.present instead of file.shortcut. (#53706)
- Add __env__ substitution inside file and pillar root paths (#55747)
- Added support cpu hot add/remove, memory hot add, and nested virtualization to VMware salt-cloud driver. (#56144)
- Add a consul state module with acl_present and acl_absent functions. (#58101)
- Added restconf module/states/proxy code for network device automation (#59006)
- Adds the ability to get version information from a file on Windows systems (#59702)
- Add aptkey=False kwarg option to the aptpkg.py module and pkgrepo state. Apt-key is on the path to be deprecated. This will allow users to not use apt-key to manage the repo keys. It will set aptkey=False automatically if it does not detect apt-key exists on the machine. (#59785)
- Added "Instant Clone" feature in the existing VMware Cloud module (#60004)
- Added support for etcd API v3 (#60325)
- Added `pkg.held` and `pkg.unheld` state functions for Zypper, YUM/DNF and APT. Improved `zypperpkg.hold` and `zypperpkg.unhold` functions. (#60432)
- Added suse_ip module allowing to manage network interfaces on SUSE based Linux systems (#60702)
- Support querying for JSON data in SQL external pillar (#60905)
- Added support for yum and dnf on AIX (#60912)
- Added percent success/failure of state runs in highstate summary output via new state_output_pct option (#60990)
- Add support for retrieve IP-address from qemu agent by Salt-cloud on Proxmox (#61146)
- Added new shortcut execution and state module to better handle UNC shortcuts and to test more thoroughly (#61170)
- added yamllint utils module and yaml execution modules (#61182)
- Add "--no-return-event" option to salt-call to prevent sending return event back to master. (#61188)
- Add Etag support for file.managed web sources (#61270)
- Adding the ability to add, delete, purge, and modify Salt scheduler jobs when the Salt minion is not running. (#61324)
- Added a force option to file.symlink to overwrite an existing symlink with the same name (#61326)
- `gpg_decrypt_must_succeed` config to prevent gpg renderer from failing silently (#61418)
- Do not load a private copy of `__grains__` and `__salt__` for the sentry log handler if it is disabled. (#61484)
- Add Jinja filters for itertools functions, flatten, and a state template workflow (#61502)
- Add feature to allow roll-up of duplicate IDs with different names in highstate output (#61549)
- Allow cp functions to derive saltenv from config if not explicitly set (#61562)
- Multiprocessing logging no longer uses multiprocessing queues which penalized performance.

  Instead, each new process configures the terminal and file logging, and also any external logging handlers configured. (#61629)
- Add a function to the freezer module for comparison of packages and repos in two frozen states (#61682)
- Add grains_refresh_pre_exec option to allow grains to be refreshed before any operation (#61708)
- Add possibility to pass extra parameters to salt-ssh pre flight script with `ssh_pre_flight_args` (#61715)
- Add Etag support for archive.extracted web sources (#61763)
- Add regex exclusions, full path matching, symlink following, and mtime/ctime comparison to file.tidied (#61823)
- Add better handling for unit abbreviations and large values to salt.utils.stringutils.human_to_bytes (#61831)
- Provide PyInstaller hooks that provide some runtime adjustments when Salt is running from a Tiamat(PyInstaller) bundled package. (#61864)
- Add configurable tiamat pip pypath location (#61937)
- Add CNAME record support to the dig exec module (#61991)
- Added support for changed user object in Zabbix 5.4+
  Added compatibility with Zabbix 4.0+ for `zabbix.user_getmedia` method
  Added support for setting medias in `zabbix.user_update` for Zabbix 3.4+ (#62012)
- Add ignore_missing parameter to file.comment state (#62044)
- General improvements on the "ansiblegate" module:
  * Add "ansible.targets" method to gather Ansible inventory
  * Add "ansible.discover_playbooks" method to help collecting playbooks
  * Fix crash when running Ansible playbooks if ansible-playbook CLI output is not the expected JSON.
  * Fix issues when processing inventory and there are groups with no members.
  * Allow new types of targets for Ansible roster (#60056)
- Add sample and shuffle functions from random (#62225)
- Add "<tiamat> python" subcommand to allow execution or arbitrary scripts via bundled Python runtime (#62381)


## Salt 3004.2 (2022-05-12)

### Fixed

- Expand environment variables in the root_dir registry key (#61445)
- Update Markup and contextfunction imports for jinja versions >=3.1. (#61848)
- Fix bug in tcp transport (#61865)
- Make sure the correct key is being used when verifying or validating communication, eg. when a Salt syndic is involved use syndic_master.pub and when a Salt minion is involved use minion_master.pub. (#61868)


### Security

- Fixed PAM auth to reject auth attempt if user account is locked. (cve-2022-22967)


## Salt 3004.1 (2022-02-16)

### Security

- Sign authentication replies to prevent MiTM (cve-2022-22935)
- Prevent job and fileserver replays (cve-2022-22936)
- Sign pillar data to prevent MiTM attacks. (cve-2202-22934)
- Fixed targeting bug, especially visible when using syndic and user auth. (CVE-2022-22941) (#60413)
- Fix denial of service in junos ifconfig output parsing.


## Salt 3004 (2021-10-11)

### Removed

- Removed the deprecated glance state and execution module in favor of the glance_image
  state module and the glanceng execution module. (#59079)
- Removed support for Ubuntu 16.04 (#59869)
- Removed the deprecated support for ``gid_from_name`` from the ``user`` state module (#60565)
- Removed deprecated virt.migrate_non_shared, virt.migrate_non_shared_inc, ssh from virt.migrate, and python2/python3 args from salt.utils.thin.gen_min and .gen_thin (#60893)


### Deprecated

- The _ext_nodes alias to the master_tops function was added back in 3004 to maintain backwards compatibility with older supported versions. This alias will now be removed in 3006. This change will break Master and Minion communication compatibility with Salt minions running versions 3003 and lower. (#60980)
- utils/boto3_elasticsearch is no longer needed (#59882)
- Changed "manufacture" grain to "manufacturer" for Solaris on SPARC to unify the name across all platforms. The old "manufacture" grain is now deprecated and will be removed in Sulfur (#60511)
- Deprecate `salt.payload.Serial` (#60953)


### Changed

- Changed nginx.version to return version without `nginx/` prefix. (#57111)
- Updated Slack webhook returner to support event returns on salt-master (#57182)
- Parsing Epoch out of version during pkg remove, since yum can't handle that in all of the cases. (#57881)
- Add extra onfail req check in the state engine to allow onfail to be used with onchanges and other reqs in the same state (#59026)
- Changed the default character set used by `utils.pycrypto.secure_password()` to include symbols and implemented arguments to control the used character set. (#59486)


### Fixed

- Set default 'bootstrap_delay' to 0 (#61005)
- Fixed issue where multiple args to netapi were not preserved (#59182)
- Handle all repo formats in the aptpkg module. (#60971)
- Do not break master_tops for minion with version lower to 3003
  This is going to be removed in Salt 3006 (Sulfur) (#60980)
- Reverting changes in PR #60150. Updating installed and removed functions to return changes when test=True. (#60995)
- Handle signals and properly exit, instead of raising exceptions. (#60391, #60963)
- Redirect imports of ``salt.ext.six`` to ``six`` (#60966)
- Surface strerror to user state instead of returning false (#20789)
- Fixing _get_envs() to preserve the order of pillar_roots. _get_envs() returned pillar_roots in a non-deterministic order. (#24501)
- Fixes salt-cloud `KeyError` that occurs when there exists any subnets with no tags when profiles use `subnetname` (#44330)
- Fixes postgres_local_cache by removing duplicate unicode encoding. (#46942)
- Fixing the state aggregation system to properly handle requisities.
  Fixing pkg state to exclude packages from aggregation if the hold attribute is in the state. (#47628)
- fix issue that allows case sensitive files to be carried through (#47969)
- Allow GCE Salt Cloud to use previously created IP Addresses. (#48947)
- Fixing rabbitmq.list_user_permissions to ensure we are returning a permission list with three elements even when some values are empty. (#49115)
- Periodically restart the fileserver update process to avoid leaks (#50313)
- Fix default value to dictionary for mine_function (#50695)
- Allow user.present to work on Alpine Linux by fixing linux_shadow.info (#50979)
- Ensure that zypper is called with only one --no-refresh parameter (#51382)
- Fixed fileclient cachedir path switching from master to minion due to incorrect MasterMinion configuration (#52288)
- Fixed the container detection inside virtual machines (#53868)
- Fix invalid dnf command when obsoletes=True in pkg.update function (#54224)
- Jinja renderer resolves wrong relative paths when importing subdirectories (#55159)
- Fixed bug #55262 where `salt.modules.iptables` would call `cmd.run` and receive and interpret interspersed `stdout` and `stderr` output from subprocesses. (#55262)
- Updated pcs support to handle auth and setup for new syntax supporting version 0.10 (#56924)
- Reinstate ignore_cidr option in salt-cloud openstack driver (#57127)
- Fix for network.wolmatch runner displaying 'invalid arguments' error with valid arguments (#57473)
- Fixed bug 57490, which prevented package installation for Open Euler and Issabel PBX. Both Open Euler and Issabel PBX use Yum for package management, added them to yumpkg.py. (#57490)
- Better handling of bad RSA public keys from minions (#57733)
- Fixing various functions in the file state module that use user.info to get group information, certain hosts particularly proxy minions do not have the user.info function available. (#57786)
- Do not monkey patch yaml loaders: Prevent breaking Ansible filter modules (#57995)
- Fix --subset command line option, and support old 'sub' parameter name in cmd_subset for backwards compatibility (#58600)
- When calling salt.utils.http.query with a HEAD method to check for the existence of a source ensure that decode_body is False, so the file is not downloaded into memory when we don't need the contents. (#58881)
- Update the runas user on freebsd for postgres versions >9.5, since freebsd will be removing the package on 2021-05-13. (#58915)
- Fix pip module linked requirements file parsing (#58944)
- Fix incorrect hostname quoting in /etc/sysconfig/networking on Red Hat family OS. (#58956)
- Fix Xen DomU virt detection in grains for long running machines. (#59001)
- add encoding when windows encoding is not defaulting to utf8 (#59063)
- Fix "aptpkg.normalize_name" in case the arch is "all" for DEB packages (#59269)
- Astra Linux now considered a Debian family distro (#59332)
- Reworking the mysql module and state so that passwordless does not try to use unix_socket until unix_socket is set to True. (#59337)
- Fixed the zabbix module to read the connection data from pillar. (#59338)
- Fix crash on "yumpkg" execution module when unexpected output at listing patches (#59354)
- Remove return that had left over py2 code from win_path.py (#59396)
- Don't create spicevmc channel for Xen virtual machines (#59416)
- Fix win_servermanager.install so it will reboot when restart=True is passed (#59424)
- Clear the cached network interface grains during minion init and grains refresh (#59490)
- Normalized grain output for LXC containers (#59573)
- Fix typo in 'salt/states/cmd.py' to use "comment" instead of "commnd". (#59581)
- add aliyun linux support and set alinux as redhat family (#59686)
- Don't fail updating network without netmask ip attribute (#59692)
- Fixed using reserved keyword 'set' as function argument in modules/ipset.py (#59714)
- Return empty changes when nothing has been done in virt.defined and virt.running states (#59739)
- Import salt.utils.azurearm instead of using __utils__ from loader in azure cloud.  This fixes an issue where __utils__ would become unavailable when we are using the ThreadPool in azurearm. (#59744)
- Fix an issue with the LGPO module when the gpt.ini file contains unix style line
  endings (/n). This was happening on a Windows Server 2019 instance created in
  Google Cloud Platform (GCP). (#59769)
- The ``ansiblegate`` module now correctly passes keyword arguments to Ansible module calls (#59792)
- Make sure cmdmod._log_cmd handles tuples properly (#59793)
- Updating the add, delete, modify, enable_job, and disable_job functions to return appropriate changes. (#59844)
- Apply pre-commit changes to entire codebase. (#59847)
- Fix Hetzner cloud driver does not recognize machines when rolling out a map (#59864)
- Update Windows build deps & DLLs, Use Python 3.8, libsodium.dll 1.0.18, OpenSSL dlls to 1.1.1k (#59865)
- Salt api verifies proper log file path when providing '--log-file' from the cli (#59880)
- Detect Mendel Linux as Debian (#59892)
- Fixed compilation of requisite_ins by also checking state type along with name/id (#59922)
- Fix xen._get_vm() to not break silently when a VM and a template on XenServer have the same name. (#59932)
- Added missing space for nftables.build_rule when using saddr or daddr. (#59958)
- Add back support to load old entrypoints by iterating instead of type checking (#59961)
- Fixed interrupting salt-call in a pdb session. (#59966)
- Validate we can import map files in states (#60003)
- Update alter_db to return True or False depending on the success of failure of the alter.  Update grant_exists to only use the full list of available privileges when the grant is on the global level, eg. datbase is "*.*". (#60031)
- Fixed firewalld.list_zones when any "rich rules" is set (#60033)
- IPCMessageSubscriber objects expose their connect method as a corotine so they
  can be wrapped by SyncWrapper. (#60049)
- Allow for Napalm dependency netmiko_mod to load correctly when used by Napalm with Cisco IOS (#60061)
- Ensure proper access to the created temporary file when ``runas`` is passed to ``cmd.exec_code_all`` (#60072)
- Fixed an IndexError in pkgng.latest_version when querying an unknown package. (#60105)
- Fixed pkgng.latest_version when querying by origin (e.g. "shells/bash"). (#60108)
- Gracefuly handle errors in virt.vm_info (#60132)
- The LGPO Module now uses "Success and Failure" for normal audit settings and advanced audit settings (#60142)
- Fixing tests/pytests/unit/utils/scheduler/test_eval.py tests so the sleep happens before the status, so the job is given time before we check it. (#60149)
- Update the external ipaddress to the latest 3.9.5 version which has some security fixes. Updating the compat.p to use the vendored version if the python version is below 3.9.5 and only run the test_ipaddress.py tests if below 3.9.5. (#60168)
- Fixed ValueError exception in state.show_state_usage (#60179)
- Redact the username and password when something goes wrong when using an HTTP source and we raise an exception. (#60203)
- Inject the Ansible functions into Salt's ``ansiblegate`` module which was broken on the 3001 release. (#60207)
- Figure out the available Python version inside containers when executing "dockermod.call" function (#60229)
- Handle IPv6 route types such as anycast, multicast, etc when returned from IPv6 route table queries (#60232)
- Move the commonly used code that converts a list to a dictionary into salt.utils.beacons.  Fixing inotify beacon close function to ensure the configuration is converted from the provided list format into a dictionary. (#60241)
- Set name of engine subprocesses (#60259)
- Properly discover block devices path in virt.running (#60296)
- Avoid exceptions when handling some exception cases. (#60330)
- Fixed faulty error message in npm.installed state. (#60339)
- Port option reinstated for Junos Proxy (accidentally removed) (#60340)
- Now hosts.rm_host can remove entries from /etc/hosts when this file have inline comments. (#60351)
- Fixes issue where the full same name is not used when making rights assignments with group policy (#60357)
- Fixed zabbix_host.present to not overwrite inventory_mode to "manual" every time inventory is updated. (#60382)
- Allowed zabbix_host.present to do partial updates of inventory, also don't erase everything if inventory is missing in state definition. (#60389)
- Fixing the mysql_cache module to handle binary inserting binary data into the database. Initially adding tests. (#60398)
- Fixed host_inventory_get to not throw an exception if host does not exist (#60418)
- Check for /dev/kvm to detect KVM hypervisor. (#60419)
- Fixing file.accumulated handling of dependencies when the state_id is used instead of {function: state_id} format. (#60426)
- Adding the ability for yumpkg.remove to handle package names with widdcards. (#60461)
- Pass emulator path to get guest capabilities from libvirt (#60491)
- virt.get_disks: properly report qemu-img errors (#60512)
- Make all platforms have psutils. This prevents a minion from starting if an instance is all ready running. (#60523)
- Ignore configuration for 'enable_fqdns_grains' for AIX, Solaris and Juniper, assume False (#60529)
- Remove check for TIAMAT_BUILD enforcing USE_STATIC_REQUIREMENTS, this is now controlled by Tiamat v7.10.1 and above (#60559)
- Have the beacon call run through a try...except, catching any errors, logging and firing an event that includes the error.
  Fixing the swapusage beacon to ensure value is a string before we attempt to filter out the %. (#60585)
- Refactor loader into logical sub-modules (#60594)
- Clean up references to ZMQDefaultLoop (#60617)
- change dep warn from Silicon to Phosphorus for the cmd,show,system_info and add_config functions in the nxos module. (#60669)
- Fix bug 60602 where the hetzner cloud provider isn't recognized correctly (#60675)
- Fix the ``pwd.getpwnam`` caching issue on macOS user module (#60676)
- Fixing beacons that can include a value in their configuration that may or may not included a percentage.  We want to handle the situation where the percentage sign is not included and the value is not handled as a string. (#60684)
- Fix RuntimeError in process manager (#60749)
- Ensure all data that is being passed along to LDAP is in an OrderedSet and contains bytes. (#60760)
- Update the AWS API version so VMs spun up by salt-cloud where the VPC has it enabled to assign ipv6 addresses by default, actually get ipv6 addresses assigned by default. (#60804)
- Remove un-needed singletons from tranports (#60851)


Added
-----

- Add windows support for file.patch with patch.exe from git for windows optional packages (#44783)
- Added ability to pass exclude kwarg to salt.state inside orchestrate. (#49130)
- Added `success_stdout` and `success_stderr` arguments to `cmd.run`, to override default return code behavior. (#50597)
- The netbox pillar now been enhanced to add support for querying virtual machines
  (in addition to devices), as well as minion interfaces and associated IP
  addresses. (#51490)
- Add support for transactional systems, like openSUSE MicroOS (#58519)
- Added namespace headers to allow use of namespace from config to communicate with Vault Enterprise namespaces (#58585)
- boto3mod unit tests (#58713)
- New decorators `allow_one_of()` and `require_one_of()` (#58742)
- Added `nosync` switch to disable initial raid synchronization (#59193)
- Expanded the documentation for the netbox pillar. (#59398)
- Rocky Linux has been added to the RedHat os_family. (#59682)
- Add "poudriere -i -j jail_name" option to list jail information for poudriere (#59831)
- Added the grains.uuid on Windows platform (#59888)
- Add a salt.util.platform check to detect the AArch64 64-bit extension of the ARM architecture. (#59915)
- Adding support for Deltaproxy controlled proxy minions into Salt Open. (#60090)
- Added functions to slsutil execution module to test if files exist in the state tree
  Added function to slsutil execution module to search for a file by walking up the state tree (#60159)
- Allow module_refresh to also refresh available beacons, eg. following a Python library being installed and "refresh_modules" being passed as an argument in a state. (#60541)
- Add the `detect_remote_minions` and `remote_minions_port` options to allow the master to detect remote ports for connected minions. This will allow users to detect Heist-Salt minions the master is connected to over port 22 by default. (#60612)
- Add the python rpm-vercmp library in the rpm_lowpkg.py module. (#60814)
- Allow a user to use the aptpkg.py module without installing python-apt. (#60818)


## Salt 3003.5 (2022-07-05)

### Fixed

- Update Markup and contextfunction imports for jinja versions >=3.1. (#61848)
- Fix bug in tcp transport (#61865)
- Make sure the correct key is being used when verifying or validating communication, eg. when a Salt syndic is involved use syndic_master.pub and when a Salt minion is involved use minion_master.pub. (#61868)


### Security

- Fixed PAM auth to reject auth attempt if user account is locked. (cve-2022-22967)


## Salt 3003.4 (2022-02-25)

### Security

- Sign authentication replies to prevent MiTM (cve-2022-22935)
- Prevent job and fileserver replays (cve-2022-22936)
- Sign pillar data to prevent MiTM attacks. (cve-2202-22934)
- Fixed targeting bug, especially visible when using syndic and user auth. (CVE-2022-22941) (#60413)
- Fix denial of service in junos ifconfig output parsing.


## Salt 3003.3 (2021-08-20)

### Fixed

- Fix issue introduced in https://github.com/saltstack/salt/pull/59648 (#60046)


### Security

- Verify the owner of an existing config before trusting it during install. If the owner cannot be verified, back it up and use defaults. (CVE-2021-22004)
- Ensure that sourced file is cached using its hash name (cve-2021-21996)


## Salt 3003.2 (2021-07-29)

### Fixed

- Periodically restart the fileserver update process to avoid leaks (#50313)
- Add ssh_timeout to kwargs in deploy_script (#59901)
- Update the external ipaddress to the latest 3.9.5 version which has some security fixes. Updating the compat.p to use the vendored version if the python version is below 3.9.5 and only run the test_ipaddress.py tests if below 3.9.5. (#60168)
- Use the right crypto library for salt.utils.crypt.reinit_crypto (#60215)
- Stop SSH from hanging if connection is lost. Also added args to customize grace period. (#60216)
- Improve reliability of Terminal class (#60504)
- Ignore configuration for 'enable_fqdns_grains' for AIX, Solaris and Juniper, assume False (#60529)


## Salt 3003.1 (2021-06-08)

### Fixed

- Import salt.utils.azurearm instead of using __utils__ from loader in azure cloud.  This fixes an issue where __utils__ would become unavailable when we are using the ThreadPool in azurearm. (#59744)
- Use contextvars library from site-packages if it is intalled. Fixes salt ssh for targets with python <=3.6 (#59942)

### Fixed

- Fixed race condition in batch logic. Added `listen` option to `LocalClient` to prevent event subscriber from purging cached events during batch iteration. (#56273)
- Fixed dependencies for Amazon Linux 2 on https://repo.saltproject.io since Amazon Linux 2 now provides some of the python libraries in their repos. (#59982)
- IPCMessageSubscriber objects expose their connect method as a coroutine so they can be wrapped by SyncWrapper. (#60049)
- Import salt.utils.azurearm instead of using __utils__ from loader in azure cloud.  This fixes an issue where __utils__ would become unavailable when we are using the ThreadPool in azurearm. (#59744)
- Use contextvars library from site-packages if it is intalled. Fixes salt ssh for targets with python <=3.6 (#59942)
- Add back support to load old entrypoints by iterating instead of type checking (#59961)
- Pass the value of the `__grains__` NamedContext to salt.pillar.get_pillar, instead of the NamedContext object itself. (#59975)
- Fix pillar serialization in jinja templates (#60083)

## Salt 3003 (2021-03-05)

### Removed

- Removed the deprecated glance state and execution module in favor of the glance_image
  state module and the glanceng execution module. (#59079)
- Removing the _ext_nodes deprecation warning and alias to the master_tops function.  This change will break compatibility with a Salt master running versions 2017.7.8 and older and Salt minions running versions 3003 and newer. (#59804)
- removed the arg `managed_private_key` from 'salt.states.x509.certificate_managed' (#59247)
- Drop support for python 3.5 on Windows (#59479)
- Removed support for Ubuntu 16.04 (#59913)


### Deprecated

- Added deprecation warning for grains.get_or_set_hash (#59425)

### Changed

- Change `brew cask --list` to `brew list --cask` (#58381)
- Store git sha in salt/_version.py when installing from a tag so it can be found if needed later. (#59137)
- Changed package manager detection in yumpkg module (#59201)
- Updating the pkg beacon to fire the events when there are upgrades to packages, but also when watched packages are installed or removed. Breaking out the logic for listing pkgs from context into a separate function to aid in testing. Updating tests to ensure context is not used when use_context option to list_pkgs is False. (#59463)


### Fixed

- When instantiating the loader grab values of grains and pillars if
  they are NamedLoaderContext instances. (#59773)
- Fixed installation on Apple Silicon Macs by checking $HOMEBREW_PREFIX for `libcrypto` instead of assuming /usr/local. (#59808)
- Fix incorrect documentation for pillar_source_merging_strategy (#26396)
- Don't iterate through cloud map errors (#34033)
- Suppress noisy warnings when very old pyzmq is used. (#50327)
- Fixed glusterfs version parsing for pre-4.0 (#50707)
- Prevent traceback when trying to list reactors when none are configured. (#53334)
- Fixed zabbix_host.present to accept all Zabbix host properties (#53838)
- Binaries for the salt installer package for OSX are now signed and the installer
  package is notarized (#54513)
- Guard boto3_elasticsearch loading properly (#55848)
- Use a capitalized string version of the value of `NodeState` instead (#56589)
- Adding missing error case to the validation for service beacon. (#56623)
- The GCE cloud driver only works with apache-libcloud>=2.5.0, prior versions have authentication issues (#56862)
- zypperpkg add_lock and remove_lock examples do not work (#56922)
- Compare bytes to bytes so we don't overwrite a correct value (#57212)
- Fixing expand_repo_def in aptpkg module to include the architecture in the line attribute when it is passed in. (#57600)
- When passing arguments pass them as keyword arguments so that we can be sure the right value is going where. (#58006, #58579, #59075)
- Improve module whitelist logic for file backends (#58041)
- Fix behavior for "onlyif/unless" state conditionals when multiple declarations (#58085)
- Ensure data is a valid keyword argument for the event.wait function. (#58182)
- Do not raise "StreamClosedError" traceback on the master logs but only log it (#58301)
- Fixed issue with win_timezone when dst is turned off. This was causing the
  minion not to start
  Use default timezone offset in scheduler when correct timezone cannot be determined (#58379)
- Pop!_OS 20.04 and 20.10 now support using pkg.* / aptpkg.* (#58395)
- Restoring functionality of the textfsm module when using textfsm_path argument (#58499)
- Invalidate file list cache when cache file has a future last modified time (#58529)
- Fix issue with setting permissions in combination with the win_perms_reset
  option (#58541)
- Adds support for Powershell 7. It is specified by passing shell="pwsh". Only
  valid if Powershell 7 is installed on the system. (#58598)
- Fixed the zabbix.host_create call on zabbix_host.present to include the
  optional parameter visible_name. Now working as documented. (#58602)
- Fixed some bugs to allow zabbix_host.present to update a host already
  existent on Zabbix server:

  - Added checks before "pop" the elements "bulk" and "details" from
    hostinterfaces_get's response. Without that, the interface comparison
    didn't works with Zabbix >= 5.0
  - Fixed the "inventory" comparison. It failed when both current and new
    inventory were missing.
  - Rewrite of the update_interfaces routine to really "update" the
    interfaces and not trying to delete and recreate all interfaces,
    which almost always gives errors as interfaces with linked items
    can't be deleted. (#58603)
- Added the "details" mandatory object with the properly default values
  when creating a SNMP hostinterface in Zabbix 5.0 (#58620)
- Fixing an issue preventing running pillar.get against pillar values with integers as pillar keys. (#58714)
- Adding a new option to pass client_flags to MySQL connections, for example passing the option to support multiple statements in queries. (#58718)
- Fixed two performance bugs in the sysctl.present state.  Their impact is
  especially great on FreeBSD machines with large amounts of RAM. (#58732)
- Fixed an issue when pillar files are included in the `top.sls` and then later included in another pillar file. (#58736)
- Left over py2 code was causing windows encoding to misbehave (#58749)
- Return result=None from module.run state to indicate that changes would be made
  Return result=False from module.run state when called with no functions (#58752)
- Fix duplicate IP addresses in fqdn_ip4 and fqdn_ip6 grains (#58799)
- Rename `salt.renderers.toml` to `salt.renderers.tomlmod` which fixes the import error issues as described in #58822
  Do note that, the renderer is still called `toml`. (#58822)
- Fixing unhold in yumpkg. Removing unnecessary code and relying on the code that handles dicts later. Adding tests when pkg.installed is called with hold=False. (#58883)
- Converts the given "grant" to upper case before compare to "ALL".
  This fixes a problem granting "all privileges" to a MySQL user. (#58933)
- Strip trailing "/" from repo.uri when comparing repos in "apktpkg.mod_repo" (#58962)
- When we are checking requisites, run reconcile_procs just on those requisite states not all running states. (#58976)
- Allow the gpg module to use export_key, delete_key and create_key without a passphrase in GnuPG >= 2.1 (#58980)
- Updated the documentation, handling and error messages for what size units are allowed by "size" parameter in lvm.lv_present (#58985)
- Fixing the two failing tests when running on Photon OS. Python 3 installed on Photon OS does not support MD4 hashing, so don't load pdbedit module and skip the test_generate_nt_hash test. Default unmask for files and directories results in them having only user and group permissions so update the test_directory_max_depth test. (#58991)
- Fixes to netmiko module and proxy module to handle situations where the device is unreachable during the initial connection phase. (#59011)
- Correct comment when updating postrges users and groups.
  Errors reported when removing postgres groups.
  Partial group membership changes in postgres groups. (#59034)
- Fixed an error when running svn.latest in test mode and using the trust_failures
  option. (#59069)
- Fixes to storing schedule items in pillar, when refreshing pillar only update the schedule items if something has changed. (#59104)
- Fixed timezone module to work in Slackware Linux (#59130)
- Enforces pywinrm to be version 0.3.0 or higher and upgrade to latest (#59138)
- Fix a race condition in the ldx module which sometimes caused devices not to be created during container creation. (#59145)
- Fix issue where passed smb port was being passed to the smb connection when
  deploying Windows with salt-cloud (#59153)
- Fixed an error when running on CentOS Stream 8. (#59161)
- Fix event publish retry when using TCP transport (#59162)
- Fix docs for `auth_timeout` (#59175)
- virt.update doesn't update the definition if efi=True and a loader is already set (#59188)
- Fixed salt.modules.solaris_shadow failing on bytes-like object is require, not 'str'. (#59191)
- Added support for io2 volumes in ec2 cloud (#59218)
- When checking if the mode had changed in the file state module, only do so if the passed mode is not None. (#59276)
- Fixing _sanitze_comments to use sqlparse instead of re.sub. (#59336)
- Allow use of query parameters in cmd.script source url (#59362)
- Access user from global group if local group fails to find user. (#59412)
- Detect and fix grub.xen path (#59484)
- Stop raising `StopIteration` on generators (#59512)
- Fix minion race conditions handling SIGTERM signal when loading modules (#59524)
- Support new output of systemd systemctl list-unit-files in the following modules systemd_service.get_enabled, systemd_service.get_disabled and systemd_service.get_static (#59526)
- Fix pkg.upgrade with -U arg on FreeBSD, -L flag was deprecated long time. (#59565)
- Fixing the virtual function for the netimiko module to allow it to run outside of a proxy minion. Adding additional tests. (#59635)
- Allow "extra_filerefs" as sanitized kwargs for SSH client.
  Fix regression on "cmd.run" when passing tuples as cmd. (#59664)


Added
-----

- Added "fips_mode" config option to master and minion configs. (#59427)
- Adding the ability to clear and show the pillar cache enabled when pillar_cache is True. (#37080)
- SCRAM-SHA-256 support for PostgreSQL passwords.
  Pass encrypted=scram-sha-256 to the postgres_user.present (or postgres_group.present) state. (#51271)
- The yumpkg module has been updated to support VMWare's Photon OS, which uses tdnf (a C implementation of dnf).  "VMware Photon OS" has been added to the "RedHat" `os_family` map as part of this change. (#51912)
- The pkgrepo state now supports VMware Photon OS. (#52550)
- Added firewallgroups to Vultr Salt Cloud provider (#53677)
- Added arbitrary kwarg support for tojson filter. (#56012)
- Add salt monitor beacon to execute salt execution module functions. (#56461)
- Allow the nameservers to be populated from systemd-resolve. (#57618)
- Adding reactor_niceness to the default minion configuration. (#57701)
- CPU model, topology and NUMA node tuning (#57880)
- Added ``pkg.services_need_restart`` which lists system services that should be restarted after package management operations. (#58261)
- Allow handling special first boot definition on virtual machine (#58589)
- Added vgcreate custom parameters to module call: addtag, alloc, autobackup, metadatatype, zero (#58747)
- Enhance console and serial support in virt module (#58844)
- Salt's versions report `salt --versions-report` now includes all installed salt extensions into its versions report. (#58938)
- Support loading entrypoints by passing a module instead of a function. (#58939)
- Added shadow.gen_password for BSD operating systems. (#59140)
- Add more network and PCI/USB host devices passthrough support to virt module and states (#59143)
- Add interface channels management support to rh_ip module. (#59147)
- Add new minion option return_retry_tries for dynamic return retry tries (#59236)
- Added salt-cloud support for Hetzner Cloud via the ``hcloud`` library of the provider. (#59301)
- "AlmaLinux" has been added to the "RedHat" `os_family` map (#59404)
- Added `blocks` and `attachments` params to the `slack_notify.post_message` function (#59428)
- Added tcp_reconnect_backoff minion config option for specifying reconnection backoff time for TCP transport (#59431)
- Added ``swapusage`` beacon to complement the existing ``memusage`` beacon. (#59460)
- The `salt-run` CLI now accepts `--jid` (#59527)
- Add bytes option for FreeBSD pkg-stats(8) module. (#59540)
- Adding mod_beacon function to pkg, service, and file state modules. This function will act similar to the mod_watch function. This will allow supported functions in those state modules to automatically add associated beacons to monitor for changes to the respective resources in the state file and fire events to the event bus when changes occur. (#59559)
- Add -B flag to FreeBSD pkgng.check() to regenerate the library dependency
  metadata for a package by extracting library requirement information from the
  binary ELF files in the package. (#59569)


## Salt 3002.9 (2022-05-25)

### Fixed

- Fixed an error when running on CentOS Stream 8. (#59161)
- Fix bug in tcp transport (#61865)
- Make sure the correct key is being used when verifying or validating communication, eg. when a Salt syndic is involved use syndic_master.pub and when a Salt minion is involved use minion_master.pub. (#61868)


### Security

- Fixed PAM auth to reject auth attempt if user account is locked. (cve-2022-22967)


## Salt 3002.8 (2022-02-25)

### Security

- Sign authentication replies to prevent MiTM (cve-2020-22935)
- Sign pillar data to prevent MiTM attacks. (cve-2022-22934)
- Prevent job and fileserver replays (cve-2022-22936)
- Fixed targeting bug, especially visible when using syndic and user auth. (CVE-2022-22941) (#60413)



## Salt 3002.7 (2021-08-20)

### Fixed

- Verify the owner of an existing config before trusting it during install. If the owner cannot be verified, back it up and use defaults. (CVE-2021-22004)


### Security

- Fix the CVE-2021-31607 vulnerability
  Additionally, an audit and a tool was put in place, ``bandit``, to address similar issues througout the code base, and prevent them. (CVE-2021-31607)
- Ensure that sourced file is cached using its hash name (cve-2021-21996)


## Salt 3002.6 (2021-03-10)

### Changed

- Store git sha in salt/_version.py when installing from a tag so it can be found if needed later. (#59137)


### Fixed

- Fix argument injection bug in restartcheck.restartcheck. This change hardens
  the fix for CVE-2020-28243. (#200)
- Allow "extra_filerefs" as sanitized kwargs for SSH client.
  Fix regression on "cmd.run" when passing tuples as cmd. (#59664)
- Allow all ssh kwargs as sanitized kwargs for SSH client. (#59748)


## Salt 3002.5 (2021-02-25)

### Fixed

- Tests and fix for CVE-2021-25283


## Salt 3002.4 (2021-02-05)

### Fixed

- Fix runners that broke when patching for CVE-2021-25281
- Fix issue with runners in SSE

## Salt 3002.3 (2021-01-25)

### Fixed

- CVE-2020-28243 - Fix local privilege escalation in the restartcheck module. (CVE-2020-28243)
- CVE-2020-28972 - Ensure authentication to vcenter, vsphere, and esxi server
  validates the SSL/TLS certificate by default. If you want to skip SSL verification
  you can use `verify_ssl: False`. (CVE-2020-28972)
- CVE-2020-35662 - Ensure the asam runner, qingcloud, splunk returner, panos
  proxy, cimc proxy, zenoss module, esxi module, vsphere module, glassfish
  module, bigip module, and keystone module validate SSL by default. If you want
  to skip SSL verification you can use `verify_ssl: False`. (CVE-2020-35662)
- CVE-2021-25281 - Fix salt-api so it honors eauth credentials for the
  wheel_async client. (CVE-2021-25281)
- CVE-2021-25282 - Fix the salt.wheel.pillar_roots.write method so it is not
  vulnerable to directory traversal. (CVE-2021-25282)
- CVE-2021-25283 - Fix the jinja render to protect against server side template
  injection attacks. (CVE-2021-25283)
- CVE-2021-25284 - Fix cmdmod so it will not log credentials to log levels info
  and error. (CVE-2021-25284)
- CVE-2021-3144 - Fix eauth tokens can be used once after expiration. (CVE-2021-3144)
- CVE-2021-3148 - Fix a command injection in the Salt-API when using the Salt-SSH client. (CVE-2021-3148)
- CVE-2021-3197 - Fix ssh client to remove ProxyCommand from arguments provided
  by cli and netapi. (CVE-2021-3197)

## Salt 3002.2 (2020-11-16)

### Fixed
- Fix server core grains issue when running inside a windows container (#59611)
- Change dict check to isinstance instead of type() for key_values in file.keyvalue. (#57758)
- Fail when func_ret is False when using the new module.run syntax. (#57768)
- Fix comparison of certificate values (#58296)
- When using ssh_pre_flight if there is a failure, fail on retcode not stderr. (#58439)
- Fix use of unauthd cached vmware service instance (#58691)
- Removing use of undefined varilable in utils/slack.py. (#58753)
- Restored the ability to specify the amount of extents for a Logical
  Volume as a percentage. (#58759)
- Ensuring that the version check function is run a second time in all the user related functions in case the user being managed is the connection user and the password has been updated. (#58773)
- Allow bytes in gpg renderer (#58794)
- Fix issue where win_wua module fails to load when BITS is set to Manual (#58848)
- Ensure that elasticsearch.index_exists is available before loading the elasticsearch returner. (#58851)
- Log a different object when debugging if we're using disk cache vs memory cache. The disk cache pillar class has the dict object but the cache pillar object which is used with the memory cache does not include a _dict obeject because it is a dict already. (#58861)
- Do not generate grains for every job run on Windows minions. This makes Windows
  conform more to the way posix OSes work today. (#58904)
- Fixes salt-ssh authentication when using tty (#58922)
- Revert LazyLoader finalizer. Removed the weakref.finalizer code. On some occasions, the finalized would run when trying to load a new module, firing a race condition. (#58947)


## Salt 3002.1 (2020-10-26)

### Fixed

- Prevent shell injections in netapi ssh client (cve-2020-16846)
- Prevent creating world readable private keys with the tls execution module. (cve-2020-17490)
- Properly validate eauth credentials and tokens along with their ACLs.
  Prior to this change eauth was not properly validated when calling
  Salt ssh via the salt-api. Any value for 'eauth' or 'token' would allow a user
  to bypass authentication and make calls to Salt ssh. (CVE-2020-25592)

## Salt 3002 (2020-10-19)

### Removed

- removed boto_vpc.describe_route_table please use boto_vpc.describe_route_tables (#58636)
- removed show_ipv4 arg from all functions in from salt.runners.manage (#58638)
- removed kwargs from mandrill.send if you use "async" please use "asynchronous" (#58640)
- removed salt/modules/mac_brew_pkg.__fix_cask_namespace (#58641)
- zfs.mount Passing '-a' as name is deprecated please just pass 'None' (#58642)
- Remove include_localhost kwarg for connected_ids method in salt/utils/minions.py (#58224)
- deprecated opts default argument of none and removed deprecation warnings (#58635)


### Deprecated

- The `ssh` parameter of `virt.migrate` has been deprecated. Use a libvirt URI `target` value instead. Both `virt.migrate_non_shared` and `virt.migrate_non_shared_inc` have been deprecated. Use the `copy_storage` parameter with `virt.migrate` instead. (#57947)


### Changed

- Allow specifying a custom port for Proxmox connection (#50620)
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

### Fixed

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
- - Added the ability for states to return `sub_state_run`s -- results from external state engines (#57993)
- Added salt-cloud support for Linode APIv4 via the ``api_version`` provider configuration parameter. (#58093)
- Added support to manage services in Slackware Linux. (#58206)
- Added list_sources to chocolatey module to have an overview of the repositories present on the minions.
  Added source_added to chocolatey state in order to add repositories to chocolatey. (#58588)
- Adding tests for changes to virtual function for netmiko module. Adding tests for netmiko proxy minion module. (#58609)
- Added features config option for feature flags. Added a feature flag
  `enable_slsvars_fixes` to enable fixes to tpldir, tplfile and sls_path.
  This flag will be deprecated in the Phosphorus release when this functionality
  becomes the default. (#58652)

## Salt 3001.8 (2021-08-20)

Version 3001.8 is a bug fix release for :ref:`3001 <release-3001>`.


### Fixed

- Verify the owner of an existing config before trusting it during install. If the owner cannot be verified, back it up and use defaults. (CVE-2021-22004)


### Security

- Fix the CVE-2021-31607 vulnerability
  Additionally, an audit and a tool was put in place, ``bandit``, to address similar issues througout the code base, and prevent them. (CVE-2021-31607)
- Ensure that sourced file is cached using its hash name (cve-2021-21996)

## Salt 3001.7 (2021-03-10)

### Fixed

- Fix argument injection bug in restartcheck.restartcheck. This change hardens
  the fix for CVE-2020-28243. (#200)
- Allow "extra_filerefs" as sanitized kwargs for SSH client.
  Fix regression on "cmd.run" when passing tuples as cmd. (#59664)
- Allow all ssh kwargs as sanitized kwargs for SSH client. (#59748)

## Salt 3001.6 (2021-02-09)

### Fixed

- Fix runners that broke when patching for CVE-2021-25281
- Fix issue with runners in SSE

## Salt 3001.5

### Fixed

- CVE-2020-28243 - Fix local privilege escalation in the restartcheck module. (CVE-2020-28243)
- CVE-2020-28972 - Ensure authentication to vcenter, vsphere, and esxi server
  validates the SSL/TLS certificate by default. If you want to skip SSL verification
  you can use `verify_ssl: False`. (CVE-2020-28972)
- CVE-2020-35662 - Ensure the asam runner, qingcloud, splunk returner, panos
  proxy, cimc proxy, zenoss module, esxi module, vsphere module, glassfish
  module, bigip module, and keystone module validate SSL by default. If you want
  to skip SSL verification you can use `verify_ssl: False`. (CVE-2020-35662)
- CVE-2021-25281 - Fix salt-api so it honors eauth credentials for the
  wheel_async client. (CVE-2021-25281)
- CVE-2021-25282 - Fix the salt.wheel.pillar_roots.write method so it is not
  vulnerable to directory traversal. (CVE-2021-25282)
- CVE-2021-25283 - Fix the jinja render to protect against server side template
  injection attacks. (CVE-2021-25283)
- CVE-2021-25284 - Fix cmdmod so it will not log credentials to log levels info
  and error. (CVE-2021-25284)
- CVE-2021-3144 - Fix eauth tokens can be used once after expiration. (CVE-2021-3144)
- CVE-2021-3148 - Fix a command injection in the Salt-API when using the Salt-SSH client. (CVE-2021-3148)
- CVE-2021-3197 - Fix ssh client to remove ProxyCommand from arguments provided
  by cli and netapi. (CVE-2021-3197)


## Salt 3001.4

### Fixed

- Fixes salt-ssh authentication when using tty (#58922)

## Salt 3001.3

### Fixed

- Properly validate eauth credentials and tokens along with their ACLs.
  Prior to this change eauth was not properly validated when calling
  Salt ssh via the salt-api. Any value for 'eauth' or 'token' would allow a user
  to bypass authentication and make calls to Salt ssh. (CVE-2020-25592)

## Salt 3001.2

### Fixed

- Prevent shell injections in netapi ssh client (cve-2020-16846)
- Prevent creating world readable private keys with the tls execution module. (cve-2020-17490)

## Salt 3001.1 (2020-07-27)

### Changed

- Change the ``enable_fqdns_grains`` setting to default to ``False`` on Windows
  to address some issues with slowness. (#56296, #57529)
- Handle the UCRT libraries the same way they are handled in the Python 3
  installer (#57594)
- Changes the 'SSDs' grain name to 'ssds' as all grains needs to be
  resolved in lowered case. (#57612)
- Updated requirement to psutil 5.6.7 due to vulnerability in psutil 5.6.6. (#58018)
- Updated requirement to PyYAML 5.3.1 due to vulnerability in PyYAML 5.2.1. (#58019)


### Fixed

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


## Salt 3001 (2020-06-17)

### Removed

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


### Changed

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


### Fixed

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

## Salt 3000.9 (2021-03-10)

### Fixed

- Allow "extra_filerefs" as sanitized kwargs for SSH client.
  Fix regression on "cmd.run" when passing tuples as cmd. (#59664)
- Allow all ssh kwargs as sanitized kwargs for SSH client. (#59748)
- Fix argument injection bug in restartcheck.restartcheck. This change hardens
  the fix for CVE-2020-28243.

## Salt 3000.8 (2021-02-09)

### Fixed

- Fix runners that broke when patching for CVE-2021-25281
- Fix issue with runners in SSE

## Salt 3000.7

### Fixed

- CVE-2020-28243 - Fix local privilege escalation in the restartcheck module. (CVE-2020-28243)
- CVE-2020-28972 - Ensure authentication to vcenter, vsphere, and esxi server
  validates the SSL/TLS certificate by default. If you want to skip SSL verification
  you can use `verify_ssl: False`. (CVE-2020-28972)
- CVE-2020-35662 - Ensure the asam runner, qingcloud, splunk returner, panos
  proxy, cimc proxy, zenoss module, esxi module, vsphere module, glassfish
  module, bigip module, and keystone module validate SSL by default. If you want
  to skip SSL verification you can use `verify_ssl: False`. (CVE-2020-35662)
- CVE-2021-25281 - Fix salt-api so it honors eauth credentials for the
  wheel_async client. (CVE-2021-25281)
- CVE-2021-25282 - Fix the salt.wheel.pillar_roots.write method so it is not
  vulnerable to directory traversal. (CVE-2021-25282)
- CVE-2021-25283 - Fix the jinja render to protect against server side template
  injection attacks. (CVE-2021-25283)
- CVE-2021-25284 - Fix cmdmod so it will not log credentials to log levels info
  and error. (CVE-2021-25284)
- CVE-2021-3144 - Fix eauth tokens can be used once after expiration. (CVE-2021-3144)
- CVE-2021-3148 - Fix a command injection in the Salt-API when using the Salt-SSH client. (CVE-2021-3148)
- CVE-2021-3197 - Fix ssh client to remove ProxyCommand from arguments provided
  by cli and netapi. (CVE-2021-3197)

## Salt 3000.6

### Fixed

- Fixes salt-ssh authentication when using tty (#58922)

## Salt 3000.5

### Fixed

- Properly validate eauth credentials and tokens along with their ACLs.
  Prior to this change eauth was not properly validated when calling
  Salt ssh via the salt-api. Any value for 'eauth' or 'token' would allow a user
  to bypass authentication and make calls to Salt ssh. (CVE-2020-25592)

## Salt 3000.4

### Fixed

- Prevent shell injections in netapi ssh client (cve-2020-16846)
- Prevent creating world readable private keys with the tls execution module. (cve-2020-17490)

## 3000.3

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
## 3000.2

### Fixed
- [#56987](https://github.com/saltstack/salt/pull/56987) - CVE fix


## 3000.1

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

## 3000 - Neon [2020-02-10]

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


- See [old release notes](https://docs.saltproject.io/en/latest/topics/releases/2019.2.1.html)
