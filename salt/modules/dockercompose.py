
# -*- coding: utf-8 -*-
'''
Module to import docker-compose via saltstack

.. versionadded:: 2016.3.0

:maintainer: Jean Praloran <jeanpralo@gmail.com>
:maturity: new
:depends: docker-compose>=1.5
:platform: all

Introduction
------------
This module allows one to deal with docker-compose file in a directory.

This is  a first version only, the following commands are missing at the moment
but will be built later on if the community is interested in this module:

- run
- logs
- port
- scale

Installation Prerequisites
--------------------------

This execution module requires at least version 1.4.0 of both docker-compose_ and
Docker_. docker-compose can easily be installed using :py:func:`pip.install
<salt.modules.pip.install>`:

.. code-block:: bash

    salt myminion pip.install docker-compose>=1.5.0

.. _docker-compose: https://pypi.python.org/pypi/docker-compose
.. _Docker: https://www.docker.com/


How to use this module?
-----------------------
In order to use the module if you have no docker-compose file on the server you
can issue the command create, it takes two arguments the path where the
docker-compose.yml will be stored and the content of this latter:

.. code-block:: bash

    # salt-call -l debug dockercompose.create /tmp/toto '
     database:
     image: mongo:3.0
     command: mongod --smallfiles --quiet --logpath=/dev/null
     '

Then you can execute a list of method defined at the bottom with at least one
argument (the path where the docker-compose.yml will be read) and an optional
python list which corresponds to the services names:

.. code-block:: bash

    # salt-call -l debug dockercompose.up /tmp/toto
    # salt-call -l debug dockercompose.restart /tmp/toto '[database]'
    # salt-call -l debug dockercompose.stop /tmp/toto
    # salt-call -l debug dockercompose.rm /tmp/toto

Docker-compose method supported
-------------------------------
- up
- restart
- stop
- start
- pause
- unpause
- kill
- rm
- ps
- pull
- build

Functions
---------
- docker-compose.yml management
    - :py:func:`dockercompose.create <salt.modules.dockercompose.create>`
    - :py:func:`dockercompose.get <salt.modules.dockercompose.get>`
- Manage containers
    - :py:func:`dockercompose.restart <salt.modules.dockercompose.restart>`
    - :py:func:`dockercompose.stop <salt.modules.dockercompose.stop>`
    - :py:func:`dockercompose.pause <salt.modules.dockercompose.pause>`
    - :py:func:`dockercompose.unpause <salt.modules.dockercompose.unpause>`
    - :py:func:`dockercompose.start <salt.modules.dockercompose.start>`
    - :py:func:`dockercompose.kill <salt.modules.dockercompose.kill>`
    - :py:func:`dockercompose.rm <salt.modules.dockercompose.rm>`
    - :py:func:`dockercompose.up <salt.modules.dockercompose.up>`
- Manage containers image:
    - :py:func:`dockercompose.pull <salt.modules.dockercompose.pull>`
    - :py:func:`dockercompose.build <salt.modules.dockercompose.build>`
- Gather information about containers:
    - :py:func:`dockercompose.ps <salt.modules.dockercompose.ps>`

Detailed Function Documentation
-------------------------------
'''

from __future__ import absolute_import

import inspect
import logging
import os
import re
import salt.utils

from operator import attrgetter
try:
    import compose
    from compose.cli.command import get_project
    from compose.service import ConvergenceStrategy
    HAS_DOCKERCOMPOSE = True
except ImportError:
    HAS_DOCKERCOMPOSE = False

try:
    from compose.project import OneOffFilter
    USE_FILTERCLASS = True
except ImportError:
    USE_FILTERCLASS = False

MIN_DOCKERCOMPOSE = (1, 5, 0)
VERSION_RE = r'([\d.]+)'

log = logging.getLogger(__name__)
debug = False

__virtualname__ = 'dockercompose'
dc_filename = 'docker-compose.yml'


def __virtual__():
    if HAS_DOCKERCOMPOSE:
        match = re.match(VERSION_RE, str(compose.__version__))
        if match:
            version = tuple([int(x) for x in match.group(1).split('.')])
            if version >= MIN_DOCKERCOMPOSE:
                return __virtualname__
    return (False, 'The dockercompose execution module not loaded: '
            'compose python library not available.')


def __standardize_result(status, message, data=None, debug_msg=None):
    '''
    Standardizes all responses

    :param status:
    :param message:
    :param data:
    :param debug_msg:
    :return:
    '''
    result = {
        'status': status,
        'message': message
    }

    if data is not None:
        result['return'] = data

    if debug_msg is not None and debug:
        result['debug'] = debug_msg

    return result


