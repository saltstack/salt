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

'''
Ansible Support
===============

This module can have an optional minion-level
configuration in /etc/salt/minion.d/ as follows:

  ansible_timeout: 1200

The timeout is how many seconds Salt should wait for
any Ansible module to respond.
'''

from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import logging
import importlib
import fnmatch
import subprocess

import salt.utils.json
from salt.exceptions import LoaderError, CommandExecutionError
import salt.utils.platform
import salt.utils.timed_subprocess
import salt.utils.yaml
from salt.ext import six

try:
    import ansible
    import ansible.constants
    import ansible.modules
except ImportError:
    ansible = None

__virtualname__ = 'ansible'
log = logging.getLogger(__name__)


class AnsibleModuleResolver(object):
    '''
    This class is to resolve all available modules in Ansible.
    '''
    def __init__(self, opts):
        self.opts = opts
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
            if os.path.islink(p_el_path):
                continue
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
    DEFAULT_TIMEOUT = 1200  # seconds (20 minutes)
    OPT_TIMEOUT_KEY = 'ansible_timeout'

    def __init__(self, resolver):
        self._resolver = resolver
        self.timeout = self._resolver.opts.get(self.OPT_TIMEOUT_KEY, self.DEFAULT_TIMEOUT)

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
        js_args = str('{{"ANSIBLE_MODULE_ARGS": {args}}}')  # future lint: disable=blacklisted-function
        js_args = js_args.format(args=salt.utils.json.dumps(kwargs))

        proc_out = salt.utils.timed_subprocess.TimedProc(
            ["echo", "{0}".format(js_args)],
            stdout=subprocess.PIPE, timeout=self.timeout)
        proc_out.run()
        proc_exc = salt.utils.timed_subprocess.TimedProc(
            ['python', module.__file__],
            stdin=proc_out.stdout, stdout=subprocess.PIPE, timeout=self.timeout)
        proc_exc.run()

        try:
            out = salt.utils.json.loads(proc_exc.stdout)
        except ValueError as ex:
            out = {'Error': (proc_exc.stderr and (proc_exc.stderr + '.') or six.text_type(ex))}
            if proc_exc.stdout:
                out['Given JSON output'] = proc_exc.stdout
            return out

        if 'invocation' in out:
            del out['invocation']

        out['timeout'] = self.timeout

        return out


_resolver = None
_caller = None


def _set_callables(modules):
    '''
    Set all Ansible modules callables
    :return:
    '''
    def _set_function(cmd_name, doc):
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

            return _caller.call(cmd_name, *args, **kwargs)
        _cmd.__doc__ = doc
        return _cmd

    for mod in modules:
        setattr(sys.modules[__name__], mod, _set_function(mod, 'Available'))


def __virtual__():
    '''
    Ansible module caller.
    :return:
    '''
    if salt.utils.platform.is_windows():
        return False, "The ansiblegate module isn't supported on Windows"
    ret = ansible is not None
    msg = not ret and "Ansible is not installed on this system" or None
    if ret:
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
        raise CommandExecutionError('Please tell me what module you want to have helped with. '
                                    'Or call "ansible.list" to know what is available.')
    try:
        module = _resolver.load_module(module)
    except (ImportError, LoaderError) as err:
        raise CommandExecutionError('Module "{0}" is currently not functional on your system.'.format(module))

    doc = {}
    ret = {}
    for docset in module.DOCUMENTATION.split('---'):
        try:
            docset = salt.utils.yaml.safe_load(docset)
            if docset:
                doc.update(docset)
        except Exception as err:
            log.error("Error parsing doc section: %s", err)
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
