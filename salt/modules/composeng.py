# -*- coding: utf-8 -*-
'''
Work with containers managed by docker-compose

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
'''

from __future__ import absolute_import
import io
import logging
import sys
import traceback
import os
import salt.utils
from collections import namedtuple
from contextlib import contextmanager
from operator import attrgetter

import yaml
from docopt import docopt
from salt.exceptions import CommandExecutionError
from salt.ext import six

try:
    from compose.cli.command import get_project
    from compose.service import ConvergenceStrategy
    from compose.config.errors import ConfigurationError
    from compose.project import OneOffFilter

    HAS_COMPOSE = True
except ImportError as e:
    HAS_COMPOSE = e

DC_FILENAME = 'docker-compose.yml'

__virtualname__ = 'composeng'

from compose.cli.main import TopLevelCommand, project_from_options

log = logging.getLogger(__name__)


def __virtual__():
    if HAS_COMPOSE is not True:
        return False, 'Failed to import required Python libraries: {0}'.format(HAS_COMPOSE)

    return __virtualname__


@contextmanager
def __capture_stdout_stderr():
    '''
    Point stdout and stderr to an in memory buffer to capture the output. Reverts streams on exit or error.

    :return:
    '''
    Buffer = namedtuple('Buffer', 'stdout stderr')

    def read(stream):
        def decode():
            return six.text_type(stream.getvalue())

        return decode

    stdout, stderr = None, None
    _stdout, _stderr = sys.stdout, sys.stderr

    try:
        sys.stdout, sys.stderr = stdout, stderr = io.BytesIO(), io.BytesIO()
        yield Buffer(stdout=read(stdout), stderr=read(stderr))
    except Exception:
        raise
    finally:
        sys.stdout, sys.stderr = _stdout, _stderr

        stdout and stdout.close()
        stderr and stderr.close()


def __catch_exception(*exceptions):
    '''
    Decorator to catch exceptions and handle them gracefully.

    :param exceptions:
    :return:
    '''
    if not exceptions:
        exceptions = (Exception,)

    def decorate(func):
        def wrap(*args, **kwargs):
            '''
            Running salt-call from command lines passed extra kwargs to our function that we don't want.
            :param args:
            :param kwargs:
            :return:
            '''
            for key in kwargs.keys():
                if key in ['__pub_fun', '__pub_jid', '__pub_pid', '__pub_tgt', '__pub_user', '__pub_arg', '__pub_tgt_type', '__pub_ret']:
                    del kwargs[key]
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                log.error('''Traceback:
                {}'''.format(traceback.format_exc()))
                raise CommandExecutionError('Caught {} exception while calling {}: {}'.format('.'.join([type(e).__module__, type(e).__name__]), func.__name__, str(e)))

        return wrap

    return decorate


def __read_docker_compose(project_dir):
    '''
    Read the docker-compose.yml file if it exists in the directory

    :param project_dir:
    :return:
    '''
    if os.path.isfile(os.path.join(project_dir, DC_FILENAME)) is False:
        raise CommandExecutionError('Path does not exist or docker-compose.yml is not present')

    try:
        with salt.utils.fopen(os.path.join(project_dir, DC_FILENAME)) as f:
            result = f.read()
    except IOError as e:
        log.error(e)
        raise

    return result


def __get_project(*args, **kwargs):
    '''
    Get Docker Compose project.

    :param args:
    :param kwargs:
    :return:
    '''
    return get_project(*args, **kwargs)


def __docker_compose(project_dir, proj_less=False, **project_options):
    '''
    Instantiate Docker Compose command.

    :param string project_dir: Path to Docker Compose directory.
    :param boolean proj_less: Is project less? Some commands such as `config` are project less. See compose/cli/main.py.
    :param project_options: Project options.
    :return:
    '''
    project_options = __kwarg_to_options(**project_options)

    project = None if proj_less else project_from_options(project_dir, project_options)
    cmd = TopLevelCommand(project, project_dir)
    cmd.project_dir = project_dir

    return cmd


def __get_convergence_plans(project, service_names=None):
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
        ret[cont] = action

    return ret


def __kwarg_to_options(**kwargs):
    '''
    Keyword arguments to cmdline options.

    :param kwargs:
    :return:
    '''
    return {'--{}'.format(k): v for k, v in six.iteritems(kwargs)}


@__catch_exception()
def get_convergence_plans(project_dir):
    '''
    Get convergence plans for a project

    :param project_dir:
    :return:
    '''
    project = __get_project(project_dir)
    return __get_convergence_plans(project)


@__catch_exception()
def get_compose(project_dir):
    '''
    Get the content of the docker-compose file in a directory

    :param project_dir:
    :return:
    '''
    content = __read_docker_compose(project_dir)
    project = __get_project(project_dir)

    if isinstance(project, dict):
        raise CommandExecutionError('Docker compose file is not valid')

    return content


@__catch_exception()
def restart(project_dir, *args, **project_options):
    '''
    Restart container(s) in the docker-compose file

    :param string project_dir: Path to Docker Compose directory.
    :param args:
    :param project_options:
    :return:
    '''
    cmd = __docker_compose(project_dir, **project_options)

    args = list(args)
    _options = docopt(cmd.restart.__doc__, args or [])
    with __capture_stdout_stderr():
        cmd.restart(_options)

    return True


@__catch_exception()
def stop(project_dir, *args, **project_options):
    '''
    Stop container(s) in the docker-compose file

    :param string project_dir: Path to Docker Compose directory.
    :param args:
    :param project_options:
    :return:
    '''
    cmd = __docker_compose(project_dir, **project_options)

    args = list(args)

    _options = docopt(cmd.stop.__doc__, args or [])
    with __capture_stdout_stderr():
        cmd.stop(_options)