def __read_docker_compose(path):
    '''
    Read the docker-compose.yml file if it exists in the directory

    :param path:
    :return:
    '''
    if os.path.isfile(os.path.join(path, dc_filename)) is False:
        return __standardize_result(False,
                                    'Path does not exist or docker-compose.yml is not present',
                                    None, None)
    f = salt.utils.fopen(os.path.join(path, dc_filename), 'r')  # pylint: disable=resource-leakage
    result = {'docker-compose.yml': ''}
    if f:
        for line in f:
            result['docker-compose.yml'] += line
        f.close()
    else:
        return __standardize_result(False, 'Could not read docker-compose.yml file.',
                                    None, None)
    return __standardize_result(True, 'Reading content of docker-compose.yml file',
                                result, None)


def __write_docker_compose(path, docker_compose):
    '''
    Write docker-compose to a temp directory
    in order to use it with docker-compose ( config check )

    :param path:

    docker_compose
        contains the docker-compose file

    :return:
    '''

    if os.path.isdir(path) is False:
        os.mkdir(path)
    f = salt.utils.fopen(os.path.join(path, dc_filename), 'w')  # pylint: disable=resource-leakage
    if f:
        f.write(docker_compose)
        f.close()
    else:
        return __standardize_result(False,
                                    'Could not write docker-compose file in {0}'.format(path),
                                    None, None)
    project = __load_project(path)
    if isinstance(project, dict):
        os.remove(os.path.join(path, dc_filename))
        return project
    return path


def __load_project(path):
    '''
    Load a docker-compose project from path

    :param path:
    :return:
    '''
    try:
        project = get_project(path)
    except Exception as inst:
        return __handle_except(inst)
    return project


def __handle_except(inst):
    '''
    Handle exception and return a standard result

    :param inst:
    :return:
    '''
    return __standardize_result(False,
                                'Docker-compose command {0} failed'.
                                format(inspect.stack()[1][3]),
                                '{0}'.format(inst), None)


def _get_convergence_plans(project, service_names):
    '''
    Get action executed for each container

    :param project:
    :param service_names:
    :return:
    '''
    ret = {}
    plans = project._get_convergence_plans(project.get_services(service_names),
                                           ConvergenceStrategy.changed)
    for cont in plans:
        (action, container) = plans[cont]
        if action == 'create':
            ret[cont] = 'Creating container'
        elif action == 'recreate':
            ret[cont] = 'Re-creating container'
        elif action == 'start':
            ret[cont] = 'Starting container'
        elif action == 'noop':
            ret[cont] = 'Container is up to date'
    return ret


def get(path):
    '''
    Get the content of the docker-compose file into a directory

    path
        Path where the docker-compose file is stored on the server

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.get /path/where/docker-compose/stored
    '''

    salt_result = __read_docker_compose(path)
    if not salt_result['status']:
        return salt_result
    project = __load_project(path)
    if isinstance(project, dict):
        salt_result['return']['valid'] = False
    else:
        salt_result['return']['valid'] = True
    return salt_result


def create(path, docker_compose):
    '''
    Create and validate a docker-compose file into a directory

    path
        Path where the docker-compose file will be stored on the server

    docker_compose
        docker_compose file

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.create /path/where/docker-compose/stored content
    '''
    if docker_compose:
        ret = __write_docker_compose(path, docker_compose)
        if isinstance(ret, dict):
            return ret
    else:
        return __standardize_result(False,
                                    'Creating a docker-compose project failed, you must send a valid docker-compose file',
                                    None, None)
    return __standardize_result(True, 'Successfully created the docker-compose file', {'compose.base_dir': path}, None)


def pull(path, service_names=None):
    '''
    Pull image for containers in the docker-compose file, service_names is a
    python list, if omitted pull all images

    path
        Path where the docker-compose file is stored on the server
    service_names
        If specified will pull only the image for the specified services

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.pull /path/where/docker-compose/stored
        salt myminion dockercompose.pull /path/where/docker-compose/stored '[janus]'
    '''

    project = __load_project(path)
    if isinstance(project, dict):
        return project
    else:
        try:
            project.pull(service_names)
        except Exception as inst:
            return __handle_except(inst)
    return __standardize_result(True, 'Pulling containers images via docker-compose succeeded',
                                None, None)


