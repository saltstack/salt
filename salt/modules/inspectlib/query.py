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

import salt

class SysInfo(object):
    '''
    System information.
    '''

    class SIException(Exception):
        '''
        System information exception.
        '''
        pass

    def __init__(self, systype):
        if systype.lower() == "solaris":
            raise SysInfo.SIException("Platform {0} not (yet) supported.".format(systype))

    def _get_fs(self):
        '''
        Get available file systems and their types.
        '''

        out = __salt__['cmd.run_all']("blkid -o export")
        salt.utils.fsutils._verify_run(out)

        return salt.utils.fsutils._blkid_output(out['stdout'])

    def _get_mem(self):
        '''
        Get memory.
        '''
        out = __salt__['cmd.run_all']("vmstat -s")
        print out.keys()
        if out['retcode']:
            raise SysInfo.SIException("Error: {0}".format(out['stderr']))

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


class Query(object):
    '''
    Query the system.
    This class is actually puts all Salt features together,
    so there would be no need to pick it from various places.
    '''

    class InspectorQueryException(Exception):
        '''
        Exception that is only for the inspector query.
        '''
        pass

    # Configuration: config files
    # Identity: users/groups
    # Software: packages, patterns, repositories
    # Services
    # System: distro, RAM etc
    # Changes: all files that are managed and were changed from the original
    # all: include all scopes (scary!)
    # payload: files that are not managed

    SCOPES = ["changes", "configuration", "identity", "system", "software", "services", "payload", "all"]

    def __init__(self, scope):
        '''
        Constructor.

        :param scope:
        :return:
        '''
        if scope not in self.SCOPES:
            raise Query.InspectorQueryException("Unknown scope: {0}".format(repr(scope)))
        self.scope = '_' + scope

    def __call__(self, *args, **kwargs):
        '''
        Call the query with the defined scope.

        :param args:
        :param kwargs:
        :return:
        '''

        return getattr(self, self.scope)(*args, **kwargs)

    def _changes(self, *args, **kwargs):
        return "This is changes"

    def _configuration(self, *args, **kwargs):
        return "This is configuration"

    def _identity(self, *args, **kwargs):
        return "This is identity"

    def _system(self, *args, **kwargs):
        '''
        This basically calls grains items and picks out only
        necessary information in a certain structure.

        :param args:
        :param kwargs:
        :return:
        '''
        CPU = 'CPU'
        data = {CPU: dict()}
        for key, value in __grains__.items():
            print "KEY:", key
            if key.startswith("cpu_"):
                data[CPU][key.replace("cpu_", "")] = value
        sysinfo = SysInfo(__grains__.get("kernel"))
        data['disks'] = sysinfo._get_fs()
        data['memory'] = sysinfo._get_mem()

        return data

    def _software(self, *args, **kwargs):
        return "This is software"

    def _services(self, *args, **kwargs):
        return "This is service"

    def _payload(self, *args, **kwargs):
        return "This is payload"

    def _all(self, *args, **kwargs):
        return "This is all"

