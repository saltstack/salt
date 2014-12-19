# -*- coding: utf-8 -*-
'''
lxc / Spin up and control LXC containers
=========================================
'''

from __future__ import absolute_import
__docformat__ = 'restructuredtext en'
import traceback


def absent(name):
    '''
    Destroy a container

    name
        id of the container to destroy

    .. code-block:: yaml

        destroyer:
          lxc.absent:
            - name: my_instance_name2

    '''
    if __opts__['test']:
        return {'name': name,
                'comment': '{0} will be removed'.format(name),
                'result': True,
                'changes': {}}
    changes = {}
    exists = __salt__['lxc.exists'](name)
    ret = {'name': name, 'changes': changes,
           'result': True, 'comment': 'Absent'}
    if exists:
        ret['result'] = False
        infos = __salt__['lxc.info'](name)
        try:
            if infos['state'] == 'running':
                cret = __salt__['lxc.stop'](name)
                infos = __salt__['lxc.infos'](name)
            if infos['state'] == 'running':
                raise Exception('Container won\'t stop')
            cret = __salt__['lxc.destroy'](name)
            if not cret.get('change', False):
                raise Exception('Container was not destroy')
            ret['result'] = not __salt__['lxc.exists'](name)
            if not ret['result']:
                raise Exception('Container won`t destroy')
        except Exception as ex:
            trace = traceback.format_exc()
            ret['result'] = False
            ret['comment'] = 'Error in container removal'
            changes['msg'] = '{1}\n{0}\n'.format(ex, trace)
        return ret
    return ret


def stopped(name):
    '''
    Stop a container

    name
        id of the container to stop

    .. code-block:: yaml

        sleepingcontainer:
          lxc.stopped:
            - name: my_instance_name2

    '''
    if __opts__['test']:
        return {'name': name,
                'comment': '{0} will be stopped'.format(name),
                'result': True,
                'changes': {}}
    cret = __salt__['lxc.stop'](name)
    cret['name'] = name
    return cret


def started(name, restart=False):
    '''
    Start a container

    name
        id of the container to start
    force
        force reboot

    .. code-block:: yaml

        destroyer:
          lxc.started:
            - name: my_instance_name2

    '''
    if __opts__['test']:
        return {'name': name,
                'comment': '{0} will be started'.format(name),
                'result': True,
                'changes': {}}
    cret = __salt__['lxc.start'](name, restart=restart)
    cret['name'] = name
    return cret


def edited_conf(name, lxc_conf=None, lxc_conf_unset=None):
    '''
    Edit LXC configuration options

    .. code-block:: bash

        setconf:
          lxc.edited_conf:
            - name: ubuntu
            - lxc_conf:
                - network.ipv4.ip: 10.0.3.6
            - lxc_conf_unset:
                - lxc.utsname
    '''
    if __opts__['test']:
        return {'name': name,
                'comment': '{0} lxc.conf will be edited'.format(name),
                'result': True,
                'changes': {}}
    if not lxc_conf_unset:
        lxc_conf_unset = {}
    if not lxc_conf:
        lxc_conf = {}
    cret = __salt__['lxc.update_lxc_conf'](name,
                                           lxc_conf=lxc_conf,
                                           lxc_conf_unset=lxc_conf_unset)
    cret['name'] = name
    return cret


def set_pass(name, password=None, user=None, users=None):
    '''
    Set the password of system users inside containers

    name
        id of the container to act on
    user
        user to set password
    users
        users to set password to

    .. code-block:: yaml

        setpass:
          lxc.stopped:
            - name: my_instance_name2
            - password: s3cret
            - user: foo

    .. code-block:: yaml

        setpass2:
          lxc.stopped:
            - name: my_instance_name2
            - password: s3cret
            - users:
              - foo
              - bar
    '''
    if __opts__['test']:
        return {'name': name,
                'comment': 'Passwords for {0} will be udpated'.format(name),
                'result': True,
                'changes': {}}
    if not isinstance(users, list):
        users = [users]
    if user and (user not in users):
        users.append(user)
    cret = __salt__['lxc.set_pass'](name, users=users, password=password)
    cret['changes'] = {}
    cret['name'] = name
    return cret


def created(name,
            template='ubuntu',
            profile=None,
            fstype=None,
            size=None,
            backing=None,
            vgname=None,
            lvname=None):
    '''
    Create a container using a template

    name
        id of the container to act on
    template
        template to create from
    profile
        pillar lxc profile
    fstype
        fstype to use
    size
        Which size
    backing
        Which backing

        None
           Filesystem
        lvm
           lv
        brtfs
           brtfs
    vgname
        If LVM, which volume group
    lvname
        If LVM, which lv


    .. code-block:: yaml

        mycreation:
          lxc.created:
            - name: my_instance_name2
            - backing: lvm
            - size: 1G
            - template: ubuntu

    '''
    if __opts__['test']:
        return {'name': name,
                'result': True,
                'comment': '{0} will be created'.format(name),
                'changes': {}}
    changes = {}
    ret = {'name': name, 'changes': changes, 'result': True, 'comment': ''}
    exists = __salt__['lxc.exists'](name)
    if exists:
        ret['comment'] = 'Container already exists'
    else:
        cret = __salt__['lxc.create'](
            name=name,
            template=template,
            profile=profile,
            fstype=fstype,
            vgname=vgname,
            size=size,
            lvname=lvname,
            backing=backing,
        )
        if cret.get('error', ''):
            ret['result'] = False
            ret['comment'] = cret['error']
        else:
            exists = (
                cret['created']
                or 'already exists' in cret.get('comment', ''))
            ret['comment'] += 'Container created\n'
            ret['changes']['status'] = 'Created'
    return ret


def cloned(name,
           orig,
           snapshot=True,
           size=None,
           vgname=None,
           profile=None):
    '''
    Clone a container

    name
        id of the container to clone to
    orig
        id of the container to clone from
    snapshot
        do we use snapshots
    size
        Which size
    vgname
        If LVM, which volume group
    profile
        pillar lxc profile

    .. code-block:: yaml

        myclone:
          lxc.cloned:
            - name: my_instance_name2
            - orig: ubuntu
            - vgname: lxc
            - snapshot: true
    '''
    if __opts__['test']:
        return {'name': name,
                'comment': '{0} will be cloned from {1}'.format(
                    name, orig),
                'result': True,
                'changes': {}}
    changes = {}
    ret = {'name': name, 'changes': changes, 'result': True, 'comment': ''}
    exists = __salt__['lxc.exists'](name)
    oexists = __salt__['lxc.exists'](orig)
    if exists:
        ret['comment'] = 'Container already exists'
    elif not oexists:
        ret['result'] = False
        ret['comment'] = (
            'container could not be cloned: {0}, '
            '{1} does not exists'.format(name, orig))
    else:
        cret = __salt__['lxc.clone'](
            name=name,
            orig=orig,
            snapshot=snapshot,
            size=size,
            vgname=vgname,
            profile=profile,
        )
        if cret.get('error', ''):
            ret['result'] = False
            ret['comment'] = '{0}\n{1}'.format(
                cret['error'], 'Container cloning error')
        else:
            ret['result'] = (
                cret['cloned'] or 'already exists' in cret.get('comment', ''))
            ret['comment'] += 'Container cloned\n'
            changes['status'] = 'cloned'
    return ret
