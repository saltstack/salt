"""
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

.. code-block:: text

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
- Manage service definitions:
    - :py:func:`dockercompose.service_create <salt.modules.dockercompose.ps>`
    - :py:func:`dockercompose.service_upsert <salt.modules.dockercompose.ps>`
    - :py:func:`dockercompose.service_remove <salt.modules.dockercompose.ps>`
    - :py:func:`dockercompose.service_set_tag <salt.modules.dockercompose.ps>`

Detailed Function Documentation
-------------------------------
"""


import inspect
import logging
import os
import re
from operator import attrgetter

import salt.utils.files
import salt.utils.stringutils
from salt.serializers import json
from salt.utils import yaml

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
VERSION_RE = r"([\d.]+)"

log = logging.getLogger(__name__)
debug = False

__virtualname__ = "dockercompose"
DEFAULT_DC_FILENAMES = ("docker-compose.yml", "docker-compose.yaml")


def __virtual__():
    if HAS_DOCKERCOMPOSE:
        match = re.match(VERSION_RE, str(compose.__version__))
        if match:
            version = tuple(int(x) for x in match.group(1).split("."))
            if version >= MIN_DOCKERCOMPOSE:
                return __virtualname__
    return (
        False,
        "The dockercompose execution module not loaded: "
        "compose python library not available.",
    )


def __standardize_result(status, message, data=None, debug_msg=None):
    """
    Standardizes all responses

    :param status:
    :param message:
    :param data:
    :param debug_msg:
    :return:
    """
    result = {"status": status, "message": message}

    if data is not None:
        result["return"] = data

    if debug_msg is not None and debug:
        result["debug"] = debug_msg

    return result


def __get_docker_file_path(path):
    """
    Determines the filepath to use

    :param path:
    :return:
    """
    if os.path.isfile(path):
        return path
    for dc_filename in DEFAULT_DC_FILENAMES:
        file_path = os.path.join(path, dc_filename)
        if os.path.isfile(file_path):
            return file_path
    # implicitly return None


def __read_docker_compose_file(file_path):
    """
    Read the compose file if it exists in the directory

    :param file_path:
    :return:
    """
    if not os.path.isfile(file_path):
        return __standardize_result(
            False, "Path {} is not present".format(file_path), None, None
        )
    try:
        with salt.utils.files.fopen(file_path, "r") as fl:
            file_name = os.path.basename(file_path)
            result = {file_name: ""}
            for line in fl:
                result[file_name] += salt.utils.stringutils.to_unicode(line)
    except OSError:
        return __standardize_result(
            False, "Could not read {}".format(file_path), None, None
        )
    return __standardize_result(
        True, "Reading content of {}".format(file_path), result, None
    )


def __load_docker_compose(path):
    """
    Read the compose file and load its' contents

    :param path:
    :return:
    """
    file_path = __get_docker_file_path(path)
    if file_path is None:
        msg = "Could not find docker-compose file at {}".format(path)
        return None, __standardize_result(False, msg, None, None)
    if not os.path.isfile(file_path):
        return (
            None,
            __standardize_result(
                False, "Path {} is not present".format(file_path), None, None
            ),
        )
    try:
        with salt.utils.files.fopen(file_path, "r") as fl:
            loaded = yaml.load(fl)
    except OSError:
        return (
            None,
            __standardize_result(
                False, "Could not read {}".format(file_path), None, None
            ),
        )
    except yaml.YAMLError as yerr:
        msg = "Could not parse {} {}".format(file_path, yerr)
        return None, __standardize_result(False, msg, None, None)
    if not loaded:
        msg = "Got empty compose file at {}".format(file_path)
        return None, __standardize_result(False, msg, None, None)
    if "services" not in loaded:
        loaded["services"] = {}
    result = {"compose_content": loaded, "file_name": os.path.basename(file_path)}
    return result, None


def __dump_docker_compose(path, content, already_existed):
    """
    Dumps

    :param path:
    :param content: the not-yet dumped content
    :return:
    """
    try:
        dumped = yaml.safe_dump(content, indent=2, default_flow_style=False)
        return __write_docker_compose(path, dumped, already_existed)
    except TypeError as t_err:
        msg = "Could not dump {} {}".format(content, t_err)
        return __standardize_result(False, msg, None, None)


