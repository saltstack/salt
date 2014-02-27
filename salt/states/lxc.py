#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
lxc / Spin up and control LXC containers
=========================================
'''
__docformat__ = 'restructuredtext en'
import difflib
import datetime
import traceback
import subprocess
import pipes


def absent(name):
    '''Destroy a container

    name
        id of the container to destroy

    .. code-block:: yaml

        destroyer:
          lxc.absent:
            - name: my_instance_name2

    '''
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
        except Exception, ex:
            trace = traceback.format_exc()
            ret['result'] = False
            ret['comment'] = 'Error in container removal'
            changes['msg'] = '{1}\n{0}\n'.format(ex, trace)
        return ret
    return ret


def stopped(name):
    '''Stop a container

    name
        id of the container to stop

    .. code-block:: yaml

        sleepingcontainer:
          lxc.stopped:
            - name: my_instance_name2

    '''
    changes = {}
    exists = __salt__['lxc.exists'](name)
    ret = {'name': name, 'changes': changes,
           'result': True, 'comment': 'Stopped'}
    if not exists:
        ret = {'name': name, 'changes': {},
               'result': True, 'comment': 'Container does not exists'}
    if exists:
        ret['result'] = False
        infos = __salt__['lxc.info'](name)
        try:
            if infos['state'] == 'running':
                __salt__['lxc.stop'](name)
                ret['changes'] = {name: 'stopped'}
            infos = __salt__['lxc.info'](name)
            ret['result'] = infos['state'] != 'running'
            if not ret['result']:
                raise Exception('Container won\'t stop')
        except Exception, ex:
            trace = traceback.format_exc()
            ret['result'] = False
            ret['comment'] = 'Error in stopping container'
            changes['msg'] = '{1}\n{0}\n'.format(ex, trace)
        return ret
    return ret


def started(name, force=False):
    '''Start a container

    name
        id of the container to start
    force
        force reboot

    .. code-block:: yaml

        destroyer:
          lxc.started:
            - name: my_instance_name2

    '''
    changes = {}
    exists = __salt__['lxc.exists'](name)
    ret = {'name': name, 'changes': changes,
           'result': True, 'comment': 'Started'}
    if not exists:
        ret = {'name': name, 'changes': {},
               'result': True, 'comment': 'Container does not exists'}
    if exists:
        if force:
            stopped(name)
        ret['result'] = False
        infos = __salt__['lxc.info'](name)
        try:
            if infos['state'] != 'running':
                __salt__['lxc.start'](name)
                ret['changes'] = {name: 'started'}
            infos = __salt__['lxc.info'](name)
            ret['result'] = infos['state'] == 'running'
            if not ret['result']:
                ret['comment'] = 'Container won\'t start'
        except Exception, ex:
            trace = traceback.format_exc()
            ret['result'] = False
            ret['comment'] = 'Error in starting container'
            ret['comment'] += '{0}\n{1}\n'.format(ex, trace)
        return ret
    return ret


def edited_conf(name, lxc_conf, lxc_conf_unset):
    '''Edit LXC configuration options

    .. code-block:: bash

        setconf:
          lxc.edited_conf:
            - name: ubuntu
            - lxc_conf:
                - network.ipv4.ip: 10.0.3.6
            - lxc_conf_unset:
                - lxc.utsname
    '''
    cret = __salt__['lxc.update_lxc_conf'](name,
                                           lxc_conf=lxc_conf,
                                           lxc_conf_unset=lxc_conf_unset)
    cret['name'] = name
    return cret


def set_pass(name, password=None, user=None, users=None):
    '''Set the password of system users inside containers

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
    if not isinstance(users, list):
        users = [users]
    if user and (not user in users):
        users.append(user)
    cret = __salt__['lxc.set_pass'](name, users, password)
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
    '''Create a container using a template

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
        Wich backing
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
    '''Clone a container

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


