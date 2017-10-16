# -*- coding: utf-8 -*-
'''
Manage Docker containers
========================

.. deprecated:: 2015.8.0
    Future feature development will be done only in :mod:`dockerng
    <salt.states.dockerng>`. See the documentation for this module for
    information on the deprecation path.

`Docker <https://www.docker.io>`_
is a lightweight, portable, self-sufficient software container
wrapper. The base supported wrapper type is
`LXC <https://en.wikipedia.org/wiki/Linux_Containers>`_,
`cgroups <https://en.wikipedia.org/wiki/Cgroups>`_, and the
`Linux Kernel <https://en.wikipedia.org/wiki/Linux_kernel>`_.

.. note::

    This state module requires
    `docker-py <https://github.com/dotcloud/docker-py>`_ version >= 0.6.0
    which supports `Docker Remote API version 1.12
    <http://docs.docker.io/en/latest/reference/api/docker_remote_api_v1.6>`_.

Available Functions
-------------------

- built

  .. code-block:: yaml

      corp/mysuperdocker_img:
        docker.built:
          - path: /path/to/dir/container

- pulled

  .. code-block:: yaml

      ubuntu:
        docker.pulled:
          - tag: latest

- pushed

  .. code-block:: yaml

      corp/mysuperdocker_img:
        docker.pushed

- installed

  .. code-block:: yaml

      mysuperdocker-container:
        docker.installed:
          - name: mysuperdocker
          - hostname: superdocker
          - image: corp/mysuperdocker_img

- loaded

  .. code-block:: yaml

      mysuperdocker-file:
        docker.loaded:
          - name: mysuperdocker
          - source: salt://_files/tmp/docker_image.tar

- running

  .. code-block:: yaml

      my_service:
        docker.running:
          - container: mysuperdocker
          - image: corp/mysuperdocker_img
          - ports:
            - "5000/tcp":
                  HostIp: ""
                  HostPort: "5000"

  .. note::

      The ``ports`` argument above is a dictionary. The double
      indentation is required for PyYAML to load the data structure
      properly as a python dictionary. More information can be found
      :ref:`here <nested-dict-indentation>`

- absent

  .. code-block:: yaml

      mys_old_uperdocker:
        docker.absent

- run

  .. code-block:: yaml

      /finish-install.sh:
        docker.run:
          - cid: mysuperdocker
          - unless: grep -q something /var/log/foo
          - docker_unless: grep -q done /install_log

Use Cases
---------

   Ensures the container is running with the latest image available

   .. code-block:: yaml

      my-service-image:
        docker.pulled:
          - name: registry/my-service:latest
          - force: true

      my-service-container:
        docker.installed:
          - image: registry/my-service:latest
          - watch:
            - docker: my-service-image

      my-service:
        docker.running:
          - container: my-service-container
          - watch:
            - docker: my-service-container

.. note::

    The docker modules are named ``dockerio`` because
    the name 'docker' would conflict with the underlying docker-py library.


'''

from __future__ import absolute_import
import functools
import logging

# Import salt libs
from salt.ext.six import string_types
import salt.utils
import salt.ext.six as six

# Enable proper logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'docker'


def __virtual__():
    '''
    Only load if the dockerio execution module is available
    '''
    if 'docker.version' in __salt__:
        return __virtualname__
    return False


INVALID_RESPONSE = 'We did not get an acceptable answer from docker'
VALID_RESPONSE = ''
NOTSET = object()


def _ret_status(exec_status=None,
                name='',
                comment='',
                result=None,
                changes=None):
    if not changes:
        changes = {}
    if exec_status is None:
        exec_status = {}
    if exec_status:
        if result is None:
            result = exec_status['status']
        scomment = exec_status.get('comment', None)
        if scomment:
            comment += '\n' + scomment
        out = exec_status.get('out', None)
        if out:
            if isinstance(out, string_types):
                comment += '\n' + out
    return {
        'changes': changes,
        'result': result,
        'name': name,
        'comment': comment,
    }


def _valid(exec_status=None, name='', comment='', changes=None):
    return _ret_status(exec_status=exec_status,
                       comment=comment,
                       name=name,
                       changes=changes,
                       result=True)


