# -*- coding: utf-8 -*-
#
# Copyright 2015 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Import Python Libs
from __future__ import absolute_import
import os
import time
import logging

# Import Salt Libs
import salt.utils.files
import salt.utils.fsutils
import salt.utils.network
from salt.modules.inspectlib.exceptions import (InspectorQueryException, SIException)
from salt.modules.inspectlib import EnvLoader
from salt.modules.inspectlib.entities import (Package, PackageCfgFile, PayloadFile)

log = logging.getLogger(__name__)


class SysInfo(object):
    '''
    System information.
    '''

    def __init__(self, systype):
        if systype.lower() == "solaris":
            raise SIException("Platform {0} not (yet) supported.".format(systype))

    def _grain(self, grain):
        '''
        An alias for grains getter.
        '''
        return __grains__.get(grain, 'N/A')

    def _get_disk_size(self, device):
        '''
        Get a size of a disk.
        '''
        out = __salt__['cmd.run_all']("df {0}".format(device))
        if out['retcode']:
            msg = "Disk size info error: {0}".format(out['stderr'])
            log.error(msg)
            raise SIException(msg)

        devpath, blocks, used, available, used_p, mountpoint = [elm for elm in
                                                                out['stdout'].split(os.linesep)[-1].split(" ") if elm]
        return {
            'device': devpath, 'blocks': blocks, 'used': used,
            'available': available, 'used (%)': used_p, 'mounted': mountpoint,
        }

    def _get_fs(self):
        '''
        Get available file systems and their types.
        '''

        data = dict()
        for dev, dev_data in salt.utils.fsutils._blkid().items():
            dev = self._get_disk_size(dev)
            device = dev.pop('device')
            dev['type'] = dev_data['type']
            data[device] = dev

        return data

    def _get_mounts(self):
        '''
        Get mounted FS on the system.
        '''
        return salt.utils.fsutils._get_mounts()

    def _get_cpu(self):
        '''
        Get available CPU information.
        '''
        # CPU data in grains is OK-ish, but lscpu is still better in this case
        out = __salt__['cmd.run_all']("lscpu")
        salt.utils.fsutils._verify_run(out)
        data = dict()
        for descr, value in [elm.split(":", 1) for elm in out['stdout'].split(os.linesep)]:
            data[descr.strip()] = value.strip()

        return data

    def _get_mem(self):
        '''
        Get memory.
        '''
        out = __salt__['cmd.run_all']("vmstat -s")
        if out['retcode']:
            raise SIException("Memory info error: {0}".format(out['stderr']))

        ret = dict()
        for line in out['stdout'].split(os.linesep):
            line = line.strip()
            if not line:
                continue
            size, descr = line.split(" ", 1)
            if descr.startswith("K "):
                descr = descr[2:]
                size = size + "K"
            ret[descr] = size
        return ret

    def _get_network(self):
        '''
        Get network configuration.
        '''
        data = dict()
        data['interfaces'] = salt.utils.network.interfaces()
        data['subnets'] = salt.utils.network.subnets()

        return data

    def _get_os(self):
        '''
        Get operating system summary
        '''
        return {
            'name': self._grain('os'),
            'family': self._grain('os_family'),
            'arch': self._grain('osarch'),
            'release': self._grain('osrelease'),
        }


