# -*- coding: utf-8 -*-
'''
Manage Docker containers
========================

`Docker <https://www.docker.io>`_
is a lightweight, portable, self-sufficient software container
wrapper. The base supported wrapper type is
`LXC <https://en.wikipedia.org/wiki/Linux_Containers>`_,
`cgroups <https://en.wikipedia.org/wiki/Cgroups>`_, and the
`Linux Kernel <https://en.wikipedia.org/wiki/Linux_kernel>`_.

.. warning::

    This state module is beta. The API is subject to change. No promise
    as to performance or functionality is yet present.

.. note::

    This state module requires
    `docker-py <https://github.com/dotcloud/docker-py>`_
    which supports `Docker Remote API version 1.6
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
- running

  .. code-block:: yaml

      my_service:
        docker.running:
          - container: mysuperdocker
          - port_bindings:
              "5000/tcp":
                  HostIp: ""
                  HostPort: "5000"

  .. note::

      The ``port_bindings`` argument above is a dictionary. Note the
      double-indentation, this is required for PyYAML to load the data
      structure properly as a dictionary. More information can be found
      :ref:`here <nested-dict-indentation>`


- absent

  .. code-block:: yaml

      mys_old_uperdocker:
        docker.absent

- run

  .. code-block:: yaml

      /finish-install.sh:
        docker.run:
          - container: mysuperdocker
          - unless: grep -q something /var/log/foo
          - docker_unless: grep -q done /install_log

.. note::

    The docker modules are named ``dockerio`` because
    the name 'docker' would conflict with the underlying docker-py library.

    We should add magic to all methods to also match containers by name
    now that the 'naming link' stuff has been merged in docker.
    This applies for example to:

    - running
    - absent
    - run


'''
import functools
import logging

# Import salt libs
from salt._compat import string_types
import salt.utils

# Enable proper logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'docker'


def __virtual__():
    '''
    Only load if the docker libs are available.
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
        # Force a restart against new container
        restarter = __salt__['docker.restart']
        status = _ret_status(restarter(kw['container']), name=name,
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
        Docker Hub Registry by supplying your credentials (username, email & password)
        using pillars. For more information, see salt.modules.dockerio execution
        module.

    name
        Name of the image

    tag
        Tag of the image

    force
        Pull even if the image is already pulled
    '''

    inspect_image = __salt__['docker.inspect_image']
    image_infos = inspect_image('{0}:{1}'.format(name, tag))
    if image_infos['status'] and not force:
        return _valid(
            name=name,
            comment='Image already pulled: {0}:{1}'.format(name, tag))

    if __opts__['test'] and force:
        comment = 'Image {0}:{1} will be pulled'.format(name, tag)
        return _ret_status(name=name, comment=comment)

    previous_id = image_infos['out']['Id'] if image_infos['status'] else None
    pull = __salt__['docker.pull']
    returned = pull(name, tag=tag)
    if previous_id != returned['id']:
        changes = {name: {'old': previous_id,
                          'new': returned['id']}}
    else:
        changes = {}
    return _ret_status(returned, name, changes=changes)


def pushed(name, tag='latest'):
    '''
    Push an image from a docker registry. (`docker push`)

    .. note::

        See first the documentation for `docker login`, `docker pull`,
        `docker push`,
        and `docker.import_image <https://github.com/dotcloud/docker-py#api>`_
        (`docker import
        <http://docs.docker.io/en/latest/reference/commandline/cli/#import>`_).
        NOTE that we added in SaltStack a way to authenticate yourself with the
        Docker Hub Registry by supplying your credentials (username, email & password)
        using pillars. For more information, see salt.modules.dockerio execution
        module.

    name
        Name of the image

    tag
        Tag of the image [Optional]

    '''

    if __opts__['test']:
        comment = 'Image {0}:{1} will be pushed'.format(name, tag)
        return _ret_status(name=name, comment=comment)

    push = __salt__['docker.push']
    returned = push(name, tag=tag)
    log.debug("Returned: "+str(returned))
    if returned['status']:
        changes = {name: {'Rev': returned['id']}}
    else:
        changes = {}
    return _ret_status(returned, name, changes=changes)