def _invalid(exec_status=None, name='', comment='', changes=None):
    return _ret_status(exec_status=exec_status,
                       comment=comment,
                       name=name,
                       changes=changes,
                       result=False)


def _get_image_name(image, tag):
    if ':' not in image:
        # backward compatibility: name could be already tagged
        return ':'.join((image, tag))
    return image


def _parse_volumes(volumes):
    '''
    Parse a given volumes state specification for later use in
    modules.docker.create_container(). This produces a dict that can be directly
    consumed by the Docker API /containers/create.

    Note: this only really exists for backwards-compatibility, and because
    modules.dockerio.start() currently takes a binds argument.

    volumes
        A structure containing information about the volumes to be included in the
        container that will be created, either:
            - a bare dictionary
            - a list of dictionaries and lists

        .. code-block:: yaml

            # bare dict style
            - volumes:
                /usr/local/etc/ssl/certs/example.crt:
                  bind: /etc/ssl/certs/com.example.internal.crt
                  ro: True
                /var/run:
                  bind: /var/run/host/
                  ro: False

            # list of dicts style:
            - volumes:
              - /usr/local/etc/ssl/certs/example.crt:
                  bind: /etc/ssl/certs/com.example.internal.crt
                  ro: True
              - /var/run: /var/run/host/ # read-write bound volume
              - /var/lib/mysql # un-bound, container-only volume

        note: bind mounts specified like "/etc/timezone:/tmp/host_tz" will fall
        through this parser.

    Returns a dict of volume specifications:

        .. code-block:: yaml

            {
              'bindvols': {
                '/usr/local/etc/ssl/certs/example.crt': {
                  'bind': '/etc/ssl/certs/com.example.internal.crt',
                  'ro': True
                  },
                '/var/run/': {
                  'bind': '/var/run/host',
                  'ro': False
                },
              },
              'contvols': [ '/var/lib/mysql/' ]
            }

    '''
    log.trace("Parsing given volumes dict: " + str(volumes))
    bindvolumes = {}
    contvolumes = []
    if isinstance(volumes, dict):
        # If volumes as a whole is a dict, then there's no way to specify a non-bound volume
        # so we exit early and assume the dict is properly formed.
        bindvolumes = volumes
    if isinstance(volumes, list):
        for vol in volumes:
            if isinstance(vol, dict):
                for volsource, voldef in vol.items():
                    if isinstance(voldef, dict):
                        target = voldef['bind']
                        read_only = voldef.get('ro', False)
                    else:
                        target = str(voldef)
                        read_only = False
                    source = volsource
            else:  # isinstance(vol, dict)
                if ':' in vol:
                    volspec = vol.split(':')
                    source = volspec[0]
                    target = volspec[1]
                    read_only = False
                    try:
                        if len(volspec) > 2:
                            read_only = volspec[2] == "ro"
                    except IndexError:
                        pass
                else:
                    contvolumes.append(str(vol))
                    continue
            bindvolumes[source] = {
                'bind': target,
                'ro': read_only
            }
    result = {'bindvols': bindvolumes, 'contvols': contvolumes}
    log.trace("Finished parsing volumes, with result: " + str(result))
    return result


def mod_watch(name, sfun=None, *args, **kw):
    if sfun == 'built':
        # Needs to refresh the image
        kw['force'] = True
        build_status = built(name, **kw)
        result = build_status['result']
        status = _ret_status(build_status, name, result=result,
                             changes={name: result})
        return status
    elif sfun == 'installed':
        # Throw away the old container and create a new one
        remove_container = __salt__['docker.remove_container']
        remove_status = _ret_status(remove_container(container=name,
                                                     force=True),
                                    name=name)
        installed_status = installed(name=name, **kw)
        result = installed_status['result'] and remove_status['result']
        comment = remove_status['comment']
        status = _ret_status(installed_status, name=name,
                             result=result,
                             changes={name: result},
                             comment=comment)
        return status
    elif sfun == 'running':
        # Force a restart or kill the container
        container = kw.get('container', name)
        kill_signal = kw.get('kill_signal')
        if kill_signal:
            killer = __salt__['docker.kill']
            status = _ret_status(killer(container, signal=kill_signal),
                                 name=name,
                                 changes={name: True})
        else:
            restarter = __salt__['docker.restart']
            status = _ret_status(restarter(container),
                                 name=name,
                                 changes={name: True})
        return status

    return {'name': name,
            'changes': {},
            'result': False,
            'comment': ('watch requisite is not'
                        ' implemented for {0}'.format(sfun))}


