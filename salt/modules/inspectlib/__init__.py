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

# Import Python libs
from __future__ import absolute_import

import os

from salt.modules.inspectlib.dbhandle import DBHandle

# Import Salt libs
from salt.modules.inspectlib.exceptions import InspectorSnapshotException


class EnvLoader(object):
    """
    Load environment.
    """

    PID_FILE = "_minion_collector.pid"
    DB_FILE = "_minion_collector.db"
    DEFAULT_PID_PATH = "/var/run"
    DEFAULT_CACHE_PATH = "/var/cache/salt"

    def __init__(self, cachedir=None, piddir=None, pidfilename=None):
        """
        Constructor.

        :param options:
        :param db_path:
        :param pid_file:
        """
        if not cachedir and "__salt__" in globals():
            cachedir = globals().get("__salt__")["config.get"]("inspector.db", "")

        self.dbfile = os.path.join(cachedir or self.DEFAULT_CACHE_PATH, self.DB_FILE)
        self.db = DBHandle(self.dbfile)

        if not piddir and "__salt__" in globals():
            piddir = globals().get("__salt__")["config.get"]("inspector.pid", "")
        self.pidfile = os.path.join(
            piddir or self.DEFAULT_PID_PATH, pidfilename or self.PID_FILE
        )
