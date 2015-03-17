# -*- coding: utf-8 -*-
'''
Management of Dockers
=====================

.. versionadded:: 2014.1.0

.. note::

    The DockerIO integration is still in beta; the API is subject to change

General Notes
-------------

As we use states, we don't want to be continuously popping dockers, so we
will map each container id (or image) with a grain whenever it is relevant.

As a corollary, we will resolve a container id either directly by the id
or try to find a container id matching something stocked in grain.

Installation Prerequisites
--------------------------

- You will need the ``docker-py`` python package in your python installation
  path that is running salt. Its version should support `Docker Remote API
  v1.12 <http://docs.docker.io/en/latest/reference/api/docker_remote_api_v1.12>`_.

  Currently, ``docker-py 0.5.0`` is known to support `Docker Remote API v1.12
  <http://docs.docker.io/en/latest/reference/api/docker_remote_api_v1.12>`_

  .. code-block:: bash

      pip install docker-py==0.5.0

Prerequisite Pillar Configuration for Authentication
----------------------------------------------------

- To push or pull you will need to be authenticated as the ``docker-py`` bindings
  require it
- For this to happen, you will need to configure a mapping in the pillar
  representing your per URL authentication bits:

  .. code-block:: yaml

      docker-registries:
          registry_url:
              email: foo@foo.com
              password: s3cr3t
              username: foo

- You need at least an entry to the default docker index:

  .. code-block:: yaml

      docker-registries:
          https://index.docker.io/v1/:
              email: foo@foo.com
              password: s3cr3t
              username: foo

- You can define multiple registry blocks for them to be aggregated. The only thing to keep
  in mind is that their ID must finish with ``-docker-registries``:

  .. code-block:: yaml

      ac-docker-registries:
          https://index.bar.io/v1/:
              email: foo@foo.com
              password: s3cr3t
              username: foo

      ab-docker-registries:
          https://index.foo.io/v1/:
              email: foo@foo.com
              password: s3cr3t
              username: foo

  This could be also written as:

  .. code-block:: yaml

      docker-registries:
          https://index.bar.io/v1/:
              email: foo@foo.com
              password: s3cr3t
              username: foo
          https://index.foo.io/v1/:
              email: foo@foo.com
              password: s3cr3t
              username: foo

Methods
_______

- Registry Dialog
    - :py:func:`login<salt.modules.dockerio.login>`
    - :py:func:`push<salt.modules.dockerio.push>`
    - :py:func:`pull<salt.modules.dockerio.pull>`
- Docker Management
    - :py:func:`version<salt.modules.dockerio.version>`
    - :py:func:`info<salt.modules.dockerio.info>`
- Image Management
    - :py:func:`search<salt.modules.dockerio.search>`
    - :py:func:`inspect_image<salt.modules.dockerio.inspect_image>`
    - :py:func:`get_images<salt.modules.dockerio.get_images>`
    - :py:func:`remove_image<salt.modules.dockerio.remove_image>`
    - :py:func:`import_image<salt.modules.dockerio.import_image>`
    - :py:func:`build<salt.modules.dockerio.build>`
    - :py:func:`tag<salt.modules.dockerio.tag>`
- Container Management
    - :py:func:`start<salt.modules.dockerio.start>`
    - :py:func:`stop<salt.modules.dockerio.stop>`
    - :py:func:`restart<salt.modules.dockerio.restart>`
    - :py:func:`kill<salt.modules.dockerio.kill>`
    - :py:func:`wait<salt.modules.dockerio.wait>`
    - :py:func:`get_containers<salt.modules.dockerio.get_containers>`
    - :py:func:`inspect_container<salt.modules.dockerio.inspect_container>`
    - :py:func:`remove_container<salt.modules.dockerio.remove_container>`
    - :py:func:`is_running<salt.modules.dockerio.is_running>`
    - :py:func:`top<salt.modules.dockerio.top>`
    - :py:func:`port<salt.modules.dockerio.port>`
    - :py:func:`logs<salt.modules.dockerio.logs>`
    - :py:func:`diff<salt.modules.dockerio.diff>`
    - :py:func:`commit<salt.modules.dockerio.commit>`
    - :py:func:`create_container<salt.modules.dockerio.create_container>`
    - :py:func:`export<salt.modules.dockerio.export>`
    - :py:func:`get_container_root<salt.modules.dockerio.get_container_root>`

Runtime Execution within a specific, already existing/running container
--------------------------------------------------------------------------

Idea is to use `lxc-attach <http://linux.die.net/man/1/lxc-attach>`_ to execute
inside the container context.
We do not want to use ``docker run`` but want to execute something inside a
running container.

These are the available methods:

- :py:func:`retcode<salt.modules.dockerio.retcode>`
- :py:func:`run<salt.modules.dockerio.run>`
- :py:func:`run_all<salt.modules.dockerio.run_all>`
- :py:func:`run_stderr<salt.modules.dockerio.run_stderr>`
- :py:func:`run_stdout<salt.modules.dockerio.run_stdout>`
- :py:func:`script<salt.modules.dockerio.script>`
- :py:func:`script_retcode<salt.modules.dockerio.script_retcode>`

'''
__docformat__ = 'restructuredtext en'

import datetime
import json
import logging
import os
import re
import traceback
import shutil
import types

from salt.modules import cmdmod
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt._compat import string_types
import salt.utils
import salt.utils.odict

try:
    import docker
    HAS_DOCKER = True
except ImportError:
    HAS_DOCKER = False

HAS_NSENTER = bool(salt.utils.which('nsenter'))


log = logging.getLogger(__name__)

INVALID_RESPONSE = 'We did not get any expected answer from docker'
VALID_RESPONSE = ''
NOTSET = object()
base_status = {
    'status': None,
    'id': None,
    'comment': '',
    'out': None
}

# Define the module's virtual name
__virtualname__ = 'docker'


def __virtual__():
    '''
    Only load if docker libs are present
    '''
    if HAS_DOCKER:
        return __virtualname__
    return False


