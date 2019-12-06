# Changelog
All notable changes to Salt will be documented in this file.

This changelog follows [keepachangelog](https://keepachangelog.com/en/1.0.0/) format, and is intended for human consumption.

This project versioning is *similar* to [Semantic Versioning](https://semver.org), and is documented in [SEP 14](https://github.com/saltstack/salt-enhancement-proposals/pull/20/files).
Versions are `MAJOR.PATCH`.

## Unreleased (Neon)

### Removed

- [#54943](https://github.com/saltstack/salt/pull/54943) - RAET transport method has been removed per the deprecation schedule - [@s0undt3ch](https://github.com/s0undt3ch)

### Deprecated
- [#55552](https://github.com/saltstack/salt/pull/55552) - The config options `hgfs_env_whitelist`, `hgfs_env_blacklist`, `svnfs_env_whitelist`, and `svnfs_env_whitelist` have been deprecated in favor of `hgfs_saltenv_whitelist`, `hgfs_saltenv_blacklist`, `svnfs_saltenv_whitelist`, `svnfs_saltenv_blacklist`.
- [#55545](https://github.com/saltstack/salt/pull/55545) - Deprecate `keyfile` and `key` arguments in nacl utils module. This deprecates the arguments for both the nacl module and runner.
                                                           Please use `sk_file` instead of `keyfile` and `sk` instead of `key`
- [#55545](https://github.com/saltstack/salt/pull/55545) - Deprecate `keyfile` and `key` arguments in nacl utils module. This deprecates the arguments for both the nacl module and runner. Please use `sk_file` instead of `keyfile` and `sk` instead of `key`

- [#55609](https://github.com/saltstack/salt/pull/55609) - Remove smartos grains `hypervisor_uuid` and `datacenter` in favor of `mdata:sdc:server_uuid` and `mdata:sdc:datacenter_name`.
- [#55539](https://github.com/saltstack/salt/pull/55539) - Deprecate salt.auth.Authorize class and the any_auth method


### Changed

- [SEP 14](https://github.com/saltstack/salt-enhancement-proposals/pull/20) - Changed to numeric versions.
- [SEP 1](https://github.com/saltstack/salt-enhancement-proposals/blob/master/accepted/0001-changelog-format.md), [SEP 14](https://github.com/saltstack/salt-enhancement-proposals/pull/20) - Adopted keepachangelog format.

### Fixed

### Added

- [#54917](https://github.com/saltstack/salt/pull/54917) - Added get_settings, put_settings and flush_synced methods for Elasticsearch module. - [@Oloremo](https://github.com/Oloremo)
- [#55418](https://github.com/saltstack/salt/pull/55418) - Added clean_parent argument for the archive state. - [@Oloremo](https://github.com/Oloremo)
- [#55593](https://github.com/saltstack/salt/issues/55593) - Added a support for a global proxy to pip module. - [@Oloremo](https://github.com/Oloremo)

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
