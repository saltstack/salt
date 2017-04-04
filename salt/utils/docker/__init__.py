# -*- coding: utf-8 -*-
'''
Common logic used by the docker state and execution module

This module contains logic to accomodate docker/salt CLI usage, as well as
input as formatted by states.
'''

# Import Python libs
from __future__ import absolute_import
import logging
import os

# Import Salt libs
import salt.utils
import salt.utils.docker.translate
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.utils.args import get_function_argspec as _argspec

# Import 3rd-party libs
import salt.ext.six as six

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
ALIASES = {
    'cmd': 'command',
    'cpuset': 'cpuset_cpus',
    'dns_option': 'dns_opt',
    'env': 'environment',
    'expose': 'ports',
    'interactive': 'stdin_open',
    'ipc': 'ipc_mode',
    'label': 'labels',
    'memory': 'mem_limit',
    'memory_swap': 'memswap_limit',
    'publish': 'port_bindings',
    'publish_all': 'publish_all_ports',
    'restart': 'restart_policy',
    'rm': 'auto_remove',
    'sysctl': 'sysctls',
    'security_opts': 'security_opt',
    'ulimit': 'ulimits',
    'user_ns_mode': 'userns_mode',
    'volume': 'volumes',
    'workdir': 'working_dir',
}
ALIASES_REVMAP = dict([(y, x) for x, y in six.iteritems(ALIASES)])

# Default timeout as of docker-py 1.0.0
CLIENT_TIMEOUT = 60
# Timeout for stopping the container, before a kill is invoked
SHUTDOWN_TIMEOUT = 10

log = logging.getLogger(__name__)


def _split(item, sep=',', maxsplit=-1):
    return [x.strip() for x in item.split(sep, maxsplit)]


def get_client_args():
    if not HAS_DOCKER_PY:
        raise CommandExecutionError('docker Python module not imported')
    try:
        create_args = _argspec(docker.APIClient.create_container).args
    except AttributeError:
        try:
            create_args = _argspec(docker.Client.create_container).args
        except AttributeError:
            raise CommandExecutionError(
                'Coult not get create_container argspec'
            )

    try:
        host_config_args = \
            _argspec(docker.types.HostConfig.__init__).args
    except AttributeError:
        try:
            host_config_args = _argspec(docker.utils.create_host_config).args
        except AttributeError:
            raise CommandExecutionError(
                'Could not get create_host_config argspec'
            )

    try:
        endpoint_config_args = \
            _argspec(docker.types.EndpointConfig.__init__).args
    except AttributeError:
        try:
            endpoint_config_args = \
                _argspec(docker.utils.utils.create_endpoint_config).args
        except AttributeError:
            try:
                endpoint_config_args = \
                    _argspec(docker.utils.create_endpoint_config).args
            except AttributeError:
                raise CommandExecutionError(
                    'Could not get create_endpoint_config argspec'
                )

    for arglist in (create_args, host_config_args, endpoint_config_args):
        try:
            # The API version is passed automagically by the API code that
            # imports these classes/functions and is not an arg that we will be
            # passing, so remove it if present.
            arglist.remove('version')
        except ValueError:
            pass

    # Remove any args in host or networking config from the main config dict.
    # This keeps us from accidentally allowing args that docker-py has moved
    # from the container config to the host config.
    for arglist in (host_config_args, endpoint_config_args):
        for item in arglist:
            try:
                create_args.remove(item)
            except ValueError:
                # Arg is not in create_args
                pass

    return {'create_container': create_args,
            'host_config': host_config_args,
            'networking_config': endpoint_config_args}


def get_repo_tag(image, default_tag='latest'):
    '''
    Resolves the docker repo:tag notation and returns repo name and tag
    '''
    if not isinstance(image, six.string_types):
        image = str(image)
    try:
        r_name, r_tag = image.rsplit(':', 1)
    except ValueError:
        r_name = image
        r_tag = default_tag
    if not r_tag:
        # Would happen if some wiseguy requests a tag ending in a colon
        # (e.g. 'somerepo:')
        log.warning(
            'Assuming tag \'%s\' for repo \'%s\'', default_tag, image
        )
        r_tag = default_tag
    elif '/' in r_tag:
        # Public registry notation with no tag specified
        # (e.g. foo.bar.com:5000/imagename)
        return image, default_tag
    return r_name, r_tag