def present(name,
            from_container=None,
            template='ubuntu',
            vgname=None,
            backing=None,
            snapshot=True,
            profile=None,
            fstype=None,
            lvname=None,
            ip=None,
            mac=None,
            netmask='24',
            bridge='lxcbr0',
            gateway='10.0.3.1',
            size='10G',
            lxc_conf_unset=None,
            lxc_conf=None,
            stopped=False,
            master=None,
            script=None,
            script_args=None,
            users=None,
            user='ubuntu',
            password='ubuntu',
            *args, **kw):

    '''
    Provision a single container

    This do not use lxc.init to provide a more generic fashion to tie minions
    to their master (if any and defined) to allow custom association code.

    Idea is whenever your lxc is accessible via ssh, you give it a script +
    params ALA salt cloud to make the association

    Order of operation

        - Spin up the lxc template container using salt.modules.lxc
          on desired minion (clone or template)
        - Change lxc config option if any to be changed
        - Start container
        - Change base passwords if any
        - Wait for lxc container to be up and ready for ssh
        - Test ssh connection and bailout in error
        - Generate seeds
        - Via ssh (with the help of salt cloud):

            - Upload deploy script and seeds
            - Run the script with args inside the context of the container

        - Ping the result minion

            - if ok:

                - Remove the authorized key path
                - Restart the container

            - else bailout in error

    name
        Name of the container
    profile
        lxc pillar profile
    Container creation/clone options
        Use a container using clone
            from_container
                Name of an original container using clone
            snapshot
                Do we use snapshots on cloned filesystems
        lxc template using total creation
            template
                template to use
            backing
                Backing store type (None, lvm, brtfs)
            lvname
                LVM lvname if any
            fstype
                fstype
        Common
            size
                Size of the container
            vgname
                LVM vgname if any
    users
        sysadmin users [ubuntu] of the container
    user
        sysadmin user (ubuntu) of the container
    password
        password for root and sysadmin (ubuntu)
    mac
        mac address to associate
    ip
        ip to link to
    netmask
        netmask for ip
    bridge
        bridge to use
    lxc_conf_unset
        Configuration variables to unset in lxc conf
    lxc_conf
        LXC configuration variables to set in lxc_conf
    master
        Master to link to if any
    '''
    changes = {}
    changed = False
    ret = {'name': name, 'changes': changes, 'result': None, 'comment': ''}
    if not users:
        users = ['root']
        if (
            __grains__['os'] in ['Ubuntu']
            and not 'ubuntu' in users
        ):
            users.append('ubuntu')
    if not user in users:
        users.append(user)
    if not users:
        users = []
    if not lxc_conf:
        lxc_conf = []
    if not lxc_conf_unset:
        lxc_conf_unset = []
    if from_container:
        method = 'clone'
    else:
        method = 'create'
    if ip is not None:
        lxc_conf.append({'lxc.network.ipv4': '{0}/{1}'.format(ip, netmask)})
    if mac is not None:
        lxc_conf.append({'lxc.network.hwaddr': mac})
    if gateway is not None:
        lxc_conf.append({'lxc.network.ipv4.gateway': gateway})
    if bridge is not None:
        lxc_conf.append({'lxc.network.link': bridge})
    changes['a_creation'] = ''
    if method == 'clone':
        cret = cloned(
            name=name,
            orig=from_container,
            snapshot=snapshot,
            size=size,
            vgname=vgname,
            profile=profile,
        )
    elif method == 'create':
        cret = created(
            name=name,
            template=template,
            profile=profile,
            fstype=fstype,
            vgname=vgname,
            size=size,
            lvname=lvname,
            backing=backing,
        )
    if not cret['result']:
        ret['result'] = False
        ret['comment'] = cret['comment']
        return ret
    if cret['changes']:
        changed = True
    changes['a_creation'] = cret['comment']

    # edit lxc conf if any
    changes['b_conf'] = ''
    cret = edited_conf(name, lxc_conf, lxc_conf_unset)
    if not cret['result']:
        ret['result'] = False
        ret['comment'] = cret['comment']
        return ret
    if cret['changes']:
        changed = True
    changes['b_conf'] = 'lxc conf ok'

    # start
    changes['c_start'] = ''
    # reboot if conf has changed
    cret = started(name, force=changed)
    if not cret['result']:
        ret['result'] = False
        ret['comment'] = cret['comment']
        return ret
    if cret['changes']:
        changed = True
    changes['c_start'] = 'started'

    # first time provisionning only, set the default user/password
    changes['d_password'] = 'Password in place'
    gid = 'lxc.{0}.initial_pass'.format(name, False)
    if not __grains__.get(gid):
        cret = set_pass(name, password=password, users=users)
        if not cret['result']:
            ret['result'] = False
            ret['comment'] = cret['comment']
            return ret
        if __salt__['grains.setval'](gid, True):
            __salt__['saltutil.sync_grains']()
        changes['d_password'] = 'Password updated'
        changed = True
    return ret


# vim:set et sts=4 ts=4 tw=80:
