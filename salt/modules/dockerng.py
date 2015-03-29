# -*- coding: utf-8 -*-
'''
Management of Docker Containers

.. versionadded:: Beryllium


Why Make a Second Docker Module?
--------------------------------

We have received a lot of feedback on our Docker support. In the process of
implementing recommended improvements, it became obvious that major changes
needed to be made to the functions and return data. In the end, a complete
rewrite was done.

The changes being too significant, it was decided that making a separate
execution module and state module (called ``docker-ng``) would be the best
option. This will give users a couple release cycles to modify their scripts,
SLS files, etc. to use the new functionality, rather than forcing users to
change everything immediately.

In the **Carbon** release of Salt (slated for late summer/early fall 2015),
this execution module will take the place of the default Docker execution
module, and backwards-compatible naming will be maintained for a couple
releases after that to allow users time to replace references to ``docker-ng``
with ``docker``.


Installation Prerequisites
--------------------------

This execution module requires docker-py_ version 0.5.0 or newer. It can easily
be installed using :py:func:`pip.install <salt.modules.pip.install>`:

.. code-block:: bash

    salt myminion pip.install docker-py

.. _docker-py: https://pypi.python.org/pypi/docker-py


Authentication
--------------

To push or pull images, credentials must be configured. Because a password must
be used, it is recommended to place this configuration in :ref:`Pillar
<pillar>` data. The configuration schema is as follows:

.. code-block:: yaml

    docker-registries:
      <registry_url>:
        email: <email_address>
        password: <password>
        username: <username>

For example:

.. code-block:: yaml

    docker-registries:
      https://index.docker.io/v1/:
        email: foo@foo.com
        password: s3cr3t
        username: foo

Mulitiple registries can be configured. This can be done in one of two ways.
The first way is to configure each registry under the ``docker-registries``
pillar key.

.. code-block:: yaml

    docker-registries:
      https://index.foo.io/v1/:
        email: foo@foo.com
        password: s3cr3t
        username: foo
      https://index.bar.io/v1/:
        email: foo@foo.com
        password: s3cr3t
        username: foo

The second way is to use separate pillar variables ending in
``-docker-registries``:

.. code-block:: yaml

    foo-docker-registries:
      https://index.foo.io/v1/:
        email: foo@foo.com
        password: s3cr3t
        username: foo

    bar-docker-registries:
      https://index.bar.io/v1/:
        email: foo@foo.com
        password: s3cr3t
        username: foo

Both methods can be combined; any registry configured under
``docker-registries`` or ``*-docker-registries`` will be detected.


Functions
---------

- Information Gathering
    - :py:func:`docker-ng.depends <salt.modules.dockerng.depends>`
    - :py:func:`docker-ng.diff <salt.modules.dockerng.diff>`
    - :py:func:`docker-ng.exists <salt.modules.dockerng.exists>`
    - :py:func:`docker-ng.history <salt.modules.dockerng.history>`
    - :py:func:`docker-ng.images <salt.modules.dockerng.images>`
    - :py:func:`docker-ng.info <salt.modules.dockerng.info>`
    - :py:func:`docker-ng.inspect <salt.modules.dockerng.inspect>`
    - :py:func:`docker-ng.inspect_container <salt.modules.dockerng.inspect_container>`
    - :py:func:`docker-ng.inspect_image <salt.modules.dockerng.inspect_image>`
    - :py:func:`docker-ng.list_containers <salt.modules.dockerng.list_containers>`
    - :py:func:`docker-ng.list_tags <salt.modules.dockerng.list_tags>`
    - :py:func:`docker-ng.logs <salt.modules.dockerng.logs>`
    - :py:func:`docker-ng.pid <salt.modules.dockerng.pid>`
    - :py:func:`docker-ng.port <salt.modules.dockerng.port>`
    - :py:func:`docker-ng.ps <salt.modules.dockerng.ps_>`
    - :py:func:`docker-ng.state <salt.modules.dockerng.state>`
    - :py:func:`docker-ng.search <salt.modules.dockerng.search>`
    - :py:func:`docker-ng.top <salt.modules.dockerng.top>`
    - :py:func:`docker-ng.version <salt.modules.dockerng.version>`
- Container Management
    - :py:func:`docker-ng.create <salt.modules.dockerng.create>`
    - :py:func:`docker-ng.copy_from <salt.modules.dockerng.copy_from>`
    - :py:func:`docker-ng.copy_to <salt.modules.dockerng.copy_to>`
    - :py:func:`docker-ng.export <salt.modules.dockerng.export>`
    - :py:func:`docker-ng.rm <salt.modules.dockerng.rm_>`
- Management of Container State
    - :py:func:`docker-ng.kill <salt.modules.dockerng.kill>`
    - :py:func:`docker-ng.pause <salt.modules.dockerng.pause>`
    - :py:func:`docker-ng.restart <salt.modules.dockerng.restart>`
    - :py:func:`docker-ng.start <salt.modules.dockerng.start>`
    - :py:func:`docker-ng.stop <salt.modules.dockerng.stop>`
    - :py:func:`docker-ng.unpause <salt.modules.dockerng.unpause>`
    - :py:func:`docker-ng.wait <salt.modules.dockerng.wait>`
- Image Management
    - :py:func:`docker-ng.build <salt.modules.dockerng.build>`
    - :py:func:`docker-ng.commit <salt.modules.dockerng.commit>`
    - :py:func:`docker-ng.import <salt.modules.dockerng.import_>`
    - :py:func:`docker-ng.load <salt.modules.dockerng.load>`
    - :py:func:`docker-ng.pull <salt.modules.dockerng.pull>`
    - :py:func:`docker-ng.push <salt.modules.dockerng.push>`
    - :py:func:`docker-ng.rmi <salt.modules.dockerng.rmi>`
    - :py:func:`docker-ng.save <salt.modules.dockerng.save>`
    - :py:func:`docker-ng.stale <salt.modules.dockerng.stale>`
    - :py:func:`docker-ng.tag <salt.modules.dockerng.tag>`

Executing Commands Within a Running Container
---------------------------------------------

Salt will detect the execution driver for the given container, and use the
appropriate interface (either nsenter_ or lxc-attach_) to run a command within
the container.

.. _nsenter: http://man7.org/linux/man-pages/man1/nsenter.1.html
.. _lxc-attach: https://linuxcontainers.org/lxc/manpages/man1/lxc-attach.1.html

This execution module provides functions that shadow those from the :mod:`cmd
<salt.modules.cmdmod>` module. They are as follows:

- :py:func:`docker-ng.retcode <salt.modules.dockerng.retcode>`
- :py:func:`docker-ng.run <salt.modules.dockerng.run>`
- :py:func:`docker-ng.run_all <salt.modules.dockerng.run_all>`
- :py:func:`docker-ng.run_stderr <salt.modules.dockerng.run_stderr>`
- :py:func:`docker-ng.run_stdout <salt.modules.dockerng.run_stdout>`
- :py:func:`docker-ng.script <salt.modules.dockerng.script>`
- :py:func:`docker-ng.script_retcode <salt.modules.dockerng.script_retcode>`


Detailed Function Documentation
-------------------------------
'''

# Import Python Futures
from __future__ import absolute_import

__docformat__ = 'restructuredtext en'

# Import Python libs
import bz2
import copy
import datetime
import fnmatch
import functools
import gzip
import json
import logging
import os
import pipes
import re
import shutil
import string
import sys
import time
import traceback
import types
import warnings

# Import Salt libs
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.utils.decorators \
    import identical_signature_wrapper as _mimic_signature
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six
# pylint: disable=import-error
from salt.ext.six.moves import range  # pylint: disable=no-name-in-module,redefined-builtin

try:
    import docker
    HAS_DOCKER = True
except ImportError:
    HAS_DOCKER = False

try:
    py_version = sys.version_info[0]
    if py_version == 2:
        import backports.lzma as lzma
    else:
        import lzma
    HAS_LZMA = True
except ImportError:
    HAS_LZMA = False
# pylint: enable=import-error

HAS_NSENTER = bool(salt.utils.which('nsenter'))

# Set up logging
log = logging.getLogger(__name__)

# Don't shadow built-in's.
__func_alias__ = {
    'import_': 'import',
    'ps_': 'ps',
    'rm_': 'rm',
    'tag_': 'tag',
}

# Default as of docker-py 1.1.0
CLIENT_TIMEOUT = 60
NOTSET = object()

# Define the module's virtual name
__virtualname__ = 'docker-ng'


def __virtual__():
    '''
    Only load if docker libs are present
    '''
    if HAS_DOCKER:
        return __virtualname__
    return False


#Decorators
class _api_version(object):  # pylint: disable=C0103
    def __init__(self, api_version):
        self.api_version = api_version

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            _get_client()
            current_api_version = __context__['docker.client'].api_version
            if float(current_api_version) < self.api_version:
                raise CommandExecutionError(
                    'This function requires a Docker API version of at least '
                    '{0}. API version in use is {1}.'
                    .format(self.api_version, current_api_version)
                )
            return func(*args, **salt.utils.clean_kwargs(**kwargs))
        return _mimic_signature(func, wrapper)


def _docker_client(wrapped):
    '''
    Decorator to run a function that requires the use of a docker.Client()
    instance.
    '''
    @functools.wraps(wrapped)
    def wrapper(*args, **kwargs):
        client_timeout = __context__.get('docker.timeout', CLIENT_TIMEOUT)
        _get_client(timeout=client_timeout)
        return wrapped(*args, **salt.utils.clean_kwargs(**kwargs))
    return wrapper


def _ensure_exists(wrapped):
    '''
    Decorator to ensure that the named container exists.
    '''
    @functools.wraps(wrapped)
    def wrapper(name, *args, **kwargs):
        if not exists(name):
            raise CommandExecutionError(
                'Container \'{0}\' does not exist'.format(name)
            )
        return wrapped(name, *args, **salt.utils.clean_kwargs(**kwargs))
    return wrapper


# Helper functions
def _cache_file(source):
    '''
    Grab a file from the Salt fileserver
    '''
    try:
        # Don't just use cp.cache_file for this. Docker has its own code to
        # pull down images from the web.
        if source.startswith('salt://'):
            cached_source = __salt__['cp.cache_file'](source)
            if not cached_source:
                raise CommandExecutionError(
                    'Unable to cache {0}'.format(source)
                )
            return cached_source
    except AttributeError:
        raise SaltInvocationError('Invalid source file {0}'.format(source))
    return source


def _change_state(name, action, expected, *args, **kwargs):
    '''
    Change the state of a container
    '''
    pre = state(name)
    if action != 'restart' and pre == expected:
        return {'result': False,
                'state': {'old': expected, 'new': expected},
                'comment': ('Container \'{0}\' already {1}'
                            .format(name, expected))}
    response = _client_wrapper(action, name, *args, **kwargs)
    _clear_context()
    try:
        post = state(name)
    except CommandExecutionError:
        # Container doesn't exist anymore
        post = None
    ret = {'result': post == expected,
           'state': {'old': pre, 'new': post}}
    if action == 'wait':
        ret['exit_status'] = response
    return ret


