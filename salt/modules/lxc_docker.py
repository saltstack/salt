# -*- coding: utf-8 -*-
'''
Work with docker containers

:maturity:      new
:depends:       lxc-docker package
:platform:      Linux kernel 3.8 or above

:configuration: By default, Docker runs at on a unix socket at
    ``unix:///var/run/docker.sock``. If you are running Docker on a TCP socket,
    you can configure your minion to connect to the correct address in
    ``/etc/salt/minion``.

    .. code-block:: yaml

        docker:
          socket: tcp://127.0.0.1:4321

'''

# Import python libs
import logging

#import salt libs
import salt.utils

# Set up logging
log = logging.getLogger(__name__)

# We make a tuple, Docker's CLI likes 3 slashes, python API likes 2 slashes
DEFAULT_SOCKET = ('unix:///var/run/docker.sock', 'unix://var/run/docker.sock')
CLI_SOCKET = DEFAULT_SOCKET[0]
API_SOCKET = DEFAULT_SOCKET[1]


def __virtual__():
    if not salt.utils.which('docker'):
        return False
    try:
        import docker
    except ImportError:
        log.error('Unable to load docker module. ' +
                  'Please install the docker python library')
        return False
    CLI_SOCKET = 'docker -H {}'.format(
            __salt__['config.option']('docker.socket', DEFAULT_SOCKET[0]))
    API_SOCKET = __salt__['config.option']('docker.socket', DEFAULT_SOCKET[1])
    return 'docker'


def _docker_cli():
    '''
    Return a docker connnection client
    '''
    import docker
    cli = docker.Client(base_url=API_SOCKET)
    return cli


def info():
    '''
    Get the version information about docker

    :rtype: dict
    :returns: A dict of the docker system information

    .. code-block:: bash

        salt '*' docker.info

    '''
    from docker import APIError
    try:
        version = _docker_cli().info()
        return version
    except APIError, e:
        log.error(e)
        return {'error': e.explanation}


def version():
    '''
    Get the version information about docker

    :rtype: dict
    :returns: A dict of the version information

    .. code-block:: bash

        salt '*' docker.version

    '''
    from docker import APIError
    try:
        version = _docker_cli().version()
        return version
    except APIError, e:
        log.error(e)
        return [{'error': e.explanation}]


def images(name=None, ids_only=False, all=False):
    '''
    List docker images

    :type name: string
    :param name: A repository name to filter on

    :type ids_only: boolean
    :param ids_only: Only show image ids, returns a list of strings

    :type all: boolean
    :param all: Show all images

    :rtype: list of dicts
    :returns: Meta data about each image with created time,
        Ex:
        [{'Created': 1364102658,
          'Id': u'b750fe792....'
          'Repository': 'ubuntu',
          'Size': 24653,
          'Tag': '12.10',
          'VirtualSize': 180116135}]

    .. code-block::bash

        salt '*' docker.images [name='name'] [ids_only] [all=(True|False)

    '''
    from docker import APIError
    try:
        images = _docker_cli().images(name=name, quiet=ids_only, all=all)
        return images
    except APIError, e:
        log.error(e)
        return [{'error': e.explanation}]


def containers(all=False, limit=-1):
    '''
    List docker containers. Identical to the ``docker ps`` command

    :type all: boolean
    :param all: Whether to list all run containers

    :type limit: int
    :param limit: The number of containers to display

    :rtype: list of dicts
    :returns: A list of dictionaries the container metadata

    .. code-block:: bash

        salt '*' docker.containers [all=False] [limit=-1]

    '''
    from docker import APIError
    try:
        containers = _docker_cli().containers(all=all, limit=limit)
        return containers
    except APIError, e:
        log.error(e)
        return [{'error': e.explanation}]


def history(image):
    '''
    Show the history of an image

    :type image: string
    :param image: The image to inspect

    :rtype: list of dicts
    :returns: A list of dictionaries the history metadata

    .. code-block:: bash

        salt '*' docker.history <image>

    '''
    import json
    from docker import APIError
    try:
        history = json.loads(_docker_cli().history(image=image))
        return history
    except APIError, e:
        log.error(e)
        return [{'error': e.explanation}]


