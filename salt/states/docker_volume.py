# -*- coding: utf-8 -*-
'''
Management of Docker volumes

.. versionadded:: Nitrogen

:depends: docker_ Python module

.. note::
    Older releases of the Python bindings for Docker were called docker-py_ in
    PyPI. All releases of docker_, and releases of docker-py_ >= 1.6.0 are
    supported. These python bindings can easily be installed using
    :py:func:`pip.install <salt.modules.pip.install>`:

    .. code-block:: bash

        salt myminion pip.install docker

.. _docker: https://pypi.python.org/pypi/docker
.. _docker-py: https://pypi.python.org/pypi/docker-py

These states were moved from the :mod:`docker <salt.states.docker>` state
module (formerly called **dockerng**) in the Nitrogen release.
'''
from __future__ import absolute_import
import logging

# Import salt libs
import salt.utils

# Enable proper logging
log = logging.getLogger(__name__)  # pylint: disable=invalid-name

# Define the module's virtual name
__virtualname__ = 'docker_volume'


def __virtual__():
    '''
    Only load if the docker execution module is available
    '''
    if 'docker.version' in __salt__:
        return __virtualname__
    return (False, __salt__.missing_fun_string('docker.version'))


def _find_volume(name):
    '''
    Find volume by name on minion
    '''
    docker_volumes = __salt__['docker.volumes']()['Volumes']
    if docker_volumes:
        volumes = [v for v in docker_volumes if v['Name'] == name]
        if volumes:
            return volumes[0]

    return None


def present(name, driver=None, driver_opts=None, force=False):
    '''
    Ensure that a volume is present.

    .. versionadded:: 2015.8.4
    .. versionchanged:: 2015.8.6
        This state no longer deletes and re-creates a volume if the existing
        volume's driver does not match the ``driver`` parameter (unless the
        ``force`` parameter is set to ``True``).
    .. versionchanged:: Nitrogen
        This state was renamed from **docker.volume_present** to **docker_volume.present**

    name
        Name of the volume

    driver
        Type of driver for that volume.  If ``None`` and the volume
        does not yet exist, the volume will be created using Docker's
        default driver.  If ``None`` and the volume does exist, this
        function does nothing, even if the existing volume's driver is
        not the Docker default driver.  (To ensure that an existing
        volume's driver matches the Docker default, you must
        explicitly name Docker's default driver here.)

    driver_opts
        Options for the volume driver

    force : False
        If the volume already exists but the existing volume's driver
        does not match the driver specified by the ``driver``
        parameter, this parameter controls whether the function errors
        out (if ``False``) or deletes and re-creates the volume (if
        ``True``).

        .. versionadded:: 2015.8.6

    Usage Examples:

    .. code-block:: yaml

        volume_foo:
          docker_volume.present


    .. code-block:: yaml

        volume_bar:
          docker_volume.present
            - name: bar
            - driver: local
            - driver_opts:
                foo: bar

    .. code-block:: yaml

        volume_bar:
          docker_volume.present
            - name: bar
            - driver: local
            - driver_opts:
                - foo: bar
                - option: value

    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}
    if salt.utils.is_dictlist(driver_opts):
        driver_opts = salt.utils.repack_dictlist(driver_opts)
    volume = _find_volume(name)
    if not volume:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('The volume \'{0}\' will be created'.format(name))
            return ret
        try:
            ret['changes']['created'] = __salt__['docker.create_volume'](
                name, driver=driver, driver_opts=driver_opts)
        except Exception as exc:
            ret['comment'] = ('Failed to create volume \'{0}\': {1}'
                              .format(name, exc))
            return ret
        else:
            result = True
            ret['result'] = result
            return ret
    # volume exists, check if driver is the same.
    if driver is not None and volume['Driver'] != driver:
        if not force:
            ret['comment'] = "Driver for existing volume '{0}' ('{1}')" \
                             " does not match specified driver ('{2}')" \
                             " and force is False".format(
                                 name, volume['Driver'], driver)
            ret['result'] = None if __opts__['test'] else False
            return ret
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = "The volume '{0}' will be replaced with a" \
                             " new one using the driver '{1}'".format(
                                 name, volume)
            return ret
        try:
            ret['changes']['removed'] = __salt__['docker.remove_volume'](name)
        except Exception as exc:
            ret['comment'] = ('Failed to remove volume \'{0}\': {1}'
                              .format(name, exc))
            return ret
        else:
            try:
                ret['changes']['created'] = __salt__['docker.create_volume'](
                    name, driver=driver, driver_opts=driver_opts)
            except Exception as exc:
                ret['comment'] = ('Failed to create volume \'{0}\': {1}'
                                  .format(name, exc))
                return ret
            else:
                result = True
                ret['result'] = result
                return ret

    ret['result'] = None if __opts__['test'] else True
    ret['comment'] = 'Volume \'{0}\' already exists.'.format(name)
    return ret


def absent(name, driver=None):
    '''
    Ensure that a volume is absent.

    .. versionadded:: 2015.8.4
    .. versionchanged:: Nitrogen
        This state was renamed from **docker.volume_absent** to **docker_volume.absent**

    name
        Name of the volume

    Usage Examples:

    .. code-block:: yaml

        volume_foo:
          docker_volume.absent

    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    volume = _find_volume(name)
    if not volume:
        ret['result'] = True
        ret['comment'] = 'Volume \'{0}\' already absent'.format(name)
        return ret

    try:
        ret['changes']['removed'] = __salt__['docker.remove_volume'](name)
        ret['result'] = True
    except Exception as exc:
        ret['comment'] = ('Failed to remove volume \'{0}\': {1}'
                          .format(name, exc))
    return ret
