# -*- coding: utf-8 -*-
#
# Author: Alberto Planas <aplanas@suse.com>
#
# Copyright 2018 SUSE LINUX GmbH, Nuernberg, Germany.
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

'''
:maintainer:    Alberto Planas <aplanas@suse.com>
:maturity:      new
:depends:       None
:platform:      Linux
'''
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os

from salt.exceptions import CommandExecutionError
from salt.utils.args import clean_kwargs
from salt.utils.files import fopen
import salt.utils.json as json
from salt.ext.six.moves import zip

log = logging.getLogger(__name__)

__func_alias__ = {
    'list_': 'list',
}


def __virtual__():
    '''
    Freezer is based on top of the pkg module.

    Return True as pkg is going to be there, so we can avoid of
    loading all modules.

    '''
    return True


def _states_path():
    '''
    Return the path where we will store the states.
    '''
    return os.path.join(__opts__['cachedir'], 'freezer')


def _paths(name=None):
    '''
    Return the full path for the packages and repository freezer
    files.

    '''
    name = 'freezer' if not name else name
    states_path = _states_path()
    return (
        os.path.join(states_path, '{}-pkgs.yml'.format(name)),
        os.path.join(states_path, '{}-reps.yml'.format(name)),
    )


def status(name=None):
    '''
    Return True if there is already a frozen state.

    A frozen state is merely a list of packages (including the
    version) in a specific time. This information can be used to
    compare with the current list of packages, and revert the
    installation of some extra packages that are in the system.

    name
        Name of the frozen state. Optional.

    CLI Example:

    .. code-block:: bash

        salt '*' freezer.status
        salt '*' freezer.status pre_install

    '''
    name = 'freezer' if not name else name
    return all(os.path.isfile(i) for i in _paths(name))


def list_():
    '''
    Return the list of frozen states.

    CLI Example:

    .. code-block:: bash

        salt '*' freezer.list

    '''
    ret = []
    states_path = _states_path()
    if not os.path.isdir(states_path):
        return ret

    for state in os.listdir(states_path):
        if state.endswith(('-pkgs.yml', '-reps.yml')):
            # Remove the suffix, as both share the same size
            ret.append(state[:-9])
    return sorted(set(ret))


def freeze(name=None, force=False, **kwargs):
    '''
    Save the list of package and repos in a freeze file.

    As this module is build on top of the pkg module, the user can
    send extra attributes to the underlying pkg module via kwargs.
    This function will call ``pkg.list_pkgs`` and ``pkg.list_repos``,
    and any additional arguments will be passed through to those
    functions.

    name
        Name of the frozen state. Optional.

    force
        If true, overwrite the state. Optional.

    CLI Example:

    .. code-block:: bash

        salt '*' freezer.freeze
        salt '*' freezer.freeze pre_install
        salt '*' freezer.freeze force=True root=/chroot

    '''
    states_path = _states_path()

    try:
        os.makedirs(states_path)
    except OSError as e:
        msg = 'Error when trying to create the freezer storage %s: %s'
        log.error(msg, states_path, e)
        raise CommandExecutionError(msg % (states_path, e))

    if status(name) and not force:
        raise CommandExecutionError('The state is already present. Use '
                                    'force parameter to overwrite.')
    safe_kwargs = clean_kwargs(**kwargs)
    pkgs = __salt__['pkg.list_pkgs'](**safe_kwargs)
    repos = __salt__['pkg.list_repos'](**safe_kwargs)
    for name, content in zip(_paths(name), (pkgs, repos)):
        with fopen(name, 'w') as fp:
            json.dump(content, fp)
    return True


