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
#
#
# Unification of the returning data

from salt.utils.scm.common import SchemaBase, SchemaMethods


class PackageSchema(SchemaBase):
    '''
    Refers to the pkg.* module.
    '''
    DIST_SPECIFIC = 'distribution-specific'

    def __init__(self, ident):
        SchemaBase.__init__(self, PackageSchema, ident=ident)

    class Yumpkg(SchemaMethods):
        '''
        Structure unifiers for Yum package manager (module/yumpkg.py)
        '''
        def mod_repo(self, data):
            schema = {}
            # Supposed to be only one repo, so not really an iteration.
            for r_filename, r_repodata in data.items():
                for r_alias, r_meta in r_repodata.items():
                    schema = {
                        'alias': r_alias,
                        'baseurl': r_meta.pop('baseurl'),
                        'enabled': bool(r_meta.pop('enabled')),
                        'refresh': 'refresh' in r_meta and bool(r_meta.pop('refresh')) or False,
                        'gpgcheck': bool(r_meta.pop('gpgcheck')),
                        'filename': r_filename,
                        'name': r_meta.pop('name'),
                    }
                    if r_meta:
                        schema[PackageSchema.DIST_SPECIFIC] = r_meta

            return schema

    class Zypper(SchemaMethods):
        '''
        Structure unifiers for Zypper package manager (modules/zypper.py)
        '''
        def mod_repo(self, data):
            alias = data.pop('alias')
            schema = {
                'alias': alias,
                'baseurl': data.pop('baseurl'),
                'enabled': data.pop('enabled'),
                'refresh': data.pop('autorefresh'),
                'gpgcheck': data.get('gpgcheck') and data.pop('gpgcheck') or False,
                'filename': data.pop('path'),
                'name': data.pop('name'),
            }
            if data:
                schema[PackageSchema.DIST_SPECIFIC] = data

            return schema

    class Aptpkg(SchemaMethods):
        '''
        Structure unifiers for Apt package manager (modules/aptpkg.py)
        '''
        def mod_repo(self, data):
            return data