def __write_docker_compose(path, docker_compose, already_existed):
    """
    Write docker-compose to a path
    in order to use it with docker-compose ( config check )

    :param path:

    docker_compose
        contains the docker-compose file

    :return:
    """
    if path.lower().endswith((".yml", ".yaml")):
        file_path = path
        dir_name = os.path.dirname(path)
    else:
        dir_name = path
        file_path = os.path.join(dir_name, DEFAULT_DC_FILENAMES[0])
    if os.path.isdir(dir_name) is False:
        os.mkdir(dir_name)
    try:
        with salt.utils.files.fopen(file_path, "w") as fl:
            fl.write(salt.utils.stringutils.to_str(docker_compose))
    except OSError:
        return __standardize_result(
            False, "Could not write {}".format(file_path), None, None
        )
    project = __load_project_from_file_path(file_path)
    if isinstance(project, dict):
        if not already_existed:
            os.remove(file_path)
        return project
    return file_path


def __load_project(path):
    """
    Load a docker-compose project from path

    :param path:
    :return:
    """
    file_path = __get_docker_file_path(path)
    if file_path is None:
        msg = "Could not find docker-compose file at {}".format(path)
        return __standardize_result(False, msg, None, None)
    return __load_project_from_file_path(file_path)


def __load_project_from_file_path(file_path):
    """
    Load a docker-compose project from file path

    :param path:
    :return:
    """
    try:
        project = get_project(
            project_dir=os.path.dirname(file_path),
            config_path=[os.path.basename(file_path)],
        )
    except Exception as inst:  # pylint: disable=broad-except
        return __handle_except(inst)
    return project


def __load_compose_definitions(path, definition):
    """
    Will load the compose file located at path
    Then determines the format/contents of the sent definition

    err or results are only set if there were any

    :param path:
    :param definition:
    :return tuple(compose_result, loaded_definition, err):
    """
    compose_result, err = __load_docker_compose(path)
    if err:
        return None, None, err
    if isinstance(definition, dict):
        return compose_result, definition, None
    elif definition.strip().startswith("{"):
        try:
            loaded_definition = json.deserialize(definition)
        except json.DeserializationError as jerr:
            msg = "Could not parse {} {}".format(definition, jerr)
            return None, None, __standardize_result(False, msg, None, None)
    else:
        try:
            loaded_definition = yaml.load(definition)
        except yaml.YAMLError as yerr:
            msg = "Could not parse {} {}".format(definition, yerr)
            return None, None, __standardize_result(False, msg, None, None)
    return compose_result, loaded_definition, None


def __dump_compose_file(path, compose_result, success_msg, already_existed):
    """
    Utility function to dump the compose result to a file.

    :param path:
    :param compose_result:
    :param success_msg: the message to give upon success
    :return:
    """
    ret = __dump_docker_compose(
        path, compose_result["compose_content"], already_existed
    )
    if isinstance(ret, dict):
        return ret
    return __standardize_result(
        True, success_msg, compose_result["compose_content"], None
    )


def __handle_except(inst):
    """
    Handle exception and return a standard result

    :param inst:
    :return:
    """
    return __standardize_result(
        False,
        "Docker-compose command {} failed".format(inspect.stack()[1][3]),
        "{}".format(inst),
        None,
    )


def _get_convergence_plans(project, service_names):
    """
    Get action executed for each container

    :param project:
    :param service_names:
    :return:
    """
    ret = {}
    plans = project._get_convergence_plans(
        project.get_services(service_names), ConvergenceStrategy.changed
    )
    for cont in plans:
        (action, container) = plans[cont]
        if action == "create":
            ret[cont] = "Creating container"
        elif action == "recreate":
            ret[cont] = "Re-creating container"
        elif action == "start":
            ret[cont] = "Starting container"
        elif action == "noop":
            ret[cont] = "Container is up to date"
    return ret


def get(path):
    """
    Get the content of the docker-compose file into a directory

    path
        Path where the docker-compose file is stored on the server

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.get /path/where/docker-compose/stored
    """
    file_path = __get_docker_file_path(path)
    if file_path is None:
        return __standardize_result(
            False, "Path {} is not present".format(path), None, None
        )
    salt_result = __read_docker_compose_file(file_path)
    if not salt_result["status"]:
        return salt_result
    project = __load_project(path)
    if isinstance(project, dict):
        salt_result["return"]["valid"] = False
    else:
        salt_result["return"]["valid"] = True
    return salt_result


def create(path, docker_compose):
    """
    Create and validate a docker-compose file into a directory

    path
        Path where the docker-compose file will be stored on the server

    docker_compose
        docker_compose file

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.create /path/where/docker-compose/stored content
    """
    if docker_compose:
        ret = __write_docker_compose(path, docker_compose, already_existed=False)
        if isinstance(ret, dict):
            return ret
    else:
        return __standardize_result(
            False,
            "Creating a docker-compose project failed, you must send a valid"
            " docker-compose file",
            None,
            None,
        )
    return __standardize_result(
        True,
        "Successfully created the docker-compose file",
        {"compose.base_dir": path},
        None,
    )