def pulled(name,
           tag='latest',
           force=False,
           insecure_registry=False,
           *args,
           **kwargs):
    '''
    Pull an image from a docker registry. (`docker pull`)

    .. note::

        See first the documentation for `docker login`, `docker pull`,
        `docker push`,
        and `docker.import_image <https://github.com/dotcloud/docker-py#api>`_
        (`docker import
        <http://docs.docker.io/en/latest/reference/commandline/cli/#import>`_).
        NOTE that we added in SaltStack a way to authenticate yourself with the
        Docker Hub Registry by supplying your credentials (username, email &
        password) using pillars. For more information, see salt.modules.dockerio
        execution module.

    name
        Name of the image

    tag
        Tag of the image

    force
        Pull even if the image is already pulled

    insecure_registry
        Set to ``True`` to allow connections to non-HTTPS registries. Default ``False``.
    '''

    inspect_image = __salt__['docker.inspect_image']
    image_name = _get_image_name(name, tag)
    image_infos = inspect_image(image_name)
    if image_infos['status'] and not force:
        return _valid(
            name=name,
            comment='Image already pulled: {0}'.format(image_name))

    if __opts__['test']:
        comment = 'Image {0} will be pulled'.format(image_name)
        return _ret_status(name=name, comment=comment)

    previous_id = image_infos['out']['Id'] if image_infos['status'] else None
    pull = __salt__['docker.pull']
    returned = pull(name, tag=tag, insecure_registry=insecure_registry)
    if previous_id != returned['id']:
        changes = {name: {'old': previous_id,
                          'new': returned['id']}}
        comment = 'Image {0} pulled'.format(image_name)
    else:
        changes = {}
        comment = ''
    return _ret_status(returned, name, changes=changes, comment=comment)


def pushed(name, tag='latest', insecure_registry=False):
    '''
    Push an image from a docker registry. (`docker push`)

    .. note::

        See first the documentation for `docker login`, `docker pull`,
        `docker push`,
        and `docker.import_image <https://github.com/dotcloud/docker-py#api>`_
        (`docker import
        <http://docs.docker.io/en/latest/reference/commandline/cli/#import>`_).
        NOTE that we added in SaltStack a way to authenticate yourself with the
        Docker Hub Registry by supplying your credentials (username, email
        & password) using pillars. For more information, see
        salt.modules.dockerio execution module.

    name
        Name of the image

    tag
        Tag of the image [Optional]

    insecure_registry
        Set to ``True`` to allow connections to non-HTTPS registries. Default ``False``.
    '''

    image_name = _get_image_name(name, tag)
    if __opts__['test']:
        comment = 'Image {0} will be pushed'.format(image_name)
        return _ret_status(name=name, comment=comment)

    push = __salt__['docker.push']
    returned = push(name, tag=tag, insecure_registry=insecure_registry)
    log.debug("Returned: "+str(returned))
    if returned['status']:
        changes = {name: {'Rev': returned['id']}}
    else:
        changes = {}
    return _ret_status(returned, name, changes=changes)


def loaded(name, tag='latest', source=None, source_hash='', force=False):
    '''
    Load an image into the local docker registry (`docker load`)

    name
        Name of the docker image

    tag
        tag of the image (defaults to 'latest')

    source
        The source .tar file to download to the minion, created by docker save
        this source file can be hosted on either the salt master server,
        or on an HTTP or FTP server.

        If the file is hosted on a HTTP or FTP server then the source_hash
        argument is also required

        .. note::

            See first the documentation for Salt `file.managed
            <http://docs.saltstack.com/en/latest/ref/states/all/salt.states.file.html#salt.states.file.managed>`_

    source_hash
        This can be one of the following:
            1. a source hash string
            2. the URI of a file that contains source hash strings

    force
        Load even if the image exists
    '''

    inspect_image = __salt__['docker.inspect_image']
    image_name = _get_image_name(name, tag)
    image_infos = inspect_image(image_name)
    if image_infos['status'] and not force:
        return _valid(
            name=name,
            comment='Image already loaded: {0}'.format(image_name))

    if __opts__['test']:
        comment = 'Image {0} will be loaded'.format(image_name)
        return _ret_status(name=name, comment=comment)

    tmp_filename = salt.utils.mkstemp()
    __states__['file.managed'](name=tmp_filename,
                               source=source,
                               source_hash=source_hash)
    changes = {}

    if image_infos['status']:
        changes['old'] = image_infos['out']['Id']
        remove_image = __salt__['docker.remove_image']
        remove_info = remove_image(image_name)
        if not remove_info['status']:
            return _invalid(name=name,
                            comment='Image could not be removed: {0}'.format(name))

    load = __salt__['docker.load']
    returned = load(tmp_filename)

    image_infos = inspect_image(image_name)
    if image_infos['status']:
        changes['new'] = image_infos['out']['Id']
    else:
        return _invalid(
            name=name,
            comment='Image {0} was not loaded into docker'.format(image_name))

    return _ret_status(returned, name, changes=changes)


