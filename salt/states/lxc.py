# -*- coding: utf-8 -*-
'''
Manage Linux Containers
=======================
'''

from __future__ import absolute_import
__docformat__ = 'restructuredtext en'

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, SaltInvocationError


# Container existence/non-existence
def present(name,
            running=None,
            clone_from=None,
            snapshot=False,
            profile=None,
            network_profile=None,
            template=None,
            options=None,
            image=None,
            config=None,
            fstype=None,
            size=None,
            backing=None,
            vgname=None,
            lvname=None,
            path=None):
    '''
    .. versionchanged:: 2015.8.0

        The :mod:`lxc.created <salt.states.lxc.created>` state has been renamed
        to ``lxc.present``, and the :mod:`lxc.cloned <salt.states.lxc.cloned>`
        state has been merged into this state.

    Create the named container if it does not exist

    name
        The name of the container to be created

    path
        path to the container parent
        default: /var/lib/lxc (system default)

        .. versionadded:: 2015.8.0


    running : False
        * If ``True``, ensure that the container is running
        * If ``False``, ensure that the container is stopped
        * If ``None``, do nothing with regards to the running state of the
          container

        .. versionadded:: 2015.8.0

    clone_from
        Create named container as a clone of the specified container

    snapshot : False
        Use Copy On Write snapshots (LVM). Only supported with ``clone_from``.

    profile
        Profile to use in container creation (see the :ref:`LXC Tutorial
        <tutorial-lxc-profiles-container>` for more information). Values in a
        profile will be overridden by the parameters listed below.

    network_profile
        Network Profile to use in container creation
        (see the :ref:`LXC Tutorial <tutorial-lxc-profiles-container>`
        for more information). Values in a profile will be overridden by
        the parameters listed below.

        .. versionadded:: 2015.5.2

    **Container Creation Arguments**

    template
        The template to use. E.g., 'ubuntu' or 'fedora'. Conflicts with the
        ``image`` argument.

        .. note::

            The ``download`` template requires the following three parameters
            to be defined in ``options``:

            * **dist** - The name of the distribution
            * **release** - Release name/version
            * **arch** - Architecture of the container

            The available images can be listed using the :mod:`lxc.images
            <salt.modules.lxc.images>` function.

    options

        .. versionadded:: 2015.5.0

        Template-specific options to pass to the lxc-create command. These
        correspond to the long options (ones beginning with two dashes) that
        the template script accepts. For example:

        .. code-block:: yaml

            web01:
              lxc.present:
                - template: download
                - options:
                    dist: centos
                    release: 6
                    arch: amd64

        Remember to double-indent the options, due to :ref:`how PyYAML works
        <nested-dict-indentation>`.

    image
        A tar archive to use as the rootfs for the container. Conflicts with
        the ``template`` argument.

    backing
        The type of storage to use. Set to ``lvm`` to use an LVM group.
        Defaults to filesystem within /var/lib/lxc.

    fstype
        Filesystem type to use on LVM logical volume

    size
        Size of the volume to create. Only applicable if ``backing`` is set to
        ``lvm``.

    vgname : lxc
        Name of the LVM volume group in which to create the volume for this
        container. Only applicable if ``backing`` is set to ``lvm``.

    lvname
        Name of the LVM logical volume in which to create the volume for this
        container. Only applicable if ``backing`` is set to ``lvm``.
    '''
    ret = {'name': name,
           'result': True,
           'comment': 'Container \'{0}\' already exists'.format(name),
           'changes': {}}

    if not any((template, image, clone_from)):
        # Take a peek into the profile to see if there is a clone source there.
        # Otherwise, we're assuming this is a template/image creation. Also
        # check to see if none of the create types are in the profile. If this
        # is the case, then bail out early.
        c_profile = __salt__['lxc.get_container_profile'](profile)
        if not any(x for x in c_profile
                   if x in ('template', 'image', 'clone_from')):
            ret['result'] = False
            ret['comment'] = ('No template, image, or clone_from parameter '
                              'was found in either the state\'s arguments or '
                              'the LXC profile')
        else:
            try:
                # Assign the profile's clone_from param to the state, so that
                # we know to invoke lxc.clone to create the container.
                clone_from = c_profile['clone_from']
            except KeyError:
                pass

    # Sanity check(s)
    if clone_from and not __salt__['lxc.exists'](clone_from, path=path):
        ret['result'] = False
        ret['comment'] = ('Clone source \'{0}\' does not exist'
                          .format(clone_from))
    if not ret['result']:
        return ret

    action = 'cloned from {0}'.format(clone_from) if clone_from else 'created'

    state = {'old': __salt__['lxc.state'](name, path=path)}
    if __opts__['test']:
        if state['old'] is None:
            ret['comment'] = (
                'Container \'{0}\' will be {1}'.format(
                    name,
                    'cloned from {0}'.format(clone_from) if clone_from
                    else 'created')
            )
            ret['result'] = None
            return ret
        else:
            if running is None:
                # Container exists and we're not managing whether or not it's
                # running. Set the result back to True and return
                return ret
            elif running:
                if state['old'] in ('frozen', 'stopped'):
                    ret['comment'] = (
                        'Container \'{0}\' would be {1}'.format(
                            name,
                            'unfrozen' if state['old'] == 'frozen'
                                else 'started'
                        )
                    )
                    ret['result'] = None
                    return ret
                else:
                    ret['comment'] += ' and is running'
                    return ret
            else:
                if state['old'] in ('frozen', 'running'):
                    ret['comment'] = (
                        'Container \'{0}\' would be stopped'.format(name)
                    )
                    ret['result'] = None
                    return ret
                else:
                    ret['comment'] += ' and is stopped'
                    return ret

    if state['old'] is None:
        # Container does not exist
        try:
            if clone_from:
                result = __salt__['lxc.clone'](name,
                                               clone_from,
                                               profile=profile,
                                               network_profile=network_profile,
                                               snapshot=snapshot,
                                               size=size,
                                               path=path,
                                               backing=backing)
            else:
                result = __salt__['lxc.create'](
                    name,
                    profile=profile,
                    network_profile=network_profile,
                    template=template,
                    options=options,
                    image=image,
                    config=config,
                    fstype=fstype,
                    size=size,
                    backing=backing,
                    vgname=vgname,
                    path=path,
                    lvname=lvname)
        except (CommandExecutionError, SaltInvocationError) as exc:
            ret['result'] = False
            ret['comment'] = exc.strerror
        else:
            if clone_from:
                ret['comment'] = ('Cloned container \'{0}\' as \'{1}\''
                                  .format(clone_from, name))
            else:
                ret['comment'] = 'Created container \'{0}\''.format(name)
            state['new'] = result['state']['new']

    if ret['result'] is True:
        # Enforce the "running" parameter
        if running is None:
            # Don't do anything
            pass
        elif running:
            c_state = __salt__['lxc.state'](name, path=path)
            if c_state == 'running':
                ret['comment'] += ' and is running'
            else:
                error = ', but it could not be started'
                try:
                    start_func = 'lxc.unfreeze' if c_state == 'frozen' \
                        else 'lxc.start'
                    state['new'] = __salt__[start_func](
                        name, path=path
                    )['state']['new']
                    if state['new'] != 'running':
                        ret['result'] = False
                        ret['comment'] += error
                except (SaltInvocationError, CommandExecutionError) as exc:
                    ret['result'] = False
                    ret['comment'] += '{0}: {1}'.format(error, exc)
                else:
                    if state['old'] is None:
                        ret['comment'] += ', and the container was started'
                    else:
                        ret['comment'] = (
                            'Container \'{0}\' was {1}'.format(
                                name,
                                'unfrozen' if state['old'] == 'frozen'
                                    else 'started'
                            )
                        )

        else:
            c_state = __salt__['lxc.state'](name, path=path)
            if c_state == 'stopped':
                if state['old'] is not None:
                    ret['comment'] += ' and is stopped'
            else:
                error = ', but it could not be stopped'
                try:
                    state['new'] = __salt__['lxc.stop'](
                        name, path=path
                    )['state']['new']
                    if state['new'] != 'stopped':
                        ret['result'] = False
                        ret['comment'] += error
                except (SaltInvocationError, CommandExecutionError) as exc:
                    ret['result'] = False
                    ret['comment'] += '{0}: {1}'.format(error, exc)
                else:
                    if state['old'] is None:
                        ret['comment'] += ', and the container was stopped'
                    else:
                        ret['comment'] = ('Container \'{0}\' was stopped'
                                          .format(name))

    if 'new' not in state:
        # Make sure we know the final state of the container before we return
        state['new'] = __salt__['lxc.state'](name, path=path)
    if state['old'] != state['new']:
        ret['changes']['state'] = state
    return ret


