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
- [#55569](https://github.com/saltstack/salt/pull/55569) - Deprecate nova cloud driver in favor of the openstack driver.
- [#55609](https://github.com/saltstack/salt/pull/55609) - Remove smartos grains `hypervisor_uuid` and `datacenter` in favor of `mdata:sdc:server_uuid` and `mdata:sdc:datacenter_name`.
- [#55539](https://github.com/saltstack/salt/pull/55539) - Deprecate salt.auth.Authorize class and the any_auth method
- [#55573](https://github.com/saltstack/salt/pull/55573) - Deprecate `quiet` kwarg in cmd.run state module. Please set `output_loglevel` to `quiet` instead.
- [#55641](https://github.com/saltstack/salt/pull/55641) - Deprecate `enviroment` kwarg from heat state and execution module. Please use correct spelling `environment`.
- [#55682](https://github.com/saltstack/salt/pull/55682) - Deprecate `get_known_host` and `recv_known_host` functions from ssh module.
- [#55683](https://github.com/saltstack/salt/pull/55683) - Deprecate `prune_services` in the firewall state module to be False by default. And update `force_masquerade` to be False by default in the firewall execution module.
- [#55722](https://github.com/saltstack/salt/pull/55722) - Deprecate all functions in salt/utils/__init__.py.
- [#55725](https://github.com/saltstack/salt/pull/55725) - Deprecate `gitfs_env_whitelist` and `gitfs_env_blacklist` in favor of `gitfs_saltenv_whitelist` and `gitfs_saltenv_blacklist`.

### Changed

- [#54013](https://github.com/saltstack/salt/pull/54103) - Set `session_id`
  cookie in the rest_tornado backend.
- [SEP 14](https://github.com/saltstack/salt-enhancement-proposals/pull/20) - Changed to numeric versions.
- [SEP 1](https://github.com/saltstack/salt-enhancement-proposals/blob/master/accepted/0001-changelog-format.md), [SEP 14](https://github.com/saltstack/salt-enhancement-proposals/pull/20) - Adopted keepachangelog format.

### Fixed

### Added

- [#54505](https://github.com/saltstack/salt/issues/54505) - Added cluster get_settings, put_settings and flush_synced methods for Elasticsearch module. - [@Oloremo](https://github.com/Oloremo)
- [#53736](https://github.com/saltstack/salt/issues/53736) - Added index get_settings, put_settings methods for Elasticsearch module. - [@Oloremo](https://github.com/Oloremo)
- [#55418](https://github.com/saltstack/salt/pull/55418) - Added clean_parent argument for the archive state. - [@Oloremo](https://github.com/Oloremo)
- [#55593](https://github.com/saltstack/salt/issues/55593) - Added a support for a global proxy to pip module. - [@Oloremo](https://github.com/Oloremo)
- [#55443](https://github.com/saltstack/salt/issues/55443) - Added a skip_files_list_verify argument to archive.extracted state. - [@Oloremo](https://github.com/Oloremo)

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