def pull(path, service_names=None):
    """
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
    """

    project = __load_project(path)
    if isinstance(project, dict):
        return project
    else:
        try:
            project.pull(service_names)
        except Exception as inst:  # pylint: disable=broad-except
            return __handle_except(inst)
    return __standardize_result(
        True, "Pulling containers images via docker-compose succeeded", None, None
    )


def build(path, service_names=None):
    """
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
    """

    project = __load_project(path)
    if isinstance(project, dict):
        return project
    else:
        try:
            project.build(service_names)
        except Exception as inst:  # pylint: disable=broad-except
            return __handle_except(inst)
    return __standardize_result(
        True, "Building containers images via docker-compose succeeded", None, None
    )


def restart(path, service_names=None):
    """
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
    """

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
                    if (
                        service_names is None
                        or container.get("Name")[1:] in service_names
                    ):
                        container.inspect_if_not_inspected()
                        debug_ret[container.get("Name")] = container.inspect()
                        result[container.get("Name")] = "restarted"
        except Exception as inst:  # pylint: disable=broad-except
            return __handle_except(inst)
    return __standardize_result(
        True, "Restarting containers via docker-compose", result, debug_ret
    )


def stop(path, service_names=None):
    """
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
    """

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
                    if (
                        service_names is None
                        or container.get("Name")[1:] in service_names
                    ):
                        container.inspect_if_not_inspected()
                        debug_ret[container.get("Name")] = container.inspect()
                        result[container.get("Name")] = "stopped"
        except Exception as inst:  # pylint: disable=broad-except
            return __handle_except(inst)
    return __standardize_result(
        True, "Stopping containers via docker-compose", result, debug_ret
    )


def pause(path, service_names=None):
    """
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
    """

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
                    if (
                        service_names is None
                        or container.get("Name")[1:] in service_names
                    ):
                        container.inspect_if_not_inspected()
                        debug_ret[container.get("Name")] = container.inspect()
                        result[container.get("Name")] = "paused"
        except Exception as inst:  # pylint: disable=broad-except
            return __handle_except(inst)
    return __standardize_result(
        True, "Pausing containers via docker-compose", result, debug_ret
    )


def unpause(path, service_names=None):
    """
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
    """

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
                    if (
                        service_names is None
                        or container.get("Name")[1:] in service_names
                    ):
                        container.inspect_if_not_inspected()
                        debug_ret[container.get("Name")] = container.inspect()
                        result[container.get("Name")] = "unpaused"
        except Exception as inst:  # pylint: disable=broad-except
            return __handle_except(inst)
    return __standardize_result(
        True, "Un-Pausing containers via docker-compose", result, debug_ret
    )


def start(path, service_names=None):
    """
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
    """

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
                    if (
                        service_names is None
                        or container.get("Name")[1:] in service_names
                    ):
                        container.inspect_if_not_inspected()
                        debug_ret[container.get("Name")] = container.inspect()
                        result[container.get("Name")] = "started"
        except Exception as inst:  # pylint: disable=broad-except
            return __handle_except(inst)
    return __standardize_result(
        True, "Starting containers via docker-compose", result, debug_ret
    )


def kill(path, service_names=None):
    """
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
    """

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
                    if (
                        service_names is None
                        or container.get("Name")[1:] in service_names
                    ):
                        container.inspect_if_not_inspected()
                        debug_ret[container.get("Name")] = container.inspect()
                        result[container.get("Name")] = "killed"
        except Exception as inst:  # pylint: disable=broad-except
            return __handle_except(inst)
    return __standardize_result(
        True, "Killing containers via docker-compose", result, debug_ret
    )


def rm(path, service_names=None):
    """
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
    """

    project = __load_project(path)
    if isinstance(project, dict):
        return project
    else:
        try:
            project.remove_stopped(service_names)
        except Exception as inst:  # pylint: disable=broad-except
            return __handle_except(inst)
    return __standardize_result(
        True, "Removing stopped containers via docker-compose", None, None
    )


def ps(path):
    """
    List all running containers and report some information about them

    path
        Path where the docker-compose file is stored on the server

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.ps /path/where/docker-compose/stored
    """

    project = __load_project(path)
    result = {}
    if isinstance(project, dict):
        return project
    else:
        if USE_FILTERCLASS:
            containers = sorted(
                project.containers(None, stopped=True)
                + project.containers(None, OneOffFilter.only),
                key=attrgetter("name"),
            )
        else:
            containers = sorted(
                project.containers(None, stopped=True)
                + project.containers(None, one_off=True),
                key=attrgetter("name"),
            )
        for container in containers:
            command = container.human_readable_command
            if len(command) > 30:
                command = "{} ...".format(command[:26])
            result[container.name] = {
                "id": container.id,
                "name": container.name,
                "command": command,
                "state": container.human_readable_state,
                "ports": container.human_readable_ports,
            }
    return __standardize_result(True, "Listing docker-compose containers", result, None)


