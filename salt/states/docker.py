# -*- coding: utf-8 -*-
'''
States to manage Docker containers, images, volumes, and networks

.. versionchanged:: Nitrogen
    The legacy Docker state and execution module have been removed, and the
    new modules (formerly called ``dockerng`` have taken their places).

.. important::
    As of the Nitrogen release, the states in this module have been separated
    into the following four state modules:

    - :mod:`docker_container <salt.states.docker_container>` - States to manage
      Docker containers
    - :mod:`docker_image <salt.states.docker_image>` - States to manage Docker
      images
    - :mod:`docker_volume <salt.states.docker_volume>` - States to manage
      Docker volumes
    - :mod:`docker_network <salt.states.docker_network>` - States to manage
      Docker networks

    The reason for this change was to make states and requisites more clear.
    For example, imagine this SLS:

    .. code-block:: yaml

        myuser/appimage:
          docker.image_present:
            - sls: docker.images.appimage

        myapp:
          docker.running:
            - image: myuser/appimage
            - require:
              - docker: myuser/appimage

    The new syntax would be:

    .. code-block:: yaml

        myuser/appimage:
          docker_image.present:
            - sls: docker.images.appimage

        myapp:
          docker_container.running:
            - image: myuser/appimage
            - require:
              - docker_image: myuser/appimage

    This is similar to how Salt handles MySQL, MongoDB, Zabbix, and other cases
    where the same execution module is used to manage several different kinds
    of objects (users, databases, roles, etc.).

    The old syntax will continue to work until the **Fluorine** release of
    Salt.
'''
from __future__ import absolute_import
import copy
import logging

# Import salt libs
import salt.utils

# Enable proper logging
log = logging.getLogger(__name__)  # pylint: disable=invalid-name

# Define the module's virtual name
__virtualname__ = 'docker'
__virtual_aliases__ = ('dockerng', 'moby')


def __virtual__():
    '''
    Only load if the docker execution module is available
    '''
    if 'docker.version' in __salt__:
        return __virtualname__
    return (False, __salt__.missing_fun_string('docker.version'))


def running(name, **kwargs):
    '''
    .. deprecated:: Nitrogen
        This state has been moved to :py:func:`docker_container.running
        <salt.states.docker_container.running>`.
    '''
    ret = __states__['docker_container.running'](
        name,
        **salt.utils.clean_kwargs(**kwargs)
    )
    msg = (
        'The docker.running state has been renamed to '
        'docker_container.running. To get rid of this warning, update your '
        'SLS to use the new name.'
    )
    salt.utils.warn_until('Fluorine', msg)
    ret.setdefault('warnings', []).append(msg)
    return ret


def stopped(**kwargs):
    '''
    .. deprecated:: Nitrogen
        This state has been moved to :py:func:`docker_container.stopped
        <salt.states.docker_container.stopped>`.
    '''
    ret = __states__['docker_container.stopped'](
        **salt.utils.clean_kwargs(**kwargs)
    )
    msg = (
        'The docker.stopped state has been renamed to '
        'docker_container.stopped. To get rid of this warning, update your '
        'SLS to use the new name.'
    )
    salt.utils.warn_until('Fluorine', msg)
    ret.setdefault('warnings', []).append(msg)
    return ret


def absent(name, **kwargs):
    '''
    .. deprecated:: Nitrogen
        This state has been moved to :py:func:`docker_container.absent
        <salt.states.docker_container.absent>`.
    '''
    ret = __states__['docker_container.absent'](
        name,
        **salt.utils.clean_kwargs(**kwargs)
    )
    msg = (
        'The docker.absent state has been renamed to '
        'docker_container.absent. To get rid of this warning, update your '
        'SLS to use the new name.'
    )
    salt.utils.warn_until('Fluorine', msg)
    ret.setdefault('warnings', []).append(msg)
    return ret