def _sizeof_fmt(num):
    '''
    Return disk format size data
    '''
    for unit in ['bytes', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if num < 1024.0:
            return '{0:3.1f} {1}'.format(num, unit)
        num /= 1024.0


def _set_status(m,
                id_=NOTSET,
                comment=INVALID_RESPONSE,
                status=False,
                out=None):
    '''
    Assign status data to a dict
    '''
    m['comment'] = comment
    m['status'] = status
    m['out'] = out
    if id_ is not NOTSET:
        m['id'] = id_
    return m


def _invalid(m, id_=NOTSET, comment=INVALID_RESPONSE, out=None):
    '''
    Return invalid status
    '''
    return _set_status(m, status=False, id_=id_, comment=comment, out=out)


def _valid(m, id_=NOTSET, comment=VALID_RESPONSE, out=None):
    '''
    Return valid status
    '''
    return _set_status(m, status=True, id_=id_, comment=comment, out=out)


def _get_client(version=None, timeout=None):
    '''
    Get a connection to a docker API (socket or URL)
    based on config.get mechanism (pillar -> grains)

    By default it will use the base docker-py defaults which
    at the time of writing are using the local socket and
    the 1.4 API

    Set those keys in your configuration tree somehow:

        - docker.url: URL to the docker service
        - docker.version: API version to use

    '''
    kwargs = {}
    get = __salt__['config.get']
    for k, p in (('base_url', 'docker.url'),
                 ('version', 'docker.version')):
        param = get(p, NOTSET)
        if param is not NOTSET:
            kwargs[k] = param
    if timeout is not None:
        # make sure we override default timeout of docker-py
        # only if defined by user.
        kwargs['timeout'] = timeout

    if 'base_url' not in kwargs and 'DOCKER_HOST' in os.environ:
        #Check if the DOCKER_HOST environment variable has been set
        kwargs['base_url'] = os.environ.get('DOCKER_HOST')

    client = docker.Client(**kwargs)
    if not version:
        # set version that match docker deamon
        client._version = client.version()['ApiVersion']

    # try to authenticate the client using credentials
    # found in pillars
    registry_auth_config = __pillar__.get('docker-registries', {})
    for k, data in __pillar__.items():
        if k.endswith('-docker-registries'):
            registry_auth_config.update(data)

    for registry, creds in registry_auth_config.items():
        client.login(creds['username'], password=creds['password'],
                     email=creds.get('email'), registry=registry)

    return client


def _get_image_infos(image):
    '''
    Verify that the image exists
    We will try to resolve either by:
        - name
        - image_id
        - tag

    image
        Image Name / Image Id / Image Tag

    Returns the image id
    '''
    status = base_status.copy()
    client = _get_client()
    try:
        infos = client.inspect_image(image)
        if infos:
            _valid(status,
                   id_=infos['Id'],
                   out=infos,
                   comment='found')
    except Exception:
        pass
    if not status['id']:
        _invalid(status)
        raise CommandExecutionError(
            'ImageID {0!r} could not be resolved to '
            'an existing Image'.format(image)
        )
    return status['out']


def _get_container_infos(container):
    '''
    Get container infos
    We will try to resolve either by:
        - the mapping grain->docker id or directly
        - dockerid

    container
        Image Id / grain name
    '''
    status = base_status.copy()
    client = _get_client()
    try:
        container_info = client.inspect_container(container)
        if container_info:
            _valid(status,
                   id_=container_info['Id'],
                   out=container_info)
    except Exception:
        pass
    if not status['id']:
        raise CommandExecutionError(
            'Container_id {0} could not be resolved to '
            'an existing container'.format(
                container)
        )
    if 'id' not in status['out'] and 'Id' in status['out']:
        status['out']['id'] = status['out']['Id']
    return status['out']


def get_containers(all=True,
                   trunc=False,
                   since=None,
                   before=None,
                   limit=-1,
                   host=False,
                   inspect=False):
    '''
    Get a list of mappings representing all containers

    all
        return all containers, Default is ``True``

    trunc
        set it to True to have the short ID, Default is ``False``

    host
        include the Docker host's ipv4 and ipv6 address in return, Default is ``False``

    inspect
        Get more granular information about each container by running a docker inspect

    CLI Example:

    .. code-block:: bash

        salt '*' docker.get_containers
        salt '*' docker.get_containers host=True
        salt '*' docker.get_containers host=True inspect=True
    '''

    client = _get_client()
    status = base_status.copy()

    if host:
        status['host'] = {}
        status['host']['interfaces'] = __salt__['network.interfaces']()

    containers = client.containers(all=all,
                                   trunc=trunc,
                                   since=since,
                                   before=before,
                                   limit=limit)

    # Optionally for each container get more granular information from them
    # by inspecting the container
    if inspect:
        for container in containers:
            container_id = container.get('Id')
            if container_id:
                inspect = _get_container_infos(container_id)
                container['detail'] = inspect.copy()

    _valid(status, comment='All containers in out', out=containers)

    return status


def logs(container):
    '''
    Return logs for a specified container

    container
        container id

    CLI Example:

    .. code-block:: bash

        salt '*' docker.logs <container id>
    '''
    status = base_status.copy()
    client = _get_client()
    try:
        container_logs = client.logs(_get_container_infos(container)['Id'])
        _valid(status, id_=container, out=container_logs)
    except Exception:
        _invalid(status, id_=container, out=traceback.format_exc())
    return status


def commit(container,
           repository=None,
           tag=None,
           message=None,
           author=None,
           conf=None):
    '''
    Commit a container (promotes it to an image)

    container
        container id
    repository
        repository/image to commit to
    tag
        tag of the image (Optional)
    message
        commit message (Optional)
    author
        author name (Optional)
    conf
        conf (Optional)

    CLI Example:

    .. code-block:: bash

        salt '*' docker.commit <container id>
    '''
    status = base_status.copy()
    client = _get_client()
    try:
        container = _get_container_infos(container)['Id']
        commit_info = client.commit(
            container,
            repository=repository,
            tag=tag,
            message=message,
            author=author,
            conf=conf)
        found = False
        for k in ('Id', 'id', 'ID'):
            if k in commit_info:
                found = True
                image_id = commit_info[k]
        if not found:
            raise Exception('Invalid commit return')
        image = _get_image_infos(image_id)['Id']
        comment = 'Image {0} created from {1}'.format(image, container)
        _valid(status, id_=image, out=commit_info, comment=comment)
    except Exception:
        _invalid(status, id_=container, out=traceback.format_exc())
    return status


def diff(container):
    '''
    Get container diffs

    container
        container id

    CLI Example:

    .. code-block:: bash

        salt '*' docker.diff <container id>
    '''
    status = base_status.copy()
    client = _get_client()
    try:
        container_diff = client.diff(_get_container_infos(container)['Id'])
        _valid(status, id_=container, out=container_diff)
    except Exception:
        _invalid(status, id_=container, out=traceback.format_exc())
    return status


def export(container, path):
    '''
    Export a container to a file

    container
        container id
    path
        path to which file is to be exported

    CLI Example:

    .. code-block:: bash

        salt '*' docker.export <container id>
    '''
    try:
        ppath = os.path.abspath(path)
        with salt.utils.fopen(ppath, 'w') as fic:
            status = base_status.copy()
            client = _get_client()
            response = client.export(_get_container_infos(container)['Id'])
            byte = response.read(4096)
            fic.write(byte)
            while byte != '':
                # Do stuff with byte.
                byte = response.read(4096)
                fic.write(byte)
            fic.flush()
        _valid(status,
               id_=container, out=ppath,
               comment='Exported to {0}'.format(ppath))
    except Exception:
        _invalid(status, id_=container, out=traceback.format_exc())
    return status


def create_container(image,
                     command=None,
                     hostname=None,
                     user=None,
                     detach=True,
                     stdin_open=False,
                     tty=False,
                     mem_limit=0,
                     ports=None,
                     environment=None,
                     dns=None,
                     volumes=None,
                     volumes_from=None,
                     name=None):
    '''
    Create a new container

    image
        image to create the container from
    command
        command to execute while starting
    hostname
        hostname of the container
    user
        user to run docker as
    detach
        daemon mode, Default is ``True``
    environment
        environment variable mapping ``({'foo':'BAR'})``
    ports
        port redirections ``({'222': {}})``
    volumes
        list of volume mappings::

            (['/mountpoint/in/container:/guest/foo', '/same/path/mounted/point'])

    tty
        attach ttys, Default is ``False``
    stdin_open
        let stdin open, Default is ``False``
    name
        name given to container

    CLI Example:

    .. code-block:: bash

        salt '*' docker.create_container o/ubuntu volumes="['/s','/m:/f']"
    '''
    status = base_status.copy()
    client = _get_client()
    try:
        mountpoints = {}
        binds = {}
        # create empty mountpoints for them to be
        # editable
        # either we have a list of guest or host:guest
        if isinstance(volumes, list):
            for mountpoint in volumes:
                mounted = mountpoint
                if ':' in mountpoint:
                    parts = mountpoint.split(':')
                    mountpoint = parts[1]
                    mounted = parts[0]
                mountpoints[mountpoint] = {}
                binds[mounted] = mountpoint
        container_info = client.create_container(
            image=image,
            command=command,
            hostname=hostname,
            user=user,
            detach=detach,
            stdin_open=stdin_open,
            tty=tty,
            mem_limit=mem_limit,
            ports=ports,
            environment=environment,
            dns=dns,
            volumes=mountpoints,
            volumes_from=volumes_from,
            name=name,
        )
        container = container_info['Id']
        callback = _valid
        comment = 'Container created'
        out = {
            'info': _get_container_infos(container),
            'out': container_info
        }
        __salt__['mine.send']('docker.get_containers', host=True)
        return callback(status, id_=container, comment=comment, out=out)
    except Exception:
        _invalid(status, id_=image, out=traceback.format_exc())
    __salt__['mine.send']('docker.get_containers', host=True)
    return status


def version():
    '''
    Get docker version

    CLI Example:

    .. code-block:: bash

        salt '*' docker.version
    '''
    status = base_status.copy()
    client = _get_client()
    try:
        docker_version = client.version()
        _valid(status, out=docker_version)
    except Exception:
        _invalid(status, out=traceback.format_exc())
    return status


def info():
    '''
    Get the version information about docker. This is similar to ``docker info`` command

    CLI Example:

    .. code-block:: bash

        salt '*' docker.info
    '''
    status = base_status.copy()
    client = _get_client()
    try:
        version_info = client.info()
        _valid(status, out=version_info)
    except Exception:
        _invalid(status, out=traceback.format_exc())
    return status


def port(container, private_port):
    '''
    Private port mapping allocation information. This method is broken on docker-py
    side. Just use the result of inspect to mangle port
    allocation

    container
        container id

    private_port
        private port on the container to query for

    CLI Example:

    .. code-block:: bash

        salt '*' docker.port <container id> <private port>
    '''
    status = base_status.copy()
    client = _get_client()
    try:
        port_info = client.port(
            _get_container_infos(container)['Id'],
            private_port)
        _valid(status, id_=container, out=port_info)
    except Exception:
        _invalid(status, id_=container, out=traceback.format_exc())
    return status


def stop(container, timeout=10):
    '''
    Stop a running container

    container
        container id

    timeout
        timeout for container to exit gracefully before killing it, Default is ``10`` seconds

    CLI Example:

    .. code-block:: bash

        salt '*' docker.stop <container id> [timeout=20]
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        dcontainer = _get_container_infos(container)['Id']
        if is_running(dcontainer):
            client.stop(dcontainer, timeout=timeout)
            if not is_running(dcontainer):
                _valid(
                    status,
                    comment='Container {0} was stopped'.format(
                        container),
                    id_=container)
            else:
                _invalid(status)
        else:
            _valid(status,
                   comment='Container {0} was already stopped'.format(
                       container),
                   id_=container)
    except Exception:
        _invalid(status, id_=container, out=traceback.format_exc(),
                 comment=(
                     'An exception occurred while stopping '
                     'your container {0}').format(container))
    __salt__['mine.send']('docker.get_containers', host=True)
    return status


def kill(container):
    '''
    Kill a running container

    container
        container id

    CLI Example:

    .. code-block:: bash

        salt '*' docker.kill <container id>
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        dcontainer = _get_container_infos(container)['Id']
        if is_running(dcontainer):
            client.kill(dcontainer)
            if not is_running(dcontainer):
                _valid(status,
                       comment='Container {0} was killed'.format(
                           container),
                       id_=container)
            else:
                _invalid(status,
                         comment='Container {0} was not killed'.format(
                             container))
        else:
            _valid(status,
                   comment='Container {0} was already stopped'.format(
                       container),
                   id_=container)
    except Exception:
        _invalid(status,
                 id_=container,
                 out=traceback.format_exc(),
                 comment=(
                     'An exception occurred while killing '
                     'your container {0}').format(container))
    __salt__['mine.send']('docker.get_containers', host=True)
    return status


def restart(container, timeout=10):
    '''
    Restart a running container

    container
        container id

    timeout
        timeout for container to exit gracefully before killing it, Default is ``10`` seconds

    CLI Example:

    .. code-block:: bash

        salt '*' docker.restart <container id> [timeout=20]
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        dcontainer = _get_container_infos(container)['Id']
        client.restart(dcontainer, timeout=timeout)
        if is_running(dcontainer):
            _valid(status,
                   comment='Container {0} was restarted'.format(container),
                   id_=container)
        else:
            _invalid(status)
    except Exception:
        _invalid(status, id_=container, out=traceback.format_exc(),
                 comment=(
                     'An exception occurred while restarting '
                     'your container {0}').format(container))
    __salt__['mine.send']('docker.get_containers', host=True)
    return status


def start(container,
          binds=None,
          port_bindings=None,
          lxc_conf=None,
          publish_all_ports=None,
          links=None,
          privileged=False,
          dns=None,
          volumes_from=None,
          network_mode=None,
          restart_policy=None,
          cap_add=None,
          cap_drop=None):
    '''
    Start the specified container

    container
        container id

    CLI Example:

    .. code-block:: bash

        salt '*' docker.start <container id>
    '''
    if not binds:
        binds = {}

    if not isinstance(binds, dict):
        raise SaltInvocationError('binds must be formatted as a dictionary')

    client = _get_client()
    status = base_status.copy()
    try:
        dcontainer = _get_container_infos(container)['Id']
        if not is_running(container):
            bindings = None
            if port_bindings is not None:
                try:
                    bindings = {}
                    for k, v in port_bindings.iteritems():
                        bindings[k] = (v.get('HostIp', ''), v['HostPort'])
                except AttributeError:
                    raise SaltInvocationError(
                        'port_bindings must be formatted as a dictionary of '
                        'dictionaries'
                    )
            client.start(dcontainer,
                         binds=binds,
                         port_bindings=bindings,
                         lxc_conf=lxc_conf,
                         publish_all_ports=publish_all_ports,
                         links=links,
                         privileged=privileged,
                         dns=dns,
                         volumes_from=volumes_from,
                         network_mode=network_mode,
                         restart_policy=restart_policy,
                         cap_add=cap_add,
                         cap_drop=cap_drop)

            if is_running(dcontainer):
                _valid(status,
                       comment='Container {0} was started'.format(container),
                       id_=container)
            else:
                _invalid(status)
        else:
            _valid(status,
                   comment='Container {0} was already started'.format(container),
                   id_=container)
    except Exception:
        _invalid(status,
                 id_=container,
                 out=traceback.format_exc(),
                 comment=(
                     'An exception occurred while starting '
                     'your container {0}').format(container))
    __salt__['mine.send']('docker.get_containers', host=True)
    return status


def wait(container):
    '''
    Wait for a container to exit gracefully

    container
        container id

    CLI Example:

    .. code-block:: bash

        salt '*' docker.wait <container id>
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        dcontainer = _get_container_infos(container)['Id']
        if is_running(dcontainer):
            client.wait(dcontainer)
            if not is_running(container):
                _valid(status,
                       id_=container,
                       comment='Container waited for stop')
            else:
                _invalid(status)
        else:
            _valid(status,
                   comment='Container {0} was already stopped'.format(container),
                   id_=container)
    except Exception:
        _invalid(status, id_=container, out=traceback.format_exc(),
                 comment=(
                     'An exception occurred while waiting '
                     'your container {0}').format(container))
    __salt__['mine.send']('docker.get_containers', host=True)
    return status


def exists(container):
    '''
    Check if a given container exists

    container
        container id

    Returns ``True`` if container exists otherwise returns ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' docker.exists <container id>

    '''
    try:
        _get_container_infos(container)
        return True
    except Exception:
        return False


def is_running(container):
    '''
    Check if the specified container is running

    container
        container id

    Returns ``True`` if container is running otherwise returns ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' docker.is_running <container id>
    '''
    try:
        infos = _get_container_infos(container)
        return infos.get('State', {}).get('Running')
    except Exception:
        return False


def remove_container(container, force=False, v=False):
    '''
    Remove a container from a docker installation

    container
        container id

    force
        remove a running container, Default is ``False``

    v
        verbose mode, Default is ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' docker.remove_container <container id> [force=True|False] [v=True|False]
    '''
    client = _get_client()
    status = base_status.copy()
    status['id'] = container
    dcontainer = None
    try:
        dcontainer = _get_container_infos(container)['Id']
        if is_running(dcontainer):
            if not force:
                _invalid(status, id_=container, out=None,
                         comment=(
                             'Container {0} is running, '
                             'won\'t remove it').format(container))
                __salt__['mine.send']('docker.get_containers', host=True)
                return status
            else:
                kill(dcontainer)
        client.remove_container(dcontainer, v=v)
        try:
            _get_container_infos(dcontainer)
            _invalid(status,
                     comment='Container was not removed: {0}'.format(container))
        except Exception:
            status['status'] = True
            status['comment'] = 'Container {0} was removed'.format(container)
    except Exception:
        _invalid(status, id_=container, out=traceback.format_exc())
    __salt__['mine.send']('docker.get_containers', host=True)
    return status


def top(container):
    '''
    Run the docker top command on a specific container

    container
        container id

    CLI Example:

    .. code-block:: bash

        salt '*' docker.top <container id>
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        dcontainer = _get_container_infos(container)['Id']
        if is_running(dcontainer):
            ret = client.top(dcontainer)
            if ret:
                ret['mprocesses'] = []
                titles = ret['Titles']
                for i in ret['Processes']:
                    data = salt.utils.odict.OrderedDict()
                    for k, j in enumerate(titles):
                        data[j] = i[k]
                    ret['mprocesses'].append(data)
                _valid(status,
                       out=ret,
                       id_=container,
                       comment='Current top for container')
            if not status['id']:
                _invalid(status)
        else:
            _invalid(status,
                     comment='Container {0} is not running'.format(container))
    except Exception:
        _invalid(status, id_=container, out=traceback.format_exc())
    return status


def inspect_container(container):
    '''
    Get container information. This is similar to ``docker inspect`` command but only for containers

    container
        container id

    CLI Example:

    .. code-block:: bash

        salt '*' docker.inspect_container <container id>

    '''
    status = base_status.copy()
    status['id'] = container
    try:
        infos = _get_container_infos(container)
        _valid(status, id_=container, out=infos)
    except Exception:
        _invalid(status, id_=container, out=traceback.format_exc(),
                 comment='Container does not exit: {0}'.format(container))
    return status


def login(url=None, username=None, password=None, email=None):
    '''
    Wrapper to the ``docker.py`` login method (does not do much yet)

    url
        registry url to authenticate to

    username
        username to authenticate

    password
        password to authenticate

    email
        email to authenticate

    CLI Example:

    .. code-block:: bash

        salt '*' docker.login <url> <username> <password> <email>
    '''
    client = _get_client()
    return client.login(username, password, email, url)


def search(term):
    '''
    Search for an image on the registry

    term
        search keyword

    CLI Example:

    .. code-block:: bash

        salt '*' docker.search <term>
    '''
    client = _get_client()
    status = base_status.copy()
    ret = client.search(term)
    if ret:
        _valid(status, out=ret, id_=term)
    else:
        _invalid(status)
    return status


def _create_image_assemble_error_status(status, ret, image_logs):
    '''
    Given input in this form::

      [{u'error': u'Get file:///r.tar.gz: unsupported protocol scheme "file"',
       u'errorDetail': {
       u'message':u'Get file:///r.tar.gz:unsupported protocol scheme "file"'}},
       {u'status': u'Downloading from file:///r.tar.gz'}]
    '''
    comment = 'An error occurred while importing your image'
    out = None
    is_invalid = True
    status['out'] = ''
    try:
        is_invalid = False
        status['out'] += '\n' + ret
        for err_log in image_logs:
            if isinstance(err_log, dict):
                if 'errorDetail' in err_log:
                    if 'code' in err_log['errorDetail']:
                        msg = '\n{0}\n{1}: {2}'.format(
                            err_log['error'],
                            err_log['errorDetail']['code'],
                            err_log['errorDetail']['message']
                        )
                    else:
                        msg = '\n{0}\n{1}'.format(
                            err_log['error'],
                            err_log['errorDetail']['message'],
                        )
                    comment += msg
    except Exception:
        is_invalid = True
        trace = traceback.format_exc()
        out = (
            'An error occurred while '
            'parsing error output:\n{0}'
        ).format(trace)
    if is_invalid:
        _invalid(status, out=out, comment=comment)
    return status


def import_image(src, repo, tag=None):
    '''
    Import content from a local tarball or a URL to a docker image

    src
        content to import (URL or absolute path to a tarball)

    repo
        repository to import to

    tag
        set tag of the image (Optional)

    CLI Example:

    .. code-block:: bash

        salt '*' docker.import_image <src> <repo> [tag]
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        ret = client.import_image(src, repository=repo, tag=tag)
        if ret:
            image_logs, _info = _parse_image_multilogs_string(ret)
            _create_image_assemble_error_status(status, ret, image_logs)
            if status['status'] is not False:
                infos = _get_image_infos(image_logs[0]['status'])
                _valid(status,
                       comment='Image {0} was created'.format(infos['Id']),
                       id_=infos['Id'],
                       out=ret)
        else:
            _invalid(status)
    except Exception:
        _invalid(status, out=traceback.format_exc())
    return status


def tag(image, repository, tag=None, force=False):
    '''
    Tag an image into a repository

    image
        name of image

    repository
        name of repository

    tag
        tag to apply (Optional)

    force
        force apply tag, Default is ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' docker.tag <image> <repository> [tag] [force=True|False]
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        dimage = _get_image_infos(image)['Id']
        ret = client.tag(dimage, repository, tag=tag, force=force)
    except Exception:
        _invalid(status,
                 out=traceback.format_exc(),
                 comment='Cant tag image {0} {1}{2}'.format(
                     image, repository,
                     tag and (':' + tag) or '').strip())
        return status
    if ret:
        _valid(status,
               id_=image,
               comment='Image was tagged: {0}{1}'.format(
                   repository,
                   tag and (':' + tag) or '').strip())
    else:
        _invalid(status)
    return status


def get_images(name=None, quiet=False, all=True):
    '''
    List docker images

    name
        repository name

    quiet
        only show image id, Default is ``False``

    all
        show all images, Default is ``True``

    CLI Example:

    .. code-block:: bash

        salt '*' docker.get_images <name> [quiet=True|False] [all=True|False]
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        infos = client.images(name=name, quiet=quiet, all=all)
        for i in range(len(infos)):
            inf = infos[i]
            try:
                inf['Human_Size'] = _sizeof_fmt(int(inf['Size']))
            except ValueError:
                pass
            try:
                ts = int(inf['Created'])
                dts = datetime.datetime.fromtimestamp(ts)
                inf['Human_IsoCreated'] = dts.isoformat()
                inf['Human_Created'] = dts.strftime(
                    '%Y-%m-%d %H:%M:%S')
            except Exception:
                pass
            try:
                inf['Human_VirtualSize'] = (
                    _sizeof_fmt(int(inf['VirtualSize'])))
            except ValueError:
                pass
        _valid(status, out=infos)
    except Exception:
        _invalid(status, out=traceback.format_exc())
    return status


def build(path=None,
          tag=None,
          quiet=False,
          fileobj=None,
          nocache=False,
          rm=True,
          timeout=None):
    '''
    Build a docker image from a dockerfile or an URL

    path
        url/branch/docker_dir or path on the filesystem to the dockerfile

    tag
        tag of the image

    quiet
        quiet mode, Default is ``False``

    nocache
        do not use docker image cache, Default is ``False``

    rm
        remove intermediate commits, Default is ``True``

    timeout
        timeout value before aborting (in seconds)

    CLI Example:

    .. code-block:: bash

        salt '*' docker.build vieux/apache
        salt '*' docker.build github.com/creack/docker-firefox
    '''
    client = _get_client(timeout=timeout)
    status = base_status.copy()
    if path or fileobj:
        try:
            ret = client.build(path=path,
                               tag=tag,
                               quiet=quiet,
                               fileobj=fileobj,
                               rm=rm,
                               nocache=nocache)

            if isinstance(ret, types.GeneratorType):

                message = json.loads(list(ret)[-1])
                if 'stream' in message:
                    if 'Successfully built' in message['stream']:
                        _valid(status, out=message['stream'])
                if 'errorDetail' in message:
                    _invalid(status, out=message['errorDetail']['message'])

            elif isinstance(ret, tuple):
                id_, out = ret[0], ret[1]
                if id_:
                    _valid(status, id_=id_, out=out, comment='Image built')
                else:
                    _invalid(status, id_=id_, out=out)

        except Exception:
            _invalid(status,
                    out=traceback.format_exc(),
                    comment='Unexpected error while building an image')
            return status

    return status


def remove_image(image):
    '''
    Remove an image from a system.

    image
        name of image

    CLI Example:

    .. code-block:: bash

        salt '*' docker.remove_image <image>
    '''
    client = _get_client()
    status = base_status.copy()
    # will raise an error if no deletion
    try:
        infos = _get_image_infos(image)
        if infos:
            status['id'] = infos['Id']
            try:
                client.remove_image(infos['Id'])
            except Exception:
                _invalid(status,
                         id_=image,
                         out=traceback.format_exc(),
                         comment='Image could not be deleted')
            try:
                infos = _get_image_infos(image)
                _invalid(status,
                         comment=(
                             'Image marked to be deleted but not deleted yet'))
            except Exception:
                _valid(status, id_=image, comment='Image deleted')
        else:
            _invalid(status)
    except Exception:
        _invalid(status,
                 out=traceback.format_exc(),
                 comment='Image does not exist: {0}'.format(image))
    return status


def inspect_image(image):
    '''
    Inspect the status of an image and return relative data. This is similar to
    ``docker inspect`` command but only for images

    image
        name of the image

    CLI Example:

    .. code-block:: bash

        salt '*' docker.inspect_image <image>
    '''
    status = base_status.copy()
    try:
        infos = _get_image_infos(image)
        try:
            for k in ['Size']:
                infos[
                    'Human_{0}'.format(k)
                ] = _sizeof_fmt(int(infos[k]))
        except Exception:
            pass
        _valid(status, id_=image, out=infos)
    except Exception:
        _invalid(status, id_=image, out=traceback.format_exc(),
                 comment='Image does not exist')
    return status


def _parse_image_multilogs_string(ret):
    '''
    Parse image log strings into grokable data
    '''
    image_logs, infos = [], None
    if ret and ret.strip().startswith('{') and ret.strip().endswith('}'):
        pushd = 0
        buf = ''
        for char in ret:
            buf += char
            if char == '{':
                pushd += 1
            if char == '}':
                pushd -= 1
            if pushd == 0:
                try:
                    buf = json.loads(buf)
                except Exception:
                    pass
                image_logs.append(buf)
                buf = ''
        image_logs.reverse()

        # Valid statest when pulling an image from the docker registry
        valid_states = [
            'Download complete',
            'Already exists',
        ]

        # search last layer grabbed
        for l in image_logs:
            if isinstance(l, dict):
                if l.get('status') in valid_states and l.get('id'):
                    infos = _get_image_infos(l['id'])
                    break

    return image_logs, infos


def _pull_assemble_error_status(status, ret, logs):
    '''
    Given input in this form::

        u'{"status":"Pulling repository foo/ubuntubox"}:
        "image (latest) from foo/  ...
         rogress":"complete","id":"2c80228370c9"}'

    construct something like that (load JSON data is possible)::

        [u'{"status":"Pulling repository foo/ubuntubox"',
         {"status":"Download","progress":"complete","id":"2c80228370c9"}]
    '''
    comment = 'An error occurred pulling your image'
    out = ''
    try:
        out = '\n' + ret
        for err_log in logs:
            if isinstance(err_log, dict):
                if 'errorDetail' in err_log:
                    if 'code' in err_log['errorDetail']:
                        msg = '\n{0}\n{1}: {2}'.format(
                            err_log['error'],
                            err_log['errorDetail']['code'],
                            err_log['errorDetail']['message']
                        )
                    else:
                        msg = '\n{0}\n{1}'.format(
                            err_log['error'],
                            err_log['errorDetail']['message'],
                        )
                    comment += msg
    except Exception:
        out = traceback.format_exc()
    _invalid(status, out=out, comment=comment)
    return status


def pull(repo, tag=None):
    '''
    Pulls an image from any registry. See documentation at top of this page to
    configure authenticated access

    repo
        name of repository

    tag
        specific tag to pull (Optional)

    CLI Example:

    .. code-block:: bash

        salt '*' docker.pull <repository> [tag]
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        ret = client.pull(repo, tag=tag)
        if ret:
            image_logs, infos = _parse_image_multilogs_string(ret)
            if infos and infos.get('Id', None):
                repotag = repo
                if tag:
                    repotag = '{0}:{1}'.format(repo, tag)
                _valid(status,
                       out=image_logs if image_logs else ret,
                       id_=infos['Id'],
                       comment='Image {0} was pulled ({1})'.format(
                           repotag, infos['Id']))

            else:
                _pull_assemble_error_status(status, ret, image_logs)
        else:
            _invalid(status)
    except Exception:
        _invalid(status, id_=repo, out=traceback.format_exc())
    return status


def _push_assemble_error_status(status, ret, logs):
    '''
    Given input in this form::

        u'{"status":"Pulling repository foo/ubuntubox"}:
        "image (latest) from foo/  ...
         rogress":"complete","id":"2c80228370c9"}'

    construct something like that (load json data is possible)::

        [u'{"status":"Pulling repository foo/ubuntubox"',
         {"status":"Download","progress":"complete","id":"2c80228370c9"}]
    '''
    comment = 'An error occurred pushing your image'
    status['out'] = ''
    try:
        status['out'] += '\n' + ret
        for err_log in logs:
            if isinstance(err_log, dict):
                if 'errorDetail' in err_log:
                    if 'code' in err_log['errorDetail']:
                        msg = '\n{0}\n{1}: {2}'.format(
                            err_log['error'],
                            err_log['errorDetail']['code'],
                            err_log['errorDetail']['message']
                        )
                    else:
                        msg = '\n{0}\n{1}'.format(
                            err_log['error'],
                            err_log['errorDetail']['message'],
                        )
                    comment += msg
    except Exception:
        trace = traceback.format_exc()
        status['out'] = (
            'An error occurred while '
            'parsing error output:\n{0}'
        ).format(trace)
    _invalid(status, comment=comment)
    return status


def push(repo, tag=None, quiet=False):
    '''
    Pushes an image to any registry. See documentation at top of this page to
    configure authenticated access

    repo
        name of repository

    tag
        specific tag to push (Optional)

    quiet
        set as ``True`` to quiet output, Default is ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' docker.push <repository> [tag] [quiet=True|False]
    '''
    client = _get_client()
    status = base_status.copy()
    registry, repo_name = docker.auth.resolve_repository_name(repo)
    try:
        ret = client.push(repo, tag=tag)
        if ret:
            image_logs, infos = _parse_image_multilogs_string(ret)
            if image_logs:
                repotag = repo_name
                if tag:
                    repotag = '{0}:{1}'.format(repo, tag)
                if not quiet:
                    status['out'] = image_logs
                else:
                    status['out'] = None
                laststatus = image_logs[2].get('status', None)
                if laststatus and (
                    ('already pushed' in laststatus)
                    or ('Pushing tags for rev' in laststatus)
                    or ('Pushing tag for rev' in laststatus)
                ):
                    status['status'] = True
                    status['id'] = _get_image_infos(repo)['Id']
                    status['comment'] = 'Image {0}({1}) was pushed'.format(
                        repotag, status['id'])
                else:
                    _push_assemble_error_status(status, ret, image_logs)
            else:
                status['out'] = ret
                _push_assemble_error_status(status, ret, image_logs)
        else:
            _invalid(status)
    except Exception:
        _invalid(status, id_=repo, out=traceback.format_exc())
    return status


def _run_wrapper(status, container, func, cmd, *args, **kwargs):
    '''
    Wrapper to a cmdmod function

    Idea is to prefix the call to cmdrun with the relevant driver to
    execute inside a container context

    .. note::

        Only lxc and native drivers are implemented.

    status
        status object
    container
        container id to execute in
    func
        cmd function to execute
    cmd
        command to execute in the container
    '''

    client = _get_client()
    # For old version of docker. lxc was the only supported driver.
    # We can safely hardcode it
    driver = client.info().get('ExecutionDriver', 'lxc-')
    container_info = _get_container_infos(container)
    container_id = container_info['Id']
    if driver.startswith('lxc-'):
        full_cmd = 'lxc-attach -n {0} -- {1}'.format(container_id, cmd)
    elif driver.startswith('native-') and HAS_NSENTER:
        # http://jpetazzo.github.io/2014/03/23/lxc-attach-nsinit-nsenter-docker-0-9/
        container_pid = container_info['State']['Pid']
        if container_pid == 0:
            _invalid(status, id_=container, comment='Container is not running')
            return status
        full_cmd = ('nsenter --target {pid} --mount --uts --ipc --net --pid'
                    ' {cmd}'.format(pid=container_pid, cmd=cmd))
    else:
        raise NotImplementedError(
            'Unknown docker ExecutionDriver {0!r}. Or didn\'t find command'
            ' to attach to the container'.format(driver))

    # now execute the command
    comment = 'Executed {0}'.format(full_cmd)
    try:
        f = __salt__[func]
        ret = f(full_cmd, *args, **kwargs)
        if ((isinstance(ret, dict) and
                ('retcode' in ret) and
                (ret['retcode'] != 0))
                or (func == 'cmd.retcode' and ret != 0)):
            return _invalid(status, id_=container, out=ret,
                            comment=comment)
        _valid(status, id_=container, out=ret, comment=comment,)
    except Exception:
        _invalid(status, id_=container,
                 comment=comment, out=traceback.format_exc())
    return status


def run(container, cmd):
    '''
    Wrapper for :py:func:`cmdmod.run<salt.modules.cmdmod.run>` inside a container context

    container
        container id (or grain)

    cmd
        command to execute

    .. note::
        The return is a bit different as we use the docker struct.
        Output of the command is in 'out' and result is always ``True``.

    .. warning::
        Be advised that this function allows for raw shell access to the named
        container! If allowing users to execute this directly it may allow more
        rights than intended!

    CLI Example:

    .. code-block:: bash

        salt '*' docker.run <container id> 'ls -l /etc'
    '''
    status = base_status.copy()
    return _run_wrapper(
        status, container, 'cmd.run', cmd)


def run_all(container, cmd):
    '''
    Wrapper for :py:func:`cmdmod.run_all<salt.modules.cmdmod.run_all>` inside a container context

    container
        container id (or grain)

    cmd
        command to execute

    .. note::
        The return is a bit different as we use the docker struct.
        Output of the command is in 'out' and result is ``False`` if
        command failed to execute.

    .. warning::
        Be advised that this function allows for raw shell access to the named
        container! If allowing users to execute this directly it may allow more
        rights than intended!

    CLI Example:

    .. code-block:: bash

        salt '*' docker.run_all <container id> 'ls -l /etc'
    '''
    status = base_status.copy()
    return _run_wrapper(
        status, container, 'cmd.run_all', cmd)


def run_stderr(container, cmd):
    '''
    Wrapper for :py:func:`cmdmod.run_stderr<salt.modules.cmdmod.run_stderr>` inside a container context

    container
        container id (or grain)

    cmd
        command to execute

    .. note::
        The return is a bit different as we use the docker struct.
        Output of the command is in 'out' and result is always ``True``.

    .. warning::
        Be advised that this function allows for raw shell access to the named
        container! If allowing users to execute this directly it may allow more
        rights than intended!

    CLI Example:

    .. code-block:: bash

        salt '*' docker.run_stderr <container id> 'ls -l /etc'
    '''
    status = base_status.copy()
    return _run_wrapper(
        status, container, 'cmd.run_stderr', cmd)


def run_stdout(container, cmd):
    '''
    Wrapper for :py:func:`cmdmod.run_stdout<salt.modules.cmdmod.run_stdout>` inside a container context

    container
        container id (or grain)

    cmd
        command to execute

    .. note::
        The return is a bit different as we use the docker struct.
        Output of the command is in 'out' and result is always ``True``.

    .. warning::
        Be advised that this function allows for raw shell access to the named
        container! If allowing users to execute this directly it may allow more
        rights than intended!

    CLI Example:

    .. code-block:: bash

        salt '*' docker.run_stdout <container id> 'ls -l /etc'
    '''
    status = base_status.copy()
    return _run_wrapper(
        status, container, 'cmd.run_stdout', cmd)


def retcode(container, cmd):
    '''
    Wrapper for :py:func:`cmdmod.retcode<salt.modules.cmdmod.retcode>` inside a container context

    container
        container id (or grain)

    cmd
        command to execute

    .. note::
        The return is a bit different as we use the docker struct.
        Output of the command is in 'out' and result is ``False`` if
        command failed to execute.

    .. warning::
        Be advised that this function allows for raw shell access to the named
        container! If allowing users to execute this directly it may allow more
        rights than intended!

    CLI Example:

    .. code-block:: bash

        salt '*' docker.retcode <container id> 'ls -l /etc'
    '''
    status = base_status.copy()
    return _run_wrapper(
        status, container, 'cmd.retcode', cmd)


def get_container_root(container):
    '''
    Get the container rootfs path

    container
        container id or grain

    CLI Example:

    .. code-block:: bash

        salt '*' docker.get_container_root <container id>
    '''
    default_path = os.path.join(
        '/var/lib/docker',
        'containers',
        _get_container_infos(container)['Id'],
    )
    default_rootfs = os.path.join(default_path, 'roofs')
    rootfs_re = re.compile(r'^lxc.rootfs\s*=\s*(.*)\s*$', re.U)
    try:
        lxcconfig = os.path.join(default_path, 'config.lxc')
        with salt.utils.fopen(lxcconfig) as fhr:
            lines = fhr.readlines()
            rlines = lines[:]
            rlines.reverse()
            for rl in rlines:
                robj = rootfs_re.search(rl)
                if robj:
                    rootfs = robj.groups()[0]
                    break
    except Exception:
        rootfs = default_rootfs
    return rootfs


def _script(status,
            container,
            source,
            args=None,
            cwd=None,
            stdin=None,
            runas=None,
            shell=cmdmod.DEFAULT_SHELL,
            env=None,
            template='jinja',
            umask=None,
            timeout=None,
            reset_system_locale=True,
            run_func_=None,
            no_clean=False,
            saltenv='base',
            output_loglevel='info',
            quiet=False,
            **kwargs):
    try:
        if not run_func_:
            run_func_ = run_all
        rpath = get_container_root(container)
        tpath = os.path.join(rpath, 'tmp')

        if isinstance(env, string_types):
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        path = salt.utils.mkstemp(dir=tpath)
        if template:
            __salt__['cp.get_template'](
                source, path, template, saltenv, **kwargs)
        else:
            fn_ = __salt__['cp.cache_file'](source, saltenv)
            if not fn_:
                return {'pid': 0,
                        'retcode': 1,
                        'stdout': '',
                        'stderr': '',
                        'cache_error': True}
            shutil.copyfile(fn_, path)
        in_path = os.path.join('/', os.path.relpath(path, rpath))
        os.chmod(path, 0755)
        command = in_path + ' ' + str(args) if args else in_path
        status = run_func_(container,
                           command,
                           cwd=cwd,
                           stdin=stdin,
                           output_loglevel=output_loglevel,
                           quiet=quiet,
                           runas=runas,
                           shell=shell,
                           umask=umask,
                           timeout=timeout,
                           reset_system_locale=reset_system_locale)
        if not no_clean:
            os.remove(path)
    except Exception:
        _invalid(status, id_=container, out=traceback.format_exc())
    return status


def script(container,
           source,
           args=None,
           cwd=None,
           stdin=None,
           runas=None,
           shell=cmdmod.DEFAULT_SHELL,
           env=None,
           template='jinja',
           umask=None,
           timeout=None,
           reset_system_locale=True,
           no_clean=False,
           saltenv='base'):
    '''
    Wrapper for :py:func:`cmdmod.script<salt.modules.cmdmod.script>` inside a container context

    container
        container id (or grain)

    additional parameters
        See :py:func:`cmd.script <salt.modules.cmdmod.script>`

    .. warning::
        Be advised that this function allows for raw shell access to the named
        container! If allowing users to execute this directly it may allow more
        rights than intended!

    Download a script from a remote location and execute the script in the container.
    The script can be located on the salt master file server or on an HTTP/FTP server.

    The script will be executed directly, so it can be written in any available programming
    language.

    The script can also be formatted as a template, the default is jinja. Arguments for the
    script can be specified as well.

    CLI Example:

    .. code-block:: bash

        salt '*' docker.script <container id> salt://docker_script.py
        salt '*' docker.script <container id> salt://scripts/runme.sh 'arg1 arg2 "arg 3"'
        salt '*' docker.script <container id> salt://scripts/windows_task.ps1 args=' -Input c:\\tmp\\infile.txt' shell='powershell'

    A string of standard input can be specified for the command to be run using the stdin
    parameter. This can be useful in cases where sensitive information must be read from
    standard input:

    CLI Example:

    .. code-block:: bash

        salt '*' docker.script <container id> salt://scripts/runme.sh stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'
    '''
    status = base_status.copy()

    if isinstance(env, string_types):
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt '
            'Boron.'
        )
        # Backwards compatibility
        saltenv = env

    return _script(status,
                   container,
                   source,
                   args=args,
                   cwd=cwd,
                   stdin=stdin,
                   runas=runas,
                   shell=shell,
                   template=template,
                   umask=umask,
                   timeout=timeout,
                   reset_system_locale=reset_system_locale,
                   no_clean=no_clean,
                   saltenv=saltenv)


def script_retcode(container,
                   source,
                   cwd=None,
                   stdin=None,
                   runas=None,
                   shell=cmdmod.DEFAULT_SHELL,
                   env=None,
                   template='jinja',
                   umask=None,
                   timeout=None,
                   reset_system_locale=True,
                   no_clean=False,
                   saltenv='base'):
    '''
    Wrapper for :py:func:`cmdmod.script_retcode<salt.modules.cmdmod.script_retcode>` inside a container context

    container
        container id (or grain)

    additional parameters
        See :py:func:`cmd.script_retcode <salt.modules.cmdmod.script_retcode>`

    .. warning::
        Be advised that this function allows for raw shell access to the named
        container! If allowing users to execute this directly it may allow more
        rights than intended!

    CLI Example:

    .. code-block:: bash

        salt '*' docker.script_retcode <container id> salt://docker_script.py
    '''

    if isinstance(env, string_types):
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt '
            'Boron.'
        )
        # Backwards compatibility
        saltenv = env

    status = base_status.copy()

    return _script(status,
                   container,
                   source=source,
                   cwd=cwd,
                   stdin=stdin,
                   runas=runas,
                   shell=shell,
                   template=template,
                   umask=umask,
                   timeout=timeout,
                   reset_system_locale=reset_system_locale,
                   run_func_=retcode,
                   no_clean=no_clean,
                   saltenv=saltenv)