def built(name,
          tag='latest',
          path=None,
          quiet=False,
          nocache=False,
          rm=True,
          force=False,
          timeout=None,
          *args, **kwargs):
    '''
    Build a docker image from a path or URL to a dockerfile. (`docker build`)

    name
        Name of the image

    tag
        tag of the image (defaults to 'latest')

    path
        URL (e.g. `url/branch/docker_dir/dockerfile`)
        or filesystem path to the dockerfile

    '''
    inspect_image = __salt__['docker.inspect_image']
    image_name = _get_image_name(name, tag)
    image_infos = inspect_image(image_name)
    if image_infos['status'] and not force:
        return _valid(
            name=name,
            comment='Image already built: {0}, id: {1}'.format(
                image_name, image_infos['out']['Id']))

    if __opts__['test']:
        comment = 'Image {0} will be built'.format(image_name)
        return {'name': name,
                'changes': {},
                'result': None,
                'comment': comment}

    previous_id = image_infos['out']['Id'] if image_infos['status'] else None
    build = __salt__['docker.build']
    kw = dict(tag=image_name,
              path=path,
              quiet=quiet,
              nocache=nocache,
              rm=rm,
              timeout=timeout,
              )
    returned = build(**kw)
    if previous_id != returned['id']:
        changes = {name: {'old': previous_id,
                          'new': returned['id']}}
        comment = 'Image {0} built'.format(image_name)
    else:
        changes = {}
        comment = ''
    return _ret_status(exec_status=returned,
                       name=name,
                       changes=changes,
                       comment=comment)


def installed(name,
              image,
              tag='latest',
              command=None,
              hostname=None,
              user=None,
              detach=True,
              stdin_open=False,
              tty=False,
              mem_limit=None,
              ports=None,
              environment=None,
              dns=None,
              volumes=None,
              volumes_from=None,
              cpu_shares=None,
              cpuset=None,
              *args, **kwargs):
    '''
    Ensure that a container with the given name exists;
    if not, build a new container from the specified image.
    (`docker run`)

    name
        Name for the container

    image
        Image from which to build this container

    tag
        tag of the image (defaults to 'latest')

    environment
        Environment variables for the container, either
            - a mapping of key, values
            - a list of mappings of key, values
    ports
        List of ports definitions, either:
            - a port to map
            - a mapping of mapping portInHost : PortInContainer
    volumes
        List of volumes (see notes for the running function)

    For other parameters, see absolutely first the salt.modules.dockerio
    execution module and the `docker-py python bindings for docker
    documentation <https://github.com/dotcloud/docker-py#api>`_ for
    `docker.create_container`.

    .. note::
        This command does not verify that the named container
        is running the specified image.
    '''
    ins_image = __salt__['docker.inspect_image']
    ins_container = __salt__['docker.inspect_container']
    create = __salt__['docker.create_container']
    image_name = _get_image_name(image, tag)
    iinfos = ins_image(image_name)
    if not iinfos['status']:
        return _invalid(comment='Image "{0}" does not exist'.format(image_name))
    cinfos = ins_container(name)
    already_exists = cinfos['status']
    # if container exists but is not started, try to start it
    if already_exists:
        return _valid(comment='Container \'{0}\' already exists'.format(name))
    dports, denvironment = {}, {}

    if __opts__['test']:
        comment = 'Container \'{0}\' will be created'.format(name)
        return _ret_status(name=name, comment=comment)

    if not ports:
        ports = []
    if not volumes:
        volumes = []
    if isinstance(environment, dict):
        for k in environment:
            denvironment[six.text_type(k)] = six.text_type(environment[k])
    if isinstance(environment, list):
        for p in environment:
            if isinstance(p, dict):
                for k in p:
                    denvironment[six.text_type(k)] = six.text_type(p[k])
    for p in ports:
        if not isinstance(p, dict):
            dports[str(p)] = {}
        else:
            for k in p:
                dports[str(p)] = {}

    parsed_volumes = _parse_volumes(volumes)
    bindvolumes = parsed_volumes['bindvols']
    contvolumes = parsed_volumes['contvols']

    kw = dict(
        binds=bindvolumes,
        command=command,
        hostname=hostname,
        user=user,
        detach=detach,
        stdin_open=stdin_open,
        tty=tty,
        mem_limit=mem_limit,
        ports=dports,
        environment=denvironment,
        dns=dns,
        volumes=contvolumes,
        volumes_from=volumes_from,
        name=name,
        cpu_shares=cpu_shares,
        cpuset=cpuset)
    out = create(image_name, **kw)
    # if container has been created, even if not started, we mark
    # it as installed
    changes = 'Container created'
    try:
        cid = out['out']['info']['id']
    except Exception as e:
        log.debug(str(e))
    else:
        changes = 'Container {0} created'.format(cid)
        out['comment'] = changes
    ret = _ret_status(out, name, changes=changes)
    return ret