def _clear_context():
    '''
    Clear the state/exists values stored in context
    '''
    # Can't use 'for key in __context__' or six.iterkeys(__context__) because
    # an exception will be raised if the size of the dict is modified during
    # iteration.
    for key in __context__.keys():
        try:
            if key.startswith('docker.') and key != 'docker.client':
                __context__.pop(key)
        except AttributeError:
            pass


def _get_client(timeout=None):
    '''
    Obtains a connection to a docker API (socket or URL) based on config.get
    mechanism (pillar -> grains)

    By default it will use the base docker-py defaults which
    at the time of writing are using the local socket and
    the 1.4 API

    Set those keys in your configuration tree somehow:

        - docker.url: URL to the docker service
        - docker.version: API version to use
    '''
    if 'docker.client' not in __context__:
        client_kwargs = {}
        for key, val in (('base_url', 'docker.url'),
                        ('version', 'docker.version')):
            param = __salt__['config.get'](val, NOTSET)
            if param is not NOTSET:
                client_kwargs[key] = param

        if 'base_url' not in client_kwargs and 'DOCKER_HOST' in os.environ:
            # Check if the DOCKER_HOST environment variable has been set
            client_kwargs['base_url'] = os.environ.get('DOCKER_HOST')

        __context__['docker.client'] = docker.Client(**client_kwargs)

    # Set a new timeout if one was passed
    if timeout is not None and __context__['docker.client'].timeout != timeout:
        __context__['docker.client'].timeout == timeout


def _get_md5(name, path):
    '''
    Get the MD5 checksum of a file from a container
    '''
    output = run_stdout(name,
                        'md5sum {0}'.format(pipes.quote(path)),
                        ignore_retcode=True)
    try:
        return output.split()[0]
    except IndexError:
        # Destination file does not exist or could not be accessed
        return None


def _get_method():
    '''
    Get the method to be used in shell commands
    '''
    # For old version of docker. lxc was the only supported driver.
    # This is a sane default.
    driver = info().get('ExecutionDriver', 'lxc-')
    if driver.startswith('lxc-'):
        return 'lxc-attach'
    elif driver.startswith('native-') and HAS_NSENTER:
        return 'nsenter'
    else:
        raise NotImplementedError(
            'Unknown docker ExecutionDriver \'{0}\', or didn\'t find command '
            'to attach to the container'.format(driver))


def _get_repo_tag(tag, default_tag='latest'):
    '''
    Resolves the docker repo:tag notation and returns repo name and tag
    '''
    if ':' in tag:
        r_name, r_tag = tag.rsplit(':', 1)
        if not r_tag:
            # Would happen if some wiseguy requests a tag ending in a colon
            # (e.g. 'somerepo:')
            log.warning(
                'Assuming tag \'{0}\' for repo \'{1}\''
                .format(default_tag, tag)
            )
            r_tag = default_tag
    else:
        r_name = tag
        r_tag = default_tag
    return r_name, r_tag


def _get_top_level_images(imagedata, subset=None):
    '''
    Returns a list of the top-level images (those which are not parents). If
    ``subset`` (an iterable) is passed, the top-level images in the subset will
    be returned, otherwise all top-level images will be returned.
    '''
    try:
        parents = [imagedata[x]['ParentId'] for x in imagedata]
        filter_ = subset if subset is not None else imagedata
        return [x for x in filter_ if x not in parents]
    except (KeyError, TypeError):
        raise CommandExecutionError(
            'Invalid image data passed to _get_top_level_images(). Please '
            'report this issue. Full image data: {0}'.format(imagedata)
        )


def _size_fmt(num):
    '''
    Format bytes as human-readable file sizes
    '''
    try:
        num = int(num)
        if num < 1024:
            return '{0} bytes'.format(num)
        num /= 1024.0
        for unit in ('KiB', 'MiB', 'GiB', 'TiB', 'PiB'):
            if num < 1024.0:
                return '{0:3.1f} {1}'.format(num, unit)
            num /= 1024.0
    except Exception as exc:
        log.error('Unable to format file size for \'{0}\''.format(num))
        return 'unknown'


@_docker_client
def _client_wrapper(attr, *args, **kwargs):
    '''
    Common functionality for getting information from a container
    '''
    catch_api_errors = kwargs.pop('catch_api_errors', True)
    func = getattr(__context__['docker.client'], attr)
    if func is None:
        raise SaltInvocationError('Invalid client action \'{0}\''.format(attr))
    err = ''
    try:
        return func(*args, **kwargs)
    except docker.errors.APIError as exc:
        if catch_api_errors:
            # Generic handling of Docker API errors
            raise CommandExecutionError(
                'Error {0}: {1}'.format(exc.response.status_code,
                                        exc.explanation)
            )
        else:
            # Allow API errors to be caught further up the stack
            raise
    except Exception as exc:
        err = '{0}'.format(exc)
    msg = 'Unable to perform {0}'.format(attr)
    if err:
        msg += ': {0}'.format(err)
    raise CommandExecutionError(msg)


@_docker_client
def _image_wrapper(attr, *args, **kwargs):
    '''
    Wrapper to run a docker-py function and return a list of dictionaries
    '''
    catch_api_errors = kwargs.pop('catch_api_errors', True)

    if kwargs.pop('client_auth', False):
        # Set credentials
        registry_auth_config = __pillar__.get('docker-registries', {})
        for key, data in six.iteritems(__pillar__):
            if key.endswith('-docker-registries'):
                registry_auth_config.update(data)

        err = (
            '{0} Docker credentials{1}. Please see the docker-ng remote '
            'execution module documentation for information on how to '
            'configure authentication.'
        )
        if not registry_auth_config:
            raise SaltInvocationError(err.format('Missing', ''))
        try:
            for registry, creds in six.iteritems(registry_auth_config):
                __context__['docker.client'].login(
                    creds['username'],
                    password=creds['password'],
                    email=creds.get('email'),
                    registry=registry)
        except KeyError:
            raise SaltInvocationError(
                err.format('Incomplete', ' for registry {0}'.format(registry))
            )
        client_timeout = kwargs.pop('client_timeout', None)
        if client_timeout is not None:
            __context__['docker.client'].timeout = client_timeout

    func = getattr(__context__['docker.client'], attr)
    if func is None:
        raise SaltInvocationError('Invalid client action \'{0}\''.format(attr))
    ret = []
    try:
        output = func(*args, **kwargs)
        if not kwargs.get('stream', False):
            output = output.splitlines()
        for line in output:
            ret.append(json.loads(line))
    except docker.errors.APIError as exc:
        if catch_api_errors:
            # Generic handling of Docker API errors
            raise CommandExecutionError(
                'Error {0}: {1}'.format(exc.response.status_code,
                                        exc.explanation)
            )
        else:
            # Allow API errors to be caught further up the stack
            raise
    except Exception as exc:
        raise CommandExecutionError(
            'Error occurred performing docker {0}: {1}'.format(attr, exc)
        )

    return ret


def _build_status(data, item):
    '''
    Process a status update from a docker build, updating the data structure
    '''
    stream = item['stream']
    if 'Running in' in stream:
        data.setdefault('Intermediate_Containers', []).append(
            stream.rstrip().split()[-1])
    if 'Successfully built' in stream:
        data['Id'] = stream.rstrip().split()[-1]


def _import_status(data, item, repo_name, repo_tag):
    '''
    Process a status update from docker import, updating the data structure
    '''
    status = item['status']
    try:
        if 'Downloading from' in status:
            return
        elif all(x in string.hexdigits for x in status):
            # Status is an image ID
            data['Image'] = '{0}:{1}'.format(repo_name, repo_tag)
            data['Id'] = status
    except (AttributeError, TypeError):
        pass


def _pull_status(data, item):
    '''
    Process a status update from a docker pull, updating the data structure
    '''
    status = item['status']
    if status == 'Already exists':
        # Layer already exists
        already_pulled = data.setdefault('Layers', {}).setdefault(
            'Already_Pulled', [])
        already_pulled.append(item['id'])
    elif status == 'Pull complete':
        # Pulled a new layer
        pulled = data.setdefault('Layers', {}).setdefault(
            'Pulled', [])
        pulled.append(item['id'])
    elif status.startswith('Status: '):
        data['Status'] = status[8:]


def _push_status(data, item):
    '''
    Process a status update from a docker push, updating the data structure
    '''
    status = item['status']
    if 'id' in item:
        if 'already pushed' in status:
            # Layer already exists
            already_pushed = data.setdefault('Layers', {}).setdefault(
                'Already_Pushed', [])
            already_pushed.append(item['id'])
        elif 'successfully pushed' in status:
            # Pushed a new layer
            pushed = data.setdefault('Layers', {}).setdefault(
                'Pushed', [])
            pushed.append(item['id'])
    else:
        try:
            image_id = re.match(
                r'Pushing tags? for rev \[([0-9a-f]+)',
                status
            ).group(1)
        except AttributeError:
            return
        else:
            data['Id'] = image_id


def _error_detail(data, item):
    '''
    Process an API error, updating the data structure
    '''
    err = item['errorDetail']
    if 'code' in err:
        msg = '{1}: {2}'.format(
            item['errorDetail']['code'],
            item['errorDetail']['message'],
        )
    else:
        msg = item['errorDetail']['message']
    data.append(msg)


# Functions for information gathering
def depends(name):
    '''
    Returns the containers and images, if any, which depend on the given image

    name
        Name or ID of image


    **RETURN DATA**

    A dictionary containing the following keys:

    - ``Containers`` - A list of containers which depend on the specified image
    - ``Images`` - A list of IDs of images which depend on the specified image


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.depends myimage
        salt myminion docker-ng.depends 0123456789ab
    '''
    # Resolve tag or short-SHA to full SHA
    image_id = inspect_image(name)['Id']

    container_depends = []
    for container in six.itervalues(ps_(all=True, verbose=True)):
        if container['Info']['Image'] == image_id:
            container_depends.extend(
                [x.lstrip('/') for x in container['Names']]
            )

    return {
        'Containers': container_depends,
        'Images': [x[:12] for x, y in six.iteritems(images(all=True))
                   if y['ParentId'] == image_id]
    }


