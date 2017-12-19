# -*- coding: utf-8 -*-
'''
Common logic used by the docker state and execution module

This module contains logic to accomodate docker/salt CLI usage, as well as
input as formatted by states.
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os

# Import Salt libs
import salt.utils.args
import salt.utils.data
import salt.utils.docker.translate
from salt.utils.docker.translate.helpers import split as _split
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.utils.args import get_function_argspec as _argspec

# Import 3rd-party libs
from salt.ext import six

try:
    import docker
    HAS_DOCKER_PY = True
except ImportError:
    HAS_DOCKER_PY = False

# These next two imports are only necessary to have access to the needed
# functions so that we can get argspecs for the container config, host config,
# and networking config (see the get_client_args() function).
try:
    import docker.types
except ImportError:
    pass
try:
    import docker.utils
except ImportError:
    pass

NOTSET = object()

# Default timeout as of docker-py 1.0.0
CLIENT_TIMEOUT = 60
# Timeout for stopping the container, before a kill is invoked
SHUTDOWN_TIMEOUT = 10

log = logging.getLogger(__name__)


def get_client_args(limit=None):
    if not HAS_DOCKER_PY:
        raise CommandExecutionError('docker Python module not imported')

    limit = salt.utils.args.split_input(limit or [])
    ret = {}

    if not limit or any(x in limit for x in
            ('create_container', 'host_config', 'connect_container_to_network')):
        try:
            ret['create_container'] = \
                _argspec(docker.APIClient.create_container).args
        except AttributeError:
            try:
                ret['create_container'] = \
                    _argspec(docker.Client.create_container).args
            except AttributeError:
                raise CommandExecutionError(
                    'Coult not get create_container argspec'
                )

        try:
            ret['host_config'] = \
                _argspec(docker.types.HostConfig.__init__).args
        except AttributeError:
            try:
                ret['host_config'] = \
                    _argspec(docker.utils.create_host_config).args
            except AttributeError:
                raise CommandExecutionError(
                    'Could not get create_host_config argspec'
                )

        try:
            ret['connect_container_to_network'] = \
                _argspec(docker.types.EndpointConfig.__init__).args
        except AttributeError:
            try:
                ret['connect_container_to_network'] = \
                    _argspec(docker.utils.utils.create_endpoint_config).args
            except AttributeError:
                try:
                    ret['connect_container_to_network'] = \
                        _argspec(docker.utils.create_endpoint_config).args
                except AttributeError:
                    raise CommandExecutionError(
                        'Could not get connect_container_to_network argspec'
                    )

    for key, wrapped_func in (
            ('logs', docker.api.container.ContainerApiMixin.logs),
            ('create_network', docker.api.network.NetworkApiMixin.create_network)):
        if not limit or key in limit:
            try:
                func_ref = wrapped_func
                if six.PY2:
                    try:
                        # create_network is decorated, so we have to dig into the
                        # closure created by functools.wraps
                        ret[key] = \
                            _argspec(func_ref.__func__.__closure__[0].cell_contents).args
                    except (AttributeError, IndexError):
                        # functools.wraps changed (unlikely), bail out
                        ret[key] = []
                else:
                    try:
                        # functools.wraps makes things a little easier in Python 3
                        ret[key] = _argspec(func_ref.__wrapped__).args
                    except AttributeError:
                        # functools.wraps changed (unlikely), bail out
                        ret[key] = []
            except AttributeError:
                # Function moved, bail out
                ret[key] = []

    if not limit or 'ipam_config' in limit:
        try:
            ret['ipam_config'] = _argspec(docker.types.IPAMPool.__init__).args
        except AttributeError:
            try:
                ret['ipam_config'] = _argspec(docker.utils.create_ipam_pool).args
            except AttributeError:
                raise CommandExecutionError('Could not get ipam args')

    for item in ret:
        # The API version is passed automagically by the API code that imports
        # these classes/functions and is not an arg that we will be passing, so
        # remove it if present. Similarly, don't include "self" if it shows up
        # in the arglist.
        for argname in ('version', 'self'):
            try:
                ret[item].remove(argname)
            except ValueError:
                pass

    # Remove any args in host or endpoint config from the create_container
    # arglist. This keeps us from accidentally allowing args that docker-py has
    # moved from the create_container function to the either the host or
    # endpoint config.
    for item in ('host_config', 'connect_container_to_network'):
        for val in ret.get(item, []):
            try:
                ret['create_container'].remove(val)
            except ValueError:
                # Arg is not in create_container arglist
                pass

    for item in ('create_container', 'host_config', 'connect_container_to_network'):
        if limit and item not in limit:
            ret.pop(item, None)

    try:
        ret['logs'].remove('container')
    except (KeyError, ValueError, TypeError):
        pass

    return ret


def translate_input(translator,
                    skip_translate=None,
                    ignore_collisions=False,
                    validate_ip_addrs=True,
                    **kwargs):
    '''
    Translate CLI/SLS input into the format the API expects. The ``translator``
    argument must be a module containing translation functions, within
    salt.utils.docker.translate. A ``skip_translate`` kwarg can be passed to
    control which arguments are translated. It can be either a comma-separated
    list or an iterable containing strings (e.g. a list or tuple), and members
    of that tuple will have their translation skipped. Optionally,
    skip_translate can be set to True to skip *all* translation.
    '''
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    invalid = {}
    collisions = []

    if skip_translate is True:
        # Skip all translation
        return kwargs
    else:
        if not skip_translate:
            skip_translate = ()
        else:
            try:
                skip_translate = _split(skip_translate)
            except AttributeError:
                pass
            if not hasattr(skip_translate, '__iter__'):
                log.error('skip_translate is not an iterable, ignoring')
                skip_translate = ()

    try:
        # Using list(kwargs) here because if there are any invalid arguments we
        # will be popping them from the kwargs.
        for key in list(kwargs):
            real_key = translator.ALIASES.get(key, key)
            if real_key in skip_translate:
                continue

            # ipam_pools is designed to be passed as a list of actual
            # dictionaries, but if each of the dictionaries passed has a single
            # element, it will be incorrectly repacked.
            if key != 'ipam_pools' and salt.utils.data.is_dictlist(kwargs[key]):
                kwargs[key] = salt.utils.data.repack_dictlist(kwargs[key])

            try:
                kwargs[key] = getattr(translator, real_key)(
                    kwargs[key],
                    validate_ip_addrs=validate_ip_addrs,
                    skip_translate=skip_translate)
            except AttributeError:
                log.debug('No translation function for argument \'%s\'', key)
                continue
            except SaltInvocationError as exc:
                kwargs.pop(key)
                invalid[key] = exc.strerror

        try:
            translator._merge_keys(kwargs)
        except AttributeError:
            pass

        # Convert CLI versions of commands to their docker-py counterparts
        for key in translator.ALIASES:
            if key in kwargs:
                new_key = translator.ALIASES[key]
                value = kwargs.pop(key)
                if new_key in kwargs:
                    collisions.append(new_key)
                else:
                    kwargs[new_key] = value

        try:
            translator._post_processing(kwargs, skip_translate, invalid)
        except AttributeError:
            pass

    except Exception as exc:
        error_message = exc.__str__()
        log.error(
            'Error translating input: \'%s\'', error_message, exc_info=True)
    else:
        error_message = None

    error_data = {}
    if error_message is not None:
        error_data['error_message'] = error_message
    if invalid:
        error_data['invalid'] = invalid
    if collisions and not ignore_collisions:
        for item in collisions:
            error_data.setdefault('collisions', []).append(
                '\'{0}\' is an alias for \'{1}\', they cannot both be used'
                .format(translator.ALIASES_REVMAP[item], item)
            )
    if error_data:
        raise CommandExecutionError(
            'Failed to translate input', info=error_data)

    return kwargs


def create_ipam_config(*pools, **kwargs):
    '''
    Builds an IP address management (IPAM) config dictionary
    '''
    kwargs = salt.utils.args.clean_kwargs(**kwargs)

    try:
        # docker-py 2.0 and newer
        pool_args = salt.utils.args.get_function_argspec(
            docker.types.IPAMPool.__init__).args
        create_pool = docker.types.IPAMPool
        create_config = docker.types.IPAMConfig
    except AttributeError:
        # docker-py < 2.0
        pool_args = salt.utils.args.get_function_argspec(
            docker.utils.create_ipam_pool).args
        create_pool = docker.utils.create_ipam_pool
        create_config = docker.utils.create_ipam_config

    for primary_key, alias_key in (('driver', 'ipam_driver'),
                                   ('options', 'ipam_opts')):

        if alias_key in kwargs:
            alias_val = kwargs.pop(alias_key)
            if primary_key in kwargs:
                log.warning(
                    'docker.create_ipam_config: Both \'%s\' and \'%s\' '
                    'passed. Ignoring \'%s\'',
                    alias_key, primary_key, alias_key
                )
            else:
                kwargs[primary_key] = alias_val

    if salt.utils.data.is_dictlist(kwargs.get('options')):
        kwargs['options'] = salt.utils.data.repack_dictlist(kwargs['options'])

    # Get all of the IPAM pool args that were passed as individual kwargs
    # instead of in the *pools tuple
    pool_kwargs = {}
    for key in list(kwargs):
        if key in pool_args:
            pool_kwargs[key] = kwargs.pop(key)

    pool_configs = []
    if pool_kwargs:
        pool_configs.append(create_pool(**pool_kwargs))
    pool_configs.extend([create_pool(**pool) for pool in pools])

    if pool_configs:
        # Sanity check the IPAM pools. docker-py's type/function for creating
        # an IPAM pool will allow you to create a pool with a gateway, IP
        # range, or map of aux addresses, even when no subnet is passed.
        # However, attempting to use this IPAM pool when creating the network
        # will cause the Docker Engine to throw an error.
        if any('Subnet' not in pool for pool in pool_configs):
            raise SaltInvocationError('A subnet is required in each IPAM pool')
        else:
            kwargs['pool_configs'] = pool_configs

    ret = create_config(**kwargs)
    pool_dicts = ret.get('Config')
    if pool_dicts:
        # When you inspect a network with custom IPAM configuration, only
        # arguments which were explictly passed are reflected. By contrast,
        # docker-py will include keys for arguments which were not passed in
        # but set the value to None. Thus, for ease of comparison, the below
        # loop will remove all keys with a value of None from the generated
        # pool configs.
        for idx, _ in enumerate(pool_dicts):
            for key in list(pool_dicts[idx]):
                if pool_dicts[idx][key] is None:
                    del pool_dicts[idx][key]

    return ret
