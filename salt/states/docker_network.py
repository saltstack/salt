# -*- coding: utf-8 -*-
'''
Management of Docker networks

.. versionadded:: Nitrogen

:depends: docker_ Python module

.. note::
    Older releases of the Python bindings for Docker were called docker-py_ in
    PyPI. All releases of docker_, and releases of docker-py_ >= 1.6.0 are
    supported. These python bindings can easily be installed using
    :py:func:`pip.install <salt.modules.pip.install>`:

    .. code-block:: bash

        salt myminion pip.install docker

    To upgrade from docker-py_ to docker_, you must first uninstall docker-py_,
    and then install docker_:

    .. code-block:: bash

        salt myminion pip.uninstall docker-py
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
__virtualname__ = 'docker_network'
__virtual_aliases__ = ('moby_network',)


def __virtual__():
    '''
    Only load if the docker execution module is available
    '''
    if 'docker.version' in __salt__:
        return __virtualname__
    return (False, __salt__.missing_fun_string('docker.version'))


def present(name,
            driver=None,
            driver_opts=None,
            containers=None):
    '''
    Ensure that a network is present.

    name
        Name of the network

    driver
        Type of driver for that network.

    driver_opts
        Options for the network driver.

    containers:
        List of container names that should be part of this network

    Usage Examples:

    .. code-block:: yaml

        network_foo:
          docker_network.present


    .. code-block:: yaml

        network_bar:
          docker_network.present
            - name: bar
            - driver_opts:
                - com.docker.network.driver.mtu: "1450"
            - containers:
                - cont1
                - cont2

    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if salt.utils.is_dictlist(driver_opts):
        driver_opts = salt.utils.repack_dictlist(driver_opts)

    if containers is None:
        containers = []
    # map containers to container's Ids.
    containers = [__salt__['docker.inspect_container'](c)['Id'] for c in containers]
    networks = __salt__['docker.networks'](names=[name])
    if networks:
        network = networks[0]  # we expect network's name to be unique
        if all(c in network['Containers'] for c in containers):
            ret['result'] = True
            ret['comment'] = 'Network \'{0}\' already exists.'.format(name)
            return ret
        result = True
        for container in containers:
            if container not in network['Containers']:
                try:
                    ret['changes']['connected'] = __salt__['docker.connect_container_to_network'](
                        container, name)
                except Exception as exc:
                    ret['comment'] = ('Failed to connect container \'{0}\' to network \'{1}\' {2}'.format(
                        container, name, exc))
                    result = False
            ret['result'] = result

    else:
        try:
            ret['changes']['created'] = __salt__['docker.create_network'](
                name,
                driver=driver,
                driver_opts=driver_opts,
                check_duplicate=True)

        except Exception as exc:
            ret['comment'] = ('Failed to create network \'{0}\': {1}'
                              .format(name, exc))
        else:
            result = True
            for container in containers:
                try:
                    ret['changes']['connected'] = __salt__['docker.connect_container_to_network'](
                        container, name)
                except Exception as exc:
                    ret['comment'] = ('Failed to connect container \'{0}\' to network \'{1}\' {2}'.format(
                        container, name, exc))
                    result = False
            ret['result'] = result
    return ret


def absent(name, driver=None):
    '''
    Ensure that a network is absent.

    name
        Name of the network

    Usage Examples:

    .. code-block:: yaml

        network_foo:
          docker_network.absent

    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    networks = __salt__['docker.networks'](names=[name])
    if not networks:
        ret['result'] = True
        ret['comment'] = 'Network \'{0}\' already absent'.format(name)
        return ret

    for container in networks[0]['Containers']:
        try:
            ret['changes']['disconnected'] = __salt__['docker.disconnect_container_from_network'](container, name)
        except Exception as exc:
            ret['comment'] = ('Failed to disconnect container \'{0}\' to network \'{1}\' {2}'.format(
                container, name, exc))
    try:
        ret['changes']['removed'] = __salt__['docker.remove_network'](name)
        ret['result'] = True
    except Exception as exc:
        ret['comment'] = ('Failed to remove network \'{0}\': {1}'
                          .format(name, exc))
    return ret
