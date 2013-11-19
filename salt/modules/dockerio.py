# -*- coding: utf-8 -*-
'''
Management of dockers
=====================

.. versionadded:: Hydrogen

.. note::

    The DockerIO integration is still in beta; the API is subject to change

General notes
-------------

- As we use states, we don't want to pop continuously dockers, we will map each
  container id  (or image) with a grain whenever it is relevant.
- As a corollary, we will resolve for a container id either directly this
  container id or try to find a container id matching something stocked in
  grain

Installation prerequisites
--------------------------

- You will need the 'docker-py' python package in your python installation
  running salt.
- For now, you need docker-py from sources:

    https://github.com/dotcloud/docker-py

Prerequisite pillar configuration for authentication
----------------------------------------------------

- To push or pull you will need to be authenticated as the docker-py bindings
  require it
- For this to happen, you will need to configure a mapping in the pillar
  representing your per URL authentication bits::

    docker-registries:
        registry_url:
            email: foo@foo.com
            password: s3cr3t
            username: foo

- You need at least an entry to the default docker index::

    docker-registries:
        https://index.docker.io/v1:
            email: foo@foo.com
            password: s3cr3t
            username: foo

you can define multiple registries blocks for them to be aggregated, their id
just must finish with -docker-registries::

   ac-docker-registries:
        https://index.bar.io/v1:
            email: foo@foo.com
            password: s3cr3t
            username: foo

   ab-docker-registries:
        https://index.foo.io/v1:
            email: foo@foo.com
            password: s3cr3t
            username: foo

Would be the equivalent to::

   docker-registries:
        https://index.bar.io/v1:
            email: foo@foo.com
            password: s3cr3t
            username: foo
        https://index.foo.io/v1:
            email: foo@foo.com
            password: s3cr3t
            username: foo

Registry dialog methods
-----------------------

- login
- push
- pull

Docker management
-----------------

- version
- info

Image management
----------------

You have those methods:

- search
- inspect_image
- get_images
- remove_image
- import_image
- build
- tag

Container management
--------------------

You have those methods:

- start
- stop
- kill
- wait
- get_containers
- inspect_container
- remove_container
- is_running
- top
- ports
- logs
- diff
- commit
- create_container
- export
- get_container_root

Runtime execution within a specific already existing and running container
--------------------------------------------------------------------------

- Idea is to use lxc-attach to execute inside the container context.
- We do not use a "docker run command" but want to execute something inside a
  running container.


You have those methods:

- retcode
- run
- run_all
- run_stderr
- run_stdout
- script
- script_retcode

'''
__docformat__ = 'restructuredtext en'

import datetime
import json
import os
import re
import traceback
import shutil

from salt.modules import cmdmod
from salt.exceptions import CommandExecutionError
from salt._compat import string_types
import salt.utils
from salt.utils.odict import OrderedDict

try:
    import docker
    HAS_DOCKER = True
except ImportError:
    HAS_DOCKER = False

import logging

log = logging.getLogger(__name__)

INVALID_RESPONSE = 'We did not get any expectable answer from docker'
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
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0


def _set_status(m,
                id=NOTSET,
                comment=INVALID_RESPONSE,
                status=False,
                out=None):
    '''
    Assign status data to a dict
    '''
    m['comment'] = comment
    m['status'] = status
    m['out'] = out
    if id is not NOTSET:
        m['id'] = id
    return m


def invalid(m, id=NOTSET, comment=INVALID_RESPONSE, out=None):
    '''
    Return invalid status
    '''
    return _set_status(m, status=False, id=id, comment=comment, out=out)


def valid(m, id=NOTSET, comment=VALID_RESPONSE, out=None):
    '''
    Return valid status
    '''
    return _set_status(m, status=True, id=id, comment=comment, out=out)


def _get_client(version=None):
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
    for k, p in {
        'base_url': 'docker.url',
        'version': 'docker.version',
    }.items():
        param = get(p, NOTSET)
        if param is not NOTSET:
            kwargs[k] = param
    client = docker.Client(**kwargs)
    # force 1..5 API for registry login
    if not version:
        if client._version == "1.4":
            client._version = "1.5"
    if getattr(client, '_cfg', None) is None:
        client._cfg = {
            'Configs': {},
            'rootPath': '/dev/null'
        }
    client._cfg.update(_merge_auth_bits())
    return client