def absent(name):
    '''
    Ensure that the container is absent; if not, it will
    will be killed and destroyed. (`docker inspect`)

    name:
        Either the container name or id
    '''
    ins_container = __salt__['docker.inspect_container']
    cinfos = ins_container(name)
    changes = {}

    if cinfos['status']:
        cid = cinfos['id']
        changes[cid] = {}
        is_running = __salt__['docker.is_running'](cid)

        if __opts__['test']:
            comment = 'Container \'{0}\' will be stopped and destroyed'.format(cid)
            return _ret_status(name=name, comment=comment)

        # Stop container gracefully, if running
        if is_running:
            changes[cid]['old'] = 'running'
            __salt__['docker.stop'](cid)
            is_running = __salt__['docker.is_running'](cid)
            if is_running:
                return _invalid(comment=('Container \'{0}\' could not be stopped'
                                         .format(cid)))
            else:
                __salt__['docker.remove_container'](cid)
                is_gone = __salt__['docker.exists'](cid)
                if is_gone:
                    return _valid(comment=('Container \'{0}\''
                                  ' was stopped and destroyed, '.format(cid)),
                                  changes={name: True})
                else:
                    return _valid(comment=('Container \'{0}\''
                                  ' was stopped but could not be destroyed,'.format(cid)),
                                  changes={name: True})
        else:
            __salt__['docker.remove_container'](cid)
            is_gone = __salt__['docker.exists'](cid)
            if is_gone:
                return _valid(comment=('Container \'{0}\''
                              'is stopped and was destroyed, '.format(cid)),
                              changes={name: True})
            else:
                return _valid(comment=('Container \'{0}\''
                              ' is stopped but could not be destroyed,'.format(cid)),
                              changes={name: True})
    else:
        return _valid(comment='Container \'{0}\' not found'.format(name))


def present(name, image=None, tag='latest', is_latest=False):
    '''
    If a container with the given name is not present, this state will fail.
    Supports optionally checking for specific image/tag
    (`docker inspect`)

    name:
        container id
    image:
        image the container should be running (defaults to any)
    tag:
        tag of the image (defaults to 'latest')
    is_latest:
        also check if the container runs the latest version of the image (
        latest defined as the latest pulled onto the local machine)
    '''
    ins_container = __salt__['docker.inspect_container']
    cinfos = ins_container(name)
    if 'id' in cinfos:
        cid = cinfos['id']
    else:
        cid = name
    if not cinfos['status']:
        return _invalid(comment='Container {0} not found'.format(cid or name))
    if cinfos['status'] and image is None:
        return _valid(comment='Container {0} exists'.format(cid))
    image_name = _get_image_name(image, tag)
    if cinfos['status'] and cinfos['out']['Config']["Image"] == image_name and not is_latest:
        return _valid(comment='Container {0} exists and has image {1}'.format(cid, image_name))
    ins_image = __salt__['docker.inspect_image']
    iinfos = ins_image(image_name)
    if cinfos['status'] and cinfos['out']['Image'] == iinfos['out']['Id']:
        return _valid(comment='Container {0} exists and has latest version of image {1}'.format(cid, image_name))
    return _invalid(comment='Container {0} found with wrong image'.format(cid or name))


