# -*- coding: utf-8 -*-
'''
This state module is used to manage Wordpress installations

:depends: wp binary from http://wp-cli.org/
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    return 'wordpress.show_plugin' in __salt__


def installed(name, user, admin_user, admin_password, admin_email, title, url):
    '''
    Run the initial setup of wordpress

    name
        path to the wordpress installation

    user
        user that owns the files for the wordpress installation

    admin_user
        username for wordpress website administrator user

    admin_password
        password for wordpress website administrator user

    admin_email
        email for wordpress website administrator user

    title
        title for the wordpress website

    url
        url for the wordpress website

    .. code-block:: yaml

        /var/www/html:
          wordpress.installed:
            - title: Daniel's Awesome Blog
            - user: apache
            - admin_user: dwallace
            - admin_email: dwallace@example.com
            - admin_password: password123
            - url: https://blog.dwallace.com
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}

    check = __salt__['wordpress.is_installed'](name, user)

    if check:
        ret['result'] = True
        ret['comment'] = 'Wordpress is already installed: {0}'.format(name)
        return ret
    elif __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Wordpress will be installed: {0}'.format(name)
        return ret

    resp = __salt__['wordpress.install'](name, user, admin_user, admin_password, admin_email, title, url)
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
    '''
    Activate wordpress plugins

    name
        name of plugin to activate

    path
        path to wordpress installation

    user
        user who should own the files in the wordpress installation

    .. code-block:: yaml

        HyperDB:
          wordpress.activated:
            - path: /var/www/html
            - user: apache
    '''
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
    '''
    Deactivate wordpress plugins

    name
        name of plugin to deactivate

    path
        path to wordpress installation

    user
        user who should own the files in the wordpress installation

    .. code-block:: yaml

        HyperDB:
          wordpress.deactivated:
            - path: /var/www/html
            - user: apache
    '''
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
