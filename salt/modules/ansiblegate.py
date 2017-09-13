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

import os
import sys
import logging
import importlib
import yaml
import fnmatch
import subprocess
import json

from salt.exceptions import LoaderError, CommandExecutionError
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
        self._modules_map = {}

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
                p_el_path = p_el_path.replace(root, '').split('.')[0]
                als_name = p_el_path.replace('.', '').replace('/', '', 1).replace('/', '.')
                paths[als_name] = p_el_path

        return paths

    def load_module(self, module):
        '''
        Introspect Ansible module.

        :param module:
        :return:
        '''
        m_ref = self._modules_map.get(module)
        if m_ref is None:
            raise LoaderError('Module "{0}" was not found'.format(module))
        mod = importlib.import_module('ansible.modules{0}'.format(
            '.'.join([elm.split('.')[0] for elm in m_ref.split(os.path.sep)])))

        return mod

    def get_modules_list(self, pattern=None):
        '''
        Return module map references.
        :return:
        '''
        if pattern and '*' not in pattern:
            pattern = '*{0}*'.format(pattern)
        modules = []
        for m_name, m_path in self._modules_map.items():
            m_path = m_path.split('.')[0]
            m_name = '.'.join([elm for elm in m_path.split(os.path.sep) if elm])
            if pattern and fnmatch.fnmatch(m_name, pattern) or not pattern:
                modules.append(m_name)
        return sorted(modules)

    def resolve(self):
        log.debug('Resolving Ansible modules')
        self._modules_map = self._get_modules_map()
        return self

    def install(self):
        log.debug('Installing Ansible modules')
        return self


class AnsibleModuleCaller(object):
    def __init__(self, resolver):
        self._resolver = resolver

    def call(self, module, *args, **kwargs):
        '''
        Call an Ansible module by invoking it.
        :param module: the name of the module.
        :param args: Arguments to the module
        :param kwargs: keywords to the module
        :return:
        '''

        module = self._resolver.load_module(module)
        if not hasattr(module, 'main'):
            raise CommandExecutionError('This module is not callable '
                                        '(see "ansible.help {0}")'.format(module.__name__.replace('ansible.modules.',
                                                                                                  '')))
        if args:
            kwargs['_raw_params'] = ' '.join(args)
        js_args = '{{"ANSIBLE_MODULE_ARGS": {args}}}'.format(args=json.dumps(kwargs))
        js_out = subprocess.Popen(["echo", "{0}".format(js_args)], stdout=subprocess.PIPE)
        md_exc = subprocess.Popen(['python', module.__file__],
                                  stdin=js_out.stdout, stdout=subprocess.PIPE)
        js_out.stdout.close()
        js_out = md_exc.communicate()[0]

        try:
            out = json.loads(js_out)
        except ValueError as ex:
            return {'Error': str(ex), "JSON": js_out}
        if 'invocation' in out:
            del out['invocation']

        return out


_resolver = None
_caller = None


def _set_callables(modules):
    '''
    Set all Ansible modules callables
    :return:
    '''
    def _mkf(cmd_name, doc):
        '''
        Create a Salt function for the Ansible module.
        '''
        def _cmd(*args, **kw):
            '''
            Call an Ansible module as a function from the Salt.
            '''
            kwargs = {}
            if kw.get('__pub_arg'):
                for _kw in kw.get('__pub_arg', []):
                    if isinstance(_kw, dict):
                        kwargs = _kw
                        break
            else:
                kw = {}

            global _caller
            return _caller.call(cmd_name, *args, **kwargs)
        _cmd.__doc__ = doc
        return _cmd

    for mod in modules:
        setattr(sys.modules[__name__], mod, _mkf(mod, 'Available'))


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
        global _resolver
        global _caller
        _resolver = AnsibleModuleResolver(__opts__).resolve().install()
        _caller = AnsibleModuleCaller(_resolver)
    _set_callables(list())

    return ret, msg


def help(module=None, *args):
    '''
    Display help on Ansible standard module.

    :param module:
    :return:
    '''
    if not module:
        raise CommandExecutionError('Please tell me what module you want to have a help on. '
                                    'Or call ansible.list to know what is available.')
    try:
        module = _resolver.load_module(module)
    except (ImportError, LoaderError) as err:
        raise CommandExecutionError('Module "{0}" is currently not functional on your system.'.format(module))

    doc = {}
    ret = {}
    for docset in module.DOCUMENTATION.split('---'):
        try:
            docset = yaml.load(docset)
            if docset:
                doc.update(docset)
        except Exception as err:
            log.error("Error parsing doc section: {0}".format(err))
    if not args:
        if 'description' in doc:
            description = doc.get('description') or ''
            del doc['description']
            ret['Description'] = description
        ret['Available sections on module "{}"'.format(module.__name__.replace('ansible.modules.', ''))] = doc.keys()
    else:
        for arg in args:
            info = doc.get(arg)
            if info is not None:
                ret[arg] = info

    return ret


def list(pattern=None):
    '''
    Lists available modules.
    :return:
    '''
    return _resolver.get_modules_list(pattern=pattern)