@_ensure_exists
def diff(name):
    '''
    Get information on changes made to container's filesystem since it was
    created. This is equivalent to running ``docker diff``.

    name
        Container name or ID


    **RETURN DATA**

    A dictionary containing any of the following keys:

    - ``Added`` - A list of paths that were added.
    - ``Changed`` - A list of paths that were changed.
    - ``Deleted`` - A list of paths that were deleted.

    These keys will only be present if there were changes, so if the container
    has no differences the return dict will be empty.


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.diff mycontainer
    '''
    changes = _client_wrapper('diff', name)
    kind_map = {0: 'Changed', 1: 'Added', 2: 'Deleted'}
    ret = {}
    for change in changes:
        key = kind_map.get(change['Kind'], 'Unknown')
        ret.setdefault(key, []).append(change['Path'])
    if 'Unknown' in ret:
        log.error(
            'Unknown changes detected in docker.diff of container {0}. '
            'This is probably due to a change in the Docker API. Please '
            'report this to the SaltStack developers'.format(name)
        )
    return ret


def exists(name):
    '''
    Check if a given container exists

    name
        Container name or ID


    **RETURN DATA**

    A boolean (``True`` if the container exists, otherwise ``False``)


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.exists mycontainer
    '''
    contextkey = 'docker.exists.{0}'.format(name)
    if contextkey in __context__:
        return __context__[contextkey]
    try:
        _client_wrapper('inspect_container', name, catch_api_errors=False)
    except docker.errors.APIError:
        __context__[contextkey] = False
    else:
        __context__[contextkey] = True
    return __context__[contextkey]


def history(name, quiet=False):
    '''
    Return the history for an image. Equivalent to running ``docker history``.

    name
        Container name or ID

    quiet : False
        If ``True``, the return data will simply be a list of the commands run to
        build the container.

        .. code-block:: bash

            stuff goes here


    **RETURN DATA**

    If ``quiet=False``, the return value will be a list of dictionaries
    containing information about each step taken to build the image. The keys
    in each step include the following:

    - ``Command`` - The command executed in this build step
    - ``Id`` - Layer ID
    - ``Size`` - Cumulative image size, in bytes
    - ``Size_Human`` - Cumulative image size, in human-readable units
    - ``Tags`` - Tag(s) assigned to this layer
    - ``Time_Created_Epoch`` - Time this build step was completed (Epoch
      time)
    - ``Time_Created_Local`` - Time this build step was completed (Minion's
      local timezone)


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.exists mycontainer
    '''
    response = _client_wrapper('history', name)
    key_map = {
        'CreatedBy': 'Command',
        'Created': 'Time_Created_Epoch',
    }
    command_prefix = re.compile(r'^/bin/sh -c (?:#\(nop\) )?')
    ret = []
    # history is most-recent first, reverse this so it is ordered top-down
    for item in reversed(response):
        step = {}
        for key, val in six.iteritems(item):
            step_key = key_map.get(key, key)
            if step_key == 'Command':
                if not val:
                    # We assume that an empty build step is 'FROM scratch'
                    val = 'FROM scratch'
                else:
                    val = command_prefix.sub('', val)
            step[step_key] = val
        if 'Time_Created_Epoch' in step:
            step['Time_Created_Local'] = \
                time.strftime(
                    '%Y-%m-%d %H:%M:%S %Z',
                    time.localtime(step['Time_Created_Epoch'])
                )
        for param in ('Size',):
            if param in step:
                step['{0}_Human'.format(param)] = _size_fmt(step[param])
        ret.append(copy.deepcopy(step))
    if quiet:
        return [x.get('Command') for x in ret]
    return ret


def images(verbose=False, **kwargs):
    '''
    Returns information about the Docker images on the Minion. Similar to
    running ``docker images``.

    all : False
        If ``True``, untagged images will also be returned

    verbose : False
        If ``True``, a ``docker inspect`` will be run on each image returned.


    **RETURN DATA**

    A dictionary with each key being an image ID, and each value some general
    info about that image (time created, size, tags associated with the image,
    etc.)


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.images
        salt myminion docker-ng.images all=True
    '''
    if 'docker.images' not in __context__:
        response = _client_wrapper('images', all=kwargs.get('all', False))
        key_map = {
            'Created': 'Time_Created_Epoch',
        }
        for img in response:
            img_id = img.pop('Id', None)
            if img_id is None:
                continue
            for item in img:
                img_state = 'untagged' \
                    if img['RepoTags'] == ['<none>:<none>'] \
                    else 'tagged'
                bucket = __context__.setdefault('docker.images', {})
                bucket = bucket.setdefault(img_state, {})
                img_key = key_map.get(item, item)
                bucket.setdefault(img_id, {})[img_key] = img[item]
            if 'Time_Created_Epoch' in bucket.get(img_id, {}):
                bucket[img_id]['Time_Created_Local'] = \
                    time.strftime(
                        '%Y-%m-%d %H:%M:%S %Z',
                        time.localtime(bucket[img_id]['Time_Created_Epoch'])
                    )
            for param in ('Size', 'VirtualSize'):
                if param in bucket.get(img_id, {}):
                    bucket[img_id]['{0}_Human'.format(param)] = \
                        _size_fmt(bucket[img_id][param])

    context_data = __context__.get('docker.images', {})
    ret = copy.deepcopy(context_data.get('tagged', {}))
    if kwargs.get('all', False):
        ret.update(copy.deepcopy(context_data.get('untagged', {})))

    # If verbose info was requested, go get it
    if verbose:
        for img_id in ret:
            ret[img_id]['Info'] = inspect_image(img_id)

    return ret


@_docker_client
def info():
    '''
    Returns a dictionary of system-wide information. Equivalent to running
    ``docker info``.

    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.info
    '''
    return _client_wrapper('info')


def inspect(name):
    '''
    This is a generic container/image inspecton function. It will first attempt
    to get container information for the passed name/ID using
    :py:func:`docker.inspect_container
    <salt.modules.dockerng.inspect_container>`, and then will try to get image
    information for the passed name/ID using :py:func:`docker.inspect_image
    <salt.modules.dockerng.inspect_image>`. If it is already known that the
    name/ID is an image, it is slightly more efficient to use
    :py:func:`docker.inspect_image <salt.modules.dockerng.inspect_image>`.

    name
        Container/image name or ID


    **RETURN DATA**

    A dictionary of container/image information


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.inspect mycontainer
        salt myminion docker-ng.inspect busybox
    '''
    try:
        return inspect_container(name)
    except CommandExecutionError as exc:
        if 'does not exist' not in exc.strerror:
            raise
    try:
        return inspect_image(name)
    except CommandExecutionError as exc:
        if not exc.strerror.startswith('Error 404'):
            raise
    raise CommandExecutionError(
        'Error 404: No such image/container: {0}'.format(name)
    )


@_ensure_exists
def inspect_container(name):
    '''
    Retrieves container information. This is equivalent to running ``docker
    inspect``, but will only look for container information.

    name
        Container name or ID


    **RETURN DATA**

    A dictionary of container information


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.inspect_container mycontainer
        salt myminion docker-ng.inspect_container 0123456789ab
    '''
    return _client_wrapper('inspect_container', name)


def inspect_image(name):
    '''
    Retrieves image information. This is equivalent to running ``docker
    inspect``, but will only look for image information.

    name
        Image name or ID


    **RETURN DATA**

    A dictionary of image information


    CLI Examples:

    .. code-block:: bash

        salt myminion docker-ng.inspect_image busybox
        salt myminion docker-ng.inspect_image centos:6
        salt myminion docker-ng.inspect_image 0123456789ab
    '''
    ret = _client_wrapper('inspect_image', name)
    for param in ('Size', 'VirtualSize'):
        if param in ret:
            ret['{0}_Human'.format(param)] = _size_fmt(ret[param])
    return ret


def list_containers(**kwargs):
    '''
    Returns a list of containers by name. This is different from
    :py:func:`docker-ng.ps <salt.modules.dockerng.ps_>` in that
    :py:func:`docker-ng.ps <salt.modules.dockerng.ps_>` returns its results
    organized by container ID.

    all : False
        If ``True``, stopped containers will be included in return data

    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.inspect_image <image>
    '''
    ret = set()
    for item in six.itervalues(ps_(all=kwargs.get('all', False))):
        for c_name in [x.lstrip('/') for x in item.get('Names', [])]:
            ret.add(c_name)
    return sorted(ret)


def list_tags():
    '''
    Returns a list of tagged images

    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.list_tags
    '''
    ret = set()
    for item in six.itervalues(images()):
        for repo_tag in item['RepoTags']:
            ret.add(repo_tag)
    return sorted(ret)


def logs(name):
    '''
    Returns the logs for the container. This is equivalent to running ``docker
    logs``.

    name
        Container name or ID

    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.logs mycontainer
    '''
    return _client_wrapper('logs', name)


@_ensure_exists
def pid(name):
    '''
    Returns the PID of a container

    name
        Container name or ID

    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.pid mycontainer
        salt myminion docker-ng.pid 0123456789ab
    '''
    return inspect_container(name)['State']['Pid']


@_ensure_exists
def port(name, private_port=None):
    '''
    Returns port mapping information for a given container. This is eqivalent
    to running ``docker port``.

    name
        Container name or ID

    private_port : None
        If specified, get information for that specific port. Can be specified
        either as a port number (i.e. ``5000``), or as a port number plus the
        protocol (i.e. ``5000/udp``).

        If this argument is omitted, all port mappings will be returned.


    **RETURN DATA**

    A dictionary of port mappings, with the keys being the port and the values
    being the mapping(s) for that port.


    CLI Examples:

    .. code-block:: bash

        salt myminion docker-ng.port mycontainer
        salt myminion docker-ng.port mycontainer 5000
        salt myminion docker-ng.port mycontainer 5000/udp
    '''
    # docker.client.Client.port() doesn't do what we need, so just inspect the
    # container and get the information from there. It's what they're already
    # doing (poorly) anyway.
    mappings = inspect_container(name).get('NetworkSettings', {}).get(
        'Ports', {})
    if not mappings:
        return {}

    if private_port is None:
        pattern = '*'
    else:
        # Sanity checks
        if isinstance(private_port, six.integer_types):
            pattern = '{0}/*'.format(private_port)
        else:
            err = (
                'Invalid private_port \'{0}\'. Must either be a port number, '
                'or be in port/protocol notation (e.g. 5000/tcp)'
                .format(private_port)
            )
            try:
                port_num, _, protocol = private_port.partition('/')
                protocol = protocol.lower()
                if not all(x in string.digits for x in port_num) \
                        or protocol not in ('tcp', 'udp'):
                    raise SaltInvocatonError(err)
                pattern = port_num + '/' + protocol
            except AttributeError:
                raise SaltInvocatonError(err)

    return dict((x, mappings[x]) for x in fnmatch.filter(mappings, pattern))