def _merge_auth_bits():
    '''
    Merge the local docker authentication file
    with the pillar configuration
    '''
    cfg = os.path.expanduser('~/.dockercfg')
    try:
        fic = open(cfg)
        try:
            config = json.loads(fic.read())
        finally:
            fic.close()
    except Exception:
        config = {'rootPath': '/dev/null'}
    if not 'Configs' in config:
        config['Configs'] = {}
    config['Configs'].update(
        __pillar__.get('docker-registries', {})
    )
    for k, data in __pillar__.items():
        if k.endswith('-docker-registries'):
            config['Configs'].update(data)
    return config


def _get_image_infos(image):
    '''
    Verify that the image exists
    We will try to resolve either by:
        - the mapping grain->docker id or directly
        - dockerid

    image
        Image Id / grain name

    Returns the image id
    '''
    status = base_status.copy()
    client = _get_client()
    try:
        infos = client.inspect_image(image)
        if infos:
            valid(
                status,
                id=infos['id'],
                out=infos,
                comment='found')
    except Exception:
        pass
    if not status['id']:
        invalid(status)
        raise CommandExecutionError(
            'ImageID "%s" could not be resolved to '
            'an existing Image' % (image)
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
        info = client.inspect_container(container)
        if info:
            valid(status,
                  id=info['ID'],
                  out=info)
    except Exception:
        pass
    if not status['id']:
        raise CommandExecutionError(
            'Container_id {0} could not be resolved to '
            'an existing container'.format(
                container)
        )
    if (
        (not 'id' in status['out'])
        and ('ID' in status['out'])
    ):
        status['out']['id'] = status['out']['ID']
    return status['out']


def get_containers(all=True,
                   trunc=False,
                   since=None,
                   before=None,
                   limit=-1,
                   *args,
                   **kwargs):
    '''
    Get a list of mappings representing all containers

    all
        Return all containers

    trunc
        Set it to True to have the short ID

    Returns a mapping of something which looks like
    container

    CLI Example:

    .. code-block:: bash

        salt '*' docker.get_containers
    '''
    client = _get_client()
    status = base_status.copy()
    ret = client.containers(all=all,
                            trunc=trunc,
                            since=since,
                            before=before,
                            limit=limit)
    if ret:
        valid(status, comment='All containers in out', out=ret)
    else:
        invalid(status)
    return status


def logs(container, *args, **kwargs):
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
        info = client.logs(_get_container_infos(container)['id'])
        valid(status, id=container, out=info)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc())
    return status


def commit(container,
           repository=None,
           tag=None,
           message=None,
           author=None,
           conf=None,
           *args,
           **kwargs):
    '''
    Commit a container (promotes it to an image)

    container
        container id
    repository
        repository/imageName to commit to
    tag
        optional tag
    message
        optional commit message
    author
        optional author
    conf
        optional conf

    CLI Example:

    .. code-block:: bash

        salt '*' docker.commit <container id>
    '''
    status = base_status.copy()
    client = _get_client()
    try:
        container = _get_container_infos(container)['id']
        info = client.commit(
            container,
            repository=repository,
            tag=tag,
            message=message,
            author=author,
            conf=conf)
        found = False
        for k in 'Id', 'id', 'ID':
            if k in info:
                found = True
                id = info[k]
        if not found:
            raise Exception('Invalid commit return')
        image = _get_image_infos(id)['id']
        comment = 'Image {0} created from {1}'.format(image, container)
        valid(status, id=image, out=info, comment=comment)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc())
    return status


def diff(container, *args, **kwargs):
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
        info = client.diff(_get_container_infos(container)['id'])
        valid(status, id=container, out=info)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc())
    return status


def export(container, path, *args, **kwargs):
    '''
    Export a container to a file

    container
        container id
    path
        path to the export

    CLI Example:

    .. code-block:: bash

        salt '*' docker.export <container id>
    '''
    try:
        ppath = os.path.abspath(path)
        fic = open(ppath, 'w')
        status = base_status.copy()
        client = _get_client()
        response = client.export(_get_container_infos(container)['id'])
        try:
            byte = response.read(4096)
            fic.write(byte)
            while byte != "":
                # Do stuff with byte.
                byte = response.read(4096)
                fic.write(byte)
        finally:
            fic.flush()
            fic.close()
        valid(status,
              id=container, out=ppath,
              comment='Exported to {0}'.format(ppath))
    except Exception:
        invalid(status, id=container, out=traceback.format_exc())
    return status