def translate_input(**kwargs):
    '''
    Translate CLI/SLS input into the format the API expects. A
    ``skip_translate`` kwarg can be passed to control which arguments are
    translated. It can be either a comma-separated list or an iterable
    containing strings (e.g. a list or tuple), and members of that tuple will
    have their translation skipped. Optionally, skip_translate can be set to
    True to skip *all* translation.
    '''
    kwargs = salt.utils.clean_kwargs(**kwargs)
    invalid = {}
    collisions = []

    skip_translate = kwargs.pop('skip_translate', None)
    if skip_translate is True:
        # Skip all translation
        return kwargs, invalid, collisions
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

    validate_ip_addrs = kwargs.pop('validate_ip_addrs', True)

    # Using list(kwargs) here because if there are any invalid arguments we
    # will be popping them from the kwargs.
    for key in list(kwargs):
        real_key = ALIASES.get(key, key)
        if real_key in skip_translate:
            continue

        if salt.utils.is_dictlist(kwargs[key]):
            kwargs[key] = salt.utils.repack_dictlist(kwargs[key])

        try:
            func = getattr(salt.utils.docker.translate, real_key)
            kwargs[key] = func(kwargs[key], validate_ip_addrs=validate_ip_addrs)
        except AttributeError:
            log.debug('No translation function for argument \'%s\'', key)
            continue
        except SaltInvocationError as exc:
            kwargs.pop(key)
            invalid[key] = exc.strerror

    log_driver = kwargs.pop('log_driver', NOTSET)
    log_opt = kwargs.pop('log_opt', NOTSET)
    if 'log_config' not in kwargs:
        # The log_config is a mixture of the CLI options --log-driver and
        # --log-opt (which we support in Salt as log_driver and log_opt,
        # respectively), but it must be submitted to the host config in the
        # format {'Type': log_driver, 'Config': log_opt}. So, we need to
        # construct this argument to be passed to the API from those two
        # arguments.
        if log_driver is not NOTSET and log_opt is not NOTSET:
            kwargs['log_config'] = {
                'Type': log_driver if log_driver is not NOTSET else 'none',
                'Config': log_opt if log_opt is not NOTSET else {}
            }

    # Convert CLI versions of commands to their API counterparts
    for key in ALIASES:
        if key in kwargs:
            new_key = ALIASES[key]
            value = kwargs.pop(key)
            if new_key in kwargs:
                collisions.append(new_key)
            else:
                kwargs[new_key] = value

    # Don't allow conflicting options to be set
    if kwargs.get('port_bindings') is not None \
            and kwargs.get('publish_all_ports'):
        kwargs.pop('port_bindings')
        invalid['port_bindings'] = 'Cannot be used when publish_all_ports=True'
    if kwargs.get('hostname') is not None \
            and kwargs.get('network_mode') == 'host':
        kwargs.pop('hostname')
        invalid['hostname'] = 'Cannot be used when network_mode=True'

    # Make sure volumes and ports are defined to match the binds and port_bindings
    if kwargs.get('binds') is not None \
            and (skip_translate is True or
                 all(x not in skip_translate
                     for x in ('binds', 'volume', 'volumes'))):
        # Make sure that all volumes defined in "binds" are included in the
        # "volumes" param.
        auto_volumes = []
        if isinstance(kwargs['binds'], dict):
            for val in six.itervalues(kwargs['binds']):
                try:
                    if 'bind' in val:
                        auto_volumes.append(val['bind'])
                except TypeError:
                    continue
        else:
            if isinstance(kwargs['binds'], list):
                auto_volume_defs = kwargs['binds']
            else:
                try:
                    auto_volume_defs = _split(kwargs['binds'])
                except AttributeError:
                    auto_volume_defs = []
            for val in auto_volume_defs:
                try:
                    auto_volumes.append(_split(val, ':')[1])
                except IndexError:
                    continue
        if auto_volumes:
            actual_volumes = kwargs.setdefault('volumes', [])
            actual_volumes.extend([x for x in auto_volumes
                                   if x not in actual_volumes])
            # Sort list to make unit tests more reliable
            actual_volumes.sort()

    if kwargs.get('port_bindings') is not None \
            and (skip_translate is True or
                 all(x not in skip_translate
                     for x in ('port_bindings', 'expose', 'ports'))):
        # Make sure that all ports defined in "port_bindings" are included in
        # the "ports" param.
        auto_ports = list(kwargs['port_bindings'])
        if auto_ports:
            actual_ports = []
            # Sort list to make unit tests more reliable
            for port in auto_ports:
                if port in actual_ports:
                    continue
                if isinstance(port, six.integer_types):
                    actual_ports.append((port, 'tcp'))
                else:
                    port, proto = port.split('/')
                    actual_ports.append((int(port), proto))
            actual_ports.sort()
            actual_ports = [
                port if proto == 'tcp' else '{}/{}'.format(port, proto) for (port, proto) in actual_ports
            ]
            kwargs.setdefault('ports', actual_ports)

    return kwargs, invalid, sorted(collisions)