def run(name,
        cid=None,
        hostname=None,
        onlyif=None,
        unless=None,
        docked_onlyif=None,
        docked_unless=None,
        *args, **kwargs):
    '''
    Run a command in a specific container

    You can match by either name or hostname

    name
        command to run in the container

    cid
        Container id or name

    state_id
        state_id

    onlyif
        Only execute cmd if statement on the host returns 0

    unless
        Do not execute cmd if statement on the host returns 0

    docked_onlyif
        Only execute cmd if statement in the container returns 0

    docked_unless
        Do not execute cmd if statement in the container returns 0

    '''
    if hostname:
        salt.utils.warn_until(
            'Helium',
            'The \'hostname\' argument has been deprecated.'
        )
    retcode = __salt__['docker.retcode']
    drun_all = __salt__['docker.run_all']
    valid = functools.partial(_valid, name=name)
    if onlyif is not None:
        if not isinstance(onlyif, string_types):
            if not onlyif:
                return valid(comment='onlyif execution failed')
        elif isinstance(onlyif, string_types):
            if not __salt__['cmd.retcode'](onlyif) == 0:
                return valid(comment='onlyif execution failed')

    if unless is not None:
        if not isinstance(unless, string_types):
            if unless:
                return valid(comment='unless execution succeeded')
        elif isinstance(unless, string_types):
            if __salt__['cmd.retcode'](unless) == 0:
                return valid(comment='unless execution succeeded')

    if docked_onlyif is not None:
        if not isinstance(docked_onlyif, string_types):
            if not docked_onlyif:
                return valid(comment='docked_onlyif execution failed')
        elif isinstance(docked_onlyif, string_types):
            if not retcode(cid, docked_onlyif):
                return valid(comment='docked_onlyif execution failed')

    if docked_unless is not None:
        if not isinstance(docked_unless, string_types):
            if docked_unless:
                return valid(comment='docked_unless execution succeeded')
        elif isinstance(docked_unless, string_types):
            if retcode(cid, docked_unless):
                return valid(comment='docked_unless execution succeeded')

    if __opts__['test']:
        comment = 'Command \'{0}\' will be executed on container {1}'.format(name, cid)
        return _ret_status(name=name, comment=comment)

    result = drun_all(cid, name)
    if result['status']:
        return valid(comment=result['comment'])
    else:
        return _invalid(comment=result['comment'], name=name)


def script(*args, **kw):
    '''
    Placeholder function for a cmd.script alike.

    .. note::

        Not yet implemented.
        Its implementation might be very similar from
        :mod:`salt.states.dockerio.run`
    '''
    raise NotImplementedError