def ps_(**kwargs):
    '''
    Returns information about the Docker containers on the Minion. Equivalent
    to running ``docker ps``.

    all : False
        If ``True``, stopped containers will also be returned

    verbose : False
        If ``True``, a ``docker inspect`` will be run on each container
        returned.


    **RETURN DATA**

    A dictionary with each key being an container ID, and each value some
    general info about that container (time created, name, command, etc.)


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.ps
        salt myminion docker-ng.ps all=True
    '''
    if 'docker.ps' not in __context__:
        response = _client_wrapper('containers', all=True)
        key_map = {
            'Created': 'Time_Created_Epoch',
        }
        for container in response:
            c_id = container.pop('Id', None)
            if c_id is None:
                continue
            for item in container:
                c_state = 'running' \
                    if container['Status'].lower().startswith('up ') \
                    else 'stopped'
                bucket = __context__.setdefault('docker.ps', {}).setdefault(
                    c_state, {})
                c_key = key_map.get(item, item)
                bucket.setdefault(c_id, {})[c_key] = container[item]
            if 'Time_Created_Epoch' in bucket.get(c_id, {}):
                bucket[c_id]['Time_Created_Local'] = \
                    time.strftime(
                        '%Y-%m-%d %H:%M:%S %Z',
                        time.localtime(bucket[c_id]['Time_Created_Epoch'])
                    )

    context_data = __context__.get('docker.ps', {})
    ret = copy.deepcopy(context_data.get('running', {}))
    if kwargs.get('all', False):
        ret.update(copy.deepcopy(context_data.get('stopped', {})))

    # If verbose info was requested, go get it
    if kwargs.get('verbose', False):
        for c_id in ret:
            ret[c_id]['Info'] = inspect_container(c_id)

    return ret


@_ensure_exists
def state(name):
    '''
    Returns the state of the container

    name
        Container name or ID


    **RETURN DATA**

    A string representing the current state of the container (either
    ``running``, ``paused``, or ``stopped``)


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.state mycontainer
    '''
    contextkey = 'docker.state.{0}'.format(name)
    if contextkey in __context__:
        return __context__[contextkey]
    c_info = inspect_container(name)
    if c_info.get('State', {}).get('Paused', False):
        __context__[contextkey] = 'paused'
    elif c_info.get('State', {}).get('Running', False):
        __context__[contextkey] = 'running'
    else:
        __context__[contextkey] = 'stopped'
    return __context__[contextkey]


def search(name, official=False, trusted=False):
    '''
    Searches the registry for an image

    name
        Search keyword

    official : False
        Limit results to official builds

    trusted : False
        Limit results to `trusted builds`_

    .. _`trusted builds`: https://blog.docker.com/2013/11/introducing-trusted-builds/


    **RETURN DATA**

    A dictionary with each key being the name of an image, and the following
    information for each image:

    - ``Description`` - Image description
    - ``Official`` - A boolean (``True`` if an official build, ``False`` if
      not)
    - ``Stars`` - Number of stars the image has on the registry
    - ``Trusted`` - A boolean (``True`` if a trusted build, ``False`` if not)


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.search centos
        salt myminion docker-ng.search centos official=True
    '''
    response = _client_wrapper('search', name)
    if not response:
        raise CommandExecutionError(
            'No images matched the search string \'{0}\''.format(name)
        )

    key_map = {
        'description': 'Description',
        'is_official': 'Official',
        'is_trusted': 'Trusted',
        'star_count': 'Stars'
    }
    limit = []
    if official:
        limit.append('Official')
    if trusted:
        limit.append('Trusted')

    results = {}
    for item in response:
        c_name = item.pop('name', None)
        if c_name is not None:
            for key in item:
                mapped_key = key_map.get(key, key)
                results.setdefault(c_name, {})[mapped_key] = item[key]

    if not limit:
        return results

    ret = {}
    for key, val in six.iteritems(results):
        for item in limit:
            if val.get(item, False):
                ret[key] = val
                break
    return ret


@_ensure_exists
def top(name):
    '''
    Runs the `docker top` command on a specific container

    name
        Container name or ID

    CLI Example:


    **RETURN DATA**

    A list of dictionaries containing information about each process


    .. code-block:: bash

        salt myminion docker-ng.top mycontainer
        salt myminion docker-ng.top 0123456789ab
    '''
    response = _client_wrapper('top', name)

    # Read in column names
    columns = {}
    for idx, col_name in enumerate(response['Titles']):
        columns[idx] = col_name

    # Build return dict
    ret = []
    for process in response['Processes']:
        cur_proc = {}
        for idx, val in enumerate(process):
            cur_proc[columns[idx]] = val
        ret.append(cur_proc)
    return ret


def version():
    '''
    Returns a dictionary of Docker version information. Equivlent to running
    ``docker version``.

    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.version
    '''
    return _client_wrapper('version')


# Functions to manage containers
def create(image,
           command=None,
           name=None,
           hostname=None,
           interactive=False,
           tty=False,
           user=None,
           detach=True,
           mem_limit=0,
           ports=None,
           environment=None,
           dns=None,
           volumes=None,
           cpu_shares=None,
           cpuset=None,
           client_timeout=CLIENT_TIMEOUT,
           **kwargs):
    '''
    Create a new container

    image
        Image from which to create the container

    command
        Command to run in the container

    name
        Name for the new container. If not provided, Docker will randomly
        generate one for you.

    hostname
        Hostname of the container. If not provided, and if a ``name`` has been
        provided, the ``hostname`` will default to the ``name`` that was
        passed.

    interactive : False
        Leave stdin open

    tty : False
        Attach TTYs

    detach : False
        Run container in daemon mode

    user
        User under which to run docker

    environment
        Environment variable mapping (ex. ``{'foo': 'BAR'}``)

    ports
        Port redirections (ex. ``{'222': {}}``)

    volumes : None
        List of volumes to expose. Using this option will create a data volume
        container. Can be passed as either a comma-separated string or a python
        list.

    cpu_shares
        CPU shares (relative weight)

    cpuset
        CPUs on which which to allow execution ('0-3' or '0,1')

    client_timeout
        Timeout in seconds for the Docker client. This is not a timeout for
        this function, but for receiving a response from the API.

        .. note::

            This is only used if Salt needs to pull the requested image.


    **RETURN DATA**

    A dictionary containing the following keys:

    - ``Id`` - ID of the newly-created container
    - ``Name`` - Name of the newly-created container


    CLI Example:

    .. code-block:: bash

        # Create a data-only container
        salt myminion docker-ng.create myuser/mycontainer volumes="/mnt/vol1,/mnt/vol2"
        # Create a CentOS 7 container that will stay running once started
        salt myminion docker-ng.create centos:7 name=mycent7 interactive=True tty=True command=bash
    '''
    if isinstance(volumes, six.string_types):
        volumes = ','.split(volumes)
    try:
        # Try to inspect the image, if it fails then we know we need to pull it
        # first.
        inspect_image(image)
    except Exception:
        pull(image, client_timeout=client_timeout)

    if hostname is None and name is not None:
        hostname = name

    time_started = time.time()
    response = _client_wrapper(
        'create_container',
        image=image,
        command=command,
        hostname=hostname,
        user=user,
        detach=detach,
        stdin_open=interactive,
        tty=tty,
        mem_limit=mem_limit,
        ports=ports,
        environment=environment,
        dns=dns,
        volumes=volumes,
        name=name,
        cpu_shares=cpu_shares,
        cpuset=cpuset
    )
    ret = {'Time_Elapsed': time.time() - time_started}
    _clear_context()

    if name is None:
        name = inspect_container(response['Id'])['Name'].lstrip('/')
    response['Name'] = name
    return response


@_ensure_exists
def copy_from(name, source, dest, overwrite=False, makedirs=False):
    '''
    Copy a file from inside a container to the Minion

    name
        Container name

    source
        Path of the file on the container's filesystem

    dest
        Destination on the Minion. Must be an absolute path. If the destination
        is a directory, the file will be copied into that directory.

    overwrite : False
        Unless this option is set to ``True``, then if a file exists at the
        location specified by the ``dest`` argument, an error will be raised.

    makedirs : False
        Create the parent directory on the container if it does not already
        exist.


    **RETURN DATA**

    A boolean (``True`` if successful, otherwise ``False``)


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.copy_from mycontainer /var/log/nginx/access.log /home/myuser
    '''
    c_state = state(name)
    if c_state != 'running':
        raise CommandExecutionError(
            'Container \'{0}\' is not running'.format(name)
        )

    source_dir, source_name = os.path.split(source)

    # Destination file sanity checks
    if not os.path.isabs(dest):
        raise SaltInvocationError('Destination path must be absolute')
    if os.path.isdir(dest):
        # Destination is a directory, full path to dest file will include the
        # basename of the source file.
        dest = os.path.join(dest, source_name)
        dest_dir = dest
    else:
        # Destination was not a directory. We will check to see if the parent
        # dir is a directory, and then (if makedirs=True) attempt to create the
        # parent directory.
        dest_dir, dest_name = os.path.split(dest)
        if not os.path.isdir(dest_dir):
            if makedirs:
                try:
                    os.makedirs(parent_dir)
                except OSError as exc:
                    raise CommandExecutionError(
                        'Unable to make destination directory {0}: {1}'
                        .format(parent_dir, exc)
                    )
            else:
                raise SaltInvocationError(
                    'Directory {0} does not exist'.format(dest_dir)
                )
    if not overwrite and os.path.exists(dest):
        raise CommandExecutionError(
            'Destination path {0} already exists. Use overwrite=True to '
            'overwrite it'.format(dest)
        )

    # Source file sanity checks
    if not os.path.isabs(source):
        raise SaltInvocationError('Source path must be absolute')
    else:
        if retcode(name,
                   'test -e {0}'.format(pipes.quote(source)),
                   ignore_retcode=True) == 0:
            if retcode(name,
                       'test -f {0}'.format(pipes.quote(source)),
                       ignore_retcode=True) != 0:
                raise SaltInvocationError('Source must be a regular file')
        else:
            raise SaltInvocationError(
                'Source file {0} does not exist'.format(source)
            )

    # Before we try to replace the file, compare checksums.
    source_md5 = _get_md5(name, source)
    if source_md5 == __salt__['file.get_sum'](dest, 'md5'):
        log.debug('{0}:{1} and {2} are the same file, skipping copy'
                  .format(name, source, dest))
        return True

    log.debug('Copying {0} from container \'{1}\' to local path {2}'
              .format(source, name, dest))

    cmd = ['docker', 'cp', '{0}:{1}'.format(name, source), dest_dir]
    __salt__['cmd.run'](cmd, python_shell=False)
    return source_md5 == __salt__['file.get_sum'](dest, 'md5')


# Docker cp gets a file from the container, alias this to copy_from
cp = copy_from


