# -*- coding: utf-8 -*-
#
# Copyright 2016 SUSE LLC
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

from __future__ import absolute_import
from salt.modules.inspectlib.fsdb import CsvDBEntity


class IgnoredDir(CsvDBEntity):
    '''
    Ignored directories
    '''
    _TABLE = 'inspector_ignored'

    def __init__(self):
        self.path = ''


class AllowedDir(CsvDBEntity):
    '''
    Allowed directories
    '''
    _TABLE = 'inspector_allowed'

    def __init__(self):
        self.path = ''


class Package(CsvDBEntity):
    '''
    Package.
    '''
    _TABLE = 'inspector_pkg'

    def __init__(self):
        self.id = 0
        self.name = ''


class PackageCfgFile(CsvDBEntity):
    '''
    Config file, belongs to the package
    '''
    _TABLE = 'inspector_pkg_cfg_files'

    def __init__(self):
        self.id = 0
        self.pkgid = 0
        self.path = ''


class PayloadFile(CsvDBEntity):
    '''
    Payload file.
    '''
    _TABLE = 'inspector_payload'

    def __init__(self):
        self.id = 0
        self.path = ''
        self.p_type = ''
        self.mode = 0
        self.uid = 0
        self.gid = 0
        self.p_size = 0
        self.atime = 0.
        self.mtime = 0.
        self.ctime = 0.