def create_container(image,
                     command='/sbin/init',
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
                     *args, **kwargs):
    '''
    Get container diffs

    image
        image to create the container from
    command
        command to execute while starting
    hostname
        hostname of the container
    user
        user to run docker as
    detach
        daemon mode
    environment
        environment variable mapping ({'foo':'BAR'})
    dns
        list of DNS servers
    ports
        ports redirections (['222:22'])
    volumes
        list of volumes mapping::

            (['/mountpoint/in/container:/guest/foo',
              '/same/path/mounted/point'])

    tty
        attach ttys
    stdin_open
        let stdin open
    volumes_from
        container to get volumes definition from

    EG:

        salt-call docker.create_container o/ubuntu volumes="['/s','/m:/f']"

    CLI Example:

    .. code-block:: bash

        salt '*' docker.create_container <image>
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
        info = client.create_container(
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
        )
        container = info['Id']
        kill(container)
        ret_start = start(container, binds=binds)
        callback = valid
        comment = 'Container created'
        out = {
            'info': _get_container_infos(container),
            'started': ret_start,
            'out': info
        }
        if not ret_start['status']:
            callback = invalid
            comment = 'Container created but cannot be started\n{0}'.format(
                ret_start['out']
            )
        return callback(status, id=container, comment=comment, out=out)
    except Exception:
        invalid(status, id=image, out=traceback.format_exc())
    return status


def version(*args, **kwargs):
    '''
    Get docker version

    CLI Example:

    .. code-block:: bash

        salt '*' docker.version
    '''
    status = base_status.copy()
    client = _get_client()
    try:
        info = client.version()
        valid(status, out=info)
    except Exception:
        invalid(status, out=traceback.format_exc())
    return status


def info(*args, **kwargs):
    '''
    Get the version information about docker

    :rtype: dict
    :returns: A status message with the command output

    CLI Example:

    .. code-block:: bash

        salt '*' docker.info
    '''
    status = base_status.copy()
    client = _get_client()
    try:
        info = client.info()
        valid(status, out=info)
    except Exception:
        invalid(status, out=traceback.format_exc())
    return status


def port(container, private_port, *args, **kwargs):
    '''
    Private/Public for a specific port mapping allocation information
    This method is broken on docker-py side
    Just use the result of inspect to mangle port
    allocation

    container
        container id
    private_port
        private port on the container to query for

    CLI Example:

    .. code-block:: bash

        salt '*' docker.port <container id>
    '''
    status = base_status.copy()
    client = _get_client()
    try:
        info = client.port(
            _get_container_infos(container)['id'],
            port)
        valid(status, id=container, out=info)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc())
    return status


def stop(container, timeout=10, *args, **kwargs):
    '''
    Stop a running container

    :type container: string
    :param container: The container id to stop

    :type timeout: int
    :param timeout: Wait for a timeout to let the container exit gracefully
        before killing it

    :rtype: dict
    :returns: A status message with the command output
          ex::

            {'id': 'abcdef123456789',
           'status': True}

    CLI Example:

    .. code-block:: bash

        salt '*' docker.stop <container id>
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        dcontainer = _get_container_infos(container)['id']
        if is_running(dcontainer):
            client.stop(dcontainer, timeout=timeout)
            if not is_running(dcontainer):
                valid(
                    status,
                    comment='Container {0} was stopped'.format(
                        container),
                    id=container)
            else:
                invalid(status)
        else:
            valid(
                status,
                comment='Container {0} was already stopped'.format(
                    container),
                id=container)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc(),
                comment=(
                    'An exception occured while stopping '
                    'your container {0}').format(container))
    return status


def kill(container, *args, **kwargs):
    '''
    Kill a running container

    :type container: string
    :param container: The container id to kill

    :rtype: dict
    :returns: A status message with the command output
          ex::

            {'id': 'abcdef123456789',
           'status': True}

    CLI Example:

    .. code-block:: bash

        salt '*' docker.kill <container id>
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        dcontainer = _get_container_infos(container)['id']
        if is_running(dcontainer):
            client.kill(dcontainer)
            if not is_running(dcontainer):
                valid(
                    status,
                    comment='Container {0} was killed'.format(
                        container),
                    id=container)
            else:
                invalid(status,
                        comment='Container {0} was not killed'.format(
                            container))
        else:
            valid(
                status,
                comment='Container {0} was already stopped'.format(
                    container),
                id=container)
    except Exception:
        invalid(status,
                id=container,
                out=traceback.format_exc(),
                comment=(
                    'An exception occurred while killing '
                    'your container {0}').format(container))
    return status


def restart(container, timeout=10, *args, **kwargs):
    '''
    Restart a running container

    :type container: string
    :param container: The container id to restart

    :type timout: int
    :param timeout: Wait for a timeout to let the container exit gracefully
        before killing it

    :rtype: dict
    :returns: A status message with the command output
          ex::

            {'id': 'abcdef123456789',
           'status': True}

    CLI Example:

    .. code-block:: bash

        salt '*' docker.restart <container id>
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        dcontainer = _get_container_infos(container)['id']
        client.restart(dcontainer, timeout=timeout)
        if is_running(dcontainer):
            valid(status,
                  comment='Container {0} was restarted'.format(container),
                  id=container)
        else:
            invalid(status)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc(),
                comment=(
                    'An exception occurred while restarting '
                    'your container {0}').format(container))
    return status


