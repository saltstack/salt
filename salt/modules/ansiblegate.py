# -*- coding: utf-8 -*-
#
# Author: Bo Maryniuk <bo@suse.de>
#
# Copyright 2017 SUSE LLC
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

import logging
import os
try:
    import ansible
    import ansible.constants
    import ansible.modules
    from ansible.plugins import module_loader
except ImportError:
    ansible = None

__virtualname__ = 'ansible'
log = logging.getLogger(__name__)


class AnsibleModuleResolver(object):
    '''
    This class is to resolve all available modules in Ansible.
    '''
    def __init__(self, opts):
        self._opts = opts
        self._modules_map = self._get_modules_map()

    def _get_modules_map(self, path=None):
        '''
        Get installed Ansible modules
        :return:
        '''
        paths = {}
        root = ansible.modules.__path__[0]
        if not path:
            path = root
        for p_el in os.listdir(path):
            p_el_path = os.path.join(path, p_el)
            if os.path.islink(p_el_path): continue
            if os.path.isdir(p_el_path):
                paths.update(self._get_modules_map(p_el_path))
            else:
                if (any(p_el.startswith(elm) for elm in ['__', '.']) or
                        not p_el.endswith('.py') or
                        p_el in ansible.constants.IGNORE_FILES):
                    continue
                m_name = p_el.split('.')[0]
                als_name = m_name[1:] if m_name.startswith('_') else m_name
                paths[als_name] = p_el_path.replace(root, '')

        return paths

    def _introspect_module(self, module):
        '''
        Introspect Ansible module.

        :param module:
        :return:
        '''

    def resolve(self):
        log.debug('Resolving Ansible modules')
        return self

    def install(self):
        log.debug('Installing Ansible modules')
        return self


def __virtual__():
    '''
    Ansible module caller.
    :return:
    '''
    ret = ansible is not None
    msg = not ret and "Ansible is not installed on this system" or None
    if msg:
        log.warning(msg)
    else:
        AnsibleModuleResolver(__opts__).resolve().install()
    return ret, msg