@_ensure_exists
def copy_to(name, source, dest, overwrite=False, makedirs=False):
    '''
    Copy a file from the host into a container

    name
        Container name

    source
        File to be copied to the container

    dest
        Destination on the container. Must be an absolute path. If the
        destination is a directory, the file will be copied into that
        directory.

    overwrite : False
        Unless this option is set to ``True``, then if a file exists at the
        location specified by the ``dest`` argument, an error will be raised.

    makedirs : False
        Create the parent directory on the container if it does not already
        exist.


    **RETURN DATA**

    A boolean (``True`` if successful, otherwise ``False``)


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.copy_to mycontainer /tmp/foo /root/foo
    '''
    return __salt__['container_resource.copy_to'](
        name,
        _cache_file(source),
        dest,
        container_type=__virtualname__,
        exec_method=_get_method(),
        makedirs=makedirs)


@_ensure_exists
def export(name,
           path,
           overwrite=False,
           makedirs=False,
           compression=None,
           **kwargs):
    '''
    Exports a container to a tar archive. It can also optionally compress that
    tar archive, and push it up to the Master.

    name
        Container name or ID

    path
        Absolute path on the Minion where the container will be exported

    overwrite : False
        Unless this option is set to ``True``, then if a file exists at the
        location specified by the ``path`` argument, an error will be raised.

    makedirs : False
        If ``True``, then if the parent directory of the file specified by the
        ``path`` argument does not exist, Salt will attempt to create it.

    compression : None
        Can be set to any of the following:

        - ``gzip`` or ``gz`` for gzip compression
        - ``bzip2`` or ``bz2`` for bzip2 compression
        - ``xz`` or ``lzma`` for XZ compression (requires `xz-utils`_, as well
          as the ``lzma`` module from Python 3.3, available in Python 2 and
          Python 3.0-3.2 as `backports.lzma`_)

        This parameter can be omitted and Salt will attempt to determine the
        compression type by examining the filename passed in the ``path``
        parameter.

        .. _`xz-utils`: http://tukaani.org/xz/
        .. _`backports.lzma`: https://pypi.python.org/pypi/backports.lzma

    push : False
        If ``True``, the container will be pushed to the master using
        :py:func:`cp.push <salt.modules.cp.push>`.

        .. note::

            This requires :conf_master:`file_recv` to be set to ``True`` on the
            Master.


    **RETURN DATA**

    A dictionary will containing the following keys:

    - ``Path`` - Path of the file that was exported
    - ``Push`` - Reports whether or not the file was successfully pushed to the
      Master

      *(Only present if push=True)*
    - ``Size`` - Size of the file, in bytes
    - ``Size_Human`` - Size of the file, in human-readable units
    - ``Time_Elapsed`` - Time in seconds taken to perform the export


    CLI Examples:

    .. code-block:: bash

        salt myminion docker-ng.export mycontainer /tmp/mycontainer.tar
        salt myminion docker-ng.export mycontainer /tmp/mycontainer.tar.xz push=True
    '''
    err = 'Path \'{0}\' is not absolute'.format(path)
    try:
        if not os.path.isabs(path):
            raise SaltInvocationError(err)
    except AttributeError:
        raise SaltInvocationError(err)

    if os.path.exists(path) and not overwrite:
        raise CommandExecutionError('{0} already exists'.format(path))

    if compression is None:
        if path.endswith('.tar.gz') or path.endswith('.tgz'):
            compression = 'gzip'
        elif path.endswith('.tar.bz2') or path.endswith('.tbz2'):
            compression = 'bzip2'
        elif path.endswith('.tar.xz') or path.endswith('.txz'):
            if HAS_LZMA:
                compression = 'xz'
            else:
                raise CommandExecutionError(
                    'XZ compression unavailable. Install the backports.lzma '
                    'module and xz-utils to enable XZ compression.'
                )
    elif compression == 'gz':
        compression = 'gzip'
    elif compression == 'bz2':
        compression = 'bzip2'
    elif compression == 'lzma':
        compression = 'xz'

    if compression and compression not in ('gzip', 'bzip2', 'xz'):
        raise SaltInvocationError(
            'Invalid compression type \'{0}\''.format(compression)
        )

    parent_dir = os.path.dirname(path)
    if not os.path.isdir(parent_dir):
        if not makedirs:
            raise CommandExecutionError(
                'Parent dir {0} of destination path does not exist. Use '
                'makedirs=True to create it.'.format(parent_dir)
            )
        try:
            os.makedirs(parent_dir)
        except OSError as exc:
            raise CommandExecutionError(
                'Unable to make parent dir {0}: {1}'
                .format(parent_dir, exc)
            )

    if compression == 'gzip':
        try:
            out = gzip.open(path, 'wb')
        except OSError as exc:
            raise CommandExecutionError(
                'Unable to open {0} for writing: {1}'.format(path, exc)
            )
    elif compression == 'bzip2':
        compressor = bz2.BZ2Compressor()
    elif compression == 'xz':
        compressor = lzma.LZMACompressor()

    time_started = time.time()
    try:
        if compression != 'gzip':
            # gzip doesn't use a Compressor object, it uses a .open() method to
            # open the filehandle. If not using gzip, we need to open the
            # filehandle here.
            out = salt.utils.fopen(path, 'wb')
        response = _client_wrapper('export', name)
        buf = None
        while buf != '':
            buf = response.read(4096)
            if buf:
                if compression in ('bzip2', 'xz'):
                    data = compressor.compress(buf)
                    if data:
                        out.write(data)
                else:
                    out.write(buf)
        if compression in ('bzip2', 'xz'):
            # Flush any remaining data out of the compressor
            data = compressor.flush()
            if data:
                out.write(data)
        out.flush()
    except Exception as exc:
        try:
            os.remove(path)
        except OSError:
            pass
        raise CommandExecutionError(
            'Error occurred during container export: {0}'.format(exc)
        )
    finally:
        out.close()
    ret = {'Time_Elapsed': time.time() - time_started}

    ret['Path'] = path
    ret['Size'] = os.stat(path).st_size
    ret['Size_Human'] = _size_fmt(ret['Size'])

    # Process push
    if kwargs.get(push, False):
        ret['Push'] = __salt__['cp.push'](path)

    return ret


@_ensure_exists
def rm_(name, force=False, volumes=False):
    '''
    Removes a container

    name
        Container name or ID

    force : False
        If ``True``, the container will be killed first before removal, as the
        Docker API will not permit a running container to be removed. This
        option is set to ``False`` by default to prevent accidental removal of
        a running container.

    volumes : False
        Also remove volumes associated with container


    **RETURN DATA**

    A list of the IDs of containers which were removed


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.rm mycontainer
        salt myminion docker-ng.rm mycontainer force=True
    '''
    if state(name) == 'running' and not force:
        raise CommandExecutionError(
            'Container \'{0}\' is running, use force=True to forcibly '
            'remove this container'.format(name)
        )
    pre = ps_(all=True)
    _client_wrapper('remove_container', name, v=volumes, force=force)
    _clear_context()
    return [x for x in pre if x not in ps_(all=True)]


# Functions to manage images
def build(path=None,
          tag=None,
          cache=True,
          rm=True,
          api_response=False,
          fileobj=None):
    '''
    Builds a docker image from a Dockerfile or a URL

    path
        Path to directory on the Minion containing the Dockerfile

    tag
        Image to be built, in ``repo:tag`` notation. If just the repository
        name is passed, a tag name of ``latest`` will be assumed.

    cache : True
        Set to ``False`` to force the build process not to use the Docker image
        cache, and pull all required intermediate image layers

    rm : True
        Remove intermediate containers created during build

    api_response : False
        If ``True``: an ``API_Response`` key will be present in the return
        data, containing the raw output from the Docker API.

    fileobj
        Allows for a file-like object containing the contents of the Dockerfile
        to be passed in place of a file ``path`` argument. This argument should
        not be used from the CLI, only from other Salt code.


    **RETURN DATA**

    A dictionary containing one or more of the following keys:

    - ``Id`` - ID of the newly-built image
    - ``Time_Elapsed`` - Time in seconds taken to perform the build
    - ``Intermediate_Containers`` - IDs of containers created during the course
      of the build process

      *(Only present if rm=False)*
    - ``Layers`` - A dictionary containing one or more of the following keys:
        - ``Already_Pulled`` - Layers that that were already present on the
          Minion
        - ``Pulled`` - Layers that that were pulled

      *(Only present if the image specified by the "tag" argument was not
      present on the Minion, or if cache=False)*
    - ``Status`` - A string containing a summary of the pull action (usually a
      message saying that an image was downloaded, or that it was up to date).

      *(Only present if the image specified by the "tag" argument was not
      present on the Minion, or if cache=False)*


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.build vieux/apache
        salt myminion docker-ng.build github.com/creack/docker-firefox
    '''
    time_started = time.time()
    response = _client_wrapper('build',
                               path=path,
                               tag=tag,
                               quiet=False,
                               fileobj=fileobj,
                               rm=rm,
                               nocache=not cache)
    ret = {'Time_Elapsed': time.time() - time_started}

    if not response:
        raise CommandExecutionError(
            'Import failed for {0}, no response returned from Docker API'
            .format(tag)
        )
    elif api_response:
        ret['API_Response'] = response

    errors = []
    # Iterate through API response and collect information
    for item in response:
        item_type = next(iter(item))
        if item_type == 'status':
            _pull_status(ret, item)
        if item_type == 'stream':
            _build_status(ret, item)
        elif item_type == 'errorDetail':
            _error_detail(errors, item)

    if 'Id' not in ret:
        # API returned information, but there was no confirmation of a
        # successful build.
        msg = 'Build failed for {0}'.format(tag)
        if errors:
            msg += '. Error(s) follow:\n\n{0}'.format(
                '\n\n'.join(errors)
            )
        raise CommandExecutionError(msg)

    if rm:
        ret.pop('Intermediate_Containers', None)
    return ret


def commit(name,
           tag,
           message=None,
           author=None):
    '''
    Commits a container, thereby promoting it to an image. This is equivalent
    to running a ``docker commit``.

    name
        Container name or ID to commit

    tag
        Image to be committed, in ``repo:tag`` notation. If just the repository
        name is passed, a tag name of ``latest`` will be assumed.

    message
        Commit message (Optional)

    author
        Author name (Optional)


    **RETURN DATA**

    A dictionary containing the following keys:

    - ``Id`` - ID of the newly-created image
    - ``Image`` - Name of the newly-created image
    - ``Time_Elapsed`` - Time in seconds taken to perform the commit


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.commit mycontainer myuser/myimage
        salt myminion docker-ng.commit mycontainer myuser/myimage:mytag
    '''
    repo_name, repo_tag = _get_repo_tag(tag)
    time_started = time.time()
    response = _client_wrapper(
        'commit',
        name,
        repository=repo_name,
        tag=repo_tag,
        message=message,
        author=author)
    ret = {'Time_Elapsed': time.time() - time_started}
    _clear_context()

    image_id = None
    for id_ in ('Id', 'id', 'ID'):
        if id_ in response:
            image_id = response[id_]
            break

    if image_id is None:
        raise CommandExecutionError('No image ID was returned in API response')

    ret['Image'] = tag
    ret['Id'] = image_id
    return ret