def logs(container):
    '''
    Get the log output from a container

    :type container: string or list of strings
    :param image: The container to get the logs from

    :rtype: string
    :returns: The stdout of the logs command

    .. code-block:: bash

        salt '*' docker.logs <container>

    '''
    cmd = '{} logs {}'.format(CLI_SOCKET, container)

    logs_result = __salt__['cmd.run']([cmd])

    return logs_result


def stop(container, timeout=10):
    '''
    Stop a running container

    :type container: string
    :param container: The running container to stop

    :type timeout: int
    :param timeout: Time to wait in seconds before killing the container.

    :rtype: string
    :returns: The stdout of the stop command

    .. code-block:: bash

        salt '*' docker.stop <container> [container, container, ...] \\
            [timeout=10]

    '''
    cmd = '{} stop '.format(CLI_SOCKET)

    if timeout > 0 and timeout != 10:
        cmd += '-t {} '.format(timeout)

    cmd += container

    stop_result = __salt__['cmd.run']([cmd])

    return stop_result


def restart(container, timeout=10):
    '''
    Restart a running container, but doesn't support attach options.

    :type container: string
    :param container: The running container to restart

    :type timeout: int
    :param timeout: Time to wait in seconds before killing the container. Once
        killed, it will be restarted

    :rtype: string
    :returns: The stdout of the restart command

    .. code-block:: bash

        salt '*' docker.restart <container> [timeout=10]

    '''
    cmd = '{} restart '.format(CLI_SOCKET)

    if timeout > 0 and timeout != 10:
        cmd += '-t {} '.format(timeout)

    cmd += container

    restart_result = __salt__['cmd.run']([cmd])

    return restart_result


def start(container):
    '''
    Restart a stopped container, but doesn't support attach options.

    :type container: string
    :param container: The container to restart

    :rtype: boolean
    :returns: True if the container started correctly
        False if there was an API error

    .. code-block:: bash

        salt '*' docker.start <container>

    '''
    from docker import APIError
    try:
        _docker_cli().start(container=container)
        return True
    except APIError, e:
        log.error(e)
        return False


def kill(container):
    '''
    Kill a running container

    :type container: string
    :param container: The container to kill

    :rtype: string
    :returns: The stdout of the kill command

    .. code-block:: bash

        salt '*' docker.kill <container>

    '''

    cmd = '{} kill {}'.format(CLI_SOCKET, container)

    kill_result = __salt__['cmd.run']([cmd])

    return kill_result


def pull(repository, tag=None):
    '''
    Pull an image or a repository from the docker registry server

    :type repository: string
    :param repository: The maintainer/image name

    :type tag: string
    :param tag: The specific tag of the image in the repository

    :rtype: dict
    :returns: a dict of the last status message
        ex: ``{"status":"Download","progress":"complete","id":"abcdef012345"}``

    .. code-block:: bash

        salt '*' docker.pull <repository> [tag=tag]

    '''

    from docker import APIError
    import json
    try:
        cli = _docker_cli()
        progress = cli.pull(repository=repository, tag=tag)
        last_item = progress[progress.rfind('{'):len(progress)]
        status = json.loads(last_item)
        return status
    except APIError, e:
        log.error(e)
        return {'error': e.explanation}
    except ValueError, e:
        log.error(e)
        return {'error': 'JSON could not load'}


def remove_container(container, remove_vols=False):
    '''
    Remove a stopped container from a system

    :type container: string
    :param container: The stopped container to remove

    :rtype: dict
    :returns: a dict of ``{'removed': 'container_id'}`` if successful
        or ``{'error': 'error_message'}``

    .. code-block:: bash

        salt '*' docker.remove_container <container> [remove_vols=(True|False)]

    '''
    from docker import APIError
    try:
        _docker_cli().remove_container(container, v=remove_vols)
        return {'removed': container}
    except APIError, e:
        log.error(e)
        return {'error': e.explanation}


def remove_image(image):
    '''
    Remove an image from a system

    :type image: string
    :param image: The image to remove

    :rtype: dict
    :returns: a dict of ``{'removed': 'imageid'}`` if successful
        or ``{'error': 'error_message'}``

    .. code-block:: bash

        salt '*' docker.remove_image <image>

    '''
    from docker import APIError
    try:
        _docker_cli().remove_image(image=image)
        return {'removed': image}
    except APIError, e:
        log.error(e)
        return {'error': e.explanation}


