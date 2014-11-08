# -*- coding: utf-8 -*-
'''
lxc / Spin up and control LXC containers
=========================================
'''

from __future__ import absolute_import
__docformat__ = 'restructuredtext en'
import traceback

# Import salt libs
from salt.exceptions import CommandExecutionError, SaltInvocationError


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


def created(name,
            template=None,
            image=None,
            config=None,
            profile=None,
            fstype=None,
            size=None,
            backing=None,
            vgname=None,
            lvname=None):
    '''
    Create a container using a template

    name
        The name of the container to be created

    template
        The template from which to create the container. Conflicts with the
        ``image`` argument

    image
        .. versionadded:: 2014.7.1

        A tar archive to use as the rootfs for the container. Conflicts with
        the ``template`` argument.

    config
        .. versionadded:: 2014.7.1

        The config file to use for the container. Defaults to system-wide
        config (usually in /etc/lxc/lxc.conf). Helpful when combined with the
        ``image`` argument to deploy a pre-configured LXC image.

        .. warning::

            Use with care when combining with the ``template`` argument.

    profile
        Profile to use in container creation (see the :ref:`LXC Tutorial
        <lxc-tutorial-profiles>` for more information). Values in a profile
        will be overridden by the parameters listed below.

    fstype
        Which fstype to use

    size
        Size of container

    backing
        Filesystem backing

        None
           Filesystem
        lvm
           lv
        brtfs
           brtfs

    vgname
        If LVM, which volume group

    lvname
        If LVM, which logical volume


    .. code-block:: yaml

        mycreation:
          lxc.created:
            - name: my_instance_1
            - backing: lvm
            - size: 1G
            - template: ubuntu

        from_ubuntu_profile:
          lxc.created:
            - name: my_instance_2
            - profile: ubuntu

        from_ubuntu_profile_2:
          lxc.created:
            - name: my_instance_3
            - profile:
                name: ubuntu
                lvname: instance3

    .. versionchanged:: 2014.7.1
        For ease of use, profiles like the ones in the
        ``from_ubuntu_profile_2`` example above can be configured with a
        leading dash before each parameter. For example:

    .. code-block:: yaml

        from_ubuntu_profile_2:
          lxc.created:
            - name: my_instance_3
            - profile:
              - name: ubuntu
              - lvname: instance3
    '''
    ret = {'name': name,
           'result': True,
           'comment': 'Container \'{0}\' already exists'.format(name),
           'changes': {}}
    exists = __salt__['lxc.exists'](name)
    if exists:
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Container \'{0}\' will be created'.format(name)
        return ret

    try:
        __salt__['lxc.create'](
            name=name,
            template=template,
            image=image,
            config=config,
            profile=profile,
            fstype=fstype,
            vgname=vgname,
            size=size,
            lvname=lvname,
            backing=backing,
        )
    except (CommandExecutionError, SaltInvocationError) as exc:
        ret['result'] = False
        ret['comment'] = '{0}'.format(exc)
    else:
        ret['comment'] = 'Created container \'{0}\''.format(name)
        ret['changes']['status'] = 'created'
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