def import_(source,
            tag,
            api_response=False):
    '''
    Imports content from a local tarball or a URL as a new docker image

    source
        Content to import (URL or absolute path to a tarball).  URL can be a
        file on the Salt fileserver (i.e.
        ``salt://path/to/rootfs/tarball.tar.xz``. To import a file from a
        saltenv other than ``base`` (e.g. ``dev``), pass it at the end of the
        URL (ex. ``salt://path/to/rootfs/tarball.tar.xz?saltenv=dev``).

    tag
        Image to be created by the import, in ``repo:tag`` notation. If just
        the repository name is passed, a tag name of ``latest`` will be
        assumed.

    api_response : False
        If ``True`` an ``api_response`` key will be present in the return data,
        containing the raw output from the Docker API.


    **RETURN DATA**

    A dictionary containing the following keys:

    - ``Id`` - ID of the newly-created image
    - ``Image`` - Name of the newly-created image
    - ``Time_Elapsed`` - Time in seconds taken to perform the commit


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.import /tmp/cent7-minimal.tar.xz myuser/centos
        salt myminion docker-ng.import /tmp/cent7-minimal.tar.xz myuser/centos:7
        salt myminion docker-ng.import salt://dockerimages/cent7-minimal.tar.xz myuser/centos:7
    '''
    repo_name, repo_tag = _get_repo_tag(tag)
    path = _cache_file(source)

    time_started = time.time()
    response = _image_wrapper('import_image',
                              path,
                              repository=repo_name,
                              tag=repo_tag)
    ret = {'Time_Elapsed': time.time() - time_started}
    _clear_context()

    if not response:
        raise CommandExecutionError(
            'Import failed for {0}, no response returned from Docker API'
            .format(source)
        )
    elif api_response:
        ret['API_Response'] = response

    errors = []
    # Iterate through API response and collect information
    for item in response:
        item_type = next(iter(item))
        if item_type == 'status':
            _import_status(ret, item, repo_name, repo_tag)
        elif item_type == 'errorDetail':
            _error_detail(errors, item)

    if 'Id' not in ret:
        # API returned information, but there was no confirmation of a
        # successful push.
        msg = 'Import failed for {0}'.format(source)
        if errors:
            msg += '. Error(s) follow:\n\n{0}'.format(
                '\n\n'.join(errors)
            )
        raise CommandExecutionError(msg)

    return ret


def load(path, tag=None):
    '''
    Load a tar archive that was created using :py:func:`docker-ng.save
    <salt.modules.dockerng.save>` (or via the Docker CLI using ``docker
    save``).

    path
        Path to docker tar archive. Path can be a file on the Minion, or the
        URL of a file on the Salt fileserver (i.e.
        ``salt://path/to/docker/saved/image.tar``). To load a file from a
        saltenv other than ``base`` (e.g. ``dev``), pass it at the end of the
        URL (ex. ``salt://path/to/rootfs/tarball.tar.xz?saltenv=dev``).

    tag : None
        If specified, the topmost layer of the newly-loaded image will be
        tagged with the specified repo and tag using :py:func:`docker-ng.tag
        <salt.modules.dockerng.tag_>`.


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``Path`` - Path of the file that was saved
    - ``Layers`` - A list containing the IDs of the layers which were loaded.
      Any layers in the file that was loaded, which were already present on the
      Minion, will not be included.
    - ``Tag`` - Name of tag applied to topmost layer

      *(Only present if tag was specified and tagging was successful)*
    - ``Time_Elapsed`` - Time in seconds taken to load the file
    - ``Warning`` - Message describing any problems encountered in attemp to
      tag the topmost layer

      *(Only present if tag was specified and tagging failed)*


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.load /path/to/image.tar
        salt myminion docker-ng.load salt://path/to/docker/saved/image.tar tag=myuser/myimage:mytag
    '''
    local_path = _cache_file(path)
    if not os.path.isfile(local_path):
        raise CommandExecutionError(
            'Source file {0} does not exist'.format(local_path)
        )

    pre = images(all=True)
    cmd = ['docker', 'load', '-i', local_path]
    time_started = time.time()
    result = __salt__['cmd.run_all'](cmd)
    ret = {'Time_Elapsed': time.time() - time_started}
    _clear_context()
    post = images(all=True)
    if result['retcode'] != 0:
        msg = 'Failed to load image(s) from {0}'.format(path)
        if result['stderr']:
            msg += ': {0}'.format(result['stderr'])
        raise CommandExecutionError(msg)
    ret['Path'] = path

    new_layers = [x for x in post if x not in pre]
    ret['Layers'] = [x[:12] for x in new_layers]
    top_level_images = _get_top_level_images(all_images, subset=new_layers)
    if len(top_level_images) > 1:
        ret['Warning'] = ('More than one top-level image layer was loaded '
                          '({0}), no image was tagged'
                          .format(', '.join(top_level_images)))
    else:
        try:
            result = tag_(top_level_images[0], tag=tag_as)
            ret['Tag'] = tag
        except IndexError:
            ret['Warning'] = ('No top-level image layers were loaded, no '
                              'image was tagged')
        except Exception as exc:
            ret['Warning'] = ('Failed to tag {0} as {1}: {2}'
                              .format(top_level_images[0], tag_as, exc))
    return ret


def layers(name):
    '''
    Returns a list of the IDs of layers belonging to the specified image, with
    the top-most layer (the one correspnding to the passed name) appearing
    last.

    name
        Image name or ID

    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.layers centos:7
    '''
    ret = []
    cmd = ['docker', 'history', '-q', name]
    for line in reversed(
            __salt__['cmd.run_stdout'](cmd, python_shell=False).splitlines()):
        ret.append(line)
    if not ret:
        raise CommandExecutionError('Image \'{0}\' not found'.format(name))
    return ret


def pull(tag,
         insecure_registry=False,
         api_response=False,
         client_timeout=CLIENT_TIMEOUT):
    '''
    Pulls an image from a Docker registry. See the documentation at the top of
    this page to configure authenticated access.

    tag
        Image to be pulled, in ``repo:tag`` notation. If just the repository
        name is passed, a tag name of ``latest`` will be assumed.

    insecure_registry : False
        If ``True``, the Docker client will permit the use of insecure
        (non-HTTPS) registries.

    api_response : False
        If ``True``, an ``API_Response`` key will be present in the return
        data, containing the raw output from the Docker API.

        .. note::

            This may result in a **lot** of additional return data, especially
            for larger images.

    client_timeout
        Timeout in seconds for the Docker client. This is not a timeout for
        this function, but for receiving a response from the API.


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``Layers`` - A dictionary containing one or more of the following keys:
        - ``Already_Pulled`` - Layers that that were already present on the
          Minion
        - ``Pulled`` - Layers that that were pulled
    - ``Status`` - A string containing a summary of the pull action (usually a
      message saying that an image was downloaded, or that it was up to date).
    - ``Time_Elapsed`` - Time in seconds taken to perform the pull


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.pull centos
        salt myminion docker-ng.pull centos:6
    '''
    repo_name, repo_tag = _get_repo_tag(tag)
    kwargs = {'tag': repo_tag,
              'stream': True,
              'client_auth': True,
              'client_timeout': client_timeout}
    if insecure_registry:
        kwargs['insecure_registry'] = insecure_registry

    time_started = time.time()
    response = _image_wrapper('pull', repo_name, **kwargs)
    ret = {'Time_Elapsed': time.time() - time_started}
    _clear_context()

    if not response:
        raise CommandExecutionError(
            'Pull failed for {0}, no response returned from Docker API'
            .format(tag)
        )
    elif api_response:
        ret['API_Response'] = response

    errors = []
    # Iterate through API response and collect information
    for item in response:
        item_type = next(iter(item))
        if item_type == 'status':
            _pull_status(ret, item)
        elif item_type == 'errorDetail':
            _error_detail(errors, item)

    try:
        inspect_image('{0}'.format(tag))
    except Exception:
        # API returned information, but the image can't be found
        msg = 'Pull failed for {0}'.format(tag)
        if errors:
            msg += '. Error(s) follow:\n\n{0}'.format(
                '\n\n'.join(errors)
            )
        raise CommandExecutionError(msg)

    return ret


def push(tag,
         insecure_registry=False,
         api_response=False,
         client_timeout=CLIENT_TIMEOUT):
    '''
    Pushes an image to a Docker registry. See the documentation at top of this
    page to configure authenticated access.

    tag
        Image to be pushed, in ``repo:tag`` notation. If just the repository
        name is passed, a tag name of ``latest`` will be assumed.

    insecure_registry : False
        If ``True``, the Docker client will permit the use of insecure
        (non-HTTPS) registries.

    api_response : False
        If ``True``, an ``API_Response`` key will be present in the return
        data, containing the raw output from the Docker API.

    client_timeout
        Timeout in seconds for the Docker client. This is not a timeout for
        this function, but for receiving a response from the API.


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``Id`` - ID of the image that was pushed
    - ``Image`` - Name of the image that was pushed
    - ``Layers`` - A dictionary containing one or more of the following keys:
        - ``Already_Pushed`` - Layers that that were already present on the
          Minion
        - ``Pushed`` - Layers that that were pushed
    - ``Time_Elapsed`` - Time in seconds taken to perform the push


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.push myuser/mycontainer
        salt myminion docker-ng.push myuser/mycontainer:mytag
    '''
    repo_name, repo_tag = _get_repo_tag(tag)
    kwargs = {'tag': repo_tag,
              'stream': True,
              'client_auth': True,
              'client_timeout': client_timeout}
    if insecure_registry:
        kwargs['insecure_registry'] = insecure_registry

    time_started = time.time()
    response = _image_wrapper('push', repo_name, **kwargs)
    ret = {'Time_Elapsed': time.time() - time_started}
    _clear_context()

    if not response:
        raise CommandExecutionError(
            'Push failed for {0}, no response returned from Docker API'
            .format(tag)
        )
    elif api_response:
        ret['API_Response'] = response

    errors = []
    # Iterate through API response and collect information
    for item in response:
        item_type = next(iter(item))
        if item_type == 'status':
            _push_status(ret, item)
        elif item_type == 'errorDetail':
            _error_detail(errors, item)

    if 'Id' not in ret:
        # API returned information, but there was no confirmation of a
        # successful push.
        msg = 'Push failed for {0}'.format(tag)
        if errors:
            msg += '. Error(s) follow:\n\n{0}'.format(
                '\n\n'.join(errors)
            )
        raise CommandExecutionError(msg)

    ret['Image'] = '{0}:{1}'.format(repo_name, repo_tag)
    return ret


