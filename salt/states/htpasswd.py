# -*- coding: utf-8 -*-
'''
Support for htpasswd module

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
                force=False, **kwargs):
    '''
    Make sure the user is inside the ``/etc/nginx/htpasswd``

    ``name``
        username

    ``password``
        password of the user

    ``htpasswd_file``
        path to the file that htpasswd will handle

    ``options``
        see :mod:`salt.module.htpasswd.useradd`

    ``force``
        touch the file even if user already created
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': None}
    useradd = __salt__['webutil.useradd_all']
    grep = __salt__['file.grep']
    grep_ret = grep(htpasswd_file, name)
    if grep_ret['retcode'] != 0 or force:
        useradd_ret = useradd(htpasswd_file, name, password, opts=options)
        if useradd_ret['retcode'] == 0:
            ret['result'] = True
            ret['comment'] = useradd_ret['stderr']
            ret['changes'] = {name: True}
            return ret
        else:
            ret['result'] = False
            ret['comment'] = useradd_ret['stderr']
            return ret
    ret['result'] = True
    ret['comment'] = 'User already known'
    return ret