def restore(name=None, **kwargs):
    '''
    Make sure that the system contains the packages and repos from a
    frozen state.

    Read the list of packages and repositories from the freeze file,
    and compare it with the current list of packages and repos. If
    there is any difference, all the missing packages are repos will
    be installed, and all the extra packages and repos will be
    removed.

    As this module is build on top of the pkg module, the user can
    send extra attributes to the underlying pkg module via kwargs.
    This function will call ``pkg.list_repos``, ``pkg.mod_repo``,
    ``pkg.list_pkgs``, ``pkg.install``, ``pkg.remove`` and
    ``pkg.del_repo``, and any additional arguments will be passed
    through to those functions.

    name
        Name of the frozen state. Optional.

    CLI Example:

    .. code-block:: bash

        salt '*' freezer.restore
        salt '*' freezer.restore root=/chroot

    '''
    if not status(name):
        raise CommandExecutionError('Frozen state not found.')

    frozen_pkgs = {}
    frozen_repos = {}
    for name, content in zip(_paths(name), (frozen_pkgs, frozen_repos)):
        with fopen(name) as fp:
            content.update(json.load(fp))

    # The ordering of removing or adding packages and repos can be
    # relevant, as maybe some missing package comes from a repo that
    # is also missing, so it cannot be installed. But can also happen
    # that a missing package comes from a repo that is present, but
    # will be removed.
    #
    # So the proposed order is;
    #   - Add missing repos
    #   - Add missing packages
    #   - Remove extra packages
    #   - Remove extra repos

    safe_kwargs = clean_kwargs(**kwargs)

    # Note that we expect that the information stored in list_XXX
    # match with the mod_XXX counterpart. If this is not the case the
    # recovery will be partial.

    res = {
        'pkgs': {'add': [], 'remove': []},
        'repos': {'add': [], 'remove': []},
        'comment': [],
    }

    # Add missing repositories
    repos = __salt__['pkg.list_repos'](**safe_kwargs)
    missing_repos = set(frozen_repos) - set(repos)
    for repo in missing_repos:
        try:
            # In Python 2 we cannot do advance destructuring, so we
            # need to create a temporary dictionary that will merge
            # all the parameters
            _tmp_kwargs = frozen_repos[repo].copy()
            _tmp_kwargs.update(safe_kwargs)
            __salt__['pkg.mod_repo'](repo, **_tmp_kwargs)
            res['repos']['add'].append(repo)
            log.info('Added missing repository %s', repo)
        except Exception as e:
            msg = 'Error adding %s repository: %s'
            log.error(msg, repo, e)
            res['comment'].append(msg % (repo, e))

    # Add missing packages
    # NOTE: we can remove the `for` using `pkgs`. This will improve
    # performance, but I want to have a more detalied report of what
    # packages are installed or failed.
    pkgs = __salt__['pkg.list_pkgs'](**safe_kwargs)
    missing_pkgs = set(frozen_pkgs) - set(pkgs)
    for pkg in missing_pkgs:
        try:
            __salt__['pkg.install'](name=pkg, **safe_kwargs)
            res['pkgs']['add'].append(pkg)
            log.info('Added missing package %s', pkg)
        except Exception as e:
            msg = 'Error adding %s package: %s'
            log.error(msg, pkg, e)
            res['comment'].append(msg % (pkg, e))

    # Remove extra packages
    pkgs = __salt__['pkg.list_pkgs'](**safe_kwargs)
    extra_pkgs = set(pkgs) - set(frozen_pkgs)
    for pkg in extra_pkgs:
        try:
            __salt__['pkg.remove'](name=pkg, **safe_kwargs)
            res['pkgs']['remove'].append(pkg)
            log.info('Removed extra package %s', pkg)
        except Exception as e:
            msg = 'Error removing %s package: %s'
            log.error(msg, pkg, e)
            res['comment'].append(msg % (pkg, e))

    # Remove extra repositories
    repos = __salt__['pkg.list_repos'](**safe_kwargs)
    extra_repos = set(repos) - set(frozen_repos)
    for repo in extra_repos:
        try:
            __salt__['pkg.del_repo'](repo, **safe_kwargs)
            res['repos']['remove'].append(repo)
            log.info('Removed extra repository %s', repo)
        except Exception as e:
            msg = 'Error removing %s repository: %s'
            log.error(msg, repo, e)
            res['comment'].append(msg % (repo, e))

    return res