def start(container, binds=None, ports=None, *args, **kwargs):
    '''
    restart the specified container

    container
        Container id
    Returns the status mapping as usual
         {'id': id of the container,
          'status': True if started }

    CLI Example:

    .. code-block:: bash

        salt '*' docker.start <container id>
    '''
    if not binds:
        binds = {}
    if not ports:
        ports = {}
    client = _get_client()
    status = base_status.copy()
    try:
        dcontainer = _get_container_infos(container)['id']
        if not is_running(container):
            client.start(dcontainer, binds=binds)
            if is_running(dcontainer):
                valid(status,
                      comment='Container {0} was started'.format(container),
                      id=container)
            else:
                invalid(status)
        else:
            valid(
                status,
                comment='Container {0} was already started'.format(container),
                id=container)
    except Exception:
        invalid(status,
                id=container,
                out=traceback.format_exc(),
                comment=(
                    'An exception occurred while starting '
                    'your container {0}').format(container))
    return status


def wait(container, *args, **kwargs):
    '''
    Blocking wait for a container exit gracefully without
    timeout killing it

    container
        Container id
    Return container id if successful
         {'id': id of the container,
          'status': True if stopped }

    CLI Example:

    .. code-block:: bash

        salt '*' docker.wait <container id>
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        dcontainer = _get_container_infos(container)['id']
        if is_running(dcontainer):
            client.wait(dcontainer)
            if not is_running(container):
                valid(status,
                      id=container,
                      comment='Container waited for stop')
            else:
                invalid(status)
        else:
            valid(
                status,
                comment='Container {0} was already stopped'.format(container),
                id=container)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc(),
                comment=(
                    'An exception occurred while waiting '
                    'your container {0}').format(container))
    return status


def exists(container, *args, **kwargs):
    '''
    Check if a given container exists

    :type container: string
    :param container: Container id

    :rtype: boolean:

    CLI Example:

    .. code-block:: bash

        salt '*' docker.exists <container>

    '''
    try:
        _get_container_infos(container)
        return True
    except Exception:
        return False


def is_running(container, *args, **kwargs):
    '''
    Is this container running

    container
        Container id

    Return boolean

    CLI Example:

    .. code-block:: bash

        salt '*' docker.is_running <container id>
    '''
    try:
        infos = _get_container_infos(container)
        return infos.get('State', {}).get('Running')
    except Exception:
        return False


def remove_container(container=None, force=False, v=False, *args, **kwargs):
    '''
    Removes a container from a docker installation

    container
        Container id to remove
    force
        By default, do not remove a running container, set this
        to remove it unconditionally
    v
        verbose mode

    Return True or False in the status mapping and also
    any information about docker in status['out']

    CLI Example:

    .. code-block:: bash

        salt '*' docker.remove_container <container id>
    '''
    client = _get_client()
    status = base_status.copy()
    status['id'] = container
    dcontainer = None
    try:
        dcontainer = _get_container_infos(container)['id']
        if is_running(dcontainer):
            if not force:
                invalid(status, id=container, out=None,
                        comment=(
                            'Container {0} is running, '
                            'won\'t remove it').format(container))
                return status
            else:
                kill(dcontainer)
        client.remove_container(dcontainer, v=v)
        try:
            _get_container_infos(dcontainer)
            invalid(status,
                    comment="Container was not removed: {0}".format(container))
        except Exception:
            status['status'] = True
            status['comment'] = 'Container {0} was removed'.format(container)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc())
    return status


def top(container, *args, **kwargs):
    '''
    Run the docker top command on a specific container

    container
        Container id

    Returns in the 'out' status mapping a mapping for
    those running processes::

       {
            'Titles': top titles list,
            'processes': list of ordered by
                         titles processes information,
            'mprocesses': list of mappings processes information
            constructed above the upon information
       }

    CLI Example:

    .. code-block:: bash

        salt '*' docker.top <container id>
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        dcontainer = _get_container_infos(container)['id']
        if is_running(dcontainer):
            ret = client.top(dcontainer)
            if ret:
                ret['mprocesses'] = []
                titles = ret['Titles']
                for i in ret['Processes']:
                    data = OrderedDict()
                    for k, j in enumerate(titles):
                        data[j] = i[k]
                    ret['mprocesses'].append(data)
                valid(status,
                      out=ret,
                      id=container,
                      comment='Current top for container')
            if not status['id']:
                invalid(status)
        else:
            invalid(status,
                    comment='Container {0} is not running'.format(container))
    except Exception:
        invalid(status, id=container, out=traceback.format_exc())
    return status