def built(name,
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

    path
        URL (e.g. `url/branch/docker_dir/dockerfile`)
        or filesystem path to the dockerfile

    '''
    inspect_image = __salt__['docker.inspect_image']
    image_infos = inspect_image(name)
    if image_infos['status'] and not force:
        return _valid(
            name=name,
            comment='Image already built: {0}, id: {1}'.format(
                name, image_infos['out']['Id']))

    if __opts__['test'] and force:
        comment = 'Image {0} will be built'.format(name)
        return {'name': name,
                'changes': {},
                'result': None,
                'comment': comment}

    previous_id = image_infos['out']['Id'] if image_infos['status'] else None
    build = __salt__['docker.build']
    kw = dict(tag=name,
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
    else:
        changes = {}
    return _ret_status(exec_status=returned,
                       name=name,
                       changes=changes)


def installed(name,
              image,
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
              *args, **kwargs):
    '''
    Ensure that a container with the given name exists;
    if not, build a new container from the specified image.
    (`docker run`)

    name
        Name for the container

    image
        Image from which to build this container

    environment
        Environment variables for the container, either
            - a mapping of key, values
            - a list of mappings of key, values
    ports
        List of ports definitions, either:
            - a port to map
            - a mapping of mapping portInHost : PortInContainer
    volumes
        List of volumes

    For other parameters, see absolutely first the salt.modules.dockerio
    execution module and the docker-py python bindings for docker
    documentation
    <https://github.com/dotcloud/docker-py#api>`_ for
    `docker.create_container`.

    .. note::
        This command does not verify that the named container
        is running the specified image.
    '''
    ins_image = __salt__['docker.inspect_image']
    ins_container = __salt__['docker.inspect_container']
    create = __salt__['docker.create_container']
    iinfos = ins_image(image)
    if not iinfos['status']:
        return _invalid(comment='image "{0}" does not exist'.format(image))
    cinfos = ins_container(name)
    already_exists = cinfos['status']
    # if container exists but is not started, try to start it
    if already_exists:
        return _valid(comment='image {0!r} already exists'.format(name))
    dports, dvolumes, denvironment = {}, [], {}
    if not ports:
        ports = []
    if not volumes:
        volumes = []
    if isinstance(environment, dict):
        for k in environment:
            denvironment[unicode(k)] = unicode(environment[k])
    if isinstance(environment, list):
        for p in environment:
            if isinstance(p, dict):
                for k in p:
                    denvironment[unicode(k)] = unicode(p[k])
    for p in ports:
        if not isinstance(p, dict):
            dports[str(p)] = {}
        else:
            for k in p:
                dports[str(p)] = {}
    for p in volumes:
        vals = []
        if not isinstance(p, dict):
            vals.append('{0}'.format(p))
        else:
            for k in p:
                vals.append('{0}:{1}'.format(k, p[k]))
        dvolumes.extend(vals)
    a, kw = [image], dict(
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
        volumes=dvolumes,
        volumes_from=volumes_from,
        name=name)
    out = create(*a, **kw)
    # if container has been created, even if not started, we mark
    # it as installed
    changes = 'Container created'
    try:
        cid = out['out']['info']['id']
    except Exception, e:
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
    if cinfos['status']:
        cid = cinfos['id']
        is_running = __salt__['docker.is_running'](cid)
        # destroy if we found meat to do
        if is_running:
            __salt__['docker.stop'](cid)
            is_running = __salt__['docker.is_running'](cid)
            if is_running:
                return _invalid(
                    comment=('Container {0!r}'
                             ' could not be stopped'.format(cid)))
            else:
                __salt__['docker.remove_container'](cid)
                is_gone = __salt__['docker.exists'](cid)
                if is_gone:
                    return _valid(comment=('Container {0!r}'
                                           ' was stopped and destroyed, '.format(cid)),
                                           changes={name: True})
                else:
                    return _valid(comment=('Container {0!r}'
                                           ' was stopped but could not be destroyed,'.format(cid)),
                                           changes={name: True})
        else:
            __salt__['docker.remove_container'](cid)
            is_gone = __salt__['docker.exists'](cid)
            if is_gone:
                return _valid(comment=('Container {0!r}'
                                       ' is stopped and was destroyed, '.format(cid)),
                                       changes={name: True})
            else:
                return _valid(comment=('Container {0!r}'
                                       ' is stopped but could not be destroyed,'.format(cid)),
                                       changes={name: True})
    else:
        return _valid(comment='Container {0!r} not found'.format(name))


def present(name):
    '''
    If a container with the given name is not present, this state will fail.
    (`docker inspect`)

    name:
        container id
    '''
    ins_container = __salt__['docker.inspect_container']
    cinfos = ins_container(name)
    if 'id' in cinfos:
        cid = cinfos['id']
    else:
        cid = name
    if cinfos['status']:
        return _valid(comment='Container {0} exists'.format(cid))
    else:
        return _invalid(comment='Container {0} not found'.format(cid or name))


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
        Container id

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
            if retcode(cid, onlyif) != 0:
                return valid(comment='onlyif execution failed')

    if unless is not None:
        if not isinstance(unless, string_types):
            if unless:
                return valid(comment='unless execution succeeded')
        elif isinstance(unless, string_types):
            if retcode(cid, unless) == 0:
                return valid(comment='unless execution succeeded')

    if docked_onlyif is not None:
        if not isinstance(docked_onlyif, string_types):
            if not docked_onlyif:
                return valid(comment='docked_onlyif execution failed')
        elif isinstance(docked_onlyif, string_types):
            if retcode(cid, docked_onlyif) != 0:
                return valid(comment='docked_onlyif execution failed')

    if docked_unless is not None:
        if not isinstance(docked_unless, string_types):
            if docked_unless:
                return valid(comment='docked_unless execution succeeded')
        elif isinstance(docked_unless, string_types):
            if retcode(cid, docked_unless) == 0:
                return valid(comment='docked_unless execution succeeded')
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


def running(name, container=None, port_bindings=None, binds=None,
            publish_all_ports=False, links=None, lxc_conf=None,
            privileged=False, dns=None, volumes_from=None,
            network_mode=None, restart_policy=None, cap_add=None,
            cap_drop=None, check_is_running=True):
    '''
    Ensure that a container is running. (`docker inspect`)

    name
        name of the service

    container
        name of the container to start

    publish_all_ports

    links
        Link several container together

        .. code-block:: yaml

            - links:
                name_other_container: alias_for_other_container

    port_bindings
        List of ports to expose on host system
            - a mapping port's guest, hostname's host and port's host.

        .. code-block:: yaml

            - port_bindings:
                "5000/tcp":
                    HostIp: ""
                    HostPort: "5000"

    binds
        List of volumes to mount (like ``-v`` of ``docker run`` command),
        mapping host directory to container directory.

        For read-write mounting, use the short form:

        .. code-block:: yaml

            - binds:
                /var/log/service: /var/log/service

        Or, to specify read-only mounting, use the extended form:

        .. code-block:: yaml

            - binds:
                /home/user1:
                    bind: /mnt/vol2
                    ro: true
                /var/www:
                    bind: /mnt/vol1
                    ro: false

    dns
        List of DNS servers.

        .. code-block:: yaml

            - dns:
                - 127.0.0.1

    volumes_from
        List of container names to get volumes definition from

        .. code-block:: yaml

            - volumes_from:
                - name_other_container

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
    '''
    if not container and name:
        container = name
    is_running = __salt__['docker.is_running'](container)
    if is_running:
        return _valid(
            comment='Container {0!r} is started'.format(container))
    else:
        started = __salt__['docker.start'](
            container, binds=binds, port_bindings=port_bindings,
            lxc_conf=lxc_conf, publish_all_ports=publish_all_ports,
            links=links, privileged=privileged,
            dns=dns, volumes_from=volumes_from, network_mode=network_mode,
            restart_policy=restart_policy, cap_add=cap_add, cap_drop=cap_drop
        )
        if check_is_running:
            is_running = __salt__['docker.is_running'](container)
            log.debug("Docker-io running:" + str(started))
            log.debug("Docker-io running:" + str(is_running))
            if is_running:
                return _valid(
                    comment='Container {0!r} started.\n'.format(container),
                    changes={name: True})
            else:
                return _invalid(
                    comment=(
                        'Container {0!r} cannot be started\n{1!s}'
                        .format(
                            container,
                            started['out'],
                        )
                    )
                )
        else:
            return _valid(
                comment='Container {0!r} started.\n'.format(container),
                changes={name: True})