def network_present(name, **kwargs):
    '''
    .. deprecated:: Nitrogen
        This state has been moved to :py:func:`docker_network.present
        <salt.states.docker_network.present>`.
    '''
    ret = __states__['docker_network.present'](
        name,
        **salt.utils.clean_kwargs(**kwargs)
    )
    msg = (
        'The docker.network_present state has been renamed to '
        'docker_network.present. To get rid of this warning, update your SLS '
        'to use the new name.'
    )
    salt.utils.warn_until('Fluorine', msg)
    ret.setdefault('warnings', []).append(msg)
    return ret


def network_absent(name, **kwargs):
    '''
    .. deprecated:: Nitrogen
        This state has been moved to :py:func:`docker_network.absent
        <salt.states.docker_network.absent>`.
    '''
    ret = __states__['docker_network.absent'](
        name,
        **salt.utils.clean_kwargs(**kwargs)
    )
    msg = (
        'The docker.network_absent state has been renamed to '
        'docker_network.absent. To get rid of this warning, update your SLS '
        'to use the new name.'
    )
    salt.utils.warn_until('Fluorine', msg)
    ret.setdefault('warnings', []).append(msg)
    return ret


def image_present(name, **kwargs):
    '''
    .. deprecated:: Nitrogen
        This state has been moved to :py:func:`docker_image.present
        <salt.states.docker_image.present>`.
    '''
    ret = __states__['docker_image.present'](
        name,
        **salt.utils.clean_kwargs(**kwargs)
    )
    msg = (
        'The docker.image_present state has been renamed to '
        'docker_image.present. To get rid of this warning, update your SLS '
        'to use the new name.'
    )
    salt.utils.warn_until('Fluorine', msg)
    ret.setdefault('warnings', []).append(msg)
    return ret


def image_absent(**kwargs):
    '''
    .. deprecated:: Nitrogen
        This state has been moved to :py:func:`docker_image.absent
        <salt.states.docker_image.absent>`.
    '''
    ret = __states__['docker_image.absent'](
        **salt.utils.clean_kwargs(**kwargs)
    )
    msg = (
        'The docker.image_absent state has been renamed to '
        'docker_image.absent. To get rid of this warning, update your SLS to '
        'use the new name.'
    )
    salt.utils.warn_until('Fluorine', msg)
    ret.setdefault('warnings', []).append(msg)
    return ret


def volume_present(name, driver=None, driver_opts=None, force=False):
    '''
    .. deprecated:: Nitrogen
        This state has been moved to :py:func:`docker_volume.present
        <salt.states.docker_volume.present>`.
    '''
    ret = __states__['docker_volume.present'](name,
                                              driver=driver,
                                              driver_opts=driver_opts,
                                              force=force)
    msg = (
        'The docker.volume_present state has been renamed to '
        'docker_volume.present. To get rid of this warning, update your SLS '
        'to use the new name.'
    )
    salt.utils.warn_until('Fluorine', msg)
    ret.setdefault('warnings', []).append(msg)
    return ret


def volume_absent(name, driver=None):
    '''
    .. deprecated:: Nitrogen
        This state has been moved to :py:func:`docker_volume.absent
        <salt.states.docker_volume.absent>`.
    '''
    ret = __states__['docker_volume.absent'](name, driver=driver)
    msg = (
        'The docker.volume_absent state has been renamed to '
        'docker_volume.absent. To get rid of this warning, update your SLS '
        'to use the new name.'
    )
    salt.utils.warn_until('Fluorine', msg)
    ret.setdefault('warnings', []).append(msg)
    return ret


# Handle requisites
def mod_watch(name, sfun=None, **kwargs):
    if sfun == 'running':
        watch_kwargs = copy.deepcopy(kwargs)
        if watch_kwargs.get('watch_action', 'force') == 'force':
            watch_kwargs['force'] = True
        else:
            watch_kwargs['send_signal'] = True
            watch_kwargs['force'] = False
        return running(name, **watch_kwargs)

    if sfun == 'image_present':
        # Force image to be updated
        kwargs['force'] = True
        return image_present(name, **kwargs)

    return {'name': name,
            'changes': {},
            'result': False,
            'comment': ('watch requisite is not'
                        ' implemented for {0}'.format(sfun))}