def inspect_container(container, *args, **kwargs):
    '''
    Get container information. This is similar to the docker inspect command.

    :type container: string
    :param container: The id of the container to inspect

    :rtype: dict
    :returns: A status message with the command output

    CLI Example:

    .. code-block:: bash

        salt '*' docker.inspect_container <container>

    '''
    status = base_status.copy()
    status['id'] = container
    try:
        infos = _get_container_infos(container)
        valid(status, id=container, out=infos)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc(),
                comment=(
                    'Container does not exit: {0}'
                ).format(container))
    return status


def login(url=None, username=None, password=None, email=None, *args, **kwargs):
    '''
    Wrapper to the docker.py login method, does not do much yet

    CLI Example:

    .. code-block:: bash

        salt '*' docker.login <container id>
    '''
    client = _get_client()
    return client.login(url, username=username, password=password, email=email)


def search(term, *args, **kwargs):
    '''
    Search for an image on the registry

    :type term: string
    :param term: The search keyword to query

    CLI Example:

    .. code-block:: bash

        salt '*' docker.search <term>
    '''
    client = _get_client()
    status = base_status.copy()
    ret = client.search(term)
    if ret:
        valid(status, out=ret, id=term)
    else:
        invalid(status)
    return status


def _create_image_assemble_error_status(status, ret, logs, *args, **kwargs):
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
        for log in logs:
            if isinstance(log, dict):
                if 'errorDetail' in log:
                    if 'code' in log['errorDetail']:
                        msg = '\n{0}\n{1}: {2}'.format(
                            log['error'],
                            log['errorDetail']['code'],
                            log['errorDetail']['message']
                        )
                    else:
                        msg = '\n{0}\n{1}'.format(
                            log['error'],
                            log['errorDetail']['message'],
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
        invalid(status, out=out, comment=comment)
    return status


def import_image(src, repo, tag=None, *args, **kwargs):
    '''
    Import content from a local tarball or a URL to a docker image

    :type src: string
    :param src: The content to import (URL, absolute path to a tarball)

    :type repo: string
    :param repo: The repository to import to

    :type tag: string
    :param tag: An optional tag to set

    CLI Example:

    .. code-block:: bash

        salt '*' docker.import_image <src> <repo> [tag]
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        ret = client.import_image(src, repository=repo, tag=tag)
        if ret:
            logs, info = _parse_image_multilogs_string(ret)
            _create_image_assemble_error_status(status, ret, logs)
            if status['status'] is not False:
                infos = _get_image_infos(logs[0]['status'])
                valid(status,
                      comment='Image {0} was created'.format(infos['id']),
                      id=infos['id'],
                      out=ret)
        else:
            invalid(status)
    except Exception:
        invalid(status, out=traceback.format_exc())
    return status


def tag(image, repository, tag=None, force=False, *args, **kwargs):
    '''
    Tag an image into a repository

    :type image: string
    :param image: The image to tag

    :type repository: string
    :param repository: The repository to tag the image

    :type tag: string
    :param tag: The tag to apply

    :type force: boolean
    :param force: Forces application of the tag

    CLI Example:

    .. code-block:: bash

        salt '*' docker.tag <image> <repository> [tag] [force=(True|False)]
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        dimage = _get_image_infos(image)['id']
        ret = client.tag(dimage, repository, tag=tag, force=force)
    except Exception:
        invalid(status,
                out=traceback.format_exc(),
                comment='Cant tag image {0} {1}{2}'.format(
                    image, repository,
                    tag and (':' + tag) or '').strip())
        return status
    if ret:
        valid(status,
              id=image,
              comment='Image was tagged: {0}{1}'.format(
                  repository,
                  tag and (':' + tag) or '').strip())
    else:
        invalid(status)
    return status


def get_images(name=None, quiet=False, all=True, *args, **kwargs):
    '''
    List docker images

    :type name: string
    :param name: A repository name to filter on

    :type quiet: boolean
    :param quiet: Only show image ids

    :type all: boolean
    :param all: Show all images

    :rtype: dict
    :returns: A status message with the command output

    CLI Example:

    .. code-block:: bash

        salt '*' docker.get_images [name] [quiet=True|False] [all=True|False]
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
        valid(status, out=infos)
    except Exception:
        invalid(status, out=traceback.format_exc())
    return status


def build(path=None,
          tag=None,
          quiet=False,
          fileobj=None,
          nocache=False,
          rm=True,
          *args, **kwargs):
    '''
    Build a docker image from a dockerfile or an URL

    You can either:

        - give the url/branch/docker_dir
        - give a path on the file system

    path
        URL or path in the filesystem to the dockerfile
    tag
        Tag of the image
    quiet
        quiet mode
    nocache
        do not use docker image cache
    rm
        remove intermediate commits

    CLI Example:

    .. code-block:: bash

        salt '*' docker.build
    '''
    client = _get_client()
    status = base_status.copy()
    if path or fileobj:
        try:
            ret = client.build(path=path,
                               tag=tag,
                               quiet=quiet,
                               fileobj=fileobj,
                               rm=rm,
                               nocache=nocache)
            if isinstance(ret, tuple):
                id, out = ret[0], ret[1]
                if id:
                    valid(status, id=id, out=out, comment='Image built')
                else:
                    invalid(status, id=id, out=out)
        except Exception:
            invalid(status,
                    out=traceback.format_exc(),
                    comment='Unexpected error while building an image')
            return status
    return status


def remove_image(image, *args, **kwargs):
    '''
    Remove an image from a system.

    :type image: string
    :param image: The image to remove

    :rtype: string
    :returns: A status message.

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
            status['id'] = infos['id']
            try:
                client.remove_image(infos['id'])
            except Exception:
                invalid(status,
                        id=image,
                        out=traceback.format_exc(),
                        comment='Image could not be deleted')
            try:
                infos = _get_image_infos(image)
                invalid(status,
                        comment=(
                            'Image marked to be deleted but not deleted yet'))
            except Exception:
                valid(status, id=image, comment='Image deleted')
        else:
            invalid(status)
    except Exception:
        invalid(status,
                out=traceback.format_exc(),
                comment='Image does not exist: {0}'.format(image))
    return status


def inspect_image(image, *args, **kwargs):
    '''
    Inspect the status of an image and return relative data

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
        valid(status, id=image, out=infos)
    except Exception:
        invalid(status, id=image, out=traceback.format_exc(),
                comment='Image does not exist')
    return status


def _parse_image_multilogs_string(ret):
    '''
    Parse image log strings into grokable data
    '''
    logs, infos = [], None
    if ret and ret.startswith('{') and ret.endswith('}'):
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
                logs.append(buf)
                buf = ''
        logs.reverse()
        # search last layer grabbed
        for l in logs:
            if isinstance(l, dict):
                if (
                    l.get('progress', 'not complete') == 'complete'
                    and l.get('id', None)
                ):
                    infos = _get_image_infos(l['id'])
                    break
    return logs, infos


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
        for log in logs:
            if isinstance(log, dict):
                if 'errorDetail' in log:
                    if 'code' in log['errorDetail']:
                        msg = '\n{0}\n{1}: {2}'.format(
                            log['error'],
                            log['errorDetail']['code'],
                            log['errorDetail']['message']
                        )
                    else:
                        msg = '\n{0}\n{1}'.format(
                            log['error'],
                            log['errorDetail']['message'],
                        )
                    comment += msg
    except Exception:
        out = traceback.format_exc()
    invalid(status, out=out, comment=comment)
    return status


def pull(repo, tag=None, *args, **kwargs):
    '''
    Pulls an image from any registry. See above documentation for
    how to configure authenticated access.

    :type repo: string
    :param repo: The repository to pull. \
        [registryurl://]REPOSITORY_NAME_image
        eg::

            index.docker.io:MyRepo/image
            superaddress.cdn:MyRepo/image
            MyRepo/image

    :type tag: string
    :param tag: The specific tag  to pull

    :rtype: dict
    :returns: A status message with the command output
        Example:

        .. code-block:: yaml

            ----------
            comment:
                Image NAME was pulled (ID
            id:
                None
            out:
                ----------
                - id:
                    2c80228370c9
                - progress:
                    complete
                - status:
                    Download
                ----------
                - id:
                    2c80228370c9
                - progress:
                    image (latest) from NAME, endpoint: URL
                - status:
                    Pulling
                ----------
                - id:
                    2c80228370c9
                - progress:
                    image (latest) from foo/ubuntubox
                - status:
                    Pulling
                ----------
                - status:
                    Pulling repository foo/ubuntubox
            status:
                True

    CLI Example:

    .. code-block:: bash

        salt '*' docker.pull <repository> [tag]
    '''
    client = _get_client()
    status = base_status.copy()
    try:
        ret = client.pull(repo, tag=tag)
        if ret:
            logs, infos = _parse_image_multilogs_string(ret)
            if infos and infos.get('id', None):
                repotag = repo
                if tag:
                    repotag = '{0}:{1}'.format(repo, tag)
                valid(status,
                      out=logs and logs or ret,
                      comment='Image {0} was pulled ({1})'.format(
                          repotag, infos['id']))

            else:
                _pull_assemble_error_status(status, ret, logs)
        else:
            invalid(status)
    except Exception:
        invalid(status, id=repo, out=traceback.format_exc())
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
        for log in logs:
            if isinstance(log, dict):
                if 'errorDetail' in log:
                    if 'code' in log['errorDetail']:
                        msg = '\n{0}\n{1}: {2}'.format(
                            log['error'],
                            log['errorDetail']['code'],
                            log['errorDetail']['message']
                        )
                    else:
                        msg = '\n{0}\n{1}'.format(
                            log['error'],
                            log['errorDetail']['message'],
                        )
                    comment += msg
    except Exception:
        trace = traceback.format_exc()
        status['out'] = (
            'An error occurred while '
            'parsing error output:\n{0}'
        ).format(trace)
    invalid(status, comment=comment)
    return status


def push(repo, *args, **kwargs):
    '''
    Pushes an image from any registry
    See this top level documentation to know
    how to configure authenticated access

    repo
        [registryurl://]REPOSITORY_NAME_image
        eg::

            index.docker.io:MyRepo/image
            superaddress.cdn:MyRepo/image
            MyRepo/image

    CLI Example:

    .. code-block:: bash

        salt '*' docker.push <repo>
    '''
    client = _get_client()
    status = base_status.copy()
    registry, repo_name = docker.auth.resolve_repository_name(repo)
    ret = client.push(repo)
    logs, infos = _parse_image_multilogs_string(ret)
    if logs:
        laststatus = logs[0].get('status', None)
        if laststatus and (
            ('already pushed' in laststatus)
            or ('Pushing tags for rev' in laststatus)
        ):
            status['status'] = True
            status['id'] = _get_image_infos(repo)['id']
            status['comment'] = 'Image {0}({1}) was pushed'.format(
                repo, status['id'])
            if logs:
                status['out'] = logs
            else:
                status['out'] = ret
        else:
            _push_assemble_error_status(status, ret, logs)
    else:
        _push_assemble_error_status(status, ret, logs)
    return status


def _run_wrapper(status, container, func, cmd,  *args, **kwargs):
    '''
    Wrapper to a cmdmod function

    Idea is to prefix the call to cmdrun with the relevant lxc-attach to
    execute inside a container context

    status
        status object
    container
        container id or grain to execute in
    func
        cmd function to execute
    cmd
        command to execute in container
    '''
    try:
        cid = _get_container_infos(container)['id']
        dcmd = 'lxc-attach -n {0} -- {1}'.format(cid, cmd)
        comment = 'Executed {0}'.format(dcmd)
        try:
            f = __salt__[func]
            ret = f(dcmd, *args, **kwargs)
            if (
                (
                    isinstance(ret, dict)
                    and (
                        ('retcode' in ret)
                        and (ret['retcode'] != 0)
                    )
                )
                or (func == 'cmd.retcode' and ret != 0)
            ):
                return invalid(status, id=container, out=ret, comment=comment)
            valid(status, id=container, out=ret, comment=comment,)
        except Exception:
            invalid(status, id=container,
                    comment=comment, out=traceback.format_exc())
    except Exception:
        invalid(status, id=container, out=traceback.format_exc())
    return status


def run(container, cmd, *args, **kwargs):
    '''
    Wrapper for cmdmod.run inside a container context

    container
        container id (or grain)

    Other params:
        See cmdmod documentation

    The return is a bit different as we use the docker struct,
    The output of the command is in 'out'
    The result is always True

    WARNING:
        Be advised that this function allows for raw shell access to the named
        container! If allowing users to execute this directly it may allow more
        rights than intended!

    CLI Example:

    .. code-block:: bash

        salt '*' docker.run <container id> 'ls -l /etc'
    '''
    status = base_status.copy()
    return _run_wrapper(
        status, container, 'cmd.run', cmd, *args, **kwargs)


def run_all(container, cmd, *args, **kwargs):
    '''
    Wrapper for cmdmod.run_all inside a container context

    container
        container id (or grain)

    Other params:
        See cmdmod documentation

    The return is a bit different as we use the docker struct,
    The output of the command is in 'out'
    The result if false if command failed

    WARNING:
        Be advised that this function allows for raw shell access to the named
        container! If allowing users to execute this directly it may allow more
        rights than intended!

    CLI Example:

    .. code-block:: bash

        salt '*' docker.run_all <container id> 'ls -l /etc'
    '''
    status = base_status.copy()
    return _run_wrapper(
        status, container, 'cmd.run_all', cmd, *args, **kwargs)


def run_stderr(container, cmd, *args, **kwargs):
    '''
    Wrapper for cmdmod.run_stderr inside a container context

    container
        container id (or grain)

    Other params:
        See cmdmod documentation

    The return is a bit different as we use the docker struct,
    The output of the command is in 'out'
    The result is always True

    WARNING:
        Be advised that this function allows for raw shell access to the named
        container! If allowing users to execute this directly it may allow more
        rights than intended!

    CLI Example:

    .. code-block:: bash

        salt '*' docker.run_stderr <container id> 'ls -l /etc'
    '''
    status = base_status.copy()
    return _run_wrapper(
        status, container, 'cmd.run_stderr', cmd, *args, **kwargs)


def run_stdout(container, cmd, *args, **kwargs):
    '''
    Wrapper for cmdmod.run_stdout inside a container context

    container
        container id (or grain)

    Other params:
        See cmdmod documentation

    The return is a bit different as we use the docker struct,
    The output of the command is in 'out'
    The result is always True

    WARNING:
        Be advised that this function allows for raw shell access to the named
        container! If allowing users to execute this directly it may allow more
        rights than intended!

    CLI Example:

    .. code-block:: bash

        salt '*' docker.run_stdout <container id> 'ls -l /etc'
    '''
    status = base_status.copy()
    return _run_wrapper(
        status, container, 'cmd.run_stdout', cmd, *args, **kwargs)


def retcode(container, cmd, *args, **kwargs):
    '''
    Wrapper for cmdmod.retcode inside a container context

    container
        container id (or grain)

    Other params:
        See cmdmod documentation

    The return is a bit different as we use the docker struct,
    The output of the command is in 'out'
    The result is false if command failed

    WARNING:
        Be advised that this function allows for raw shell access to the named
        container! If allowing users to execute this directly it may allow more
        rights than intended!

    CLI Example:

    .. code-block:: bash

        salt '*' docker.retcode <container id> 'ls -l /etc'
    '''
    status = base_status.copy()
    return _run_wrapper(
        status, container, 'cmd.retcode', cmd, *args, **kwargs)


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
        _get_container_infos(container)['id'],
    )
    default_rootfs = os.path.join(default_path, 'roofs')
    rootfs_re = re.compile(r'^lxc.rootfs\s*=\s*(.*)\s*$', re.U)
    try:
        lxcconfig = os.path.join(
            default_path, 'config.lxc')
        f = open(lxcconfig)
        try:
            lines = f.readlines()
            rlines = lines[:]
            rlines.reverse()
            for rl in rlines:
                robj = rootfs_re.search(rl)
                if robj:
                    rootfs = robj.groups()[0]
                    break
        finally:
            f.close()
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
                           quiet=kwargs.get('quiet', False),
                           runas=runas,
                           shell=shell,
                           umask=umask,
                           timeout=timeout,
                           reset_system_locale=reset_system_locale)
        if not no_clean:
            os.remove(path)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc())
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
           saltenv='base',
           *nargs,
           **kwargs):
    '''
    Same usage as cmd.script but running inside a container context

    container
        container id or grain
    others params and documentation
        See cmd.retcode

    WARNING:
        Be advised that this function allows for raw shell access to the named
        container! If allowing users to execute this directly it may allow more
        rights than intended!

    CLI Example:

    .. code-block:: bash

        salt '*' docker.script <container id> salt://docker_script.py
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
                   saltenv=saltenv,
                   **kwargs)


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
                   saltenv='base',
                   *args,
                   **kwargs):
    '''
    Same usage as cmd.script_retcode but running inside a container context

    container
        container id or grain
    others params and documentation
        See cmd.retcode

    WARNING:
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

    return _script(container,
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
                   saltenv=saltenv,
                   **kwargs)
