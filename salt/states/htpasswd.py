# -*- coding: utf-8 -*-
'''
Support for htpasswd module. Requires the apache2-utils package for Debian-based distros.

.. versionadded:: 2014.7.0

.. code-block:: yaml

    username:
      webutil.user_exists:
        - password: secr3t
        - htpasswd_file: /etc/nginx/htpasswd
        - options: d
        - force: true

'''
from __future__ import absolute_import
import salt.utils


__virtualname__ = 'webutil'


def __virtual__():
    '''
    depends on webutil module
    '''

    return __virtualname__ if salt.utils.which('htpasswd') else False


def user_exists(name, password=None, htpasswd_file=None, options='',
                force=False, runas=None):
    '''
    Make sure the user is inside the specified htpasswd file

    name
        User name

    password
        User password

    htpasswd_file
        Path to the htpasswd file

    options
        See :mod:`salt.modules.htpasswd.useradd`

    force
        Touch the file even if user already created

    runas
        The system user to run htpasswd command with

    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': None}

    grep = __salt__['file.grep']
    grep_ret = grep(htpasswd_file, name)
    if grep_ret['retcode'] != 0 or force:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('User {0!r} is set to be added to htpasswd '
                              'file').format(name)
            ret['changes'] = {name: True}
            return ret

        useradd_ret = __salt__['webutil.useradd_all'](htpasswd_file, name,
                                                      password, opts=options,
                                                      runas=runas)
        if useradd_ret['retcode'] == 0:
            ret['result'] = True
            ret['comment'] = useradd_ret['stderr']
            ret['changes'] = {name: True}
            return ret
        else:
            ret['result'] = False
            ret['comment'] = useradd_ret['stderr']
            return ret

    if __opts__['test'] and ret['changes']:
        ret['result'] = None
    else:
        ret['result'] = True
    ret['comment'] = 'User already known'
    return ret