def rmi(name, force=False, prune=True):
    '''
    Removes an image

    name
        Tag or ID of image

    force : False
        If ``True``, the image will be removed even if the Minion has
        containers created from that image

    prune : True
        If ``True``, untagged parent image layers will be removed as well, set
        this to ``False`` to keep them.


    **RETURN DATA**

    A dictionary will be returned, containing the following two keys:

    - ``Tags`` - A list of the tags that were removed
    - ``Images`` - A list of the IDs of image layers that were removed


    CLI Examples:

    .. code-block:: bash

        salt myminion docker-ng.rmi busybox
        salt myminion docker-ng.rmi busybox force=True
    '''
    image_id = inspect_image(name)['Id']
    pre_images = images(all=True)
    pre_tags = list_tags()
    try:
        _client_wrapper('remove_image',
                        image_id,
                        force=force,
                        noprune=not prune,
                        catch_api_errors=False)
        _clear_context()
    except docker.errors.APIError as exc:
        if exc.response.status_code == 409:
            err = ('Unable to remove image {0} because it is in use by '
                   .format(name))
            deps = depends(name)
            if deps['Containers']:
                err += 'container(s): {0}'.format(
                    ', '.join(deps['Containers'])
                )
            if deps['Images']:
                if deps['Containers']:
                    err += ' and '
                err += 'image(s): {0}'.format(', '.join(deps['Images']))
            raise CommandExecutionError(err)
        else:
            raise CommandExecutionError(
                'Error {0}: {1}'.format(exc.response.status_code,
                                        exc.explanation)
            )
    return {'Images': [x for x in pre_images if x not in images(all=True)],
            'Tags': [x for x in pre_tags if x not in list_tags()]}


def save(image_id,
         path,
         overwrite=False,
         makedirs=False,
         compression=None,
         **kwargs):
    '''
    Saves an image and to a file on the minion using
    ``docker save``. More than one image can be specified, space-delimited,
    followed by the destination file. Additional options are as follows:

    image_id
        Image ID

    path
        Absolute path on the Minion where the image will be exported

    overwrite : False
        Unless this option is set to ``True``, then if the destination file
        exists an error will be raised.

    makedirs : False
        If ``True``, then if the parent directory of the file specified by the
        ``path`` argument does not exist, Salt will attempt to create it.

    compression : None
        Can be set to any of the following:

        - ``gzip`` or ``gz`` for gzip compression
        - ``bzip2`` or ``bz2`` for bzip2 compression
        - ``xz`` or ``lzma`` for XZ compression (requires `xz-utils`_, as well
          as the ``lzma`` module from Python 3.3, available in Python 2 and
          Python 3.0-3.2 as `backports.lzma`_)

        This parameter can be omitted and Salt will attempt to determine the
        compression type by examining the filename passed in the ``path``
        parameter.

        .. note::
            Since the Docker API does not support ``docker save``, compression
            will be a bit slower with this function than with
            :py:func:`docker.export <salt.modules.dockerng.export>` since the
            image(s) will first be saved and then the compression done
            afterwards.

        .. _`xz-utils`: http://tukaani.org/xz/
        .. _`backports.lzma`: https://pypi.python.org/pypi/backports.lzma

    push : False
        If ``True``, the container will be pushed to the master using
        :py:func:`cp.push <salt.modules.cp.push>`.

        .. note::

            This requires :conf_master:`file_recv` to be set to ``True`` on the
            Master.


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``Path`` - Path of the file that was saved
    - ``Push`` - Reports whether or not the file was successfully pushed to the
      Master

      *(Only present if push=True)*
    - ``Size`` - Size of the file, in bytes
    - ``Size_Human`` - Size of the file, in human-readable units
    - ``Time_Elapsed`` - Time in seconds taken to perform the save


    CLI Examples:

    .. code-block:: bash

        salt myminion docker-ng.save centos:7 /tmp/cent7.tar
        salt myminion docker-ng.save 0123456789ab cdef01234567 /tmp/saved.tar
    '''
    err = 'Path \'{0}\' is not absolute'.format(path)
    try:
        if not os.path.isabs(path):
            raise SaltInvocationError(err)
    except AttributeError:
        raise SaltInvocationError(err)

    if os.path.exists(path) and not kwargs.get('overwrite', False):
        raise CommandExecutionError('{0} already exists'.format(path))

    compression = kwargs.get('compression')
    if compression is None:
        if path.endswith('.tar.gz') or path.endswith('.tgz'):
            compression = 'gzip'
        elif path.endswith('.tar.bz2') or path.endswith('.tbz2'):
            compression = 'bzip2'
        elif path.endswith('.tar.xz') or path.endswith('.txz'):
            if HAS_LZMA:
                compression = 'xz'
            else:
                raise CommandExecutionError(
                    'XZ compression unavailable. Install the backports.lzma '
                    'module and xz-utils to enable XZ compression.'
                )
    elif compression == 'gz':
        compression = 'gzip'
    elif compression == 'bz2':
        compression = 'bzip2'
    elif compression == 'lzma':
        compression = 'xz'

    if compression and compression not in ('gzip', 'bzip2', 'xz'):
        raise SaltInvocationError(
            'Invalid compression type \'{0}\''.format(compression)
        )

    parent_dir = os.path.dirname(path)
    if not os.path.isdir(parent_dir):
        if not kwargs.get('makedirs', False):
            raise CommandExecutionError(
                'Parent dir \'{0}\' of destination path does not exist. Use '
                'makedirs=True to create it.'.format(parent_dir)
            )

    if compression:
        saved_path = salt.utils.mkstemp()
    else:
        saved_path = path

    cmd = ['docker', 'save', '-o', saved_path, inspect_image(name)['Id']]
    time_started = time.time()
    result = __salt__['cmd.run_all'](cmd, python_shell=False)
    if result['retcode'] != 0:
        err = 'Failed to save image(s) to {0}'.format(path)
        if result['stderr']:
            err += ': {0}'.format(result['stderr'])
        raise CommandExecutionError(err)

    if compression:
        if compression == 'gzip':
            try:
                out = gzip.open(path, 'wb')
            except OSError as exc:
                raise CommandExecutionError(
                    'Unable to open {0} for writing: {1}'.format(path, exc)
                )
        elif compression == 'bzip2':
            compressor = bz2.BZ2Compressor()
        elif compression == 'xz':
            compressor = lzma.LZMACompressor()

        try:
            with salt.utils.fopen(saved_path, 'rb') as uncompressed:
                if compression != 'gzip':
                    # gzip doesn't use a Compressor object, it uses a .open()
                    # method to open the filehandle. If not using gzip, we need to
                    # open the filehandle here.
                    out = salt.utils.fopen(path, 'wb')
                buf = None
                while buf != '':
                    buf = uncompressed.read(4096)
                    if buf:
                        if compression in ('bzip2', 'xz'):
                            data = compressor.compress(buf)
                            if data:
                                out.write(data)
                        else:
                            out.write(buf)
                if compression in ('bzip2', 'xz'):
                    # Flush any remaining data out of the compressor
                    data = compressor.flush()
                    if data:
                        out.write(data)
                out.flush()
        except Exception as exc:
            try:
                os.remove(path)
            except OSError:
                pass
            raise CommandExecutionError(
                'Error occurred during image save: {0}'.format(exc)
            )
        finally:
            try:
                # Clean up temp file
                os.remove(saved_path)
            except OSError:
                pass
            out.close()
    ret = {'Time_Elapsed': time.time() - time_started}

    ret['Path'] = path
    ret['Size'] = os.stat(path).st_size
    ret['Size_Human'] = _size_fmt(ret['Size'])

    # Process push
    if kwargs.get(push, False):
        ret['Push'] = __salt__['cp.push'](path)

    return ret


def stale(prune=False, force=False):
    '''
    Return images which were once tagged but were later untagged, such as those
    superseded by committing a new copy of an existing tagged image. These are
    the images that show up as ``<none>:<none>`` in the output from ``docker
    images`` without the ``-a`` argument.

    prune : False
        Remove these images

    force : False
        If ``True``, and if ``prune=True``, then forcibly remove these images.

    **RETURN DATA**

    A dictionary with each key being the ID of the stale image, and the
    following information for each image:

    - ``Comment`` - Any error encountered when trying to prune a stale image

      *(Only present if prune=True and prune failed)*
    - ``Image`` - Name of the stale image
    - ``Removed`` - A boolean (``True`` if prune was successful, ``False`` if
      not)

      *(Only present if prune=True)*


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.stale
        salt myminion docker-ng.stale prune=True
    '''
    all_images = images(all=True)
    stale_images = [x[:12] for x in _get_top_level_images(all_images)
                    if '<none>:<none>' in all_images[x]['RepoTags']]
    ret = {}
    for image in stale_images:
        old_image = inspect_image(image)['ContainerConfig']['Image']
        ret.setdefault(image, {})['Image'] = old_image
        if prune:
            try:
                ret[image]['Removed'] = rmi(image, force=force)
            except Exception as exc:
                err = '{0}'.format(exc)
                log.error(err)
                ret[image]['Comment'] = err
                ret[image]['Removed'] = False
    return ret


def tag_(name, tag, force=False):
    '''
    Tag an image into a repository and return ``True``. If the tag was
    unsuccessful, an error will be raised.

    name
        ID of image

    tag
        Tag to apply to the image, in ``repo:tag`` notation. If just the
        repository name is passed, a tag name of ``latest`` will be assumed.

    force : False
        Force apply tag

    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.tag 0123456789ab myrepo/mycontainer
        salt myminion docker-ng.tag 0123456789ab myrepo/mycontainer:mytag
    '''
    image_id = inspect_image(image)['Id']
    repo_name, repo_tag = _get_repo_tag(tag)
    response = _client_wrapper('tag',
                               image_id,
                               repo_name,
                               tag=repo_tag,
                               force=force)
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response


# Functions to manage container state
@_ensure_exists
def kill(name):
    '''
    Kill all processes in a running container instead of performing a graceful
    shutdown

    name
        Container name or ID


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``comment`` - Only present if the container cannot be killed


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.kill mycontainer
    '''
    return _change_state(name, 'kill', 'stopped')


@_api_version(1.12)
@_ensure_exists
def pause(name):
    '''
    Pauses a container

    name
        Container name or ID


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``comment`` - Only present if the container cannot be paused


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.pause mycontainer
    '''
    orig_state = state(name)
    if orig_state == 'stopped':
        return {'result': False,
                'state': {'old': orig_state, 'new': orig_state},
                'comment': ('Container \'{0}\' is stopped, cannot pause'
                            .format(name))}
    return _change_state(name, 'pause', 'paused')

freeze = pause


@_ensure_exists
def restart(name, timeout=10):
    '''
    Restarts a container

    name
        Container name or ID

    timeout : 10
        Timeout in seconds after which the container will be killed (if it has
        not yet gracefully shut down)


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``restarted`` - If restart was successful, this key will be present and
      will be set to ``True``.


    CLI Examples:

    .. code-block:: bash

        salt myminion docker-ng.restart mycontainer
        salt myminion docker-ng.restart mycontainer timeout=20
    '''
    ret = _change_state(name, 'restart', 'running', timeout=timeout)
    if ret['result']:
        ret['restarted'] = True
    return ret