def running(name,
            image,
            tag='latest',
            container=None,
            command=None,
            hostname=None,
            user=None,
            detach=True,
            stdin_open=False,
            tty=False,
            mem_limit=None,
            ports=None,
            environment=None,
            dns=None,
            volumes=None,
            volumes_from=None,
            start=True,
            cap_add=None,
            cap_drop=None,
            privileged=None,
            lxc_conf=None,
            network_mode=None,
            check_is_running=True,
            publish_all_ports=False,
            links=None,
            restart_policy=None,
            cpu_shares=None,
            cpuset=None,
            kill_signal=None,
            *args, **kwargs):
    '''
    Ensure that a container is running. If the container does not exist, it
    will be created from the specified image. (`docker run`)

    name / container
        Name for the container

    image
        Image from which to build this container

    tag
        tag of the image (defaults to 'latest')

    environment
        Environment variables for the container, either
            - a mapping of key, values
            - a list of mappings of key, values
    ports
        List of ports definitions, either:
            - a port to map
            - a mapping of mapping portInHost : PortInContainer

        .. code-block:: yaml

            - ports:
              - "5000/tcp":
                    HostIp: ""
                    HostPort: "5000"

    publish_all_ports
        Publish all ports from the port list (default is false,
        only meaningful if port does not contain portinhost:portincontainer mapping)

    volumes
        List of volumes to mount or create in the container (like ``-v`` of ``docker run`` command),
        mapping host directory to container directory.

        To specify a volume in the container in terse list format:

        .. code-block:: yaml

            - volumes:
              - "/var/log/service" # container-only volume
              - "/srv/timezone:/etc/timezone" # bound volume
              - "/usr/local/etc/passwd:/etc/passwd:ro" # read-only bound volume

        You can also use the short dictionary form (note that the notion of
        source:target from docker is preserved):

        .. code-block:: yaml

            - volumes:
              - /var/log/service: /var/log/service # mandatory read-write implied

        Or, alternatively, to specify read-only mounting, use the extended form:

        .. code-block:: yaml

            - volumes:
              - /home/user1:
                  bind: /mnt/vol2
                  ro: True
              - /var/www:
                  bind: /mnt/vol1
                  ro: False

        Or (for backwards compatibility) another dict style:

        .. code-block:: yaml

            - volumes:
                /home/user1:
                  bind: /mnt/vol2
                  ro: True
                /var/www:
                  bind: /mnt/vol1
                  ro: False

    volumes_from
        List of containers to share volumes with

    dns
        List of DNS servers.

        .. code-block:: yaml

            - dns:
                - 127.0.0.1

    network_mode
        - 'bridge': creates a new network stack for the container on the docker bridge
        - 'none': no networking for this container
        - 'container:[name|id]': reuses another container network stack)
        - 'host': use the host network stack inside the container

        .. code-block:: yaml

            - network_mode: host

    restart_policy
        Restart policy to apply when a container exits (no, on-failure[:max-retry], always)

        .. code-block:: yaml

            - restart_policy:
                MaximumRetryCount: 5
                Name: on-failure

    cap_add
        List of capabilities to add in a container.

    cap_drop
        List of capabilities to drop in a container.

    check_is_running
        Enable checking if a container should run or not.
        Useful for data-only containers that must be linked to another one.
        e.g. nginx <- static-files

    cpu_shares
        CPU shares (relative weight)

        .. code-block:: yaml

            - cpu_shares: 2
    cpuset
        CPUs in which to allow execution ('0-3' or '0,1')

        .. code-block:: yaml

            - cpuset: '0-3'
    kill_signal
        If defined, its value will be sent as a kill signal to the running
        container. i.e. It will use client.kill(signal=kill_signal)
        instead of client.restart(), when the state is triggered by a watcher
        requisite.

        possible use case: Soft reload of nginx

        .. code-block:: yaml

            nginx:
              docker.running:
                - image: some-fictional-registry.com/nginx
                - tag: latest
                - kill_signal: SIGHUP
                - watch:
                  - file: /etc/nginx/nginx.conf

        This state will ask nginx to reload (instead of restart)
        each time the /etc/nginx/nginx.conf is modified.

        .. versionadded:: 2015.8.0


    For other parameters, see salt.modules.dockerio execution module
    and the docker-py python bindings for docker documentation
    <https://github.com/dotcloud/docker-py#api>`_ for
    `docker.create_container`.

    .. note::
        This command does not verify that the named container
        is running the specified image.
    '''
    if container is None:
        container = name
    ins_image = __salt__['docker.inspect_image']
    ins_container = __salt__['docker.inspect_container']
    create = __salt__['docker.create_container']
    image_name = _get_image_name(image, tag)
    iinfos = ins_image(image_name)
    image_exists = iinfos['status']

    if not image_exists:
        return _invalid(comment='image "{0}" does not exists'.format(image_name))

    cinfos = ins_container(name)
    already_exists = cinfos['status']
    already_exists_with_same_image = (
        # if container is known by name,
        already_exists
        # and the container is based on expected image,
        and cinfos['out']['Image'] == iinfos['out']['Id']
        # then assume it already exists.
    )

    is_running = __salt__['docker.is_running'](container)

    # if container exists but is not started, try to start it
    if already_exists_with_same_image and (is_running or not start):
        return _valid(comment='container \'{0}\' already exists'.format(name))
    if not already_exists_with_same_image and already_exists:
        # Outdated container: It means it runs against an old image.
        # We're gonna have to stop and remove the old container, to let
        # the name available for the new one.
        if __opts__['test']:
            comment = 'Will replace outdated container \'{0}\''.format(name)
            return _ret_status(name=name, comment=comment)
        if is_running:
            stop_status = __salt__['docker.stop'](name)
            if not stop_status['status']:
                return _invalid(comment='Failed to stop outdated container \'{0}\''.format(name))

        remove_status = __salt__['docker.remove_container'](name)
        if not remove_status['status']:
            return _invalid(comment='Failed to remove outdated container \'{0}\''.format(name))
        already_exists = False
        # now it's clear, the name is available for the new container

    if __opts__['test']:
        comment = 'Will create container \'{0}\''.format(name)
        return _ret_status(name=name, comment=comment)

    # parse input data
    exposeports, bindports, contvolumes, bindvolumes, denvironment, changes = [], {}, [], {}, {}, []
    if not ports:
        ports = {}
    if not volumes:
        volumes = {}
    if not volumes_from:
        volumes_from = []
    if isinstance(environment, dict):
        for key in environment:
            denvironment[six.text_type(key)] = six.text_type(environment[key])
    if isinstance(environment, list):
        for var in environment:
            if isinstance(var, dict):
                for key in var:
                    denvironment[six.text_type(key)] = six.text_type(var[key])
    if isinstance(volumes, dict):
        bindvolumes = volumes
    if isinstance(volumes, list):
        for vol in volumes:
            if isinstance(vol, dict):
                # get source as the dict key
                source = list(vol.keys())[0]
                # then find target
                if isinstance(vol[source], dict):
                    target = vol[source]['bind']
                    read_only = vol[source].get('ro', False)
                else:
                    target = str(vol[source])
                    read_only = False
                bindvolumes[source] = {'bind': target,
                                       'ro': read_only
                                       }
            else:
                # assume just an own volumes
                contvolumes.append(str(vol))
    if isinstance(ports, dict):
        bindports = ports
        # in dict form all ports bind, so no need for exposeports
    if isinstance(ports, list):
        for port in ports:
            if isinstance(port, dict):
                container_port = list(port.keys())[0]
                # find target
                if isinstance(port[container_port], dict):
                    host_port = port[container_port]['HostPort']
                    host_ip = port[container_port].get('HostIp', '0.0.0.0')
                else:
                    host_port = str(port[container_port])
                    host_ip = '0.0.0.0'
                bindports[container_port] = {
                    'HostPort': host_port,
                    'HostIp': host_ip
                }
            else:
                # assume just a port to expose
                exposeports.append(str(port))

    parsed_volumes = _parse_volumes(volumes)
    bindvolumes = parsed_volumes['bindvols']
    contvolumes = parsed_volumes['contvols']

    if not already_exists:
        kwargs = dict(command=command,
                      hostname=hostname,
                      user=user,
                      detach=detach,
                      stdin_open=stdin_open,
                      tty=tty,
                      mem_limit=mem_limit,
                      ports=exposeports,
                      environment=denvironment,
                      dns=dns,
                      binds=bindvolumes,
                      volumes=contvolumes,
                      name=name,
                      cpu_shares=cpu_shares,
                      cpuset=cpuset)
        out = create(image_name, **kwargs)
        # if container has been created, even if not started, we mark
        # it as installed
        try:
            cid = out['out']['info']['id']
            log.debug(str(cid))
        except Exception as e:
            changes.append('Container created')
            log.debug(str(e))
        else:
            changes.append('Container {0} created'.format(cid))
    if start:
        started = __salt__['docker.start'](name,
                                           binds=bindvolumes,
                                           port_bindings=bindports,
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
        if check_is_running:
            is_running = __salt__['docker.is_running'](name)
            log.debug("Docker-io running:" + str(started))
            log.debug("Docker-io running:" + str(is_running))
            if is_running:
                changes.append('Container \'{0}\' started.\n'.format(name))
            else:
                return _invalid(comment=('Container \'{0}\' cannot be started\n{1!s}'
                                         .format(name, started['out'],)))
        else:
            changes.append('Container \'{0}\' started.\n'.format(name))
    return _valid(comment='\n'.join(changes), changes={name: True})