def build(path, service_names=None):
    '''
    Build image for containers in the docker-compose file, service_names is a
    python list, if omitted build images for all containers. Please note
    that at the moment the module does not allow you to upload your Dockerfile,
    nor any other file you could need with your docker-compose.yml, you will
    have to make sure the files you need are actually in the directory specified
    in the `build` keyword

    path
        Path where the docker-compose file is stored on the server
    service_names
        If specified will pull only the image for the specified services

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.build /path/where/docker-compose/stored
        salt myminion dockercompose.build /path/where/docker-compose/stored '[janus]'
    '''

    project = __load_project(path)
    if isinstance(project, dict):
        return project
    else:
        try:
            project.build(service_names)
        except Exception as inst:
            return __handle_except(inst)
    return __standardize_result(True, 'Building containers images via docker-compose succeeded',
                                None, None)


def restart(path, service_names=None):
    '''
    Restart container(s) in the docker-compose file, service_names is a python
    list, if omitted restart all containers

    path
        Path where the docker-compose file is stored on the server

    service_names
        If specified will restart only the specified services

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.restart /path/where/docker-compose/stored
        salt myminion dockercompose.restart /path/where/docker-compose/stored '[janus]'
    '''

    project = __load_project(path)
    debug_ret = {}
    result = {}
    if isinstance(project, dict):
        return project
    else:
        try:
            project.restart(service_names)
            if debug:
                for container in project.containers():
                    if service_names is None or container.get('Name')[1:] in service_names:
                        container.inspect_if_not_inspected()
                        debug_ret[container.get('Name')] = container.inspect()
                        result[container.get('Name')] = 'restarted'
        except Exception as inst:
            return __handle_except(inst)
    return __standardize_result(True, 'Restarting containers via docker-compose', result, debug_ret)


def stop(path, service_names=None):
    '''
    Stop running containers in the docker-compose file, service_names is a python
    list, if omitted stop all containers

    path
        Path where the docker-compose file is stored on the server
    service_names
        If specified will stop only the specified services

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.stop /path/where/docker-compose/stored
        salt myminion dockercompose.stop  /path/where/docker-compose/stored '[janus]'
    '''

    project = __load_project(path)
    debug_ret = {}
    result = {}
    if isinstance(project, dict):
        return project
    else:
        try:
            project.stop(service_names)
            if debug:
                for container in project.containers(stopped=True):
                    if service_names is None or container.get('Name')[1:] in service_names:
                        container.inspect_if_not_inspected()
                        debug_ret[container.get('Name')] = container.inspect()
                        result[container.get('Name')] = 'stopped'
        except Exception as inst:
            return __handle_except(inst)
    return __standardize_result(True, 'Stopping containers via docker-compose', result, debug_ret)


def pause(path, service_names=None):
    '''
    Pause running containers in the docker-compose file, service_names is a python
    list, if omitted pause all containers

    path
        Path where the docker-compose file is stored on the server
    service_names
        If specified will pause only the specified services

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.pause /path/where/docker-compose/stored
        salt myminion dockercompose.pause /path/where/docker-compose/stored '[janus]'
    '''

    project = __load_project(path)
    debug_ret = {}
    result = {}
    if isinstance(project, dict):
        return project
    else:
        try:
            project.pause(service_names)
            if debug:
                for container in project.containers():
                    if service_names is None or container.get('Name')[1:] in service_names:
                        container.inspect_if_not_inspected()
                        debug_ret[container.get('Name')] = container.inspect()
                        result[container.get('Name')] = 'paused'
        except Exception as inst:
            return __handle_except(inst)
    return __standardize_result(True, 'Pausing containers via docker-compose', result, debug_ret)


def unpause(path, service_names=None):
    '''
    Un-Pause containers in the docker-compose file, service_names is a python
    list, if omitted unpause all containers

    path
        Path where the docker-compose file is stored on the server
    service_names
        If specified will un-pause only the specified services

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.pause /path/where/docker-compose/stored
        salt myminion dockercompose.pause /path/where/docker-compose/stored '[janus]'
    '''

    project = __load_project(path)
    debug_ret = {}
    result = {}
    if isinstance(project, dict):
        return project
    else:
        try:
            project.unpause(service_names)
            if debug:
                for container in project.containers():
                    if service_names is None or container.get('Name')[1:] in service_names:
                        container.inspect_if_not_inspected()
                        debug_ret[container.get('Name')] = container.inspect()
                        result[container.get('Name')] = 'unpaused'
        except Exception as inst:
            return __handle_except(inst)
    return __standardize_result(True, 'Un-Pausing containers via docker-compose', result, debug_ret)