@__catch_exception()
def pause(project_dir, *args, **project_options):
    '''
    Pause container(s) in the docker-compose file

    Equivalent to docker-compose pause.

    :param string project_dir: Path to Docker Compose directory.
    :param args:
    :param project_options:
    :return:
    '''
    cmd = __docker_compose(project_dir, **project_options)
    args = list(args)
    _options = docopt(cmd.pause.__doc__, args or [])
    with __capture_stdout_stderr():
        cmd.pause(_options)

    return True


@__catch_exception()
def unpause(project_dir, *args, **project_options):
    '''
    Unpause container(s) in the docker-compose file

    Equivalent to docker-compose pause.

    :param string project_dir: Path to Docker Compose directory.
    :param args:
    :param project_options:

    '''
    cmd = __docker_compose(project_dir, **project_options)

    args = list(args)
    _options = docopt(cmd.unpause.__doc__, args or [])
    with __capture_stdout_stderr():
        cmd.unpause(_options)

    return True


@__catch_exception()
def start(project_dir, *args, **project_options):
    '''
    Bring up Compose project.

    Equivalent to docker-compose start.

    :param string project_dir: Path to Docker Compose directory.
    :param args:
    :param project_options:
    :return:
    '''
    cmd = __docker_compose(project_dir, **project_options)

    _options = docopt(cmd.start.__doc__, args or [])
    with __capture_stdout_stderr():
        cmd.start(_options)

    return True


@__catch_exception()
def kill(project_dir, *args, **project_options):
    '''
    Kill containers in the docker-compose file

    Equivalent to docker-compose kill.

    :param string project_dir: Path to Docker Compose directory.
    :param args:
    :param project_options:
    :return:
    '''
    cmd = __docker_compose(project_dir, **project_options)
    args = list(args)
    _options = docopt(cmd.kill.__doc__, args or [])
    with __capture_stdout_stderr():
        cmd.kill(_options)

    return True


@__catch_exception(ConfigurationError)
def up(project_dir, *args, **project_options):
    '''
    Bring up Compose project.

    Equivalent to docker-compose up.

    :param string project_dir: Path to Docker Compose directory.
    :param args:
    :param project_options:
    :return:
    '''
    cmd = __docker_compose(project_dir, **project_options)

    args = list(args) + ['-d']
    _options = docopt(cmd.up.__doc__, args or [])
    with __capture_stdout_stderr():
        cmd.up(_options)

    return True


@__catch_exception(ConfigurationError)
def config(project_dir, *args, **project_options):
    '''
    Validates and returns a Compose file.

    Equivalent to docker-compose config.

    :param string project_dir: Path to Docker Compose directory.
    :param string args: Arguments for the config command.
    :param project_options:
    :return dict: Valid Docker Compose.
    '''
    cmd = __docker_compose(project_dir, True)

    _options = docopt(cmd.config.__doc__, args or [])
    with __capture_stdout_stderr() as buf:
        cmd.config(__kwarg_to_options(**project_options), _options)
        stdout = buf.stdout()

    return yaml.load(stdout)


get = config  # alias config to get


@__catch_exception()
def down(project_dir, *args, **project_options):
    '''
    Bring down Compose project.

    Equivalent to docker-compose down.

    :param string project_dir: Path to Docker Compose directory.
    :param args:
    :param project_options:
    :return:
    '''
    cmd = __docker_compose(project_dir, **project_options)
    args = list(args)
    _options = docopt(cmd.down.__doc__, args or [])
    with __capture_stdout_stderr():
        cmd.down(_options)

    return True


@__catch_exception()
def pull(path, service_names=None):
    '''
    Pull image for containers in the docker-compose file, service_names is a python list, if omitted pull all images

    :param string project_dir: Path to Docker Compose directory.
    :param list|None service_names: If specified will remove only the specified stopped services
    '''

    project = __get_project(path)

    if isinstance(project, dict):
        raise CommandExecutionError('Unable to load project, docker-compose.yaml file is invalid')

    try:
        project.pull(service_names)
    except Exception:
        raise CommandExecutionError('Pulling containers images via docker-compose failed')

    return True


@__catch_exception()
def rm(project_dir, service_names=None):
    '''
    Remove containers

    Equivalent to docker-compose rm.

    :param string project_dir: Path to Docker Compose directory.
    :param list|None service_names: If specified will remove only the specified stopped services
    :return:
    '''
    project = __get_project(project_dir)
    if isinstance(project, dict):
        raise CommandExecutionError('Unable to load project, docker-compose.yaml file is invalid')

    project.remove_stopped(service_names)

    return True


@__catch_exception()
def build(project_dir, service_names=None):
    '''
    Build image for containers in the docker-compose file, service_names is a
    python list, if omitted build images for all containers. Please note
    that at the moment the module does not allow you to upload your Dockerfile,
    nor any other file you could need with your docker-compose.yml, you will
    have to make sure the files you need are actually in the directory specified
    in the `build` keyword

    :param string project_dir: Path to Docker Compose directory.
    :param list|None service_names: If specified will remove only the specified stopped services
    '''

    project = __get_project(project_dir)
    if isinstance(project, dict):
        raise CommandExecutionError('Unable to load project, docker-compose.yaml file is invalid')

    project.build(service_names)

    return True


@__catch_exception()
def ps(project_dir):
    '''
    List all running containers and report some information about them

    :param string project_dir: Path to Docker Compose directory.
    :return string
    '''

    project = __get_project(project_dir)

    if isinstance(project, dict):
        raise CommandExecutionError('Unable to load project, docker-compose.yaml file is invalid')

    result = {}
    containers = sorted(
        project.containers(None, stopped=True) +
        project.containers(None, OneOffFilter.only),
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

    return result