def up(path, service_names=None):
    """
    Create and start containers defined in the docker-compose.yml file
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
    """

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
                    if (
                        service_names is None
                        or container.get("Name")[1:] in service_names
                    ):
                        container.inspect_if_not_inspected()
                        debug_ret[container.get("Name")] = container.inspect()
        except Exception as inst:  # pylint: disable=broad-except
            return __handle_except(inst)
    return __standardize_result(
        True, "Adding containers via docker-compose", result, debug_ret
    )


def service_create(path, service_name, definition):
    """
    Create the definition of a docker-compose service
    This fails when the service already exists
    This does not pull or up the service
    This wil re-write your yaml file. Comments will be lost. Indentation is set to 2 spaces

    path
        Path where the docker-compose file is stored on the server
    service_name
        Name of the service to create
    definition
        Service definition as yaml or json string

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.service_create /path/where/docker-compose/stored service_name definition
    """
    compose_result, loaded_definition, err = __load_compose_definitions(
        path, definition
    )
    if err:
        return err
    services = compose_result["compose_content"]["services"]
    if service_name in services:
        msg = "Service {} already exists".format(service_name)
        return __standardize_result(False, msg, None, None)
    services[service_name] = loaded_definition
    return __dump_compose_file(
        path,
        compose_result,
        "Service {} created".format(service_name),
        already_existed=True,
    )


def service_upsert(path, service_name, definition):
    """
    Create or update the definition of a docker-compose service
    This does not pull or up the service
    This wil re-write your yaml file. Comments will be lost. Indentation is set to 2 spaces

    path
        Path where the docker-compose file is stored on the server
    service_name
        Name of the service to create
    definition
        Service definition as yaml or json string

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.service_upsert /path/where/docker-compose/stored service_name definition
    """
    compose_result, loaded_definition, err = __load_compose_definitions(
        path, definition
    )
    if err:
        return err
    services = compose_result["compose_content"]["services"]
    if service_name in services:
        msg = "Service {} already exists".format(service_name)
        return __standardize_result(False, msg, None, None)
    services[service_name] = loaded_definition
    return __dump_compose_file(
        path,
        compose_result,
        "Service definition for {} is set".format(service_name),
        already_existed=True,
    )


def service_remove(path, service_name):
    """
    Remove the definition of a docker-compose service
    This does not rm the container
    This wil re-write your yaml file. Comments will be lost. Indentation is set to 2 spaces

    path
        Path where the docker-compose file is stored on the server
    service_name
        Name of the service to remove

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.service_remove /path/where/docker-compose/stored service_name
    """
    compose_result, err = __load_docker_compose(path)
    if err:
        return err
    services = compose_result["compose_content"]["services"]
    if service_name not in services:
        return __standardize_result(
            False, "Service {} did not exists".format(service_name), None, None
        )
    del services[service_name]
    return __dump_compose_file(
        path,
        compose_result,
        "Service {} is removed from {}".format(service_name, path),
        already_existed=True,
    )


def service_set_tag(path, service_name, tag):
    """
    Change the tag of a docker-compose service
    This does not pull or up the service
    This wil re-write your yaml file. Comments will be lost. Indentation is set to 2 spaces

    path
        Path where the docker-compose file is stored on the server
    service_name
        Name of the service to remove
    tag
        Name of the tag (often used as version) that the service image should have

    CLI Example:

    .. code-block:: bash

        salt myminion dockercompose.service_create /path/where/docker-compose/stored service_name tag
    """
    compose_result, err = __load_docker_compose(path)
    if err:
        return err
    services = compose_result["compose_content"]["services"]
    if service_name not in services:
        return __standardize_result(
            False, "Service {} did not exists".format(service_name), None, None
        )
    if "image" not in services[service_name]:
        return __standardize_result(
            False,
            'Service {} did not contain the variable "image"'.format(service_name),
            None,
            None,
        )
    image = services[service_name]["image"].split(":")[0]
    services[service_name]["image"] = "{}:{}".format(image, tag)
    return __dump_compose_file(
        path,
        compose_result,
        'Service {} is set to tag "{}"'.format(service_name, tag),
        already_existed=True,
    )
