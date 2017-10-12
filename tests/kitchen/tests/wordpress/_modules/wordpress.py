# -*- coding: utf-8 -*-
'''
Manage wordpress plugins
'''
import re
import pprint
import collections

import salt.utils

Plugin = collections.namedtuple('Plugin', 'name status update versino')


def __virtual__():
    if salt.utils.which('wp'):
        return True
    return False


def _get_plugins(stuff):
    return Plugin(stuff)

def list_plugins(path, user):
    """
    Check if plugin is activated in path
    """
    ret = []
    resp = __salt__['cmd.shell']((
        'wp --path={0} plugin list'
    ).format(path), runas=user)
    for line in resp.split('\n')[1:]:
        ret.append(line.split('\t'))
    return [plugin.__dict__ for plugin in map(_get_plugins, ret)]


def show_plugin(name, path, user):
    ret = {'name': name}
    resp = __salt__['cmd.shell']((
        'wp --path={0} plugin status {1}'
    ).format(path, name), runas=user).split('\n')
    for line in resp:
        if 'Status' in line:
            ret['status'] = line.split(' ')[-1].lower()
        elif 'Version' in line:
            ret['version'] = line.split(' ')[-1].lower()
    return ret


def activate(name, path, user):
    check = show_plugin(name, path, user)
    if check['status'] == 'active':
        # already active
        return None
    resp = __salt__['cmd.shell']((
        'wp --path={0} plugin activate {1}'
    ).format(path, name), runas=user)
    if 'Success' in resp:
        return True
    elif show_plugin(name, path, user)['status'] == 'active':
        return True
    return False


def deactivate(name, path, user):
    check = show_plugin(name, path, user)
    if check['status'] == 'inactive':
        # already inactive
        return None
    resp = __salt__['cmd.shell']((
        'wp --path={0} plugin deactivate {1}'
    ).format(path, name), runas=user)
    if 'Success' in resp:
        return True
    elif show_plugin(name, path, user)['status'] == 'inactive':
        return True
    return False


def is_installed(path, user=None):
    retcode = __salt__['cmd.retcode']((
        'wp --path={0} core is-installed'
    ).format(path), runas=user)
    if retcode == 0:
        return True
    return False


def install(path, user, admin_user, admin_password, admin_email, title, url):
    retcode = __salt__['cmd.retcode']((
        'wp --path={0} core install '
        '--title="{1}" '
        '--admin_user={2} '
        "--admin_password='{3}' "
        '--admin_email={4} '
        '--url={5}'
    ).format(
        path,
        title,
        admin_user,
        admin_password,
        admin_email,
        url
    ), runas=user)

    if retcode == 0:
        return True
    return False