@_ensure_exists
def start(name,
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
    Start a container

    Name
        Container name or ID


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``comment`` - Only present if the container cannot be started


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.start mycontainer
    '''
    orig_state = state(name)
    if orig_state == 'paused':
        return {'result': False,
                'state': {'old': orig_state, 'new': orig_state},
                'comment': ('Container \'{0}\' is paused, cannot start'
                            .format(name))}
    if not binds:
        binds = {}

    if not isinstance(binds, dict):
        raise SaltInvocationError('binds must be formatted as a dictionary')

    bindings = None
    if port_bindings is not None:
        try:
            bindings = {}
            for key, val in six.iteritems(port_bindings):
                bindings[key] = (val.get('HostIp', ''), val['HostPort'])
        except AttributeError:
            raise SaltInvocationError(
                'port_bindings must be formatted as a dictionary of '
                'dictionaries'
            )

    return _change_state(name, 'start', 'running',
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


@_ensure_exists
def stop(name, unpause=False, timeout=10):
    '''
    Stops a running container

    name
        Container name or ID

    unpause : False
        If ``True`` and the container is paused, it will be unpaused before
        attempting to stop the container.

    timeout : 10
        Timeout in seconds after which the container will be killed (if it has
        not yet gracefully shut down)


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``comment`` - Only present if the container can not be stopped


    CLI Examples:

    .. code-block:: bash

        salt myminion docker-ng.stop mycontainer
        salt myminion docker-ng.stop mycontainer unpause=True
        salt myminion docker-ng.stop mycontainer timeout=20
    '''
    orig_state = state(name)
    if orig_state == 'paused':
        if unpause:
            unpause_result = _change_state(name, 'unpause', 'running')
            if unpause_result['result'] is False:
                unpause_result['comment'] = (
                    'Failed to unpause container \'{0}\''.format(name)
                )
                return unpause_result
        else:
            return {'result': False,
                    'state': {'old': orig_state, 'new': orig_state},
                    'comment': ('Container \'{0}\' is paused, run with '
                                'unpause=True to unpause before stopping'
                                .format(name))}
    ret = _change_state(name, 'stop', 'stopped', timeout=timeout)
    ret['state']['old'] = orig_state
    return ret


@_api_version(1.12)
@_ensure_exists
def unpause(name):
    '''
    Unpauses a container

    name
        Container name or ID


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``comment`` - Only present if the container can not be unpaused


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.pause mycontainer
    '''
    orig_state = state(name)
    if orig_state == 'stopped':
        return {'result': False,
                'state': {'old': orig_state, 'new': orig_state},
                'comment': ('Container \'{0}\' is stopped, cannot unpause'
                            .format(name))}
    return _change_state(name, 'unpause', 'running')

unfreeze = unpause


def wait(name):
    '''
    Wait for the container to exit gracefully, and return its exit code

    .. note::

        This function will block until the container is stopped.

    name
        Container name or ID


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``exit_status`` - Exit status for the container
    - ``comment`` - Only present if the container is already stopped


    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.wait mycontainer
    '''
    return _change_state(name, 'wait', 'stopped')


# Functions to run commands inside containers
@_ensure_exists
def _run(name,
         cmd,
         output=None,
         stdin=None,
         python_shell=True,
         output_loglevel='debug',
         ignore_retcode=False,
         use_vt=False,
         keep_env=None):
    '''
    Common logic for docker.run functions
    '''
    ret = __salt__['container_resource.run'](
        name,
        cmd,
        container_type=__virtualname__,
        exec_method=_get_method(),
        output=output,
        stdin=stdin,
        python_shell=python_shell,
        output_loglevel=output_loglevel,
        ignore_retcode=ignore_retcode,
        use_vt=use_vt,
        keep_env=keep_env)

    if output in (None, 'all'):
        return ret
    else:
        return ret[output]


def _script(name,
            source,
            saltenv='base',
            args=None,
            template=None,
            stdin=None,
            python_shell=True,
            output_loglevel='debug',
            ignore_retcode=False,
            use_vt=False,
            keep_env=None):
    '''
    Common logic to run a script on a container
    '''
    def _cleanup_tempfile(path):
        try:
            os.remove(path)
        except (IOError, OSError) as exc:
            log.error('cmd.script: Unable to clean tempfile {0!r}: {1}'
                      .format(path, exc))

    path = salt.utils.mkstemp(dir='/tmp',
                              prefix='salt',
                              suffix=os.path.splitext(source)[1])
    if template:
        fn_ = __salt__['cp.get_template'](source, path, template, saltenv)
        if not fn_:
            _cleanup_tempfile(path)
            return {'pid': 0,
                    'retcode': 1,
                    'stdout': '',
                    'stderr': '',
                    'cache_error': True}
    else:
        fn_ = __salt__['cp.cache_file'](source, saltenv)
        if not fn_:
            _cleanup_tempfile(path)
            return {'pid': 0,
                    'retcode': 1,
                    'stdout': '',
                    'stderr': '',
                    'cache_error': True}
        shutil.copyfile(fn_, path)

    copy_to(name, path, path)
    run(name, 'chmod 700 ' + path)
    ret = run_all(
        name,
        path + ' ' + str(args) if args else path,
        stdin=stdin,
        python_shell=python_shell,
        output_loglevel=output_loglevel,
        ignore_retcode=ignore_retcode,
        use_vt=use_vt,
        keep_env=keep_env)
    _cleanup_tempfile(path)
    run(name, 'rm ' + path)
    return ret


def retcode(name,
            cmd,
            stdin=None,
            python_shell=True,
            output_loglevel='debug',
            use_vt=False,
            ignore_retcode=False,
            keep_env=None):
    '''
    Run :py:func:`cmd.retcode <salt.modules.cmdmod.retcode>` within a container

    name
        Container name or ID in which to run the command

    cmd
        Command to run

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.

    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.retcode mycontainer 'ls -l /etc'
    '''
    return _run(name,
                cmd,
                output='retcode',
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def run(name,
        cmd,
        stdin=None,
        python_shell=True,
        output_loglevel='debug',
        use_vt=False,
        ignore_retcode=False,
        keep_env=None):
    '''
    Run :py:func:`cmd.run <salt.modules.cmdmod.run>` within a container

    name
        Container name or ID in which to run the command

    cmd
        Command to run

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.

    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.run mycontainer 'ls -l /etc'
    '''
    return _run(name,
                cmd,
                output=None,
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def run_all(name,
            cmd,
            stdin=None,
            python_shell=True,
            output_loglevel='debug',
            use_vt=False,
            ignore_retcode=False,
            keep_env=None):
    '''
    Run :py:func:`cmd.run_all <salt.modules.cmdmod.run_all>` within a container

    name
        Container name or ID in which to run the command

    cmd
        Command to run

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.

    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.run_all mycontainer 'ls -l /etc'
    '''
    return _run(name,
                cmd,
                output='all',
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def run_stderr(name,
               cmd,
               stdin=None,
               python_shell=True,
               output_loglevel='debug',
               use_vt=False,
               ignore_retcode=False,
               keep_env=None):
    '''
    Run :py:func:`cmd.run_stderr <salt.modules.cmdmod.run_stderr>` within a
    container

    name
        Container name or ID in which to run the command

    cmd
        Command to run

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.

    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.run_stderr mycontainer 'ls -l /etc'
    '''
    return _run(name,
                cmd,
                output='stderr',
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def run_stdout(name,
               cmd,
               stdin=None,
               python_shell=True,
               output_loglevel='debug',
               use_vt=False,
               ignore_retcode=False,
               keep_env=None):
    '''
    Run :py:func:`cmd.run_stdout <salt.modules.cmdmod.run_stdout>` within a
    container

    name
        Container name or ID in which to run the command

    cmd
        Command to run

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.

    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.run_stdout mycontainer 'ls -l /etc'
    '''
    return _run(name,
                cmd,
                output='stdout',
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def script(name,
           source,
           saltenv='base',
           args=None,
           template=None,
           stdin=None,
           python_shell=True,
           output_loglevel='debug',
           ignore_retcode=False,
           use_vt=False,
           keep_env=None):
    '''
    Run :py:func:`cmd.script <salt.modules.cmdmod.script>` within a container

    name
        Container name or ID

    source
        Path to the script. Can be a local path on the Minion or a remote file
        from the Salt fileserver.

    args
        A string containing additional command-line options to pass to the
        script.

    template : None
        Templating engine to use on the script before running.

    stdin : None
        Standard input to be used for the script

    output_loglevel : debug
        Level at which to log the output from the script. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.

    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.script mycontainer salt://docker_script.py
        salt myminion docker-ng.script mycontainer salt://scripts/runme.sh 'arg1 arg2 "arg 3"'
        salt myminion docker-ng.script mycontainer salt://scripts/runme.sh stdin='one\\ntwo\\nthree\\nfour\\nfive\\n' output_loglevel=quiet
    '''
    return _script(name,
                   source,
                   saltenv=saltenv,
                   args=args,
                   template=template,
                   stdin=stdin,
                   python_shell=python_shell,
                   output_loglevel=output_loglevel,
                   ignore_retcode=ignore_retcode,
                   use_vt=use_vt,
                   keep_env=keep_env)


def script_retcode(name,
                   source,
                   saltenv='base',
                   args=None,
                   template=None,
                   stdin=None,
                   python_shell=True,
                   output_loglevel='debug',
                   ignore_retcode=False,
                   use_vt=False,
                   keep_env=None):
    '''
    Run :py:func:`cmd.script_retcode <salt.modules.cmdmod.script_retcode>`
    within a container

    name
        Container name or ID

    source
        Path to the script. Can be a local path on the Minion or a remote file
        from the Salt fileserver.

    args
        A string containing additional command-line options to pass to the
        script.

    template : None
        Templating engine to use on the script before running.

    stdin : None
        Standard input to be used for the script

    output_loglevel : debug
        Level at which to log the output from the script. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.

    CLI Example:

    .. code-block:: bash

        salt myminion docker-ng.script_retcode mycontainer salt://docker_script.py
        salt myminion docker-ng.script_retcode mycontainer salt://scripts/runme.sh 'arg1 arg2 "arg 3"'
        salt myminion docker-ng.script_retcode mycontainer salt://scripts/runme.sh stdin='one\\ntwo\\nthree\\nfour\\nfive\\n' output_loglevel=quiet
    '''
    return _script(name,
                   source,
                   saltenv=saltenv,
                   args=args,
                   template=template,
                   stdin=stdin,
                   python_shell=python_shell,
                   output_loglevel=output_loglevel,
                   ignore_retcode=ignore_retcode,
                   use_vt=use_vt,
                   keep_env=keep_env)['retcode']
