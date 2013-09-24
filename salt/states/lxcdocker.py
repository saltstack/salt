#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Managment of dockers
=====================

Available Functions
-------------------
- built

.. code-block:: yaml

    corp/mysuperdocker_img:
        lxcdocker.build:
            - path: /path/to/dir/container/Dockerfile

- pulled

.. code-block:: yaml

    ubuntu:
      lxcdocker.pulled

- installed

.. code-block:: yaml

    mysuperdocker:
        lxcdocker.installed:
            - hostname: superdocker
            - image: corp/mysuperdocker_img

- absent

.. code-block:: yaml

     mys_old_uperdocker:
        lxcdocker.absent

- run

.. code-block:: yaml

     /finish-install.sh:
         lxcdocker.run:
             - container: mysuperdocker
             - unless: grep -q something /var/log/foo
             - docker_unless: grep -q done /install_log

Note:
The lxcdocker Modules can't be called docker as
it would conflict with the underlying binding modules: docker-py
'''


from salt._compat import string_types


def pulled(name,
           registry_url=None,
           login=None,
           password=None):
    '''
    Pull an image from a docker registry

    name
        Tag of the image

    registry_url
        Url of the repository for image base in dockerfile

    login
        login for repository

    password
        password for repository
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    pull = __salt__['lxcdocker.pull']
    if not pull(name):
        ret['comment'] += 'Image {0} was not fetched.\n'.format(name)
        ret['result'] = False
    else:
        ret['result'] = True
        ret['comment'] = 'Image {0} already exists\n'.format(name)
    return ret


def built(name, path=None,
          registry_url=None, login=None, password=None,
          *args, **kwargs):
    '''
    Build a docker image from a dockerfile or an URL

    You can either:

        - give the url/branch/docker_dir
        - give a path on the file system

    name
        Tag of the image

    path
        URL or path in the filesystem to the dockerfile

    registry_url
        Url of the repository for image base in dockerfile

    login
        login for repository

    password
        password for repository

    '''


def installed(name, hostname=None,
              image=None, path=None,
              registry_url=None, login=None, password=None,
              volumes=None, ports=None, *args, **kwargs):
    '''
    Verify that a docker exists or create it

    You can match by either name or hostname
    You can create it either by specifying :

        - an image
        - an absolute path on the filesystem

    name
        name of the container

    hostname
        hostname (name by default)

    image
        Tag of the image to use

    path
        Path in the filesystem to the dockerfile

    registry_url
        Url of the repository for image base in dockerfile

    login
        login for repository

    password
        password for repository

    volumes
        List of extra volumes to mount inside:

            - volumes:
                - /mnt/data:/data
                - /mnt/data2:/data2

    ports
        ports to expose (mapping of ports definition)::

            - ports:
                - 8080:80
                - 2222:22

    '''
    cid = name
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    if not hostname:
        hostname = cid
    exists = __salt__['lxcdocker.exists']
    create = __salt__['lxcdocker.create']
    already_exists = exists(cid)
    if not already_exists:
        create(**kw)
        ret['comment'] += 'Docker {0} created.\n'.format(cid)
        ret['result'] = True
    else:
        ret['result'] = True
        ret['comment'] = 'Docker {0} already exists\n'.format(
            cid)
    return ret


def absent(name, hostname=None, *args, **kwargs):
    '''
    Container should be absent or will be destroyed

    You can match by either name or hostname

    name
        Container_id or hostname

    '''
    cid = name
    exists = __salt__['lxcdocker.exists']
    rm = __salt__['lxcdocker.remove_container']
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    if not hostname:
        hostname = cid
    exists = exists(cid, hostname)
    if not exists:
        ret['result'] = True
        ret['comment'] = 'Docker {0} does not exists'.format(
            cid)
    else:
        rm(cid, hostname, force=True)
        ret['result'] = True
        ret['comment'] = 'Docker {0} was deleted'.format(
            cid)
    return ret


def run(name,
        cid=None,
        hostname=None,
        stateful=False,
        onlyif=None,
        unless=None,
        docked_onlyif=None,
        docked_unless=None,
        *args, **kwargs):
    '''Run a command in a specific container

    You can match by either name or hostname

    name
        command to run in the docker

    cid
        Container id

    hostname
        hostname

    stateful
        stateful mode

    onlyif
        Only execute cmd if statement on the host return 0

    unless
        Do not execute cmd if statement on the host return 0

    docked_onlyif
        Same as onlyif but executed in the context of the docker

    docked_unless
        Same as unless but executed in the context of the docker

    '''
    if not hostname:
        hostname=cid
    retcode = __salt__['lxcdocker.retcode']
    dretcode = __salt__['cmd.retcode']
    drun = __salt__['lxcdocker.run']
    cmd_kwargs = ''
    if onlyif is not None:
        if not isinstance(onlyif, string_types):
            if not onlyif:
                return {'comment': 'onlyif execution failed',
                        'result': True}
        elif isinstance(onlyif, string_types):
            if retcode(onlyif, **cmd_kwargs) != 0:
                return {'comment': 'onlyif execution failed',
                        'result': True}

    if unless is not None:
        if not isinstance(unless, string_types):
            if unless:
                return {'comment': 'unless execution succeeded',
                        'result': True}
        elif isinstance(unless, string_types):
            if retcode(unless, **cmd_kwargs) == 0:
                return {'comment': 'unless execution succeeded',
                        'result': True}

    if docked_onlyif is not None:
        if not isinstance(docked_onlyif, string_types):
            if not docked_onlyif:
                return {'comment': 'docked_onlyif execution failed',
                        'result': True}
        elif isinstance(docked_onlyif, string_types):
            if drun(docked_onlyif, **cmd_kwargs) != 0:
                return {'comment': 'docked_onlyif execution failed',
                        'result': True}

    if docked_unless is not None:
        if not isinstance(docked_unless, string_types):
            if docked_unless:
                return {'comment': 'docked_unless execution succeeded',
                        'result': True}
        elif isinstance(docked_unless, string_types):
            if drun(docked_unless, **cmd_kwargs) == 0:
                return {'comment': 'docked_unless execution succeeded',
                        'result': True}
    return drun(**cmd_kwargs)