def start(path, service_names=None):
    '''
    Start containers in the docker-compose file, service_names is a python
    list, if omitted start all containers

    path
        Path where the docker-compose file is stored on the server
    service_names
        If specified will start only the specified services

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.start /path/where/docker-compose/stored
        salt myminion dockercompose.start /path/where/docker-compose/stored '[janus]'
    '''

    project = __load_project(path)
    debug_ret = {}
    result = {}
    if isinstance(project, dict):
        return project
    else:
        try:
            project.start(service_names)
            if debug:
                for container in project.containers():
                    if service_names is None or container.get('Name')[1:] in service_names:
                        container.inspect_if_not_inspected()
                        debug_ret[container.get('Name')] = container.inspect()
                        result[container.get('Name')] = 'started'
        except Exception as inst:
            return __handle_except(inst)
    return __standardize_result(True, 'Starting containers via docker-compose', result, debug_ret)


def kill(path, service_names=None):
    '''
    Kill containers in the docker-compose file, service_names is a python
    list, if omitted kill all containers

    path
        Path where the docker-compose file is stored on the server
    service_names
        If specified will kill only the specified services

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.kill /path/where/docker-compose/stored
        salt myminion dockercompose.kill /path/where/docker-compose/stored '[janus]'
    '''

    project = __load_project(path)
    debug_ret = {}
    result = {}
    if isinstance(project, dict):
        return project
    else:
        try:
            project.kill(service_names)
            if debug:
                for container in project.containers(stopped=True):
                    if service_names is None or container.get('Name')[1:] in service_names:
                        container.inspect_if_not_inspected()
                        debug_ret[container.get('Name')] = container.inspect()
                        result[container.get('Name')] = 'killed'
        except Exception as inst:
            return __handle_except(inst)
    return __standardize_result(True, 'Killing containers via docker-compose', result, debug_ret)


def rm(path, service_names=None):
    '''
    Remove stopped containers in the docker-compose file, service_names is a python
    list, if omitted remove all stopped containers

    path
        Path where the docker-compose file is stored on the server
    service_names
        If specified will remove only the specified stopped services

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.rm /path/where/docker-compose/stored
        salt myminion dockercompose.rm /path/where/docker-compose/stored '[janus]'
    '''

    project = __load_project(path)
    if isinstance(project, dict):
        return project
    else:
        try:
            project.remove_stopped(service_names)
        except Exception as inst:
            return __handle_except(inst)
    return __standardize_result(True, 'Removing stopped containers via docker-compose', None, None)


def ps(path):
    '''
    List all running containers and report some information about them

    path
        Path where the docker-compose file is stored on the server

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.ps /path/where/docker-compose/stored
    '''

    project = __load_project(path)
    result = {}
    if isinstance(project, dict):
        return project
    else:
        if USE_FILTERCLASS:
            containers = sorted(
                project.containers(None, stopped=True) +
                project.containers(None, OneOffFilter.only),
                key=attrgetter('name'))
        else:
            containers = sorted(
                project.containers(None, stopped=True) +
                project.containers(None, one_off=True),
                key=attrgetter('name'))
        for container in containers:
            command = container.human_readable_command
            if len(command) > 30:
                command = '{0} ...'.format(command[:26])
            result[container.name] = {
                'id': container.id,
                'name': container.name,
                'command': command,
                'state': container.human_readable_state,
                'ports': container.human_readable_ports,
            }
    return __standardize_result(True, 'Listing docker-compose containers', result, None)


def up(path, service_names=None):
    '''
    Create and start containers defined in the the docker-compose.yml file
    located in path, service_names is a python list, if omitted create and
    start all containers

    path
        Path where the docker-compose file is stored on the server
    service_names
        If specified will create and start only the specified services

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.up /path/where/docker-compose/stored
        salt myminion dockercompose.up /path/where/docker-compose/stored '[janus]'
    '''

    debug_ret = {}
    project = __load_project(path)
    if isinstance(project, dict):
        return project
    else:
        try:
            result = _get_convergence_plans(project, service_names)
            ret = project.up(service_names)
            if debug:
                for container in ret:
                    if service_names is None or container.get('Name')[1:] in service_names:
                        container.inspect_if_not_inspected()
                        debug_ret[container.get('Name')] = container.inspect()
        except Exception as inst:
            return __handle_except(inst)
    return __standardize_result(True, 'Adding containers via docker-compose', result, debug_ret)
