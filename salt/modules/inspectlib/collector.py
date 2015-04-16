# -*- coding: utf-8 -*-
#
# Copyright 2014 SUSE LLC
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

import os
import sys
from subprocess import Popen, PIPE, STDOUT
from salt.modules.inspectlib.dbhandle import DBHandle
from salt.modules.inspectlib.exceptions import (InspectorSnapshotException)

class Inspector(object):

    MODE = ['configuration', 'payload', 'all']

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

    def snapshot(self, mode):
        '''
        Take a snapshot of the system.
        '''
        data = self._get_cfg_pkgs()
        self._save_cfg_pkgs(data)

    def request_snapshot(self, mode, priority=19):
        '''
        Take a snapshot of the system.
        '''
        if mode not in self.MODE:
            raise InspectorSnapshotException("Unknown mode: '{0}'".format(mode))

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
            sys.exit(0)
    except OSError as ex:
        sys.exit(1)

    os.setsid()
    os.umask(0)

    try:
        pid = os.fork()
        if pid > 0:
            fpid = open(pidfile, "w")
            fpid.write("{0}\n".format(pid))
            fpid.close()
            sys.exit(0)
    except OSError as ex:
        sys.exit(1)

    main(dbfile, pidfile, mode)
