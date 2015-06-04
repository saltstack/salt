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
import sys
import stat
from subprocess import Popen, PIPE, STDOUT

# Import Salt Libs
from salt.modules.inspectlib.dbhandle import DBHandle
from salt.modules.inspectlib.exceptions import (InspectorSnapshotException)
import salt.utils
from salt.utils import fsutils
from salt.utils import reinit_crypto


class Inspector(object):

    MODE = ['configuration', 'payload', 'all']
    IGNORE_MOUNTS = ["proc", "sysfs", "devtmpfs", "tmpfs", "fuse.gvfs-fuse-daemon"]
    IGNORE_FS_TYPES = ["autofs", "cifs", "nfs", "nfs4"]
    IGNORE_PATHS = ["/tmp", "/var/tmp", "/lost+found", "/var/run",
                    "/var/lib/rpm", "/.snapshots", "/.zfs", "/etc/ssh",
                    "/root", "/home"]

    def __init__(self, db_path=None, pid_file=None):
        # Configured path
        if not db_path and '__salt__' in globals():
            db_path = globals().get('__salt__')['config.get']('inspector.db', '')

        if not db_path:
            raise InspectorSnapshotException("Inspector database location is not configured yet in minion.")
        self.dbfile = db_path

        self.db = DBHandle(self.dbfile)
        self.db.open()

        if not pid_file and '__salt__' in globals():
            pid_file = globals().get('__salt__')['config.get']('inspector.pid', '')

        if not pid_file:
            raise InspectorSnapshotException("Inspector PID file location is not configured yet in minion.")
        self.pidfile = pid_file

    def _syscall(self, command, input=None, env=None, *params):
        '''
        Call an external system command.
        '''
        return Popen([command] + list(params), stdout=PIPE, stdin=PIPE, stderr=STDOUT,
                     env=env or os.environ).communicate(input=input)

    def _get_cfg_pkgs(self):
        '''
        Get packages with configuration files.
        '''
        out, err = self._syscall('rpm', None, None, '-qa', '--configfiles',
                                 '--queryformat', '%{name}-%{version}-%{release}\\n')
        data = dict()
        pkg_name = None
        pkg_configs = []

        out = salt.utils.to_str(out)
        for line in out.split(os.linesep):
            line = line.strip()
            if not line:
                continue
            if not line.startswith("/"):
                if pkg_name and pkg_configs:
                    data[pkg_name] = pkg_configs
                pkg_name = line
                pkg_configs = []
            else:
                pkg_configs.append(line)

        if pkg_name and pkg_configs:
            data[pkg_name] = pkg_configs

        return data

    def _get_changed_cfg_pkgs(self, data):
        '''
        Filter out unchanged packages.
        '''
        f_data = dict()
        for pkg_name, pkg_files in data.items():
            cfgs = list()
            out, err = self._syscall("rpm", None, None, '-V', '--nodeps', '--nodigest',
                                     '--nosignature', '--nomtime', '--nolinkto', pkg_name)
            out = salt.utils.to_str(out)
            for line in out.split(os.linesep):
                line = line.strip()
                if not line or line.find(" c ") < 0 or line.split(" ")[0].find("5") < 0:
                    continue

                cfg_file = line.split(" ")[-1]
                if cfg_file in pkg_files:
                    cfgs.append(cfg_file)
            if cfgs:
                f_data[pkg_name] = cfgs

        return f_data

    def _save_cfg_pkgs(self, data):
        '''
        Save configuration packages.
        '''
        for table in ["inspector_pkg", "inspector_pkg_cfg_files"]:
            self.db.flush(table)

        pkg_id = 0
        pkg_cfg_id = 0
        for pkg_name, pkg_configs in data.items():
            self.db.cursor.execute("INSERT INTO inspector_pkg (id, name) VALUES (?, ?)",
                                   (pkg_id, pkg_name))
            for pkg_config in pkg_configs:
                self.db.cursor.execute("INSERT INTO inspector_pkg_cfg_files (id, pkgid, path) VALUES (?, ?, ?)",
                                       (pkg_cfg_id, pkg_id, pkg_config))
                pkg_cfg_id += 1
            pkg_id += 1

        self.db.connection.commit()

    def _save_payload(self, files, directories, links):
        '''
        Save payload (unmanaged files)
        '''
        idx = 0
        for p_type, p_list in (('f', files), ('d', directories), ('l', links,),):
            for p_obj in p_list:
                stats = os.stat(p_obj)
                self.db.cursor.execute("INSERT INTO inspector_payload "
                                       "(id, path, p_type, mode, uid, gid, p_size, atime, mtime, ctime)"
                                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       (idx, p_obj, p_type, stats.st_mode, stats.st_uid, stats.st_gid, stats.st_size,
                                        stats.st_atime, stats.st_mtime, stats.st_ctime))
                idx += 1

        self.db.connection.commit()

    def _get_managed_files(self):
        '''
        Build a in-memory data of all managed files.
        '''
        dirs = set()
        links = set()
        files = set()

        cmd = __salt__['cmd.run_stdout']('rpm -qlav')

        for line in cmd:
            line = line.strip()
            if not line:
                continue
            line = line.replace("\t", " ").split(" ")
            if line[0][0] == "d":
                dirs.add(line[-1])
            elif line[0][0] == "l":
                links.add(line[-1])
            elif line[0][0] == "-":
                files.add(line[-1])

        return sorted(files), sorted(dirs), sorted(links)

    def _get_all_files(self, path, *exclude):
        '''
        Walk implementation. Version in python 2.x and 3.x works differently.
        '''
        files = list()
        dirs = list()
        links = list()

        for obj in os.listdir(path):
            obj = os.path.join(path, obj)
            valid = True
            for ex_obj in exclude:
                if obj.startswith(str(ex_obj)):
                    valid = False
                    continue
            if not valid or not os.path.exists(obj):
                continue
            mode = os.lstat(obj).st_mode
            if stat.S_ISLNK(mode):
                links.append(obj)
            elif stat.S_ISDIR(mode):
                dirs.append(obj)
                f_obj, d_obj, l_obj = self._get_all_files(obj, *exclude)
                files.extend(f_obj)
                dirs.extend(d_obj)
                links.extend(l_obj)
            elif stat.S_ISREG(mode):
                files.append(obj)

        return sorted(files), sorted(dirs), sorted(links)

    def _get_unmanaged_files(self, managed, system_all):
        '''
        Get the intersection between all files and managed files.
        '''
        def intr(src, data):
            out = set()
            for d_el in data:
                if d_el not in src:
                    out.add(d_el)
            return out

        m_files, m_dirs, m_links = managed
        s_files, s_dirs, s_links = system_all

        return sorted(intr(m_files, s_files)), sorted(intr(m_dirs, s_dirs)), sorted(intr(m_links, s_links))

    def _scan_payload(self):
        '''
        Scan the system.
        '''
        # Get ignored points
        allowed = list()
        self.db.cursor.execute("SELECT path FROM inspector_allowed")
        for alwd_path in self.db.cursor.fetchall():
            if os.path.exists(alwd_path[0]):
                allowed.append(alwd_path[0])

        ignored = list()
        if not allowed:
            self.db.cursor.execute("SELECT path FROM inspector_ignored")
            for ign_path in self.db.cursor.fetchall():
                ignored.append(ign_path[0])

        all_files = list()
        all_dirs = list()
        all_links = list()
        for entry_path in [pth for pth in (allowed or os.listdir("/")) if pth]:
            if entry_path[0] != "/":
                entry_path = "/{0}".format(entry_path)
            if entry_path in ignored:
                continue
            e_files, e_dirs, e_links = self._get_all_files(entry_path, *ignored)
            all_files.extend(e_files)
            all_dirs.extend(e_dirs)
            all_links.extend(e_links)

        return self._get_unmanaged_files(self._get_managed_files(), (all_files, all_dirs, all_links,))

    def _prepare_full_scan(self, **kwargs):
        '''
        Prepare full system scan by setting up the database etc.
        '''
        # TODO: Backup the SQLite database. Backup should be restored automatically if current db failed while queried.
        self.db.purge()

        # Add ignored filesystems
        ignored_fs = set()
        ignored_fs |= set(self.IGNORE_PATHS)
        mounts = fsutils._get_mounts()
        for device, data in mounts.items():
            if device in self.IGNORE_MOUNTS:
                for mpt in data:
                    ignored_fs.add(mpt['mount_point'])
                continue
            for mpt in data:
                if mpt['type'] in self.IGNORE_FS_TYPES:
                    ignored_fs.add(mpt['mount_point'])

        # Remove leafs of ignored filesystems
        ignored_all = list()
        for entry in sorted(list(ignored_fs)):
            valid = True
            for e_entry in ignored_all:
                if entry.startswith(e_entry):
                    valid = False
                    break
            if valid:
                ignored_all.append(entry)
        # Save to the database for further scan
        for ignored_dir in ignored_all:
            self.db.cursor.execute("INSERT INTO inspector_ignored VALUES (?)", (ignored_dir,))

        # Add allowed filesystems (overrides all above at full scan)
        allowed = [elm for elm in kwargs.get("filter", "").split(",") if elm]
        for allowed_dir in allowed:
            self.db.cursor.execute("INSERT INTO inspector_allowed VALUES (?)", (allowed_dir,))

        self.db.connection.commit()

        return ignored_all

    def snapshot(self, mode):
        '''
        Take a snapshot of the system.
        '''
        # TODO: Mode

        self._save_cfg_pkgs(self._get_changed_cfg_pkgs(self._get_cfg_pkgs()))
        self._save_payload(*self._scan_payload())

    def request_snapshot(self, mode, priority=19, **kwargs):
        '''
        Take a snapshot of the system.
        '''
        if mode not in self.MODE:
            raise InspectorSnapshotException("Unknown mode: '{0}'".format(mode))

        self._prepare_full_scan(**kwargs)

        os.system("nice -{0} python {1} {2} {3} {4} & > /dev/null".format(
            priority, __file__, self.pidfile, self.dbfile, mode))


def is_alive(pidfile):
    '''
    Check if PID is still alive.
    '''
    # Just silencing os.kill exception if no such PID, therefore try/pass.
    try:
        os.kill(int(open(pidfile).read().strip()), 0)
        sys.exit(1)
    except Exception as ex:
        pass


def main(dbfile, pidfile, mode):
    '''
    Main analyzer routine.
    '''
    Inspector(dbfile, pidfile).snapshot(mode)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print >> sys.stderr, "This module is not intended to use directly!"
        sys.exit(1)

    pidfile, dbfile, mode = sys.argv[1:]
    is_alive(pidfile)

    # Double-fork stuff
    try:
        if os.fork() > 0:
            reinit_crypto()
            sys.exit(0)
        else:
            reinit_crypto()
    except OSError as ex:
        sys.exit(1)

    os.setsid()
    os.umask(0)

    try:
        pid = os.fork()
        if pid > 0:
            reinit_crypto()
            fpid = open(pidfile, "w")
            fpid.write("{0}\n".format(pid))
            fpid.close()
            sys.exit(0)
    except OSError as ex:
        sys.exit(1)

    reinit_crypto()
    main(dbfile, pidfile, mode)