def absent(name, stop=False, path=None):
    '''
    Ensure a container is not present, destroying it if present

    name
        Name of the container to destroy

    stop
        stop before destroying
        default: false

        .. versionadded:: 2015.5.2

    path
        path to the container parent
        default: /var/lib/lxc (system default)

        .. versionadded:: 2015.8.0


    .. code-block:: yaml

        web01:
          lxc.absent
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Container \'{0}\' does not exist'.format(name)}

    if not __salt__['lxc.exists'](name, path=path):
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Container \'{0}\' would be destroyed'.format(name)
        return ret

    try:
        result = __salt__['lxc.destroy'](name, stop=stop, path=path)
    except (SaltInvocationError, CommandExecutionError) as exc:
        ret['result'] = False
        ret['comment'] = 'Failed to destroy container: {0}'.format(exc)
    else:
        ret['changes']['state'] = result['state']
        ret['comment'] = 'Container \'{0}\' was destroyed'.format(name)
    return ret


# Container state (running/frozen/stopped)
def running(name, restart=False, path=None):
    '''
    .. versionchanged:: 2015.5.0
        The :mod:`lxc.started <salt.states.lxc.started>` state has been renamed
        to ``lxc.running``

    Ensure that a container is running

    .. note::

        This state does not enforce the existence of the named container, it
        just starts the container if it is not running. To ensure that the
        named container exists, use :mod:`lxc.present
        <salt.states.lxc.present>`.

    name
        The name of the container

    path
        path to the container parent
        default: /var/lib/lxc (system default)

        .. versionadded:: 2015.8.0

    restart : False
        Restart container if it is already running

    .. code-block:: yaml

        web01:
          lxc.running

        web02:
          lxc.running:
            - restart: True
    '''
    ret = {'name': name,
           'result': True,
           'comment': 'Container \'{0}\' is already running'.format(name),
           'changes': {}}

    state = {'old': __salt__['lxc.state'](name, path=path)}
    if state['old'] is None:
        ret['result'] = False
        ret['comment'] = 'Container \'{0}\' does not exist'.format(name)
        return ret
    elif state['old'] == 'running' and not restart:
        return ret
    elif state['old'] == 'stopped' and restart:
        # No need to restart since container is not running
        restart = False

    if restart:
        if state['old'] != 'stopped':
            action = ('restart', 'restarted')
        else:
            action = ('start', 'started')
    else:
        if state['old'] == 'frozen':
            action = ('unfreeze', 'unfrozen')
        else:
            action = ('start', 'started')

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('Container \'{0}\' would be {1}'
                          .format(name, action[1]))
        return ret

    try:
        if state['old'] == 'frozen' and not restart:
            result = __salt__['lxc.unfreeze'](name, path=path)
        else:
            if restart:
                result = __salt__['lxc.restart'](name, path=path)
            else:
                result = __salt__['lxc.start'](name, path=path)
    except (CommandExecutionError, SaltInvocationError) as exc:
        ret['result'] = False
        ret['comment'] = exc.strerror
        state['new'] = __salt__['lxc.state'](name, path=path)
    else:
        state['new'] = result['state']['new']
        if state['new'] != 'running':
            ret['result'] = False
            ret['comment'] = ('Unable to {0} container \'{1}\''
                              .format(action[0], name))
        else:
            ret['comment'] = ('Container \'{0}\' was successfully {1}'
                              .format(name, action[1]))
        try:
            ret['changes']['restarted'] = result['restarted']
        except KeyError:
            pass

    if state['old'] != state['new']:
        ret['changes']['state'] = state
    return ret


def frozen(name, start=True, path=None):
    '''
    .. versionadded:: 2015.5.0

    Ensure that a container is frozen

    .. note::

        This state does not enforce the existence of the named container, it
        just freezes the container if it is running. To ensure that the named
        container exists, use :mod:`lxc.present <salt.states.lxc.present>`.

    name
        The name of the container

    path
        path to the container parent
        default: /var/lib/lxc (system default)

        .. versionadded:: 2015.8.0


    start : True
        Start container first, if necessary. If ``False``, then this state will
        fail if the container is not running.

    .. code-block:: yaml

        web01:
          lxc.frozen

        web02:
          lxc.frozen:
            - start: False
    '''
    ret = {'name': name,
           'result': True,
           'comment': 'Container \'{0}\' is already frozen'.format(name),
           'changes': {}}

    state = {'old': __salt__['lxc.state'](name, path=path)}
    if state['old'] is None:
        ret['result'] = False
        ret['comment'] = 'Container \'{0}\' does not exist'.format(name)
    elif state['old'] == 'stopped' and not start:
        ret['result'] = False
        ret['comment'] = 'Container \'{0}\' is stopped'.format(name)

    if ret['result'] is False or state['old'] == 'frozen':
        return ret

    if state['old'] == 'stopped':
        action = ('start and freeze', 'started and frozen')
    else:
        action = ('freeze', 'frozen')

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('Container \'{0}\' would be {1}'
                          .format(name, action[1]))
        return ret

    try:
        result = __salt__['lxc.freeze'](name, start=start, path=path)
    except (CommandExecutionError, SaltInvocationError) as exc:
        ret['result'] = False
        ret['comment'] = exc.strerror
        state['new'] = __salt__['lxc.state'](name, path=path)
    else:
        state['new'] = result['state']['new']
        if state['new'] != 'frozen':
            ret['result'] = False
            ret['comment'] = ('Unable to {0} container \'{1}\''
                              .format(action[0], name))
        else:
            ret['comment'] = ('Container \'{0}\' was successfully {1}'
                              .format(name, action[1]))
        try:
            ret['changes']['started'] = result['started']
        except KeyError:
            pass

    if state['old'] != state['new']:
        ret['changes']['state'] = state
    return ret


def stopped(name, kill=False, path=None):
    '''
    Ensure that a container is stopped

    .. note::

        This state does not enforce the existence of the named container, it
        just stops the container if it running or frozen. To ensure that the
        named container exists, use :mod:`lxc.present
        <salt.states.lxc.present>`, or use the :mod:`lxc.absent
        <salt.states.lxc.absent>` state to ensure that the container does not
        exist.

    name
        The name of the container

    path
        path to the container parent
        default: /var/lib/lxc (system default)

        .. versionadded:: 2015.8.0

    kill : False
        Do not wait for the container to stop, kill all tasks in the container.
        Older LXC versions will stop containers like this irrespective of this
        argument.

        .. versionadded:: 2015.5.0

    .. code-block:: yaml

        web01:
          lxc.stopped
    '''
    ret = {'name': name,
           'result': True,
           'comment': 'Container \'{0}\' is already stopped'.format(name),
           'changes': {}}

    state = {'old': __salt__['lxc.state'](name, path=path)}
    if state['old'] is None:
        ret['result'] = False
        ret['comment'] = 'Container \'{0}\' does not exist'.format(name)
        return ret
    elif state['old'] == 'stopped':
        return ret

    if kill:
        action = ('force-stop', 'force-stopped')
    else:
        action = ('stop', 'stopped')

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('Container \'{0}\' would be {1}'
                          .format(name, action[1]))
        return ret

    try:
        result = __salt__['lxc.stop'](name, kill=kill, path=path)
    except (CommandExecutionError, SaltInvocationError) as exc:
        ret['result'] = False
        ret['comment'] = exc.strerror
        state['new'] = __salt__['lxc.state'](name, path=path)
    else:
        state['new'] = result['state']['new']
        if state['new'] != 'stopped':
            ret['result'] = False
            ret['comment'] = ('Unable to {0} container \'{1}\''
                              .format(action[0], name))
        else:
            ret['comment'] = ('Container \'{0}\' was successfully {1}'
                              .format(name, action[1]))

    if state['old'] != state['new']:
        ret['changes']['state'] = state
    return ret


# Deprecated states
def created(name, **kwargs):
    '''
    .. deprecated:: 2015.5.0
        Use :mod:`lxc.present <salt.states.lxc.present>`
    '''
    salt.utils.warn_until(
        'Carbon',
        'The lxc.created state has been renamed to lxc.present, please use '
        'lxc.present'
    )
    return present(name, **kwargs)


def started(name, path=None, restart=False):
    '''
    .. deprecated:: 2015.5.0
        Use :mod:`lxc.running <salt.states.lxc.running>`
    '''
    salt.utils.warn_until(
        'Carbon',
        'The lxc.started state has been renamed to lxc.running, please use '
        'lxc.running'
    )
    return running(name, restart=restart, path=path)


def cloned(name,
           orig,
           snapshot=True,
           size=None,
           vgname=None,
           path=None,
           profile=None):
    '''
    .. deprecated:: 2015.5.0
        Use :mod:`lxc.present <salt.states.lxc.present>`
    '''
    salt.utils.warn_until(
        'Carbon',
        'The lxc.cloned state has been merged into the lxc.present state. '
        'Please update your states to use lxc.present, with the '
        '\'clone_from\' argument set to the name of the clone source.'
    )
    return present(name,
                   clone_from=orig,
                   snapshot=snapshot,
                   size=size,
                   vgname=vgname,
                   path=path,
                   profile=profile)


def set_pass(name, **kwargs):  # pylint: disable=W0613
    '''
    .. deprecated:: 2015.5.0

    This state function has been disabled, as it did not conform to design
    guidelines. Specifically, due to the fact that :mod:`lxc.set_password
    <salt.modules.lxc.set_password>` uses ``chpasswd(8)`` to set the password,
    there was no method to make this action idempotent (in other words, the
    password would be changed every time). This makes this state redundant,
    since the following state will do the same thing:

    .. code-block:: yaml

        setpass:
          module.run:
            - name: set_pass
            - m_name: root
            - password: secret
    '''
    return {'name': name,
            'comment': 'The lxc.set_pass state is no longer supported. Please '
                       'see the LXC states documentation for further '
                       'information.',
            'result': False,
            'changes': {}}


def edited_conf(name, lxc_conf=None, lxc_conf_unset=None):
    '''
    .. warning::

        This state is unsuitable for setting parameters that appear more than
        once in an LXC config file, or parameters which must appear in a
        certain order (such as when configuring more than one network
        interface). It is slated to be replaced, and as of version 2015.5.0 it
        is deprecated.

    Edit LXC configuration options

    path
        path to the container parent
        default: /var/lib/lxc (system default)

        .. versionadded:: 2015.8.0


    .. code-block:: bash

        setconf:
          lxc.edited_conf:
            - name: ubuntu
            - lxc_conf:
                - network.ipv4.ip: 10.0.3.6
            - lxc_conf_unset:
                - lxc.utsname
    '''
    salt.utils.warn_until(
        'Carbon',
        'This state is unsuitable for setting parameters that appear more '
        'than once in an LXC config file, or parameters which must appear in '
        'a certain order (such as when configuring more than one network '
        'interface). It is slated to be replaced, and as of version 2015.5.0 '
        'it is deprecated.'
    )
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
