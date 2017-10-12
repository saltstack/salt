# -*- coding: utf-8 -*-
'''
Manage wordpress plugins
'''


def __virtual__():
    return 'wordpress.show_plugin' in __salt__


def installed(name, path, user, admin_user, admin_password, admin_email, title, url):
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}

    check = __salt__['wordpress.is_installed'](path, user)

    if check:
        ret['result'] = True
        ret['comment'] = 'Wordpress is already installed: {0}'.format(name)
        return ret
    elif __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Wordpress will be installed: {0}'.format(name)
        return ret

    resp = __salt__['wordpress.install'](path, user, admin_user, admin_password, admin_email, title, url)
    if resp:
        ret['result'] = True
        ret['comment'] = 'Wordpress Installed: {0}'.format(name)
        ret['changes'] = {
            'new': resp
        }
    else:
        ret['comment'] = 'Failed to install wordpress: {0}'.format(name)

    return ret


def activated(name, path, user):
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}

    check = __salt__['wordpress.show_plugin'](name, path, user)

    if check['status'] == 'active':
        ret['result'] = True
        ret['comment'] = 'Plugin already activated: {0}'.format(name)
        return ret
    elif __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Plugin will be activated: {0}'.format(name)
        return ret

    resp = __salt__['wordpress.activate'](name, path, user)
    if resp is True:
        ret['result'] = True
        ret['comment'] = 'Plugin activated: {0}'.format(name)
        ret['changes'] = {
            'old': check,
            'new': __salt__['wordpress.show_plugin'](name, path, user)
        }
    elif resp is None:
        ret['result'] = True
        ret['comment'] = 'Plugin already activated: {0}'.format(name)
        ret['changes'] = {
            'old': check,
            'new': __salt__['wordpress.show_plugin'](name, path, user)
        }
    else:
        ret['comment'] = 'Plugin failed to activate: {0}'.format(name)

    return ret


def deactivated(name, path, user):
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}

    check = __salt__['wordpress.show_plugin'](name, path, user)

    if check['status'] == 'inactive':
        ret['result'] = True
        ret['comment'] = 'Plugin already deactivated: {0}'.format(name)
        return ret
    elif __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Plugin will be deactivated: {0}'.format(name)
        return ret

    resp = __salt__['wordpress.deactivate'](name, path, user)
    if resp is True:
        ret['result'] = True
        ret['comment'] = 'Plugin deactivated: {0}'.format(name)
        ret['changes'] = {
            'old': check,
            'new': __salt__['wordpress.show_plugin'](name, path, user)
        }
    elif resp is None:
        ret['result'] = True
        ret['comment'] = 'Plugin already deactivated: {0}'.format(name)
        ret['changes'] = {
            'old': check,
            'new': __salt__['wordpress.show_plugin'](name, path, user)
        }
    else:
        ret['comment'] = 'Plugin failed to deactivate: {0}'.format(name)

    return ret
