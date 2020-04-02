# Changelog
All notable changes to Salt will be documented in this file.

This changelog follows [keepachangelog](https://keepachangelog.com/en/1.0.0/) format, and is intended for human consumption.

This project versioning is _similar_ to [Semantic Versioning](https://semver.org), and is documented in [SEP 14](https://github.com/saltstack/salt-enhancement-proposals/pull/20/files).
Versions are `MAJOR.PATCH`.

### 3000.1

### Removed

### Deprecated

### Changed

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


- See [old release notes](https://docs.saltstack.com/en/latest/topics/releases/2019.2.1.html) 