def run(image,
        command=None,
        command_args=None,
        cpus=None,
        dns=None,
        env_vars=None,
        entrypoint=None,
        hostname=None,
        mem_limit=None,
        networking=True,
        ports=None,
        privileged=False,
        user=None,
        volumes=None,
        volumes_from=None,
        cwd=None):
    '''
    Run a command in a new container in the background

    :type image: string
    :param image: The image to be run

    :type command: string
    :param command: The command to run in the container

    :type command_args: string
    :param command_args: The arguments to pass to the command.
        Only evaluate if the command parameter is set

    :type cpus: int
    :param cpus: CPU shares (relative weight)

    :type dns: string or list of strings
    :param dns: Set custom dns server(s) for the container

    :type env_vars: dict
    :param env_vars: A dictionalry of environment variables

    :type entrypoint: string
    :param entrypoint: Overwrite the default entrypoint of the image

    :type hostname: string
    :param hostname: Set the container host name

    :type mem_limit: int
    :param mem_limit: Memory limit (in bytes)

    :type networking: boolean
    :param networking: Enable networking for this container

    :type ports: list of strings
    :param ports: Expose a container's port to the host. \
        Valid string examples are ``80``, ``80:80``, or ``5300:53/udp``. \
        See http://docs.docker.io/en/latest/use/port_redirection/ for a
        thorough explanation of formatting

    :type privileged: boolean
    :param privileged: Give extended privileges to this container

    :type user: string
    :param user: Username or UID

    :type volumes: list of strings
    :param volumes: A list of volumes to mount into the container.
        Create a bind mount with: [host-dir]:[container-dir]:[rw|ro]. If
        "host-dir" is missing, then docker creates a new volume.

    :type volumes-from: list of strings
    :param volumes-from: Mount volumes from the specified container

    :rtype: string
    :returns: A string of the container id

    .. code-block:: bash

        salt '*' docker.run <image> [command=cmd] [command_args=args] \\
                [cpus=cpu_shares] [dns=dns_addrs] [env_vars={'k':'v'}] \\
                [entrypoint=entry_cmd] [hostname=hostname] [mem_limit=limit] \\
                [networking=(True|False)] [ports=['1234:1234/udp']] \\
                [privileged=(True|False)] [user=(username|UID)] \\
                [volumes=['/host:/container:ro']] \\
                [volumes_from=['/container/vol']] [cwd='/cwd/']

    '''
    cmd = '{} run -d '.format(CLI_SOCKET)

    if cpus is not None and int(cpus) <= __grains__['num_cpus']:
        cmd += '-c {} '.format(cpus)

    if dns is not None:
        if type(dns) is list:
            for ns in dns:
                cmd += '-dns {} '.format(ns)
        elif type(dns) is str:
            cmd += '-dns {} '.format(dns)

    if env_vars is not None and type(env_vars) is dict:
        for k, v in env_vars.iteritems():
            cmd += '-e {}={} '.format(k, v)

    if entrypoint is not None:
        cmd += '-entrypoint {} '.format(entrypoint)

    if hostname is not None and type(hostname) is str:
        cmd += '-h {} '.format(hostname)

    if mem_limit is not None:
        cmd += '-m {} '.format(mem_limit)

    if networking is False:
        cmd += '-n false '

    if ports is not None and len(ports) > 0:
        for port in ports:
            cmd += '-p {} '.format(port)

    if privileged:
        cmd += '-privileged=true '

    if user is not None:
        cmd += '-u {} '.format(user)

    if volumes is not None and len(volumes) > 0:
        for volume in volumes:
            cmd += '-v {} '.format(volume)

    if volumes_from is not None and len(volumes) > 0:

        for vol in volumes_from:
            cmd += '-volumes-from {} '.format(volumes_from)

    cmd += image

    if command is not None:
        cmd += ' {}'.format(command)
        if command_args is not None:
            cmd += ' {}'.format(command_args)

    log.debug('Running docker container with command: {}'.format(cmd))

    container_id = __salt__['cmd.run']([cmd])

    return container_id
