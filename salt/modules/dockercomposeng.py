# -*- coding: utf-8 -*-
'''
dockercomposeng exposes a more accurate and direct interface to the original Compose library.

As the `compose` package from Docker is [intentionally undocumented](https://github.com/docker/compose/issues/4542),
the new module chose to interface with Compose through the same code it's CLI interface uses via docopt (the argument
parser). This should mean this new module will be more resilient to internal changes in the Compose library. New
parameters and options to any `docker-compose` command we have already wraped will be supported with no code changes
to the module. The new module also returns unmodified output directly from the Compose library in a more consistent
format and throws exceptions when necessary making it easier to work with.


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

:depends: docker-compose
'''

from __future__ import absolute_import
import io
import logging
import sys
import traceback
import os
import salt.utils
import collections
import contextlib
import operator
import yaml
import docopt

from salt.exceptions import CommandExecutionError
import salt.ext.six as six

try:
    import compose.cli.main
    import compose.cli.command
    import compose.service
    import compose.config.errors
    import compose.project

    HAS_COMPOSE = True
except ImportError as e:
    HAS_COMPOSE = e

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

DC_FILENAME = 'docker-compose.yml'

__virtualname__ = 'dockercomposeng'

log = logging.getLogger(__name__)


def __virtual__():
    if HAS_COMPOSE is not True:
        return False, 'Failed to import required Python libraries: {0}'.format(HAS_COMPOSE)

    return __virtualname__


@contextlib.contextmanager
def __capture_stdout_stderr():
    '''
    Point stdout and stderr to an in memory buffer to capture the output. Reverts streams on exit or error.

    :return:
    '''
    Buffer = collections.namedtuple('Buffer', 'stdout stderr')

    def read(stream):
        def decode():
            return six.text_type(stream.getvalue())

        return decode

    stdout, stderr = None, None

    try:
        sys.stdout, sys.stderr = stdout, stderr = StringIO(), StringIO()
        yield Buffer(stdout=read(stdout), stderr=read(stderr))
    except Exception:
        raise
    finally:
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__

        if stdout:
            stdout.close()
        if stderr:
            stderr.close()


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
            for key in ['__pub_fun', '__pub_jid', '__pub_pid', '__pub_tgt', '__pub_user', '__pub_arg', '__pub_tgt_type', '__pub_ret']:
                if key in kwargs:
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
    return compose.cli.command.get_project(*args, **kwargs)


def __docker_compose(project_dir, proj_less=False, **project_options):
    '''
    Instantiate Docker Compose command.

    :param string project_dir: Path to Docker Compose directory.
    :param boolean proj_less: Is project less? Some commands such as `config` are project less. See compose/cli/main.py.
    :param project_options: Project options.
    :return:
    '''
    project_options = __kwarg_to_options(**project_options)

    project = None if proj_less else compose.cli.main.project_from_options(project_dir, project_options)
    cmd = compose.cli.main.TopLevelCommand(project, project_dir)
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
                                           compose.service.ConvergenceStrategy.changed)
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

    CLI Example:

    .. code-block:: bash

        salt 'myminion' dockercomposeng.get_convergence_plans /path/to/project/dir
    '''
    project = __get_project(project_dir)
    return __get_convergence_plans(project)


@__catch_exception()
def get_compose(project_dir):
    '''
    Get the content of the docker-compose file in a directory

    :param project_dir:
    :return:

    CLI Example:

    .. code-block:: bash

        salt 'myminion' dockercomposeng.get_compose /path/to/project/dir
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

    CLI Example:

    .. code-block:: bash

        salt 'myminion' dockercomposeng.restart /path/to/project/dir [foobar]
    '''
    cmd = __docker_compose(project_dir, **project_options)

    args = list(args)
    _options = docopt.docopt(cmd.restart.__doc__, args or [])
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

    CLI Example:

    .. code-block:: bash

        salt 'myminion' dockercomposeng.stop /path/to/project/dir [foobar]
    '''
    cmd = __docker_compose(project_dir, **project_options)

    args = list(args)

    _options = docopt.docopt(cmd.stop.__doc__, args or [])
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

    CLI Example:

    .. code-block:: bash

        salt 'myminion' dockercomposeng.pause /path/to/project/dir [foobar]
    '''
    cmd = __docker_compose(project_dir, **project_options)
    args = list(args)
    _options = docopt.docopt(cmd.pause.__doc__, args or [])
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
    :return:

    CLI Example:

    .. code-block:: bash

        salt 'myminion' dockercomposeng.unpause /path/to/project/dir [foobar]
    '''
    cmd = __docker_compose(project_dir, **project_options)

    args = list(args)
    _options = docopt.docopt(cmd.unpause.__doc__, args or [])
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

    CLI Example:

    .. code-block:: bash

        salt 'myminion' dockercomposeng.start /path/to/project/dir [foobar]
    '''
    cmd = __docker_compose(project_dir, **project_options)

    _options = docopt.docopt(cmd.start.__doc__, args or [])
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

    CLI Example:

    .. code-block:: bash

        salt 'myminion' dockercomposeng.kill /path/to/project/dir [foobar]
    '''
    cmd = __docker_compose(project_dir, **project_options)
    args = list(args)
    _options = docopt.docopt(cmd.kill.__doc__, args or [])
    with __capture_stdout_stderr():
        cmd.kill(_options)

    return True


