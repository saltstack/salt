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

r'''
Execution of Ansible modules from within states
===============================================

With `ansible.call` these states allow individual Ansible module calls to be
made via states. To call an Ansible module function use a :mod:`module.run <salt.states.ansible.call>`
state:

.. code-block:: yaml

    some_set_of_tasks:
      ansible:
        - system.ping
        - packaging.os.zypper
          - name: emacs
          - state: installed

'''
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os
import sys

# Import salt modules
import salt.fileclient
import salt.ext.six as six
from salt.utils.decorators import depends
import salt.utils.decorators.path

log = logging.getLogger(__name__)
__virtualname__ = 'ansible'


@depends('ansible')
class AnsibleState(object):
    '''
    Ansible state caller.
    '''
    def get_args(self, argset):
        '''
        Get args and kwargs from the argset.

        :param argset:
        :return:
        '''
        args = []
        kwargs = {}
        for element in argset or []:
            if isinstance(element, dict):
                kwargs.update(element)
            else:
                args.append(element)
        return args, kwargs

    def __call__(self, **kwargs):
        '''
        Call Ansible module.

        :return:
        '''

        ret = {
            'name': kwargs.pop('name'),
            'changes': {},
            'comment': '',
            'result': True,
        }

        for mod_name, mod_params in kwargs.items():
            args, kwargs = self.get_args(mod_params)
            try:
                ans_mod_out = __salt__['ansible.{0}'.format(mod_name)](**{'__pub_arg': [args, kwargs]})
            except Exception as err:  # pylint: disable=broad-except
                ans_mod_out = 'Module "{0}" failed. Error message: ({1}) {2}'.format(
                    mod_name, err.__class__.__name__, err)
                ret['result'] = False
            ret['changes'][mod_name] = ans_mod_out

        return ret


def __virtual__():
    '''
    Disable, if Ansible is not available around on the Minion.
    '''
    setattr(sys.modules[__name__], 'call', lambda **kwargs: AnsibleState()(**kwargs))   # pylint: disable=W0108
    return __virtualname__


def _client():
    '''
    Get a fileclient
    '''
    return salt.fileclient.get_file_client(__opts__)


def _changes(plays):
    '''
    Find changes in ansible return data
    '''
    changes = {}
    for play in plays['plays']:
        task_changes = {}
        for task in play['tasks']:
            host_changes = {}
            for host, data in six.iteritems(task['hosts']):
                if data['changed'] is True:
                    host_changes[host] = data.get('diff', data.get('changes', {}))
            if host_changes:
                task_changes[task['task']['name']] = host_changes
        if task_changes:
            changes[play['play']['name']] = task_changes
    return changes


@salt.utils.decorators.path.which('ansible-playbook')
def playbooks(name, rundir=None, git_repo=None, git_kwargs=None, ansible_kwargs=None):
    '''
    Run Ansible Playbooks

    :param name: path to playbook. This can be relative to rundir or the git repo
    :param rundir: location to run ansible-playbook from.
    :param git_repo: git repository to clone for ansible playbooks.  This is cloned
                     using the `git.latest` state, and is cloned to the `rundir`
                     if specified, otherwise it is clone to the `cache_dir`
    :param git_kwargs: extra kwargs to pass to `git.latest` state module besides
                       the `name` and `target`
    :param ansible_kwargs: extra kwargs to pass to `ansible.playbooks` execution
                           module besides the `name` and `target`

    :return: Ansible playbook output.

    .. code-block:: yaml

        run nginx install:
          ansible.playbooks:
            - name: install.yml
            - git_repo: git://github.com/gituser/playbook.git
            - git_kwargs:
                rev: master
    '''
    ret = {
        'result': False,
        'changes': {},
        'comment': 'Running playbook {0}'.format(name),
        'name': name,
    }
    if git_repo:
        if not isinstance(rundir, six.text_type) or not os.path.isdir(rundir):
            rundir = _client()._extrn_path(git_repo, 'base')
            log.trace('rundir set to %s', rundir)
        if not isinstance(git_kwargs, dict):
            log.debug('Setting git_kwargs to empty dict: %s', git_kwargs)
            git_kwargs = {}
        __states__['git.latest'](
            name=git_repo,
            target=rundir,
            **git_kwargs
        )
    if not isinstance(ansible_kwargs, dict):
        log.debug('Setting ansible_kwargs to empty dict: %s', ansible_kwargs)
        ansible_kwargs = {}
    checks = __salt__['ansible.playbooks'](name, rundir=rundir, check=True, diff=True, **ansible_kwargs)
    if all(not check['changed'] for check in six.itervalues(checks['stats'])):
        ret['comment'] = 'No changes to be made from playbook {0}'.format(name)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'Changes will be made from playbook {0}'.format(name)
        ret['result'] = None
        ret['changes'] = _changes(checks)
    else:
        results = __salt__['ansible.playbooks'](name, rundir=rundir, diff=True, **ansible_kwargs)
        ret['comment'] = 'Changes were made by playbook {0}'.format(name)
        ret['changes'] = _changes(results)
        ret['result'] = all(
            not check['failures'] and not check['unreachable']
            for check in six.itervalues(checks['stats'])
        )
    return ret
