# -*- coding: utf-8 -*-
'''
Management of Docker networks

.. versionadded:: 2017.7.0

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
module (formerly called **dockerng**) in the 2017.7.0 release.
'''
from __future__ import absolute_import
import logging

# Import salt libs
from salt.ext import six
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
            gateway=None,
            ip_range=None,
            subnet=None,
            containers=None):
    '''
    Ensure that a network is present.

    name
        Name of the network

    driver
        Type of driver for that network.

    driver_opts
        Options for the network driver.

    gateway
        IPv4 or IPv6 gateway for the master subnet

    ip_range
        Allocate container IP from a sub-range within the subnet

    containers:
        List of container names that should be part of this network

    subnet:
        Subnet in CIDR format that represents a network segment

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


    .. code-block:: yaml

        network_baz:
          docker_network.present
            - name: baz
            - driver_opts:
                - parent: eth0
            - gateway: "172.20.0.1"
            - ip_range: "172.20.0.128/25"
            - subnet: "172.20.0.0/24"

    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if salt.utils.is_dictlist(driver_opts):
        driver_opts = salt.utils.repack_dictlist(driver_opts)

    # If any containers are specified, get details of each one, we need the Id and Name fields later
    if containers is not None:
        containers = [__salt__['docker.inspect_container'](c) for c in containers]

    networks = __salt__['docker.networks'](names=[name])
    log.trace(
        'docker_network.present: current networks: {0}'.format(networks)
    )

    # networks will contain all Docker networks which partially match 'name'.
    # We need to loop through to find the matching network, if there is one.
    network = None
    if networks:
        for network_iter in networks:
            if network_iter['Name'] == name:
                network = network_iter
                break

    # We might disconnect containers in the process of recreating the network, we'll need to keep track these containers
    # so we can reconnect them later.
    containers_disconnected = {}

    # If the network already exists
    if network is not None:
        log.debug('Network \'{0}\' already exists'.format(name))

        # Set the comment now to say that it already exists, if we need to recreate the network with new config we'll
        # update the comment later.
        ret['comment'] = 'Network \'{0}\' already exists'.format(name)

        # Update network details with result from network inspect, which will contain details of any containers
        # attached to the network.
        network = __salt__['docker.inspect_network'](network_id=network['Id'])

        log.trace('Details of \'{0}\' network: {1}'.format(name, network))

        # For the IPAM and driver config options which can be passed, check that if they are passed, they match the
        # current configuration.
        original_config = {}
        new_config = {}

        if driver and driver != network['Driver']:
            new_config['driver'] = driver
            original_config['driver'] = network['Driver']

        if driver_opts and driver_opts != network['Options']:
            new_config['driver_opts'] = driver_opts
            original_config['driver_opts'] = network['Options']

        # Multiple IPAM configs is probably not that common so for now we'll only worry about the simple case where
        # there's a single IPAM config.  If there's more than one (or none at all) then we'll bail out.
        if len(network['IPAM']['Config']) != 1:
            ret['comment'] = ('docker_network.present does only supports Docker networks with a single IPAM config,'
                              'network \'{0}\' has {1}'.format(name, len(network['IPAM']['Config'])))
            return ret

        ipam = network['IPAM']['Config'][0]

        if gateway and gateway != ipam['Gateway']:
            new_config['gateway'] = gateway
            original_config['gateway'] = ipam['Gateway']

        if subnet and subnet != ipam['Subnet']:
            new_config['subnet'] = subnet
            original_config['subnet'] = ipam['Subnet']

        if ip_range:
            # IPRange isn't always configured so check it's even set before attempting to compare it.
            if 'IPRange' in ipam and ip_range != ipam['IPRange']:
                new_config['ip_range'] = ip_range
                original_config['ip_range'] = ipam['IPRange']
            elif 'IPRange' not in ipam:
                new_config['ip_range'] = ip_range
                original_config['ip_range'] = ''

        if new_config != original_config:
            log.debug('New config is different to current;\nnew: {0}\ncurrent: {1}'.format(new_config, original_config))

            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'Network {0} will be recreated with new config'.format(name)
                return ret

            remove_result = _remove_network(name, network['Containers'])
            if not remove_result['result']:
                return remove_result

            # We've removed the network, so there are now no containers attached to it.
            if network['Containers']:
                containers_disconnected = network['Containers']
                network['Containers'] = []

            try:
                __salt__['docker.create_network'](
                    name,
                    driver=driver,
                    driver_opts=driver_opts,
                    gateway=gateway,
                    ip_range=ip_range,
                    subnet=subnet)
            except Exception as exc:
                ret['comment'] = ('Failed to replace network \'{0}\': {1}'
                                  .format(name, exc))
                return ret

            ret['changes']['updated'] = {name: {'old': original_config, 'new': new_config}}
            ret['comment'] = 'Network \'{0}\' was replaced with updated config'.format(name)

    # If the network does not yet exist, we create it
    else:
        log.debug('The network \'{0}\' will be created'.format(name))
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('The network \'{0}\' will be created'.format(name))
            return ret
        try:
            ret['changes']['created'] = __salt__['docker.create_network'](
                name,
                driver=driver,
                driver_opts=driver_opts,
                gateway=gateway,
                ip_range=ip_range,
                subnet=subnet)

        except Exception as exc:
            ret['comment'] = ('Failed to create network \'{0}\': {1}'
                              .format(name, exc))
            return ret

    # Finally, figure out the list of containers which should now be connected.
    containers_to_connect = {}
    # If no containers were specified in the state but we have disconnected some in the process of recreating the
    # network, we should reconnect those containers.
    if containers is None and containers_disconnected:
        containers_to_connect = containers_disconnected
    # If containers were specified in the state, regardless of what we've disconnected, we should now just connect
    # the containers specified.
    elif containers:
        for container in containers:
            containers_to_connect[container['Id']] = container

    if network is None:
        network = {'Containers': {}}

    # At this point, if all the containers we want connected are already connected to the network, we can set our
    # result and finish.
    if all(c in network['Containers'] for c in containers_to_connect):
        ret['result'] = True
        return ret

    # If we've not exited by this point it's because we have containers which we need to connect to the network.
    result = True
    reconnected_containers = []
    connected_containers = []
    for container_id, container in six.iteritems(containers_to_connect):
        if container_id not in network['Containers']:
            try:
                connect_result = __salt__['docker.connect_container_to_network'](container_id, name)
                log.trace(
                    'docker.connect_container_to_network({0}, {1}) result: {2}'.
                    format(container, name, connect_result)
                )
                # If this container was one we disconnected earlier, add it to the reconnected list.
                if container_id in containers_disconnected:
                    reconnected_containers.append(container['Name'])
                # Otherwise add it to the connected list.
                else:
                    connected_containers.append(container['Name'])

            except Exception as exc:
                ret['comment'] = ('Failed to connect container \'{0}\' to network \'{1}\' {2}'.format(
                    container['Name'], name, exc))
                result = False

    # If we populated any of our container lists then add them to our list of changes.
    if connected_containers:
        ret['changes']['connected'] = connected_containers
    if reconnected_containers:
        ret['changes']['reconnected'] = reconnected_containers

    # Figure out if we removed any containers as a result of replacing the network and then not re-connecting the
    # containers, because they weren't specified in the state.
    disconnected_containers = []
    for container_id, container in six.iteritems(containers_disconnected):
        if container_id not in containers_to_connect:
            disconnected_containers.append(container['Name'])

    if disconnected_containers:
        ret['changes']['disconnected'] = disconnected_containers

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
    log.trace(
        'docker_network.absent: current networks: {0}'.format(networks)
    )

    # networks will contain all Docker networks which partially match 'name'.
    # We need to loop through to find the matching network, if there is one.
    network = None
    if networks:
        for network_iter in networks:
            if network_iter['Name'] == name:
                network = network_iter
                break

    if network is None:
        ret['result'] = True
        ret['comment'] = 'Network \'{0}\' already absent'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('The network \'{0}\' will be removed'.format(name))
        return ret

    return _remove_network(network=name, containers=networks[0]['Containers'])


def _remove_network(network, containers=None):
    '''
    Remove network, removing any specified containers from it beforehand
    '''

    ret = {'name': network,
           'changes': {},
           'result': False,
           'comment': ''}

    if containers is None:
        containers = []
    for container in containers:
        try:
            ret['changes']['disconnected'] = __salt__['docker.disconnect_container_from_network'](container, network)
        except Exception as exc:
            ret['comment'] = ('Failed to disconnect container \'{0}\' from network \'{1}\' {2}'.format(
                container, network, exc))
    try:
        ret['changes']['removed'] = __salt__['docker.remove_network'](network)
        ret['result'] = True
    except Exception as exc:
        ret['comment'] = ('Failed to remove network \'{0}\': {1}'
                          .format(network, exc))

    return ret