@__catch_exception(compose.config.errors.ConfigurationError)
def up(project_dir, *args, **project_options):
    '''
    Bring up Compose project.

    Equivalent to docker-compose up.

    :param string project_dir: Path to Docker Compose directory.
    :param args:
    :param project_options:
    :return:

    CLI Example:

    .. code-block:: bash

        salt 'myminion' dockercomposeng.up /path/to/project/dir [foobar]
    '''
    cmd = __docker_compose(project_dir, **project_options)

    args = list(args) + ['-d']
    _options = docopt.docopt(cmd.up.__doc__, args or [])
    with __capture_stdout_stderr():
        cmd.up(_options)

    return True


@__catch_exception(compose.config.errors.ConfigurationError)
def config(project_dir, *args, **project_options):
    '''
    Validates and returns a Compose file.

    Equivalent to docker-compose config.

    :param string project_dir: Path to Docker Compose directory.
    :param string args: Arguments for the config command.
    :param project_options:
    :return dict: Valid Docker Compose.

    CLI Example:

    .. code-block:: bash

        salt 'myminion' dockercomposeng.config /path/to/project/dir [foobar]
    '''
    cmd = __docker_compose(project_dir, True)

    _options = docopt.docopt(cmd.config.__doc__, args or [])
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

    CLI Example:

    .. code-block:: bash

        salt 'myminion' dockercomposeng.down /path/to/project/dir [foobar]
    '''
    cmd = __docker_compose(project_dir, **project_options)
    args = list(args)
    _options = docopt.docopt(cmd.down.__doc__, args or [])
    with __capture_stdout_stderr():
        cmd.down(_options)

    return True


@__catch_exception()
def pull(project_dir, *args, **project_options):
    '''
    Pull image for containers in the docker-compose file, service_names is a python list, if omitted pull all images

    :param string project_dir: Path to Docker Compose directory.
    :param args:
    :param project_options:
    :return:

    CLI Example:

    .. code-block:: bash

        salt 'myminion' dockercomposeng.pull /path/to/project/dir [service_names]
    '''
    cmd = __docker_compose(project_dir, **project_options)
    args = list(args)
    _options = docopt.docopt(cmd.pull.__doc__, args or [])
    with __capture_stdout_stderr():
        cmd.pull(_options)

    return True


@__catch_exception()
def rm(project_dir, *args, **project_options):
    '''
    Remove containers

    Equivalent to docker-compose rm.

    :param string project_dir: Path to Docker Compose directory.
    :param list|None service_names: If specified will remove only the specified stopped services
    :return:

    CLI Example:

    .. code-block:: bash

        salt 'myminion' dockercomposeng.rm /path/to/project/dir [service_names]
    '''
    cmd = __docker_compose(project_dir, **project_options)
    args = list(args) + ['-f']
    _options = docopt.docopt(cmd.rm.__doc__, args or [])
    with __capture_stdout_stderr():
        cmd.rm(_options)

    return True


@__catch_exception()
def build(project_dir, *args, **project_options):
    '''
    Build image for containers in the docker-compose file, Please note
    that at the moment the module does not allow you to upload your Dockerfile,
    nor any other file you could need with your docker-compose.yml, you will
    have to make sure the files you need are actually in the directory specified
    in the `build` keyword

    :param string project_dir: Path to Docker Compose directory.
    :param list|None service_names: If specified will remove only the specified stopped services
    :return:

    CLI Example:

    .. code-block:: bash

        salt 'myminion' dockercomposeng.build /path/to/project/dir [service_names]
    '''
    cmd = __docker_compose(project_dir, **project_options)
    args = list(args)
    _options = docopt.docopt(cmd.build.__doc__, args or [])
    with __capture_stdout_stderr():
        cmd.build(_options)

    return True


@__catch_exception()
def ps(project_dir):
    '''
    List all running containers and report some information about them

    :param string project_dir: Path to Docker Compose directory.
    :return string

    CLI Example:

    .. code-block:: bash

        salt 'myminion' dockercomposeng.ps /path/to/project/dir
    '''
    project = __get_project(project_dir)

    if isinstance(project, dict):
        raise CommandExecutionError('Unable to load project, docker-compose.yaml file is invalid')

    result = {}
    containers = sorted(
        project.containers(None, stopped=True) +
        project.containers(None, compose.project.OneOffFilter.only),
        key=operator.attrgetter('name'))

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