class Query(EnvLoader):
    '''
    Query the system.
    This class is actually puts all Salt features together,
    so there would be no need to pick it from various places.
    '''

    # Configuration: config files
    # Identity: users/groups
    # Software: packages, patterns, repositories
    # Services
    # System: distro, RAM etc
    # Changes: all files that are managed and were changed from the original
    # all: include all scopes (scary!)
    # payload: files that are not managed

    SCOPES = ["changes", "configuration", "identity", "system", "software", "services", "payload", "all"]

    def __init__(self, scope, cachedir=None):
        '''
        Constructor.

        :param scope:
        :return:
        '''
        if scope and scope not in self.SCOPES:
            raise InspectorQueryException(
                "Unknown scope: {0}. Must be one of: {1}".format(repr(scope), ", ".join(self.SCOPES))
            )
        elif not scope:
            raise InspectorQueryException(
                "Scope cannot be empty. Must be one of: {0}".format(", ".join(self.SCOPES))
            )
        EnvLoader.__init__(self, cachedir=cachedir)
        self.scope = '_' + scope
        self.local_identity = dict()

    def __call__(self, *args, **kwargs):
        '''
        Call the query with the defined scope.

        :param args:
        :param kwargs:
        :return:
        '''

        return getattr(self, self.scope)(*args, **kwargs)

    def _changes(self, *args, **kwargs):
        '''
        Returns all diffs to the configuration files.
        '''
        raise Exception("Not yet implemented")

    def _configuration(self, *args, **kwargs):
        '''
        Return configuration files.
        '''

        data = dict()
        self.db.open()
        for pkg in self.db.get(Package):
            configs = list()
            for pkg_cfg in self.db.get(PackageCfgFile, eq={'pkgid': pkg.id}):
                configs.append(pkg_cfg.path)
            data[pkg.name] = configs

        if not data:
            raise InspectorQueryException("No inspected configuration yet available.")

        return data

    def _get_local_users(self, disabled=None):
        '''
        Return all known local accounts to the system.
        '''
        users = dict()
        path = '/etc/passwd'
        with salt.utils.files.fopen(path, 'r') as fp_:
            for line in fp_:
                line = line.strip()
                if ':' not in line:
                    continue
                name, password, uid, gid, gecos, directory, shell = line.split(':')
                active = not (password == '*' or password.startswith('!'))
                if (disabled is False and active) or (disabled is True and not active) or disabled is None:
                    users[name] = {
                        'uid': uid,
                        'git': gid,
                        'info': gecos,
                        'home': directory,
                        'shell': shell,
                        'disabled': not active
                    }

        return users

    def _get_local_groups(self):
        '''
        Return all known local groups to the system.
        '''
        groups = dict()
        path = '/etc/group'
        with salt.utils.files.fopen(path, 'r') as fp_:
            for line in fp_:
                line = line.strip()
                if ':' not in line:
                    continue
                name, password, gid, users = line.split(':')
                groups[name] = {
                    'gid': gid,
                }

                if users:
                    groups[name]['users'] = users.split(',')

        return groups

    def _get_external_accounts(self, locals):
        '''
        Return all known accounts, excluding local accounts.
        '''
        users = dict()
        out = __salt__['cmd.run_all']("passwd -S -a")
        if out['retcode']:
            # System does not supports all accounts descriptions, just skipping.
            return users
        status = {'L': 'Locked', 'NP': 'No password', 'P': 'Usable password', 'LK': 'Locked'}
        for data in [elm.strip().split(" ") for elm in out['stdout'].split(os.linesep) if elm.strip()]:
            if len(data) < 2:
                continue
            name, login = data[:2]
            if name not in locals:
                users[name] = {
                    'login': login,
                    'status': status.get(login, 'N/A')
                }

        return users

    def _identity(self, *args, **kwargs):
        '''
        Local users and groups.

        accounts
            Can be either 'local', 'remote' or 'all' (equal to "local,remote").
            Remote accounts cannot be resolved on all systems, but only
            those, which supports 'passwd -S -a'.

        disabled
            True (or False, default) to return only disabled accounts.
        '''
        LOCAL = 'local accounts'
        EXT = 'external accounts'

        data = dict()
        data[LOCAL] = self._get_local_users(disabled=kwargs.get('disabled'))
        data[EXT] = self._get_external_accounts(data[LOCAL].keys()) or 'N/A'
        data['local groups'] = self._get_local_groups()

        return data

    def _system(self, *args, **kwargs):
        '''
        This basically calls grains items and picks out only
        necessary information in a certain structure.

        :param args:
        :param kwargs:
        :return:
        '''
        sysinfo = SysInfo(__grains__.get("kernel"))

        data = dict()
        data['cpu'] = sysinfo._get_cpu()
        data['disks'] = sysinfo._get_fs()
        data['mounts'] = sysinfo._get_mounts()
        data['memory'] = sysinfo._get_mem()
        data['network'] = sysinfo._get_network()
        data['os'] = sysinfo._get_os()

        return data

    def _software(self, *args, **kwargs):
        '''
        Return installed software.
        '''
        data = dict()
        if 'exclude' in kwargs:
            excludes = kwargs['exclude'].split(",")
        else:
            excludes = list()

        os_family = __grains__.get("os_family").lower()

        # Get locks
        if os_family == 'suse':
            LOCKS = "pkg.list_locks"
            if 'products' not in excludes:
                products = __salt__['pkg.list_products']()
                if products:
                    data['products'] = products
        elif os_family == 'redhat':
            LOCKS = "pkg.get_locked_packages"
        else:
            LOCKS = None

        if LOCKS and 'locks' not in excludes:
            locks = __salt__[LOCKS]()
            if locks:
                data['locks'] = locks

        # Get patterns
        if os_family == 'suse':
            PATTERNS = 'pkg.list_installed_patterns'
        elif os_family == 'redhat':
            PATTERNS = 'pkg.group_list'
        else:
            PATTERNS = None

        if PATTERNS and 'patterns' not in excludes:
            patterns = __salt__[PATTERNS]()
            if patterns:
                data['patterns'] = patterns

        # Get packages
        if 'packages' not in excludes:
            data['packages'] = __salt__['pkg.list_pkgs']()

        # Get repositories
        if 'repositories' not in excludes:
            repos = __salt__['pkg.list_repos']()
            if repos:
                data['repositories'] = repos

        return data

    def _services(self, *args, **kwargs):
        '''
        Get list of enabled and disabled services on the particular system.
        '''
        return {
            'enabled': __salt__['service.get_enabled'](),
            'disabled': __salt__['service.get_disabled'](),
        }

    def _id_resolv(self, iid, named=True, uid=True):
        '''
        Resolve local users and groups.

        :param iid:
        :param named:
        :param uid:
        :return:
        '''

        if not self.local_identity:
            self.local_identity['users'] = self._get_local_users()
            self.local_identity['groups'] = self._get_local_groups()

        if not named:
            return iid

        for name, meta in self.local_identity[uid and 'users' or 'groups'].items():
            if (uid and int(meta.get('uid', -1)) == iid) or (not uid and int(meta.get('gid', -1)) == iid):
                return name

        return iid

    def _payload(self, *args, **kwargs):
        '''
        Find all unmanaged files. Returns maximum 1000 values.

        Parameters:

        * **filter**: Include only results which path starts from the filter string.
        * **time**: Display time in Unix ticks or format according to the configured TZ (default)
                    Values: ticks, tz (default)
        * **size**: Format size. Values: B, KB, MB, GB
        * **owners**: Resolve UID/GID to an actual names or leave them numeric (default).
                      Values: name (default), id
        * **type**: Comma-separated type of included payload: dir (or directory), link and/or file.
        * **brief**: Return just a list of matches, if True. Default: False
        * **offset**: Offset of the files
        * **max**: Maximum returned values. Default 1000.

        Options:

        * **total**: Return a total amount of found payload files
        '''
        def _size_format(size, fmt):
            if fmt is None:
                return size

            fmt = fmt.lower()
            if fmt == "b":
                return "{0} Bytes".format(size)
            elif fmt == "kb":
                return "{0} Kb".format(round((float(size) / 0x400), 2))
            elif fmt == "mb":
                return "{0} Mb".format(round((float(size) / 0x400 / 0x400), 2))
            elif fmt == "gb":
                return "{0} Gb".format(round((float(size) / 0x400 / 0x400 / 0x400), 2))

        filter = kwargs.get('filter')
        offset = kwargs.get('offset', 0)

        timeformat = kwargs.get("time", "tz")
        if timeformat not in ["ticks", "tz"]:
            raise InspectorQueryException('Unknown "{0}" value for parameter "time"'.format(timeformat))
        tfmt = lambda param: timeformat == "tz" and time.strftime("%b %d %Y %H:%M:%S", time.gmtime(param)) or int(param)

        size_fmt = kwargs.get("size")
        if size_fmt is not None and size_fmt.lower() not in ["b", "kb", "mb", "gb"]:
            raise InspectorQueryException('Unknown "{0}" value for parameter "size". '
                                          'Should be either B, Kb, Mb or Gb'.format(timeformat))

        owners = kwargs.get("owners", "id")
        if owners not in ["name", "id"]:
            raise InspectorQueryException('Unknown "{0}" value for parameter "owners". '
                                          'Should be either name or id (default)'.format(owners))

        incl_type = [prm for prm in kwargs.get("type", "").lower().split(",") if prm]
        if not incl_type:
            incl_type.append("file")

        for i_type in incl_type:
            if i_type not in ["directory", "dir", "d", "file", "f", "link", "l"]:
                raise InspectorQueryException('Unknown "{0}" values for parameter "type". '
                                              'Should be comma separated one or more of '
                                              'dir, file and/or link.'.format(", ".join(incl_type)))
        self.db.open()

        if "total" in args:
            return {'total': len(self.db.get(PayloadFile))}

        brief = kwargs.get("brief")
        pld_files = list() if brief else dict()
        for pld_data in self.db.get(PayloadFile)[offset:offset + kwargs.get('max', 1000)]:
            if brief:
                pld_files.append(pld_data.path)
            else:
                pld_files[pld_data.path] = {
                    'uid': self._id_resolv(pld_data.uid, named=(owners == "id")),
                    'gid': self._id_resolv(pld_data.gid, named=(owners == "id"), uid=False),
                    'size': _size_format(pld_data.p_size, fmt=size_fmt),
                    'mode': oct(pld_data.mode),
                    'accessed': tfmt(pld_data.atime),
                    'modified': tfmt(pld_data.mtime),
                    'created': tfmt(pld_data.ctime),
                }

        return pld_files

    def _all(self, *args, **kwargs):
        '''
        Return all the summary of the particular system.
        '''
        data = dict()
        data['software'] = self._software(**kwargs)
        data['system'] = self._system(**kwargs)
        data['services'] = self._services(**kwargs)
        try:
            data['configuration'] = self._configuration(**kwargs)
        except InspectorQueryException as ex:
            data['configuration'] = 'N/A'
            log.error(ex)
        data['payload'] = self._payload(**kwargs) or 'N/A'

        return data
