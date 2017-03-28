# -*- coding: utf-8 -*-
'''
Management of Docker Containers

.. versionadded:: 2015.8.0
.. versionchanged:: Nitrogen
    This module has replaced the legacy docker execution module.

:depends: docker_ Python module

.. note::
    Older releases of the Python bindings for Docker were called docker-py_ in
    PyPI. All releases of docker_, and releases of docker-py_ >= 1.6.0 are
    supported. These python bindings can easily be installed using
    :py:func:`pip.install <salt.modules.pip.install>`:

    .. code-block:: bash

        salt myminion pip.install docker

    To upgrade from docker-py_ to docker_, you must first uninstall docker-py_,
    and then install docker_:

    .. code-block:: bash

        salt myminion pip.uninstall docker-py
        salt myminion pip.install docker

.. _docker: https://pypi.python.org/pypi/docker
.. _docker-py: https://pypi.python.org/pypi/docker-py

.. _docker-authentication:

Authentication
--------------

To push or pull images, credentials must be configured. By default this module
will try to get the credentials from the default docker auth file, located
under the home directory of the user running the salt-minion
(HOME/.docker/config.json). Because a password must be used, it is recommended
to place this configuration in :ref:`Pillar <pillar>` data. If pillar data
specifies a registry already present in the default docker auth file, it will
override.

The configuration schema is as follows:

.. code-block:: yaml

    docker-registries:
      <registry_url>:
        email: <email_address>
        password: <password>
        username: <username>
        reauth: <boolean>

For example:

.. code-block:: yaml

    docker-registries:
      https://index.docker.io/v1/:
        email: foo@foo.com
        password: s3cr3t
        username: foo

Reauth is an optional parameter that forces the docker login to reauthorize using
the credentials passed in the pillar data. Defaults to false.

.. versionadded:: 2016.3.5,2016.11.1

For example:

.. code-block:: yaml

    docker-registries:
      https://index.docker.io/v1/:
        email: foo@foo.com
        password: s3cr3t
        username: foo
        reauth: True

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

Configuration Options
---------------------

The following configuration options can be set to fine-tune how Salt uses
Docker:

- ``docker.url``: URL to the docker service (default: local socket).
- ``docker.version``: API version to use
- ``docker.exec_driver``: Execution driver to use, one of ``nsenter``,
  ``lxc-attach``, or ``docker-exec``. See the :ref:`Executing Commands Within a
  Running Container <docker-execution-driver>` section for more details on how
  this config parameter is used.

These configuration options are retrieved using :py:mod:`config.get
<salt.modules.config.get>` (click the link for further information).

Functions
---------

- Information Gathering
    - :py:func:`docker.depends <salt.modules.docker.depends>`
    - :py:func:`docker.diff <salt.modules.docker.diff>`
    - :py:func:`docker.exists <salt.modules.docker.exists>`
    - :py:func:`docker.history <salt.modules.docker.history>`
    - :py:func:`docker.images <salt.modules.docker.images>`
    - :py:func:`docker.info <salt.modules.docker.info>`
    - :py:func:`docker.inspect <salt.modules.docker.inspect>`
    - :py:func:`docker.inspect_container
      <salt.modules.docker.inspect_container>`
    - :py:func:`docker.inspect_image <salt.modules.docker.inspect_image>`
    - :py:func:`docker.list_containers
      <salt.modules.docker.list_containers>`
    - :py:func:`docker.list_tags <salt.modules.docker.list_tags>`
    - :py:func:`docker.logs <salt.modules.docker.logs>`
    - :py:func:`docker.pid <salt.modules.docker.pid>`
    - :py:func:`docker.port <salt.modules.docker.port>`
    - :py:func:`docker.ps <salt.modules.docker.ps>`
    - :py:func:`docker.state <salt.modules.docker.state>`
    - :py:func:`docker.search <salt.modules.docker.search>`
    - :py:func:`docker.top <salt.modules.docker.top>`
    - :py:func:`docker.version <salt.modules.docker.version>`
- Container Management
    - :py:func:`docker.create <salt.modules.docker.create>`
    - :py:func:`docker.copy_from <salt.modules.docker.copy_from>`
    - :py:func:`docker.copy_to <salt.modules.docker.copy_to>`
    - :py:func:`docker.export <salt.modules.docker.export>`
    - :py:func:`docker.rm <salt.modules.docker.rm>`
- Management of Container State
    - :py:func:`docker.kill <salt.modules.docker.kill>`
    - :py:func:`docker.pause <salt.modules.docker.pause>`
    - :py:func:`docker.restart <salt.modules.docker.restart>`
    - :py:func:`docker.start <salt.modules.docker.start>`
    - :py:func:`docker.stop <salt.modules.docker.stop>`
    - :py:func:`docker.unpause <salt.modules.docker.unpause>`
    - :py:func:`docker.wait <salt.modules.docker.wait>`
- Image Management
    - :py:func:`docker.build <salt.modules.docker.build>`
    - :py:func:`docker.commit <salt.modules.docker.commit>`
    - :py:func:`docker.dangling <salt.modules.docker.dangling>`
    - :py:func:`docker.import <salt.modules.docker.import>`
    - :py:func:`docker.load <salt.modules.docker.load>`
    - :py:func:`docker.pull <salt.modules.docker.pull>`
    - :py:func:`docker.push <salt.modules.docker.push>`
    - :py:func:`docker.rmi <salt.modules.docker.rmi>`
    - :py:func:`docker.save <salt.modules.docker.save>`
    - :py:func:`docker.tag <salt.modules.docker.tag>`
- Network Management
    - :py:func:`docker.networks <salt.modules.docker.networks>`
    - :py:func:`docker.create_network <salt.modules.docker.create_network>`
    - :py:func:`docker.remove_network <salt.modules.docker.remove_network>`
    - :py:func:`docker.inspect_network
      <salt.modules.docker.inspect_network>`
    - :py:func:`docker.connect_container_to_network
      <salt.modules.docker.connect_container_to_network>`
    - :py:func:`docker.disconnect_container_from_network
      <salt.modules.docker.disconnect_container_from_network>`

- Salt Functions and States Execution
    - :py:func:`docker.call <salt.modules.docker.call>`
    - :py:func:`docker.sls <salt.modules.docker.sls>`
    - :py:func:`docker.sls_build <salt.modules.docker.sls_build>`


.. _docker-execution-driver:

Executing Commands Within a Running Container
---------------------------------------------

.. note::
    With the release of Docker 1.13.1, the Execution Driver has been removed.
    Starting in versions 2016.3.6, 2016.11.4, and Nitrogen, Salt defaults to
    using ``docker exec`` to run commands in containers, however for older Salt
    releases it will be necessary to set the ``docker.exec_driver`` config
    option to either ``docker-exec`` or ``nsenter`` for Docker versions 1.13.1
    and newer.

Multiple methods exist for executing commands within Docker containers:

- lxc-attach_: Default for older versions of docker
- nsenter_: Enters container namespace to run command
- docker-exec_: Native support for executing commands in Docker containers
  (added in Docker 1.3)

Adding a configuration option (see :py:func:`config.get
<salt.modules.config.get>`) called ``docker.exec_driver`` will tell Salt which
execution driver to use:

.. code-block:: yaml

    docker.exec_driver: docker-exec

If this configuration option is not found, Salt will use the appropriate
interface (either nsenter_ or lxc-attach_) based on the ``Execution Driver``
value returned from ``docker info``. docker-exec_ will not be used by default,
as it is presently (as of version 1.6.2) only able to execute commands as the
effective user of the container. Thus, if a ``USER`` directive was used to run
as a non-privileged user, docker-exec_ would be unable to perform the action as
root. Salt can still use docker-exec_ as an execution driver, but must be
explicitly configured (as in the example above) to do so at this time.

If possible, try to manually specify the execution driver, as it will save Salt
a little work.

.. _lxc-attach: https://linuxcontainers.org/lxc/manpages/man1/lxc-attach.1.html
.. _nsenter: http://man7.org/linux/man-pages/man1/nsenter.1.html
.. _docker-exec: http://docs.docker.com/reference/commandline/cli/#exec

This execution module provides functions that shadow those from the :mod:`cmd
<salt.modules.cmdmod>` module. They are as follows:

- :py:func:`docker.retcode <salt.modules.docker.retcode>`
- :py:func:`docker.run <salt.modules.docker.run>`
- :py:func:`docker.run_all <salt.modules.docker.run_all>`
- :py:func:`docker.run_stderr <salt.modules.docker.run_stderr>`
- :py:func:`docker.run_stdout <salt.modules.docker.run_stdout>`
- :py:func:`docker.script <salt.modules.docker.script>`
- :py:func:`docker.script_retcode <salt.modules.docker.script_retcode>`


Detailed Function Documentation
-------------------------------
'''

# Import Python Futures
from __future__ import absolute_import

__docformat__ = 'restructuredtext en'

# Import Python libs
import bz2
import copy
# Remove unused-import from disabled pylint checks when we uncomment the logic
# in _get_exec_driver() which checks the docker version
import fnmatch
import functools
import gzip
import io
import json
import logging
import os
import os.path
import pipes
import re
import shutil
import string
import time
import uuid
import base64
import errno
import subprocess

# Import Salt libs
from salt.exceptions import CommandExecutionError, SaltInvocationError
import salt.ext.six as six
from salt.ext.six.moves import map  # pylint: disable=import-error,redefined-builtin
import salt.utils
import salt.utils.decorators
import salt.utils.docker
import salt.utils.files
import salt.utils.thin
import salt.pillar
import salt.exceptions
import salt.fileclient
from salt.utils.versions import StrictVersion as _StrictVersion

from salt.state import HighState
import salt.client.ssh.state

# pylint: disable=import-error
try:
    import docker
    HAS_DOCKER_PY = True
except ImportError:
    HAS_DOCKER_PY = False

try:
    if six.PY2:
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
    'signal_': 'signal',
    'tag_': 'tag',
}

# Minimum supported versions
MIN_DOCKER = (1, 9, 0)
MIN_DOCKER_PY = (1, 6, 0)

VERSION_RE = r'([\d.]+)'

NOTSET = object()

# Define the module's virtual name and alias
__virtualname__ = 'docker'
__virtual_aliases__ = ('dockerng',)


def __virtual__():
    '''
    Only load if docker libs are present
    '''
    if HAS_DOCKER_PY:
        try:
            docker_py_versioninfo = _get_docker_py_versioninfo()
        except Exception:
            # May fail if we try to connect to a docker daemon but can't
            return (False, 'Docker module found, but no version could be'
                    ' extracted')
        # Don't let a failure to interpret the version keep this module from
        # loading. Log a warning (log happens in _get_docker_py_versioninfo()).
        if docker_py_versioninfo is None:
            return (False, 'Docker module found, but no version could be'
                    ' extracted')
        if docker_py_versioninfo >= MIN_DOCKER_PY:
            try:
                docker_versioninfo = version().get('VersionInfo')
            except Exception:
                docker_versioninfo = None

            if docker_versioninfo is None or docker_versioninfo >= MIN_DOCKER:
                return __virtualname__
            else:
                return (False,
                        'Insufficient Docker version (required: {0}, '
                        'installed: {1})'.format(
                            '.'.join(map(str, MIN_DOCKER)),
                            '.'.join(map(str, docker_versioninfo))))
        return (False,
                'Insufficient docker-py version (required: {0}, '
                'installed: {1})'.format(
                    '.'.join(map(str, MIN_DOCKER_PY)),
                    '.'.join(map(str, docker_py_versioninfo))))
    return (False, 'Could not import docker module, is docker-py installed?')


class DockerJSONDecoder(json.JSONDecoder):
    def decode(self, s, _w=None):
        objs = []
        for line in s.splitlines():
            if not line:
                continue
            obj, _ = self.raw_decode(line)
            objs.append(obj)
        return objs


def _get_docker_py_versioninfo():
    '''
    Returns the version_info tuple from docker-py
    '''
    try:
        return docker.version_info
    except AttributeError:
        pass


# Decorators
class _api_version(object):
    '''
    Enforce a specific Docker Remote API version
    '''
    def __init__(self, api_version):
        self.api_version = api_version

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            '''
            Get the current client version and check it against the one passed
            '''
            _get_client()
            current_api_version = __context__['docker.client'].api_version
            if float(current_api_version) < self.api_version:
                raise CommandExecutionError(
                    'This function requires a Docker API version of at least '
                    '{0}. API version in use is {1}.'
                    .format(self.api_version, current_api_version)
                )
            return func(*args, **salt.utils.clean_kwargs(**kwargs))
        return salt.utils.decorators.identical_signature_wrapper(func, wrapper)


class _client_version(object):
    '''
    Enforce a specific Docker client version
    '''
    def __init__(self, version):
        self.version = _StrictVersion(version)

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            '''
            Get the current client version and check it against the one passed
            '''
            _get_client()
            current_version = '.'.join(map(str, _get_docker_py_versioninfo()))
            if _StrictVersion(current_version) < self.version:
                error_message = (
                    'This function requires a Docker Client version of at least '
                    '{0}. Version in use is {1}.'
                    .format(self.version, current_version))
                minion_conf = __salt__['config.get']('docker.version', NOTSET)
                if minion_conf is not NOTSET:
                    error_message += (
                        ' Hint: Your minion configuration specified'
                        ' `docker.version` = "{0}"'.format(minion_conf))
                raise CommandExecutionError(error_message)
            return func(*args, **salt.utils.clean_kwargs(**kwargs))
        return salt.utils.decorators.identical_signature_wrapper(func, wrapper)


def _docker_client(wrapped):
    '''
    Decorator to run a function that requires the use of a docker.Client()
    instance.
    '''
    @functools.wraps(wrapped)
    def wrapper(*args, **kwargs):
        '''
        Ensure that the client is present
        '''
        client_timeout = __context__.get('docker.timeout',
                                         salt.utils.docker.CLIENT_TIMEOUT)
        _get_client(timeout=client_timeout)
        return wrapped(*args, **salt.utils.clean_kwargs(**kwargs))
    return wrapper


def _ensure_exists(wrapped):
    '''
    Decorator to ensure that the named container exists.
    '''
    @functools.wraps(wrapped)
    def wrapper(name, *args, **kwargs):
        '''
        Check for container existence and raise an error if it does not exist
        '''
        if not exists(name):
            raise CommandExecutionError(
                'Container \'{0}\' does not exist'.format(name)
            )
        return wrapped(name, *args, **salt.utils.clean_kwargs(**kwargs))
    return wrapper


def _refresh_mine_cache(wrapped):
    '''
    Decorator to trigger a refresh of salt mine data.
    '''
    @functools.wraps(wrapped)
    def wrapper(*args, **kwargs):
        '''
        refresh salt mine on exit.
        '''
        returned = wrapped(*args, **salt.utils.clean_kwargs(**kwargs))
        __salt__['mine.send']('docker.ps', verbose=True, all=True, host=True)
        return returned
    return wrapper


# Helper functions
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
    _client_wrapper(action, name, *args, **kwargs)
    _clear_context()
    try:
        post = state(name)
    except CommandExecutionError:
        # Container doesn't exist anymore
        post = None
    ret = {'result': post == expected,
           'state': {'old': pre, 'new': post}}
    return ret


def _clear_context():
    '''
    Clear the state/exists values stored in context
    '''
    # Can't use 'for key in __context__' or six.iterkeys(__context__) because
    # an exception will be raised if the size of the dict is modified during
    # iteration.
    keep_context = (
        'docker.client', 'docker.exec_driver', 'docker._pull_status',
        'docker.docker_version', 'docker.docker_py_version'
    )
    for key in list(__context__):
        try:
            if key.startswith('docker.') and key not in keep_context:
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
        - docker.version: API version to use (default: "auto")
    '''
    # In some edge cases, the client instance is missing attributes. Don't use
    # the cached client in those cases.
    if 'docker.client' not in __context__ \
            or not hasattr(__context__['docker.client'], 'timeout'):
        client_kwargs = {}
        if timeout is not None:
            client_kwargs['timeout'] = timeout
        for key, val in (('base_url', 'docker.url'),
                         ('version', 'docker.version')):
            param = __salt__['config.get'](val, NOTSET)
            if param is not NOTSET:
                client_kwargs[key] = param

        if 'base_url' not in client_kwargs and 'DOCKER_HOST' in os.environ:
            # Check if the DOCKER_HOST environment variable has been set
            client_kwargs['base_url'] = os.environ.get('DOCKER_HOST')

        if 'version' not in client_kwargs:
            # Let docker-py auto detect docker version incase
            # it's not defined by user.
            client_kwargs['version'] = 'auto'

        docker_machine = __salt__['config.get']('docker.machine', NOTSET)

        if docker_machine is not NOTSET:
            docker_machine_json = __salt__['cmd.run']('docker-machine inspect ' + docker_machine)
            try:
                docker_machine_json = json.loads(docker_machine_json)
                docker_machine_tls = docker_machine_json['HostOptions']['AuthOptions']
                docker_machine_ip = docker_machine_json['Driver']['IPAddress']
                client_kwargs['base_url'] = 'https://' + docker_machine_ip + ':2376'
                client_kwargs['tls'] = docker.tls.TLSConfig(
                    client_cert=(docker_machine_tls['ClientCertPath'],
                                 docker_machine_tls['ClientKeyPath']),
                    ca_cert=docker_machine_tls['CaCertPath'],
                    assert_hostname=False,
                    verify=True)
            except Exception as exc:
                raise CommandExecutionError(
                    'Docker machine {0} failed: {1}'.format(docker_machine, exc))

        try:
            # docker-py 2.0 renamed this client attribute
            __context__['docker.client'] = docker.APIClient(**client_kwargs)
        except AttributeError:
            __context__['docker.client'] = docker.Client(**client_kwargs)


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


def _get_exec_driver():
    '''
    Get the method to be used in shell commands
    '''
    contextkey = 'docker.exec_driver'
    if contextkey not in __context__:
        from_config = __salt__['config.get'](contextkey, None)
        # This if block can be removed once we make docker-exec a default
        # option, as it is part of the logic in the commented block above.
        if from_config is not None:
            __context__[contextkey] = from_config
            return from_config

        # The execution driver was removed in Docker 1.13.1, docker-exec is now
        # the default.
        driver = info().get('ExecutionDriver', 'docker-exec')
        if driver == 'docker-exec':
            __context__[contextkey] = driver
        elif driver.startswith('lxc-'):
            __context__[contextkey] = 'lxc-attach'
        elif driver.startswith('native-') and HAS_NSENTER:
            __context__[contextkey] = 'nsenter'
        elif not driver.strip() and HAS_NSENTER:
            log.warning(
                'ExecutionDriver from \'docker info\' is blank, falling '
                'back to using \'nsenter\'. To squelch this warning, set '
                'docker.exec_driver. See the Salt documentation for the '
                'docker module for more information.'
            )
            __context__[contextkey] = 'nsenter'
        else:
            raise NotImplementedError(
                'Unknown docker ExecutionDriver \'{0}\', or didn\'t find '
                'command to attach to the container'.format(driver)
            )
    return __context__[contextkey]


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


def _prep_pull():
    '''
    Populate __context__ with the current (pre-pull) image IDs (see the
    docstring for _pull_status for more information).
    '''
    __context__['docker._pull_status'] = [x[:12] for x in images(all=True)]


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
    except Exception:
        log.error('Unable to format file size for \'%s\'', num)
        return 'unknown'


@_docker_client
def _client_wrapper(attr, *args, **kwargs):
    '''
    Common functionality for getting information from a container
    '''
    catch_api_errors = kwargs.pop('catch_api_errors', True)
    if 'docker.client' not in __context__:
        raise CommandExecutionError('Docker service not running or not installed?')
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
        # Get credential from the home directory of the user running
        # salt-minion, default auth file for docker (~/.docker/config.json)
        registry_auth_config = {}
        try:
            home = os.path.expanduser("~")
            docker_auth_file = os.path.join(home, '.docker', 'config.json')
            with salt.utils.fopen(docker_auth_file) as fp:
                try:
                    docker_auth = json.load(fp)
                    fp.close()
                except (OSError, IOError) as exc:
                    if exc.errno != errno.ENOENT:
                        log.error('Failed to read docker auth file %s: %s', docker_auth_file, exc)
                        docker_auth = {}
                if isinstance(docker_auth, dict):
                    if 'auths' in docker_auth and isinstance(docker_auth['auths'], dict):
                        for key, data in six.iteritems(docker_auth['auths']):
                            if isinstance(data, dict):
                                email = str(data.get('email', ''))
                                b64_auth = base64.b64decode(data.get('auth', ''))
                                username, password = b64_auth.split(':')
                                registry = 'https://{registry}'.format(registry=key)
                                registry_auth_config.update({registry: {
                                    'username': username,
                                    'password': password,
                                    'email': email
                                }})
        except Exception as exc:
            log.debug(
                'Salt was unable to load credentials from ~/.docker/config.json. '
                'Attempting to load credentials from Pillar data. Error '
                'message: %s', exc
            )
        # Set credentials from pillar - Overwrite auth from config.json
        registry_auth_config.update(__pillar__.get('docker-registries', {}))
        for key, data in six.iteritems(__pillar__):
            if key.endswith('-docker-registries'):
                registry_auth_config.update(data)

        err = (
            '{0} Docker credentials{1}. Please see the docker remote '
            'execution module documentation for information on how to '
            'configure authentication.'
        )
        try:
            for registry, creds in six.iteritems(registry_auth_config):
                __context__['docker.client'].login(
                    creds['username'],
                    password=creds['password'],
                    email=creds.get('email'),
                    registry=registry,
                    reauth=creds.get('reauth', False))
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
    Process a status update from a docker pull, updating the data structure.

    For containers created with older versions of Docker, there is no
    distinction in the status updates between layers that were already present
    (and thus not necessary to download), and those which were actually
    downloaded. Because of this, any function that needs to invoke this
    function needs to pre-fetch the image IDs by running _prep_pull() in any
    function that calls _pull_status(). It is important to grab this
    information before anything is pulled so we aren't looking at the state of
    the images post-pull.

    We can't rely on the way that __context__ is utilized by the images()
    function, because by design we clear the relevant context variables once
    we've made changes to allow the next call to images() to pick up any
    changes that were made.
    '''
    def _already_exists(id_):
        '''
        Layer already exists
        '''
        already_pulled = data.setdefault('Layers', {}).setdefault(
            'Already_Pulled', [])
        if id_ not in already_pulled:
            already_pulled.append(id_)

    def _new_layer(id_):
        '''
        Pulled a new layer
        '''
        pulled = data.setdefault('Layers', {}).setdefault(
            'Pulled', [])
        if id_ not in pulled:
            pulled.append(id_)

    if 'docker._pull_status' not in __context__:
        log.warning(
            '_pull_status context variable was not populated, information on '
            'downloaded layers may be inaccurate. Please report this to the '
            'SaltStack development team, and if possible include the image '
            '(and tag) that was being pulled.'
        )
        __context__['docker._pull_status'] = NOTSET
    status = item['status']
    if status == 'Already exists':
        _already_exists(item['id'])
    elif status in 'Pull complete':
        _new_layer(item['id'])
    elif status.startswith('Status: '):
        data['Status'] = status[8:]
    elif status == 'Download complete':
        if __context__['docker._pull_status'] is not NOTSET:
            id_ = item['id']
            if id_ in __context__['docker._pull_status']:
                _already_exists(id_)
            else:
                _new_layer(id_)


def _push_status(data, item):
    '''
    Process a status update from a docker push, updating the data structure
    '''
    status = item['status'].lower()
    if 'id' in item:
        if 'already pushed' in status or 'already exists' in status:
            # Layer already exists
            already_pushed = data.setdefault('Layers', {}).setdefault(
                'Already_Pushed', [])
            already_pushed.append(item['id'])
        elif 'successfully pushed' in status or status == 'pushed':
            # Pushed a new layer
            pushed = data.setdefault('Layers', {}).setdefault(
                'Pushed', [])
            pushed.append(item['id'])


def _error_detail(data, item):
    '''
    Process an API error, updating the data structure
    '''
    err = item['errorDetail']
    if 'code' in err:
        try:
            msg = ': '.join((
                item['errorDetail']['code'],
                item['errorDetail']['message']
            ))
        except TypeError:
            msg = '{0}: {1}'.format(
                item['errorDetail']['code'],
                item['errorDetail']['message'],
            )
    else:
        msg = item['errorDetail']['message']
    data.append(msg)


# Functions to handle docker-py client args
def get_client_args():
    '''
    .. versionadded:: 2016.3.6,2016.11.4,Nitrogen
    .. versionchanged:: Nitrogen
        Replaced the container config args with the ones from the API's
        ``create_container`` function.

    Returns the args for docker-py's `low-level API`_, organized by args for
    container creation, host config, and networking config.

    .. _`low-level API`: http://docker-py.readthedocs.io/en/stable/api.html

    CLI Example:

    .. code-block:: bash

        salt myminion docker.get_client_args
    '''
    return salt.utils.docker.get_client_args()


def _get_create_kwargs(image,
                       skip_translate=None,
                       ignore_collisions=False,
                       **kwargs):
    '''
    Take input kwargs and return a kwargs dict to pass to docker-py's
    create_container() function.
    '''
    try:
        kwargs, invalid, collisions = \
            salt.utils.docker.translate_input(skip_translate=skip_translate,
                                              **kwargs)
    except Exception as translate_exc:
        error_message = translate_exc.__str__()
        log.error('docker.create: Error translating input: \'%s\'',
                  error_message, exc_info=True)
    else:
        error_message = None

    error_data = {}
    if invalid:
        error_data['invalid'] = invalid
    if collisions and not ignore_collisions:
        for item in collisions:
            error_data.setdefault('collisions', []).append(
                '\'{0}\' is an alias for \'{1}\', they cannot both be used'
                .format(salt.utils.docker.ALIASES_REVMAP[item], item)
            )
    if error_message is not None:
        error_data['error_message'] = error_message

    if error_data:
        raise CommandExecutionError('Failed to translate input', info=error_data)

    try:
        client_args = get_client_args()
    except CommandExecutionError as exc:
        log.error('docker.create: Error getting client args: \'%s\'',
                  exc.__str__(), exc_info=True)
        raise CommandExecutionError('Failed to get client args: {0}'.format(exc))

    full_host_config = {}
    host_kwargs = {}
    create_kwargs = {}
    # Using list() becausee we'll be altering kwargs during iteration
    for arg in list(kwargs):
        if arg in client_args['host_config']:
            host_kwargs[arg] = kwargs.pop(arg)
            continue
        if arg in client_args['create_container']:
            if arg == 'host_config':
                full_host_config.update(kwargs.pop(arg))
            else:
                create_kwargs[arg] = kwargs.pop(arg)
            continue
    create_kwargs['host_config'] = \
            _client_wrapper('create_host_config', **host_kwargs)
    # In the event that a full host_config was passed, overlay it on top of the
    # one we just created.
    create_kwargs['host_config'].update(full_host_config)
    # The "kwargs" dict at this point will only contain unused args
    return create_kwargs, kwargs


def compare_container(first, second, ignore=None):
    '''
    .. versionadded:: Nitrogen

    Compare two containers' Config and and HostConfig and return any
    differences between the two.

    first
        Name or ID of first container

    second
        Name or ID of second container

    ignore
        A comma-separated list (or Python list) of keys to ignore when
        comparing. This is useful when comparing two otherwise identical
        containers which have different hostnames.
    '''
    if ignore is None:
        ignore = []
    if not isinstance(ignore, list):
        try:
            ignore = ignore.split(',')
        except AttributeError:
            ignore = str(ignore).split(',')
    result1 = inspect_container(first)
    result2 = inspect_container(second)
    ret = {}
    for conf_dict in ('Config', 'HostConfig'):
        for item in result1[conf_dict]:
            if item in ignore:
                continue
            val1 = result1[conf_dict][item]
            val2 = result2[conf_dict].get(item)
            if val1 != val2:
                ret.setdefault(conf_dict, {})[item] = {'old': val1, 'new': val2}
        # Check for optionally-present items that were in the second container
        # and not the first.
        for item in result2[conf_dict]:
            if item in ignore or item in ret.get(conf_dict, {}):
                # We're either ignoring this or we already processed this
                # when iterating through result1. Either way, skip it.
                continue
            val1 = result1[conf_dict].get(item)
            val2 = result2[conf_dict][item]
            if val1 != val2:
                ret.setdefault(conf_dict, {})[item] = {'old': val1, 'new': val2}
    return ret


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

        salt myminion docker.depends myimage
        salt myminion docker.depends 0123456789ab
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
    created. Equivalent to running the ``docker diff`` Docker CLI command.

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

        salt myminion docker.diff mycontainer
    '''
    changes = _client_wrapper('diff', name)
    kind_map = {0: 'Changed', 1: 'Added', 2: 'Deleted'}
    ret = {}
    for change in changes:
        key = kind_map.get(change['Kind'], 'Unknown')
        ret.setdefault(key, []).append(change['Path'])
    if 'Unknown' in ret:
        log.error(
            'Unknown changes detected in docker.diff of container %s. '
            'This is probably due to a change in the Docker API. Please '
            'report this to the SaltStack developers', name
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

        salt myminion docker.exists mycontainer
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
    Return the history for an image. Equivalent to running the ``docker
    history`` Docker CLI command.

    name
        Container name or ID

    quiet : False
        If ``True``, the return data will simply be a list of the commands run
        to build the container.

        .. code-block:: bash

            $ salt myminion docker.history nginx:latest quiet=True
            myminion:
                - FROM scratch
                - ADD file:ef063ed0ae9579362871b9f23d2bc0781ef7cd4de6ac822052cf6c9c5a12b1e2 in /
                - CMD [/bin/bash]
                - MAINTAINER NGINX Docker Maintainers "docker-maint@nginx.com"
                - apt-key adv --keyserver pgp.mit.edu --recv-keys 573BFD6B3D8FBC641079A6ABABF5BD827BD9BF62
                - echo "deb http://nginx.org/packages/mainline/debian/ wheezy nginx" >> /etc/apt/sources.list
                - ENV NGINX_VERSION=1.7.10-1~wheezy
                - apt-get update &&     apt-get install -y ca-certificates nginx=${NGINX_VERSION} &&     rm -rf /var/lib/apt/lists/*
                - ln -sf /dev/stdout /var/log/nginx/access.log
                - ln -sf /dev/stderr /var/log/nginx/error.log
                - VOLUME [/var/cache/nginx]
                - EXPOSE map[80/tcp:{} 443/tcp:{}]
                - CMD [nginx -g daemon off;]
                        https://github.com/saltstack/salt/pull/22421


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

        salt myminion docker.exists mycontainer
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
    Returns information about the Docker images on the Minion. Equivalent to
    running the ``docker images`` Docker CLI command.

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

        salt myminion docker.images
        salt myminion docker.images all=True
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
                img_state = ('untagged' if
                             img['RepoTags'] in (
                               ['<none>:<none>'],  # docker API <1.24
                               None,  # docker API >=1.24
                             ) else 'tagged')
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
    the ``docker info`` Docker CLI command.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.info
    '''
    return _client_wrapper('info')


def inspect(name):
    '''
    .. versionchanged:: Nitrogen
        Volumes and networks are now checked, in addition to containers and
        images.

    This is a generic container/image/volume/network inspecton function. It
    will run the following functions in order:

    - :py:func:`docker.inspect_container
      <salt.modules.docker.inspect_container>`
    - :py:func:`docker.inspect_image <salt.modules.docker.inspect_image>`
    - :py:func:`docker.inspect_volume <salt.modules.docker.inspect_volume>`
    - :py:func:`docker.inspect_network <salt.modules.docker.inspect_network>`

    The first of these to find a match will be returned.

    name
        Container/image/volume/network name or ID


    **RETURN DATA**

    A dictionary of container/image/volume/network information


    CLI Example:

    .. code-block:: bash

        salt myminion docker.inspect mycontainer
        salt myminion docker.inspect busybox
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
    try:
        return inspect_volume(name)
    except CommandExecutionError as exc:
        if not exc.strerror.startswith('Error 404'):
            raise
    try:
        return inspect_network(name)
    except CommandExecutionError as exc:
        if not exc.strerror.startswith('Error 404'):
            raise

    raise CommandExecutionError(
        'Error 404: No such image/container/volume/network: {0}'.format(name)
    )


@_ensure_exists
def inspect_container(name):
    '''
    Retrieves container information. Equivalent to running the ``docker
    inspect`` Docker CLI command, but will only look for container information.

    name
        Container name or ID


    **RETURN DATA**

    A dictionary of container information


    CLI Example:

    .. code-block:: bash

        salt myminion docker.inspect_container mycontainer
        salt myminion docker.inspect_container 0123456789ab
    '''
    return _client_wrapper('inspect_container', name)


def inspect_image(name):
    '''
    Retrieves image information. Equivalent to running the ``docker inspect``
    Docker CLI command, but will only look for image information.

    .. note::
        To inspect an image, it must have been pulled from a registry or built
        locally. Images on a Docker registry which have not been pulled cannot
        be inspected.

    name
        Image name or ID


    **RETURN DATA**

    A dictionary of image information


    CLI Examples:

    .. code-block:: bash

        salt myminion docker.inspect_image busybox
        salt myminion docker.inspect_image centos:6
        salt myminion docker.inspect_image 0123456789ab
    '''
    ret = _client_wrapper('inspect_image', name)
    for param in ('Size', 'VirtualSize'):
        if param in ret:
            ret['{0}_Human'.format(param)] = _size_fmt(ret[param])
    return ret


def list_containers(**kwargs):
    '''
    Returns a list of containers by name. This is different from
    :py:func:`docker.ps <salt.modules.docker.ps_>` in that
    :py:func:`docker.ps <salt.modules.docker.ps_>` returns its results
    organized by container ID.

    all : False
        If ``True``, stopped containers will be included in return data

    CLI Example:

    .. code-block:: bash

        salt myminion docker.inspect_image <image>
    '''
    ret = set()
    for item in six.itervalues(ps_(all=kwargs.get('all', False))):
        names = item.get('Names')
        if not names:
            continue
        for c_name in [x.lstrip('/') for x in names or []]:
            ret.add(c_name)
    return sorted(ret)


def list_tags():
    '''
    Returns a list of tagged images

    CLI Example:

    .. code-block:: bash

        salt myminion docker.list_tags
    '''
    ret = set()
    for item in six.itervalues(images()):
        if not item.get('RepoTags'):
            continue
        ret.update(set(item['RepoTags']))
    return sorted(ret)


def logs(name):
    '''
    Returns the logs for the container. Equivalent to running the ``docker
    logs`` Docker CLI command.

    name
        Container name or ID

    CLI Example:

    .. code-block:: bash

        salt myminion docker.logs mycontainer
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

        salt myminion docker.pid mycontainer
        salt myminion docker.pid 0123456789ab
    '''
    return inspect_container(name)['State']['Pid']


@_ensure_exists
def port(name, private_port=None):
    '''
    Returns port mapping information for a given container. Equivalent to
    running the ``docker port`` Docker CLI command.

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

        salt myminion docker.port mycontainer
        salt myminion docker.port mycontainer 5000
        salt myminion docker.port mycontainer 5000/udp
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
                if not port_num.isdigit() or protocol not in ('tcp', 'udp'):
                    raise SaltInvocationError(err)
                pattern = port_num + '/' + protocol
            except AttributeError:
                raise SaltInvocationError(err)

    return dict((x, mappings[x]) for x in fnmatch.filter(mappings, pattern))


def ps_(filters=None, **kwargs):
    '''
    Returns information about the Docker containers on the Minion. Equivalent
    to running the ``docker ps`` Docker CLI command.

    all : False
        If ``True``, stopped containers will also be returned

    host: False
        If ``True``, local host's network topology will be included

    verbose : False
        If ``True``, a ``docker inspect`` will be run on each container
        returned.

    filters: None
        A dictionary of filters to be processed on the container list.
        Available filters:

          - exited (int): Only containers with specified exit code
          - status (str): One of restarting, running, paused, exited
          - label (str): format either "key" or "key=value"

    **RETURN DATA**

    A dictionary with each key being an container ID, and each value some
    general info about that container (time created, name, command, etc.)


    CLI Example:

    .. code-block:: bash

        salt myminion docker.ps
        salt myminion docker.ps all=True
        salt myminion docker.ps filters="{'label': 'role=web'}"
    '''
    response = _client_wrapper('containers', all=True, filters=filters)
    key_map = {
        'Created': 'Time_Created_Epoch',
    }
    context_data = {}
    for container in response:
        c_id = container.pop('Id', None)
        if c_id is None:
            continue
        for item in container:
            c_state = 'running' \
                if container.get('Status', '').lower().startswith('up ') \
                else 'stopped'
            bucket = context_data.setdefault(c_state, {})
            c_key = key_map.get(item, item)
            bucket.setdefault(c_id, {})[c_key] = container[item]
        if 'Time_Created_Epoch' in bucket.get(c_id, {}):
            bucket[c_id]['Time_Created_Local'] = \
                time.strftime(
                    '%Y-%m-%d %H:%M:%S %Z',
                    time.localtime(bucket[c_id]['Time_Created_Epoch'])
                )

    ret = copy.deepcopy(context_data.get('running', {}))
    if kwargs.get('all', False):
        ret.update(copy.deepcopy(context_data.get('stopped', {})))

    # If verbose info was requested, go get it
    if kwargs.get('verbose', False):
        for c_id in ret:
            ret[c_id]['Info'] = inspect_container(c_id)

    if kwargs.get('host', False):
        ret.setdefault(
            'host', {}).setdefault(
                'interfaces', {}).update(__salt__['network.interfaces']())
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

        salt myminion docker.state mycontainer
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

        salt myminion docker.search centos
        salt myminion docker.search centos official=True
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

        salt myminion docker.top mycontainer
        salt myminion docker.top 0123456789ab
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
    Returns a dictionary of Docker version information. Equivalent to running
    the ``docker version`` Docker CLI command.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.version
    '''
    ret = _client_wrapper('version')
    version_re = re.compile(VERSION_RE)
    if 'Version' in ret:
        match = version_re.match(str(ret['Version']))
        if match:
            ret['VersionInfo'] = tuple(
                [int(x) for x in match.group(1).split('.')]
            )
    if 'ApiVersion' in ret:
        match = version_re.match(str(ret['ApiVersion']))
        if match:
            ret['ApiVersionInfo'] = tuple(
                [int(x) for x in match.group(1).split('.')]
            )
    return ret


# Functions to manage containers
@_refresh_mine_cache
def create(image,
           name=None,
           skip_translate=None,
           ignore_collisions=False,
           validate_ip_addrs=True,
           client_timeout=salt.utils.docker.CLIENT_TIMEOUT,
           **kwargs):
    '''
    Create a new container

    image
        Image from which to create the container

    name
        Name for the new container. If not provided, Docker will randomly
        generate one for you (it will be included in the return data).

    skip_translate
        This function translates Salt CLI input into the format which
        docker-py_ expects. However, in the event that Salt's translation logic
        fails (due to potential changes in the Docker Remote API, or to bugs in
        the translation code), this argument can be used to exert granular
        control over which arguments are translated and which are not.

        Pass this argument as a comma-separated list (or Python list) of
        arguments, and translation for each passed argument name will be
        skipped. Alternatively, pass ``True`` and *all* translation will be
        skipped.

        Skipping tranlsation allows for arguments to be formatted directly in
        the format which docker-py_ expects. This allows for API changes and
        other issues to be more easily worked around. An example of using this
        option to skip translation would be:

        .. code-block:: bash

            salt myminion docker.create image=centos:7.3.1611 skip_translate=environment environment="{'FOO': 'bar'}"

        See the following links for more information:

        - `docker-py Low-level API`_
        - `Docker Engine API`_

    .. _docker-py: https://pypi.python.org/pypi/docker-py
    .. _`docker-py Low-level API`: http://docker-py.readthedocs.io/en/stable/api.html#docker.api.container.ContainerApiMixin.create_container
    .. _`Docker Engine API`: https://docs.docker.com/engine/api/v1.26/#operation/ContainerCreate

    ignore_collisions : False
        Since many of docker-py_'s arguments differ in name from their CLI
        counterparts (with which most Docker users are more familiar), Salt
        detects usage of these and aliases them to the docker-py_ version of
        that argument. However, if both the alias and the docker-py_ version of
        the same argument (e.g. ``env`` and ``environment``) are used, an error
        will be raised. Set this argument to ``True`` to suppress these errors
        and keep the docker-py_ version of the argument.

    validate_ip_addrs : True
        For parameters which accept IP addresses as input, IP address
        validation will be performed. To disable, set this to ``False``

    client_timeout : 60
        Timeout in seconds for the Docker client. This is not a timeout for
        this function, but for receiving a response from the API.

        .. note::

            This is only used if Salt needs to pull the requested image.

    **CONTAINER CONFIGURATION ARGUMENTS**

    auto_remove (or *rm*) : False
        Enable auto-removal of the container on daemon side when the
        container’s process exits (analogous to running a docker container with
        ``--rm`` on the CLI).

        Examples:

        - ``auto_remove=True``
        - ``rm=True``

    binds
        Files/directories to bind mount. Each bind mount should be passed in
        the format ``<host_path>:<container_path>:<read_only>``, where
        ``<read_only>`` is one of ``rw`` (for read-write access) or ``ro`` (for
        read-only access).  Optionally, the read-only information can be left
        off the end and the bind mount will be assumed to be read-write.

        Examples:

        - ``binds=/srv/www:/var/www:ro``
        - ``binds=/srv/www:/var/www:rw``
        - ``binds=/srv/www:/var/www``

        .. note::
            The second and third examples above are equivalent.

    blkio_weight
        Block IO weight (relative weight), accepts a weight value between 10
        and 1000.

        Example: ``blkio_weight=100``

    blkio_weight_device
        Block IO weight (relative device weight), specified as a list of
        expressions in the format ``PATH:WEIGHT``

        Example: ``blkio_weight_device=/dev/sda:100``

    cap_add
        List of capabilities to add within the container. Can be passed as a
        comma-separated list or a Python list. Requires Docker 1.2.0 or
        newer.

        Example: ``cap_add=SYS_ADMIN,MKNOD``, ``cap_add="[SYS_ADMIN, MKNOD]"``

    cap_drop
        List of capabilities to drop within the container. Can be passed as a
        comma-separated string or a Python list. Requires Docker 1.2.0 or
        newer.

        Example: ``cap_drop=SYS_ADMIN,MKNOD``,
        ``cap_drop="[SYS_ADMIN, MKNOD]"``

    command (or *cmd*)
        Command to run in the container

        Example: ``command=bash`` or ``cmd=bash``

        .. versionchanged:: 2015.8.1
            ``cmd`` is now also accepted

    cpuset_cpus (or *cpuset*)
        CPUs on which which to allow execution, specified as a string
        containing a range (e.g. ``0-3``) or a comma-separated list of CPUs
        (e.g. ``0,1``).

        Examples:

        - ``cpuset_cpus="0-3"``
        - ``cpuset="0,1"``

    cpuset_mems
        Memory nodes on which which to allow execution, specified as a string
        containing a range (e.g. ``0-3``) or a comma-separated list of MEMs
        (e.g. ``0,1``). Only effective on NUMA systems.

        Examples:

        - ``cpuset_mems="0-3"``
        - ``cpuset_mems="0,1"``

    cpu_group
        The length of a CPU period in microseconds

        Example: ``cpu_group=100000``

    cpu_period
        Microseconds of CPU time that the container can get in a CPU period

        Example: ``cpu_period=50000``

    cpu_shares
        CPU shares (relative weight), specified as an integer between 2 and 1024.

        Example: ``cpu_shares=512``

    detach : False
        If ``True``, run the container's command in the background (daemon
        mode)

        Example: ``detach=True``

    devices
        List of host devices to expose within the container

        Examples:

        - ``devices="/dev/net/tun,/dev/xvda1:/dev/xvda1,/dev/xvdb1:/dev/xvdb1:r"``
        - ``devices="['/dev/net/tun', '/dev/xvda1:/dev/xvda1', '/dev/xvdb1:/dev/xvdb1:r']"``

    device_read_bps
        Limit read rate (bytes per second) from a device, specified as a list
        of expressions in the format ``PATH:RATE``, where ``RATE`` is either an
        integer number of bytes, or a string ending in ``kb``, ``mb``, or
        ``gb``.

        Examples:

        - ``device_read_bps="/dev/sda:1mb,/dev/sdb:5mb"``
        - ``device_read_bps="['/dev/sda:100mb', '/dev/sdb:5mb']"``

    device_read_iops
        Limit read rate (I/O per second) from a device, specified as a list
        of expressions in the format ``PATH:RATE``, where ``RATE`` is a number
        of I/O operations.

        Examples:

        - ``device_read_iops="/dev/sda:1000,/dev/sdb:500"``
        - ``device_read_iops="['/dev/sda:1000', '/dev/sdb:500']"``

    device_write_bps
        Limit write rate (bytes per second) from a device, specified as a list
        of expressions in the format ``PATH:RATE``, where ``RATE`` is either an
        integer number of bytes, or a string ending in ``kb``, ``mb`` or
        ``gb``.


        Examples:

        - ``device_write_bps="/dev/sda:100mb,/dev/sdb:50mb"``
        - ``device_write_bps="['/dev/sda:100mb', '/dev/sdb:50mb']"``

    device_read_iops
        Limit write rate (I/O per second) from a device, specified as a list
        of expressions in the format ``PATH:RATE``, where ``RATE`` is a number
        of I/O operations.

        Examples:

        - ``device_read_iops="/dev/sda:1000,/dev/sdb:500"``
        - ``device_read_iops="['/dev/sda:1000', '/dev/sdb:500']"``

    dns
        List of DNS nameservers. Can be passed as a comma-separated list or a
        Python list.

        Examples:

        - ``dns=8.8.8.8,8.8.4.4``
        - ``dns="['8.8.8.8', '8.8.4.4']"``

        .. note::

            To skip IP address validation, use ``validate_ip_addrs=False``

    dns_opt
        Additional options to be added to the container’s ``resolv.conf`` file

        Example: ``dns_opt=ndots:9``

    dns_search
        List of DNS search domains. Can be passed as a comma-separated list
        or a Python list.

        Example: ``dns_search=foo1.domain.tld,foo2.domain.tld`` or
        ``dns_search="[foo1.domain.tld, foo2.domain.tld]"``

    domainname
        Set custom DNS search domains

        Example: ``domainname=domain.tld,domain2.tld``

    entrypoint
        Entrypoint for the container. Either a string (e.g. ``"mycmd --arg1
        --arg2"``) or a Python list (e.g.  ``"['mycmd', '--arg1', '--arg2']"``)

        Examples:

        - ``entrypoint="cat access.log"``
        - ``entrypoint="['cat', 'access.log']"``

    environment (or *env*)
        Either a dictionary of environment variable names and their values, or
        a Python list of strings in the format ``VARNAME=value``.

        Examples:

        - ``environment='VAR1=value,VAR2=value'``
        - ``environment="['VAR1=value', 'VAR2=value']"``
        - ``environment="{'VAR1': 'value', 'VAR2': 'value'}"``

    extra_hosts
        Additional hosts to add to the container's /etc/hosts file. Can be
        passed as a comma-separated list or a Python list. Requires Docker
        1.3.0 or newer.

        Examples:

        - ``extra_hosts=web1:10.9.8.7,web2:10.9.8.8``
        - ``extra_hosts="['web1:10.9.8.7', 'web2:10.9.8.8']"``
        - ``extra_hosts="{'web1': '10.9.8.7', 'web2': '10.9.8.8'}"``

        .. note::

            To skip IP address validation, use ``validate_ip_addrs=False``

    group_add
        List of additional group names and/or IDs that the container process
        will run as

        Examples:

        - ``group_add=web,network``
        - ``group_add="['web', 'network']"``

    hostname
        Hostname of the container. If not provided, and if a ``name`` has been
        provided, the ``hostname`` will default to the ``name`` that was
        passed.

        Example: ``hostname=web1``

        .. warning::

            If the container is started with ``network_mode=host``, the
            hostname will be overridden by the hostname of the Minion.

    interactive (or *stdin_open*): False
        Leave stdin open, even if not attached

        Examples:

        - ``interactive=True``
        - ``stdin_open=True``

    ipc_mode (or *ipc*)
        Set the IPC mode for the container. The default behavior is to create a
        private IPC namespace for the container, but this option can be
        used to change that behavior:

        - ``container:<container_name_or_id>`` reuses another container shared
          memory, semaphores and message queues
        - ``host``: use the host's shared memory, semaphores and message queues

        Examples:

        - ``ipc_mode=container:foo``
        - ``ipc=host``

        .. warning::
            Using ``host`` gives the container full access to local shared
            memory and is therefore considered insecure.

    isolation
        Specifies the type of isolation technology used by containers

        Example: ``isolation=hyperv``

        .. note::
            The default value on Windows server is ``process``, while the
            default value on Windows client is ``hyperv``. On Linux, only
            ``default`` is supported.

    labels (or *label*)
        Add metadata to the container. Labels can be set both with and without
        values:

        Examples (*with* values):

        - ``labels="label1=value1,label2=value2"``
        - ``labels="['label1=value1', 'label2=value2']"``
        - ``labels="{'label1': 'value1', 'label2': 'value2'}"``

        Examples (*without* values):

        - ``labels=label1,label2``
        - ``labels="['label1', 'label2']"``

    links
        Link this container to another. Links should be specified in the format
        ``<container_name_or_id>:<link_alias>``. Multiple links can be passed,
        ether as a comma separated list or a Python list.

        Examples:

        - ``links=web1:link1,web2:link2``,
        - ``links="['web1:link1', 'web2:link2']"``
        - ``links="{'web1': 'link1', 'web2': 'link2'}"``

    log_driver
        Set container's logging driver. Requires Docker 1.6 or newer.

        Example:

        - ``log_driver=syslog``

        .. note::
            The logging driver feature was improved in Docker 1.13 introducing
            option name changes. Please see Docker's `Configure logging
            drivers`_ documentation for more information.

        .. _`Configure logging drivers`: https://docs.docker.com/engine/admin/logging/overview/

    log_opt
        Config options for the ``log_driver`` config option. Requires Docker
        1.6 or newer.

        Example:

        - ``log_opt="syslog-address=tcp://192.168.0.42,syslog-facility=daemon"
        - ``log_opt="['syslog-address=tcp://192.168.0.42', 'syslog-facility=daemon']"
        - ``log_opt="{'syslog-address': 'tcp://192.168.0.42', 'syslog-facility: daemon

    lxc_conf
        Additional LXC configuration parameters to set before starting the
        container.

        Examples:

        - ``lxc_conf="lxc.utsname=docker,lxc.arch=x86_64"``
        - ``lxc_conf="['lxc.utsname=docker', 'lxc.arch=x86_64']"``
        - ``lxc_conf="{'lxc.utsname': 'docker', 'lxc.arch': 'x86_64'}"``

        .. note::

            These LXC configuration parameters will only have the desired
            effect if the container is using the LXC execution driver, which
            has been deprecated for some time.

    mac_address
        MAC address to use for the container. If not specified, a random MAC
        address will be used.

        Example: ``mac_address=01:23:45:67:89:0a``

    mem_limit (or *memory*) : 0
        Memory limit. Can be specified in bytes or using single-letter units
        (i.e. ``512M``, ``2G``, etc.). A value of ``0`` (the default) means no
        memory limit.

        Examples:

        - ``mem_limit=512M``
        - ``memory=1073741824``

    mem_swappiness
        Tune a container's memory swappiness behavior. Accepts an integer
        between 0 and 100.

        Example: ``mem_swappiness=60``

    memswap_limit (or *memory_swap*) : -1
        Total memory limit (memory plus swap). Set to ``-1`` to disable swap. A
        value of ``0`` means no swap limit.

        Examples:

        - ``memswap_limit=1G``
        - ``memory_swap=2147483648``

    network_disabled : False
        If ``True``, networking will be disabled within the container

        Example: ``network_disabled=True``

    network_mode : bridge
        One of the following:

        - ``bridge`` - Creates a new network stack for the container on the
          docker bridge
        - ``none`` - No networking (equivalent of the Docker CLI argument
          ``--net=none``). Not to be confused with Python's ``None``.
        - ``container:<name_or_id>`` - Reuses another container's network stack
        - ``host`` - Use the host's network stack inside the container

          .. warning::
              Using ``host`` mode gives the container full access to the hosts
              system's services (such as D-Bus), and is therefore considered
              insecure.

        Examples:

        - ``network_mode=null``
        - ``network_mode=container:web1``

    oom_kill_disable
        Whether to disable OOM killer

        Example: ``oom_kill_disable=False``

    oom_score_adj
        An integer value containing the score given to the container in order
        to tune OOM killer preferences

        Example: ``oom_score_adj=500``

    pid_mode
        Set to ``host`` to use the host container's PID namespace within the
        container. Requires Docker 1.5.0 or newer.

        Example: ``pid_mode=host``

    pids_limit
        Set the container's PID limit. Set to ``-1`` for unlimited.

        Example: ``pids_limit=2000``

    port_bindings (or *publish*)
        Bind exposed ports which were exposed using the ``ports`` argument to
        :py:func:`docker.create <salt.modules.docker.create>`. These
        should be passed in the same way as the ``--publish`` argument to the
        ``docker run`` CLI command:

        - ``ip:hostPort:containerPort`` - Bind a specific IP and port on the
          host to a specific port within the container.
        - ``ip::containerPort`` - Bind a specific IP and an ephemeral port to a
          specific port within the container.
        - ``hostPort:containerPort`` - Bind a specific port on all of the
          host's interfaces to a specific port within the container.
        - ``containerPort`` - Bind an ephemeral port on all of the host's
          interfaces to a specific port within the container.

        Multiple bindings can be separated by commas, or passed as a Python
        list. The below two examples are equivalent:

        - ``port_bindings="5000:5000,2123:2123/udp,8080"``
        - ``port_bindings="['5000:5000', '2123:2123/udp', 8080]"``

        Port bindings can also include ranges:

        - ``port_bindings="14505-14506:4505-4506"``

        .. note::
            When specifying a protocol, it must be passed in the
            ``containerPort`` value, as seen in the examples above.

    ports
        A list of ports to expose on the container. Can be passed as
        comma-separated list or a Python list. If the protocol is omitted, the
        port will be assumed to be a TCP port.

        Examples:

        - ``ports=1111,2222/udp``
        - ``ports="[1111, '2222/udp']"``

    privileged : False
        If ``True``, runs the exec process with extended privileges

        Example: ``privileged=True``

    publish_all_ports (or *publish_all*): False
        Publish all ports to the host

        Example: ``publish_all_ports=True``

    read_only : False
        If ``True``, mount the container’s root filesystem as read only

        Example: ``read_only=True``

    restart_policy (or *restart*)
        Set a restart policy for the container. Must be passed as a string in
        the format ``policy[:retry_count]`` where ``policy`` is one of
        ``always``, ``unless-stopped``, or ``on-failure``, and ``retry_count``
        is an optional limit to the number of retries. The retry count is ignored
        when using the ``always`` or ``unless-stopped`` restart policy.

        Examples:

        - ``restart_policy=on-failure:5``
        - ``restart_policy=always``

    security_opt
        Security configuration for MLS systems such as SELinux and AppArmor.
        Can be passed as a comma-separated list or a Python list.

        Examples:

        - ``security_opt=apparmor:unconfined,param2:value2``
        - ``security_opt='["apparmor:unconfined", "param2:value2"]'``

        .. important::
            Some security options can contain commas. In these cases, this
            argument *must* be passed as a Python list, as splitting by comma
            will result in an invalid configuration.

        .. note::
            See the documentation for security_opt at
            https://docs.docker.com/engine/reference/run/#security-configuration

    shm_size
        Size of /dev/shm

        Example: ``shm_size=128M``

    stop_signal
        The signal used to stop the container. The default is ``SIGTERM``.

        Example: ``stop_signal=SIGRTMIN+3``

    stop_timeout
        Timeout to stop the container, in seconds

        Example: ``stop_timeout=5``

    storage_opt
        Storage driver options for the container

        Examples:

        - ``storage_opt='dm.basesize=40G'``
        - ``storage_opt="['dm.basesize=40G']"``
        - ``storage_opt="{'dm.basesize': '40G'}"``

    sysctls (or *sysctl*)
        Set sysctl options for the container

        Examples:

        - ``sysctl='fs.nr_open=1048576,kernel.pid_max=32768'``
        - ``sysctls="['fs.nr_open=1048576', 'kernel.pid_max=32768']"``
        - ``sysctls="{'fs.nr_open': '1048576', 'kernel.pid_max': '32768'}"``

    tmpfs
        A map of container directories which should be replaced by tmpfs
        mounts, and their corresponding mount options. Can be passed as Python
        list of PATH:VALUE mappings, or a Python dictionary. However, since
        commas usually appear in the values, this option *cannot* be passed as
        a comma-separated list.

        Examples:

        - ``tmpfs="['/run:rw,noexec,nosuid,size=65536k', '/var/lib/mysql:rw,noexec,nosuid,size=600m']"``
        - ``tmpfs="{'/run': 'rw,noexec,nosuid,size=65536k', '/var/lib/mysql': 'rw,noexec,nosuid,size=600m'}"``

    tty : False
        Attach TTYs

        Example: ``tty=True``

    ulimits (or *ulimit*)
        List of ulimits. These limits should be passed in the format
        ``<ulimit_name>:<soft_limit>:<hard_limit>``, with the hard limit being
        optional. Can be passed as a comma-separated list or a Python list.

        Examples:

        - ``ulimits="nofile=1024:1024,nproc=60"``
        - ``ulimits="['nofile=1024:1024', 'nproc=60']"``

    user
        User under which to run exec process

        Example: ``user=foo``

    userns_mode (or *user_ns_mode*)
        Sets the user namsepace mode, when the user namespace remapping option
        is enabled.

        Example: ``userns_mode=host``

    volumes (or *volume*)
        List of directories to expose as volumes. Can be passed as a
        comma-separated list or a Python list.

        Examples:

        - ``volumes=/mnt/vol1,/mnt/vol2``
        - ``volume="['/mnt/vol1', '/mnt/vol2']"``

    volumes_from
        Container names or IDs from which the container will get volumes. Can
        be passed as a comma-separated list or a Python list.

        Example: ``volumes_from=foo``, ``volumes_from=foo,bar``,
        ``volumes_from="[foo, bar]"``

    volume_driver
        Sets the container's volume driver

        Example: ``volume_driver=foobar``

    working_dir (or *workdir*)
        Working directory inside the container

        Examples:

        - ``working_dir=/var/log/nginx``
        - ``workdir=/var/www/myapp``

    **RETURN DATA**

    A dictionary containing the following keys:

    - ``Id`` - ID of the newly-created container
    - ``Name`` - Name of the newly-created container


    CLI Example:

    .. code-block:: bash

        # Create a data-only container
        salt myminion docker.create myuser/mycontainer volumes="/mnt/vol1,/mnt/vol2"
        # Create a CentOS 7 container that will stay running once started
        salt myminion docker.create centos:7 name=mycent7 interactive=True tty=True command=bash
    '''
    try:
        # Try to inspect the image, if it fails then we know we need to pull it
        # first.
        inspect_image(image)
    except Exception:
        pull(image, client_timeout=client_timeout)

    if name is not None and kwargs.get('hostname') is None:
        kwargs['hostname'] = name

    kwargs, unused_kwargs = _get_create_kwargs(
        image=image,
        skip_translate=skip_translate,
        ignore_collisions=ignore_collisions,
        **kwargs)

    if unused_kwargs:
        log.warning(
            'The following arguments were ignored because they are not '
            'recognized by docker-py: %s', sorted(unused_kwargs)
        )

    log.debug(
        'docker.create: creating container %susing the following '
        'arguments: %s',
        'with name \'{0}\' '.format(name) if name is not None else '',
        kwargs
    )
    time_started = time.time()
    response = _client_wrapper('create_container', image, name=name, **kwargs)
    response['Time_Elapsed'] = time.time() - time_started
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

        salt myminion docker.copy_from mycontainer /var/log/nginx/access.log /home/myuser
    '''
    c_state = state(name)
    if c_state != 'running':
        raise CommandExecutionError(
            'Container \'{0}\' is not running'.format(name)
        )

    # Destination file sanity checks
    if not os.path.isabs(dest):
        raise SaltInvocationError('Destination path must be absolute')
    if os.path.isdir(dest):
        # Destination is a directory, full path to dest file will include the
        # basename of the source file.
        dest = os.path.join(dest, os.path.basename(source))
        dest_dir = dest
    else:
        # Destination was not a directory. We will check to see if the parent
        # dir is a directory, and then (if makedirs=True) attempt to create the
        # parent directory.
        dest_dir = os.path.split(dest)[0]
        if not os.path.isdir(dest_dir):
            if makedirs:
                try:
                    os.makedirs(dest_dir)
                except OSError as exc:
                    raise CommandExecutionError(
                        'Unable to make destination directory {0}: {1}'
                        .format(dest_dir, exc)
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
        log.debug(
            '%s:%s and %s are the same file, skipping copy',
            name, source, dest
        )
        return True

    log.debug(
        'Copying %s from container \'%s\' to local path %s',
        source, name, dest
    )

    try:
        src_path = ':'.join((name, source))
    except TypeError:
        src_path = '{0}:{1}'.format(name, source)
    cmd = ['docker', 'cp', src_path, dest_dir]
    __salt__['cmd.run'](cmd, python_shell=False)
    return source_md5 == __salt__['file.get_sum'](dest, 'md5')


# Docker cp gets a file from the container, alias this to copy_from
cp = salt.utils.alias_function(copy_from, 'cp')


@_ensure_exists
def copy_to(name,
            source,
            dest,
            exec_driver=None,
            overwrite=False,
            makedirs=False):
    '''
    Copy a file from the host into a container

    name
        Container name

    source
        File to be copied to the container. Can be a local path on the Minion
        or a remote file from the Salt fileserver.

    dest
        Destination on the container. Must be an absolute path. If the
        destination is a directory, the file will be copied into that
        directory.

    exec_driver : None
        If not passed, the execution driver will be detected as described
        :ref:`above <docker-execution-driver>`.

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

        salt myminion docker.copy_to mycontainer /tmp/foo /root/foo
    '''
    return __salt__['container_resource.copy_to'](
        name,
        __salt__['container_resource.cache_file'](source),
        dest,
        container_type=__virtualname__,
        exec_driver=exec_driver,
        overwrite=overwrite,
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

        salt myminion docker.export mycontainer /tmp/mycontainer.tar
        salt myminion docker.export mycontainer /tmp/mycontainer.tar.xz push=True
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
            # filehandle here. We make sure to close it in the "finally" block
            # below.
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


@_refresh_mine_cache
@_ensure_exists
def rm_(name, force=False, volumes=False, **kwargs):
    '''
    Removes a container

    name
        Container name or ID

    force : False
        If ``True``, the container will be killed first before removal, as the
        Docker API will not permit a running container to be removed. This
        option is set to ``False`` by default to prevent accidental removal of
        a running container.

    stop : False
        If ``True``, the container will be stopped first before removal, as the
        Docker API will not permit a running container to be removed. This
        option is set to ``False`` by default to prevent accidental removal of
        a running container.

        .. versionadded:: Nitrogen

    volumes : False
        Also remove volumes associated with container


    **RETURN DATA**

    A list of the IDs of containers which were removed


    CLI Example:

    .. code-block:: bash

        salt myminion docker.rm mycontainer
        salt myminion docker.rm mycontainer force=True
    '''
    kwargs = salt.utils.clean_kwargs(**kwargs)
    stop_ = kwargs.pop('stop', False)
    if kwargs:
        salt.utils.invalid_kwargs(kwargs)

    if state(name) == 'running' and not (force or stop_):
        raise CommandExecutionError(
            'Container \'{0}\' is running, use force=True to forcibly '
            'remove this container'.format(name)
        )
    if stop_ and not force:
        stop(name)
    pre = ps_(all=True)
    _client_wrapper('remove_container', name, v=volumes, force=force)
    _clear_context()
    return [x for x in pre if x not in ps_(all=True)]


def rename(name, new_name):
    '''
    .. versionadded:: Nitrogen

    Renames a container. Returns ``True`` if successful, and raises an error if
    the API returns one. If unsuccessful and the API returns no error (should
    not happen), then ``False`` will be returned.

    name
        Name or ID of existing container

    new_name
        New name to assign to container

    CLI Example:

    .. code-block:: bash

        salt myminion docker.rename foo bar
    '''
    id_ = inspect_container(name)['Id']
    log.debug('Renaming container \'%s\' (ID: %s) to \'%s\'', name, id_, new_name)
    _client_wrapper('rename', id_, new_name)
    # Confirm that the ID of the container corresponding to the new name is the
    # same as it was before.
    return inspect_container(new_name)['Id'] == id_


# Functions to manage images
def build(path=None,
          image=None,
          cache=True,
          rm=True,
          api_response=False,
          fileobj=None,
          dockerfile=None,
          buildargs=None):
    '''
    Builds a docker image from a Dockerfile or a URL

    path
        Path to directory on the Minion containing a Dockerfile

    image
        Image to be built, in ``repo:tag`` notation. If just the repository
        name is passed, a tag name of ``latest`` will be assumed. If building
        from a URL, this parameted can be omitted.

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

    dockerfile
        Allows for an alternative Dockerfile to be specified.  Path to alternative
        Dockefile is relative to the build path for the Docker container.

        .. versionadded:: develop

    buildargs
        A dictionary of build arguments provided to the docker build process.


    **RETURN DATA**

    A dictionary containing one or more of the following keys:

    - ``Id`` - ID of the newly-built image
    - ``Time_Elapsed`` - Time in seconds taken to perform the build
    - ``Intermediate_Containers`` - IDs of containers created during the course
      of the build process

      *(Only present if rm=False)*
    - ``Images`` - A dictionary containing one or more of the following keys:
        - ``Already_Pulled`` - Layers that that were already present on the
          Minion
        - ``Pulled`` - Layers that that were pulled

      *(Only present if the image specified by the "image" argument was not
      present on the Minion, or if cache=False)*
    - ``Status`` - A string containing a summary of the pull action (usually a
      message saying that an image was downloaded, or that it was up to date).

      *(Only present if the image specified by the "image" argument was not
      present on the Minion, or if cache=False)*


    CLI Example:

    .. code-block:: bash

        salt myminion docker.build /path/to/docker/build/dir image=myimage:dev
        salt myminion docker.build https://github.com/myuser/myrepo.git image=myimage:latest

        .. versionadded:: develop

        salt myminion docker.build /path/to/docker/build/dir dockerfile=Dockefile.different image=myimage:dev
    '''
    _prep_pull()

    image = ':'.join(salt.utils.docker.get_repo_tag(image))
    time_started = time.time()
    response = _client_wrapper('build',
                               path=path,
                               tag=image,
                               quiet=False,
                               fileobj=fileobj,
                               rm=rm,
                               nocache=not cache,
                               dockerfile=dockerfile,
                               buildargs=buildargs)
    ret = {'Time_Elapsed': time.time() - time_started}
    _clear_context()

    if not response:
        raise CommandExecutionError(
            'Build failed for {0}, no response returned from Docker API'
            .format(image)
        )

    stream_data = []
    for line in response:
        stream_data.extend(json.loads(line, cls=DockerJSONDecoder))
    errors = []
    # Iterate through API response and collect information
    for item in stream_data:
        try:
            item_type = next(iter(item))
        except StopIteration:
            continue
        if item_type == 'status':
            _pull_status(ret, item)
        if item_type == 'stream':
            _build_status(ret, item)
        elif item_type == 'errorDetail':
            _error_detail(errors, item)

    if 'Id' not in ret:
        # API returned information, but there was no confirmation of a
        # successful build.
        msg = 'Build failed for {0}'.format(image)
        log.error(msg)
        log.error(stream_data)
        if errors:
            msg += '. Error(s) follow:\n\n{0}'.format(
                '\n\n'.join(errors)
            )
        raise CommandExecutionError(msg)

    for image_id, image_info in six.iteritems(images()):
        if image_id.startswith(ret['Id']):
            if image in image_info.get('RepoTags', []):
                ret['Image'] = image
            else:
                ret['Warning'] = \
                    'Failed to tag image as {0}'.format(image)

    if api_response:
        ret['API_Response'] = stream_data

    if rm:
        ret.pop('Intermediate_Containers', None)
    return ret


def commit(name,
           image,
           message=None,
           author=None):
    '''
    Commits a container, thereby promoting it to an image. Equivalent to
    running the ``docker commit`` Docker CLI command.

    name
        Container name or ID to commit

    image
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

        salt myminion docker.commit mycontainer myuser/myimage
        salt myminion docker.commit mycontainer myuser/myimage:mytag
    '''
    repo_name, repo_tag = salt.utils.docker.get_repo_tag(image)
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

    ret['Image'] = image
    ret['Id'] = image_id
    return ret


def dangling(prune=False, force=False):
    '''
    Return top-level images (those on which no other images depend) which do
    not have a tag assigned to them. These include:

    - Images which were once tagged but were later untagged, such as those
      which were superseded by committing a new copy of an existing tagged
      image.
    - Images which were loaded using :py:func:`docker.load
      <salt.modules.docker.load>` (or the ``docker load`` Docker CLI
      command), but not tagged.

    prune : False
        Remove these images

    force : False
        If ``True``, and if ``prune=True``, then forcibly remove these images.

    **RETURN DATA**

    If ``prune=False``, the return data will be a list of dangling image IDs.

    If ``prune=True``, the return data will be a dictionary with each key being
    the ID of the dangling image, and the following information for each image:

    - ``Comment`` - Any error encountered when trying to prune a dangling image

      *(Only present if prune failed)*
    - ``Removed`` - A boolean (``True`` if prune was successful, ``False`` if
      not)


    CLI Example:

    .. code-block:: bash

        salt myminion docker.dangling
        salt myminion docker.dangling prune=True
    '''
    all_images = images(all=True)
    dangling_images = [x[:12] for x in _get_top_level_images(all_images)
                       if all_images[x]['RepoTags'] is None]
    if not prune:
        return dangling_images

    ret = {}
    for image in dangling_images:
        try:
            ret.setdefault(image, {})['Removed'] = rmi(image, force=force)
        except Exception as exc:
            err = exc.__str__()
            log.error(err)
            ret.setdefault(image, {})['Comment'] = err
            ret[image]['Removed'] = False
    return ret


def import_(source,
            image,
            api_response=False):
    '''
    Imports content from a local tarball or a URL as a new docker image

    source
        Content to import (URL or absolute path to a tarball).  URL can be a
        file on the Salt fileserver (i.e.
        ``salt://path/to/rootfs/tarball.tar.xz``. To import a file from a
        saltenv other than ``base`` (e.g. ``dev``), pass it at the end of the
        URL (ex. ``salt://path/to/rootfs/tarball.tar.xz?saltenv=dev``).

    image
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

        salt myminion docker.import /tmp/cent7-minimal.tar.xz myuser/centos
        salt myminion docker.import /tmp/cent7-minimal.tar.xz myuser/centos:7
        salt myminion docker.import salt://dockerimages/cent7-minimal.tar.xz myuser/centos:7
    '''
    repo_name, repo_tag = salt.utils.docker.get_repo_tag(image)
    path = __salt__['container_resource.cache_file'](source)

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
        try:
            item_type = next(iter(item))
        except StopIteration:
            continue
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


def load(path, image=None):
    '''
    Load a tar archive that was created using :py:func:`docker.save
    <salt.modules.docker.save>` (or via the Docker CLI using ``docker save``).

    path
        Path to docker tar archive. Path can be a file on the Minion, or the
        URL of a file on the Salt fileserver (i.e.
        ``salt://path/to/docker/saved/image.tar``). To load a file from a
        saltenv other than ``base`` (e.g. ``dev``), pass it at the end of the
        URL (ex. ``salt://path/to/rootfs/tarball.tar.xz?saltenv=dev``).

    image : None
        If specified, the topmost layer of the newly-loaded image will be
        tagged with the specified repo and tag using :py:func:`docker.tag
        <salt.modules.docker.tag_>`. The image name should be specified in
        ``repo:tag`` notation. If just the repository name is passed, a tag
        name of ``latest`` will be assumed.


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``Path`` - Path of the file that was saved
    - ``Layers`` - A list containing the IDs of the layers which were loaded.
      Any layers in the file that was loaded, which were already present on the
      Minion, will not be included.
    - ``Image`` - Name of tag applied to topmost layer

      *(Only present if tag was specified and tagging was successful)*
    - ``Time_Elapsed`` - Time in seconds taken to load the file
    - ``Warning`` - Message describing any problems encountered in attemp to
      tag the topmost layer

      *(Only present if tag was specified and tagging failed)*


    CLI Example:

    .. code-block:: bash

        salt myminion docker.load /path/to/image.tar
        salt myminion docker.load salt://path/to/docker/saved/image.tar image=myuser/myimage:mytag
    '''
    if image is not None:
        image = ':'.join(salt.utils.docker.get_repo_tag(image))
    local_path = __salt__['container_resource.cache_file'](path)
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
    top_level_images = _get_top_level_images(post, subset=new_layers)
    if image:
        if len(top_level_images) > 1:
            ret['Warning'] = (
                'More than one top-level image layer was loaded ({0}), no '
                'image was tagged'.format(', '.join(top_level_images))
            )
        else:
            try:
                result = tag_(top_level_images[0], image=image)
                ret['Image'] = image
            except IndexError:
                ret['Warning'] = ('No top-level image layers were loaded, no '
                                  'image was tagged')
            except Exception as exc:
                ret['Warning'] = ('Failed to tag {0} as {1}: {2}'
                                  .format(top_level_images[0], image, exc))
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

        salt myminion docker.layers centos:7
    '''
    ret = []
    cmd = ['docker', 'history', '-q', name]
    for line in reversed(
            __salt__['cmd.run_stdout'](cmd, python_shell=False).splitlines()):
        ret.append(line)
    if not ret:
        raise CommandExecutionError('Image \'{0}\' not found'.format(name))
    return ret


def pull(image,
         insecure_registry=False,
         api_response=False,
         client_timeout=salt.utils.docker.CLIENT_TIMEOUT):
    '''
    Pulls an image from a Docker registry. See the documentation at the top of
    this page to configure authenticated access.

    image
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

        salt myminion docker.pull centos
        salt myminion docker.pull centos:6
    '''
    _prep_pull()

    repo_name, repo_tag = salt.utils.docker.get_repo_tag(image)
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
            .format(image)
        )
    elif api_response:
        ret['API_Response'] = response

    errors = []
    # Iterate through API response and collect information
    for item in response:
        try:
            item_type = next(iter(item))
        except StopIteration:
            continue
        if item_type == 'status':
            _pull_status(ret, item)
        elif item_type == 'errorDetail':
            _error_detail(errors, item)

    try:
        inspect_image('{0}'.format(image))
    except Exception:
        # API returned information, but the image can't be found
        msg = 'Pull failed for {0}'.format(image)
        if errors:
            msg += '. Error(s) follow:\n\n{0}'.format(
                '\n\n'.join(errors)
            )
        raise CommandExecutionError(msg)

    return ret


def push(image,
         insecure_registry=False,
         api_response=False,
         client_timeout=salt.utils.docker.CLIENT_TIMEOUT):
    '''
    .. versionchanged:: 2015.8.4
        The ``Id`` and ``Image`` keys are no longer present in the return data.
        This is due to changes in the Docker Remote API.

    Pushes an image to a Docker registry. See the documentation at top of this
    page to configure authenticated access.

    image
        Image to be pushed, in ``repo:tag`` notation.

        .. versionchanged:: 2015.8.4
            If just the repository name is passed, then all tagged images for
            the specified repo will be pushed. In prior releases, a tag of
            ``latest`` was assumed if the tag was omitted.

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

    - ``Layers`` - A dictionary containing one or more of the following keys:
        - ``Already_Pushed`` - Layers that that were already present on the
          Minion
        - ``Pushed`` - Layers that that were pushed
    - ``Time_Elapsed`` - Time in seconds taken to perform the push


    CLI Example:

    .. code-block:: bash

        salt myminion docker.push myuser/mycontainer
        salt myminion docker.push myuser/mycontainer:mytag
    '''
    if ':' in image:
        repo_name, repo_tag = salt.utils.docker.get_repo_tag(image)
    else:
        repo_name = image
        repo_tag = None
        log.info('Attempting to push all tagged images matching %s', repo_name)

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
            .format(image)
        )
    elif api_response:
        ret['API_Response'] = response

    errors = []
    # Iterate through API response and collect information
    for item in response:
        try:
            item_type = next(iter(item))
        except StopIteration:
            continue
        if item_type == 'status':
            _push_status(ret, item)
        elif item_type == 'errorDetail':
            _error_detail(errors, item)

    return ret


def rmi(*names, **kwargs):
    '''
    Removes an image

    name
        Name (in ``repo:tag`` notation) or ID of image.

    force : False
        If ``True``, the image will be removed even if the Minion has
        containers created from that image

    prune : True
        If ``True``, untagged parent image layers will be removed as well, set
        this to ``False`` to keep them.


    **RETURN DATA**

    A dictionary will be returned, containing the following two keys:

    - ``Layers`` - A list of the IDs of image layers that were removed
    - ``Tags`` - A list of the tags that were removed
    - ``Errors`` - A list of any errors that were encountered


    CLI Examples:

    .. code-block:: bash

        salt myminion docker.rmi busybox
        salt myminion docker.rmi busybox force=True
        salt myminion docker.rmi foo bar baz
    '''
    pre_images = images(all=True)
    pre_tags = list_tags()
    force = kwargs.get('force', False)
    noprune = not kwargs.get('prune', True)

    errors = []
    for name in names:
        image_id = inspect_image(name)['Id']
        try:
            _client_wrapper('remove_image',
                            image_id,
                            force=force,
                            noprune=noprune,
                            catch_api_errors=False)
        except docker.errors.APIError as exc:
            if exc.response.status_code == 409:
                err = ('Unable to remove image \'{0}\' because it is in '
                       'use by '.format(name))
                deps = depends(name)
                if deps['Containers']:
                    err += 'container(s): {0}'.format(
                        ', '.join(deps['Containers'])
                    )
                if deps['Images']:
                    if deps['Containers']:
                        err += ' and '
                    err += 'image(s): {0}'.format(', '.join(deps['Images']))
                errors.append(err)
            else:
                errors.append('Error {0}: {1}'.format(exc.response.status_code,
                                                      exc.explanation))

    _clear_context()
    ret = {'Layers': [x for x in pre_images if x not in images(all=True)],
           'Tags': [x for x in pre_tags if x not in list_tags()]}
    if errors:
        ret['Errors'] = errors
    return ret


def save(name,
         path,
         overwrite=False,
         makedirs=False,
         compression=None,
         **kwargs):
    '''
    Saves an image and to a file on the minion. Equivalent to running the
    ``docker save`` Docker CLI command, but unlike ``docker save`` this will
    also work on named images instead of just images IDs.

    name
        Name or ID of image. Specify a specific tag by using the ``repo:tag``
        notation.

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
            :py:func:`docker.export <salt.modules.docker.export>` since the
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

        salt myminion docker.save centos:7 /tmp/cent7.tar
        salt myminion docker.save 0123456789ab cdef01234567 /tmp/saved.tar
    '''
    err = 'Path \'{0}\' is not absolute'.format(path)
    try:
        if not os.path.isabs(path):
            raise SaltInvocationError(err)
    except AttributeError:
        raise SaltInvocationError(err)

    if os.path.exists(path) and not overwrite:
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
        if not makedirs:
            raise CommandExecutionError(
                'Parent dir \'{0}\' of destination path does not exist. Use '
                'makedirs=True to create it.'.format(parent_dir)
            )

    if compression:
        saved_path = salt.utils.files.mkstemp()
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
                    # method to open the filehandle. If not using gzip, we need
                    # to open the filehandle here.
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


def tag_(name, image, force=False):
    '''
    Tag an image into a repository and return ``True``. If the tag was
    unsuccessful, an error will be raised.

    name
        ID of image

    image
        Tag to apply to the image, in ``repo:tag`` notation. If just the
        repository name is passed, a tag name of ``latest`` will be assumed.

    force : False
        Force apply tag

    CLI Example:

    .. code-block:: bash

        salt myminion docker.tag 0123456789ab myrepo/mycontainer
        salt myminion docker.tag 0123456789ab myrepo/mycontainer:mytag
    '''
    image_id = inspect_image(name)['Id']
    repo_name, repo_tag = salt.utils.docker.get_repo_tag(image)
    response = _client_wrapper('tag',
                               image_id,
                               repo_name,
                               tag=repo_tag,
                               force=force)
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response

# Network Management


@_api_version(1.21)
@_client_version('1.5.0')
def networks(names=None, ids=None):
    '''
    List existing networks

    names
        Filter by name

    ids
        Filter by id

    CLI Example:

    .. code-block:: bash

        salt myminion docker.networks names="['network-web']"
        salt myminion docker.networks ids="['1f9d2454d0872b68dd9e8744c6e7a4c66b86f10abaccc21e14f7f014f729b2bc']"
    '''
    response = _client_wrapper('networks',
                               names=names,
                               ids=ids,
                               )
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response


@_api_version(1.21)
@_client_version('1.5.0')
def create_network(name, driver=None):
    '''
    Create a new network

    network_id
        ID of network

    driver
        Driver of the network

    CLI Example:

    .. code-block:: bash

        salt myminion docker.create_network web_network driver=bridge
    '''
    response = _client_wrapper('create_network', name, driver=driver)
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response


@_api_version(1.21)
@_client_version('1.5.0')
def remove_network(network_id):
    '''
    Remove a network

    network_id
        ID of network

    CLI Example:

    .. code-block:: bash

        salt myminion docker.remove_network 1f9d2454d0872b68dd9e8744c6e7a4c66b86f10abaccc21e14f7f014f729b2bc
    '''
    response = _client_wrapper('remove_network', network_id)
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response


@_api_version(1.21)
@_client_version('1.5.0')
def inspect_network(network_id):
    '''
    Inspect Network

    network_id
        ID of network

    CLI Example:

    .. code-block:: bash

        salt myminion docker.inspect_network 1f9d2454d0872b68dd9e8744c6e7a4c66b86f10abaccc21e14f7f014f729b2bc
    '''
    response = _client_wrapper('inspect_network', network_id)
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response


@_api_version(1.21)
@_client_version('1.5.0')
def connect_container_to_network(container, network_id, ipv4_address=None):
    '''
    Connect container to network.

    container
        Container name or ID

    network_id
        ID of network

    ipv4_address
        The IPv4 address to connect to the container

    CLI Example:

    .. code-block:: bash

        salt myminion docker.connect_container_from_network web-1 1f9d2454d0872b68dd9e8744c6e7a4c66b86f10abaccc21e14f7f014f729b2bc
    '''
    response = _client_wrapper('connect_container_to_network',
                               container,
                               network_id,
                               ipv4_address)
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response


@_api_version(1.21)
@_client_version('1.5.0')
def disconnect_container_from_network(container, network_id):
    '''
    Disconnect container from network.

    container
        Container name or ID

    network_id
        ID of network

    CLI Example:

    .. code-block:: bash

        salt myminion docker.disconnect_container_from_network web-1 1f9d2454d0872b68dd9e8744c6e7a4c66b86f10abaccc21e14f7f014f729b2bc
    '''
    response = _client_wrapper('disconnect_container_from_network',
                               container,
                               network_id)
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response

# Volume Management


@_api_version(1.21)
@_client_version('1.5.0')
def volumes(filters=None):
    '''
    List existing volumes

    .. versionadded:: 2015.8.4

    filters
      There is one available filter: dangling=true

    CLI Example:

    .. code-block:: bash

        salt myminion docker.volumes filters="{'dangling': True}"
    '''
    response = _client_wrapper('volumes', filters=filters)
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response


@_api_version(1.21)
@_client_version('1.5.0')
def create_volume(name, driver=None, driver_opts=None):
    '''
    Create a new volume

    .. versionadded:: 2015.8.4

    name
        name of volume

    driver
        Driver of the volume

    driver_opts
        Options for the driver volume

    CLI Example:

    .. code-block:: bash

        salt myminion docker.create_volume my_volume driver=local
    '''
    response = _client_wrapper('create_volume', name, driver=driver,
                               driver_opts=driver_opts)
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response


@_api_version(1.21)
@_client_version('1.5.0')
def remove_volume(name):
    '''
    Remove a volume

    .. versionadded:: 2015.8.4

    name
        Name of volume

    CLI Example:

    .. code-block:: bash

        salt myminion docker.remove_volume my_volume
    '''
    response = _client_wrapper('remove_volume', name)
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response


@_api_version(1.21)
@_client_version('1.5.0')
def inspect_volume(name):
    '''
    Inspect Volume

    .. versionadded:: 2015.8.4

    name
      Name of volume

    CLI Example:

    .. code-block:: bash

        salt myminion docker.inspect_volume my_volume
    '''
    response = _client_wrapper('inspect_volume', name)
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response


# Functions to manage container state
@_refresh_mine_cache
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

        salt myminion docker.kill mycontainer
    '''
    return _change_state(name, 'kill', 'stopped')


@_refresh_mine_cache
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

        salt myminion docker.pause mycontainer
    '''
    orig_state = state(name)
    if orig_state == 'stopped':
        return {'result': False,
                'state': {'old': orig_state, 'new': orig_state},
                'comment': ('Container \'{0}\' is stopped, cannot pause'
                            .format(name))}
    return _change_state(name, 'pause', 'paused')

freeze = salt.utils.alias_function(pause, 'freeze')


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

        salt myminion docker.restart mycontainer
        salt myminion docker.restart mycontainer timeout=20
    '''
    ret = _change_state(name, 'restart', 'running', timeout=timeout)
    if ret['result']:
        ret['restarted'] = True
    return ret


@_refresh_mine_cache
@_ensure_exists
def signal_(name, signal):
    '''
    Send a signal to a container. Signals can be either strings or numbers, and
    are defined in the **Standard Signals** section of the ``signal(7)``
    manpage. Run ``man 7 signal`` on a Linux host to browse this manpage.

    name
        Container name or ID

    signal
        Signal to send to container

    **RETURN DATA**

    If the signal was successfully sent, ``True`` will be returned. Otherwise,
    an error will be raised.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.signal mycontainer SIGHUP
    '''
    _client_wrapper('kill', name, signal=signal)
    return True


@_refresh_mine_cache
@_ensure_exists
def start(name):
    '''
    Start a container

    name
        Container name or ID

    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``comment`` - Only present if the container cannot be started


    CLI Example:

    .. code-block:: bash

        salt myminion docker.start mycontainer
    '''
    orig_state = state(name)
    if orig_state == 'paused':
        return {'result': False,
                'state': {'old': orig_state, 'new': orig_state},
                'comment': ('Container \'{0}\' is paused, cannot start'
                            .format(name))}

    return _change_state(name, 'start', 'running')


@_refresh_mine_cache
@_ensure_exists
def stop(name, timeout=None, **kwargs):
    '''
    Stops a running container

    name
        Container name or ID

    unpause : False
        If ``True`` and the container is paused, it will be unpaused before
        attempting to stop the container.

    timeout
        Timeout in seconds after which the container will be killed (if it has
        not yet gracefully shut down)

        .. versionchanged:: Nitrogen
            If this argument is not passed, then the container's configuration
            will be checked. If the container was created using the
            ``stop_timeout`` argument, then the configured timeout will be
            used, otherwise the timeout will be 10 seconds.

    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``comment`` - Only present if the container can not be stopped


    CLI Examples:

    .. code-block:: bash

        salt myminion docker.stop mycontainer
        salt myminion docker.stop mycontainer unpause=True
        salt myminion docker.stop mycontainer timeout=20
    '''
    if timeout is None:
        try:
            # Get timeout from container config
            timeout = inspect_container(name)['Config']['StopTimeout']
        except KeyError:
            # Fall back to a global default defined in salt.utils.docker
            timeout = salt.utils.docker.SHUTDOWN_TIMEOUT

    orig_state = state(name)
    if orig_state == 'paused':
        if kwargs.get('unpause', False):
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


@_refresh_mine_cache
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

        salt myminion docker.pause mycontainer
    '''
    orig_state = state(name)
    if orig_state == 'stopped':
        return {'result': False,
                'state': {'old': orig_state, 'new': orig_state},
                'comment': ('Container \'{0}\' is stopped, cannot unpause'
                            .format(name))}
    return _change_state(name, 'unpause', 'running')

unfreeze = salt.utils.alias_function(unpause, 'unfreeze')


def wait(name, ignore_already_stopped=False, fail_on_exit_status=False):
    '''
    Wait for the container to exit gracefully, and return its exit code

    .. note::

        This function will block until the container is stopped.

    name
        Container name or ID

    ignore_already_stopped
        Boolean flag that prevent execution to fail, if a container
        is already stopped.

    fail_on_exit_status
        Boolean flag to report execution as failure if ``exit_status``
        is different than 0.

    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``exit_status`` - Exit status for the container
    - ``comment`` - Only present if the container is already stopped


    CLI Example:

    .. code-block:: bash

        salt myminion docker.wait mycontainer
    '''
    try:
        pre = state(name)
    except CommandExecutionError:
        # Container doesn't exist anymore
        return {'result': ignore_already_stopped,
                'comment': 'Container \'{0}\' absent'.format(name)}
    already_stopped = pre == 'stopped'
    response = _client_wrapper('wait', name)
    _clear_context()
    try:
        post = state(name)
    except CommandExecutionError:
        # Container doesn't exist anymore
        post = None

    if already_stopped:
        success = ignore_already_stopped
    elif post == 'stopped':
        success = True
    else:
        success = False

    result = {'result': success,
              'state': {'old': pre, 'new': post},
              'exit_status': response}
    if already_stopped:
        result['comment'] = 'Container \'{0}\' already stopped'.format(name)
    if fail_on_exit_status and result['result']:
        result['result'] = result['exit_status'] == 0
    return result


# Functions to run commands inside containers
@_refresh_mine_cache
@_ensure_exists
def _run(name,
         cmd,
         exec_driver=None,
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
    if exec_driver is None:
        exec_driver = _get_exec_driver()
    ret = __salt__['container_resource.run'](
        name,
        cmd,
        container_type=__virtualname__,
        exec_driver=exec_driver,
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


@_refresh_mine_cache
def _script(name,
            source,
            saltenv='base',
            args=None,
            template=None,
            exec_driver=None,
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
        '''
        Remove the tempfile allocated for the script
        '''
        try:
            os.remove(path)
        except (IOError, OSError) as exc:
            log.error(
                'cmd.script: Unable to clean tempfile \'%s\': %s',
                path, exc
            )

    path = salt.utils.files.mkstemp(dir='/tmp',
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

    if exec_driver is None:
        exec_driver = _get_exec_driver()

    copy_to(name, path, path, exec_driver=exec_driver)
    run(name, 'chmod 700 ' + path)

    ret = run_all(
        name,
        path + ' ' + str(args) if args else path,
        exec_driver=exec_driver,
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
            exec_driver=None,
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

    exec_driver : None
        If not passed, the execution driver will be detected as described
        :ref:`above <docker-execution-driver>`.

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

        salt myminion docker.retcode mycontainer 'ls -l /etc'
    '''
    return _run(name,
                cmd,
                exec_driver=exec_driver,
                output='retcode',
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def run(name,
        cmd,
        exec_driver=None,
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

    exec_driver : None
        If not passed, the execution driver will be detected as described
        :ref:`above <docker-execution-driver>`.

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

        salt myminion docker.run mycontainer 'ls -l /etc'
    '''
    return _run(name,
                cmd,
                exec_driver=exec_driver,
                output=None,
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def run_all(name,
            cmd,
            exec_driver=None,
            stdin=None,
            python_shell=True,
            output_loglevel='debug',
            use_vt=False,
            ignore_retcode=False,
            keep_env=None):
    '''
    Run :py:func:`cmd.run_all <salt.modules.cmdmod.run_all>` within a container

    .. note::

        While the command is run within the container, it is initiated from the
        host. Therefore, the PID in the return dict is from the host, not from
        the container.

    name
        Container name or ID in which to run the command

    cmd
        Command to run

    exec_driver : None
        If not passed, the execution driver will be detected as described
        :ref:`above <docker-execution-driver>`.

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

        salt myminion docker.run_all mycontainer 'ls -l /etc'
    '''
    return _run(name,
                cmd,
                exec_driver=exec_driver,
                output='all',
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def run_stderr(name,
               cmd,
               exec_driver=None,
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

    exec_driver : None
        If not passed, the execution driver will be detected as described
        :ref:`above <docker-execution-driver>`.

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

        salt myminion docker.run_stderr mycontainer 'ls -l /etc'
    '''
    return _run(name,
                cmd,
                exec_driver=exec_driver,
                output='stderr',
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def run_stdout(name,
               cmd,
               exec_driver=None,
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

    exec_driver : None
        If not passed, the execution driver will be detected as described
        :ref:`above <docker-execution-driver>`.

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

        salt myminion docker.run_stdout mycontainer 'ls -l /etc'
    '''
    return _run(name,
                cmd,
                exec_driver=exec_driver,
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
           exec_driver=None,
           stdin=None,
           python_shell=True,
           output_loglevel='debug',
           ignore_retcode=False,
           use_vt=False,
           keep_env=None):
    '''
    Run :py:func:`cmd.script <salt.modules.cmdmod.script>` within a container

    .. note::

        While the command is run within the container, it is initiated from the
        host. Therefore, the PID in the return dict is from the host, not from
        the container.

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

    exec_driver : None
        If not passed, the execution driver will be detected as described
        :ref:`above <docker-execution-driver>`.

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

        salt myminion docker.script mycontainer salt://docker_script.py
        salt myminion docker.script mycontainer salt://scripts/runme.sh 'arg1 arg2 "arg 3"'
        salt myminion docker.script mycontainer salt://scripts/runme.sh stdin='one\\ntwo\\nthree\\nfour\\nfive\\n' output_loglevel=quiet
    '''
    return _script(name,
                   source,
                   saltenv=saltenv,
                   args=args,
                   template=template,
                   exec_driver=exec_driver,
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
                   exec_driver=None,
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

    exec_driver : None
        If not passed, the execution driver will be detected as described
        :ref:`above <docker-execution-driver>`.

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

        salt myminion docker.script_retcode mycontainer salt://docker_script.py
        salt myminion docker.script_retcode mycontainer salt://scripts/runme.sh 'arg1 arg2 "arg 3"'
        salt myminion docker.script_retcode mycontainer salt://scripts/runme.sh stdin='one\\ntwo\\nthree\\nfour\\nfive\\n' output_loglevel=quiet
    '''
    return _script(name,
                   source,
                   saltenv=saltenv,
                   args=args,
                   template=template,
                   exec_driver=exec_driver,
                   stdin=stdin,
                   python_shell=python_shell,
                   output_loglevel=output_loglevel,
                   ignore_retcode=ignore_retcode,
                   use_vt=use_vt,
                   keep_env=keep_env)['retcode']


def _mk_fileclient():
    '''
    Create a file client and add it to the context.
    '''
    if 'cp.fileclient' not in __context__:
        __context__['cp.fileclient'] = salt.fileclient.get_file_client(__opts__)


def _generate_tmp_path():
    return os.path.join(
        '/tmp',
        'salt.docker.{0}'.format(uuid.uuid4().hex[:6]))


def _prepare_trans_tar(name, mods=None, saltenv='base', pillar=None):
    '''
    Prepares a self contained tarball that has the state
    to be applied in the container
    '''
    chunks = _compile_state(mods, saltenv)
    # reuse it from salt.ssh, however this function should
    # be somewhere else
    refs = salt.client.ssh.state.lowstate_file_refs(chunks)
    _mk_fileclient()
    trans_tar = salt.client.ssh.state.prep_trans_tar(
        __opts__,
        __context__['cp.fileclient'],
        chunks, refs, pillar, name)
    return trans_tar


def _compile_state(mods=None, saltenv='base'):
    '''
    Generates the chunks of lowdata from the list of modules
    '''
    st_ = HighState(__opts__)

    high_data, errors = st_.render_highstate({saltenv: mods})
    high_data, ext_errors = st_.state.reconcile_extend(high_data)
    errors += ext_errors
    errors += st_.state.verify_high(high_data)
    if errors:
        return errors

    high_data, req_in_errors = st_.state.requisite_in(high_data)
    errors += req_in_errors
    high_data = st_.state.apply_exclude(high_data)
    # Verify that the high data is structurally sound
    if errors:
        return errors

    # Compile and verify the raw chunks
    return st_.state.compile_high_data(high_data)


def _gather_pillar(pillarenv, pillar_override, **grains):
    '''
    Gathers pillar with a custom set of grains, which should
    be first retrieved from the container
    '''
    pillar = salt.pillar.get_pillar(
        __opts__,
        grains,
        # Not sure if these two are correct
        __opts__['id'],
        __opts__['environment'],
        pillar=pillar_override,
        pillarenv=pillarenv
    )
    ret = pillar.compile_pillar()
    if pillar_override and isinstance(pillar_override, dict):
        ret.update(pillar_override)
    return ret


def call(name, function, *args, **kwargs):
    '''
    Executes a Salt function inside a running container

    .. versionadded:: 2016.11.0

    The container does not need to have Salt installed, but Python is required.

    name
        Container name or ID

    function
        Salt execution module function

    CLI Example:

    .. code-block:: bash

        salt myminion docker.call test.ping
        salt myminion test.arg arg1 arg2 key1=val1
        salt myminion dockerng.call compassionate_mirzakhani test.arg arg1 arg2 key1=val1

    '''
    # where to put the salt-thin
    thin_dest_path = _generate_tmp_path()
    mkdirp_thin_argv = ['mkdir', '-p', thin_dest_path]

    # put_archive reqires the path to exist
    ret = run_all(name, subprocess.list2cmdline(mkdirp_thin_argv))
    if ret['retcode'] != 0:
        return {'result': False, 'comment': ret['stderr']}

    if function is None:
        raise CommandExecutionError('Missing function parameter')

    # move salt into the container
    thin_path = salt.utils.thin.gen_thin(__opts__['cachedir'],
                                         extra_mods=__salt__['config.option']("thin_extra_mods", ''),
                                         so_mods=__salt__['config.option']("thin_so_mods", ''))
    with io.open(thin_path, 'rb') as file:
        _client_wrapper('put_archive', name, thin_dest_path, file)
    try:
        salt_argv = [
            'python',
            os.path.join(thin_dest_path, 'salt-call'),
            '--metadata',
            '--local',
            '--out', 'json',
            '-l', 'quiet',
            '--',
            function
        ] + list(args) + ['{0}={1}'.format(key, value) for (key, value) in kwargs.items() if not key.startswith('__')]

        ret = run_all(name, subprocess.list2cmdline(map(str, salt_argv)))
        # python not found
        if ret['retcode'] != 0:
            raise CommandExecutionError(ret['stderr'])

        # process "real" result in stdout
        try:
            data = salt.utils.find_json(ret['stdout'])
            local = data.get('local', data)
            if isinstance(local, dict):
                if 'retcode' in local:
                    __context__['retcode'] = local['retcode']
            return local.get('return', data)
        except ValueError:
            return {'result': False,
                    'comment': 'Can\'t parse container command output'}
    finally:
        # delete the thin dir so that it does not end in the image
        rm_thin_argv = ['rm', '-rf', thin_dest_path]
        run_all(name, subprocess.list2cmdline(rm_thin_argv))


def sls(name, mods=None, saltenv='base', **kwargs):
    '''
    Apply the states defined by the specified SLS modules to the running
    container

    .. versionadded:: 2016.11.0

    The container does not need to have Salt installed, but Python is required.

    name
        Container name or ID

    mods : None
        A string containing comma-separated list of SLS with defined states to
        apply to the container.

    saltenv : base
        Specify the environment from which to retrieve the SLS indicated by the
        `mods` parameter.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.sls compassionate_mirzakhani mods=rails,web

    '''
    mods = [item.strip() for item in mods.split(',')] if mods else []

    # gather grains from the container
    grains = call(name, 'grains.items')

    # compile pillar with container grains
    pillar = _gather_pillar(saltenv, {}, **grains)

    trans_tar = _prepare_trans_tar(name, mods=mods, saltenv=saltenv, pillar=pillar)

    # where to put the salt trans tar
    trans_dest_path = _generate_tmp_path()
    mkdirp_trans_argv = ['mkdir', '-p', trans_dest_path]
    # put_archive requires the path to exist
    ret = run_all(name, subprocess.list2cmdline(mkdirp_trans_argv))
    if ret['retcode'] != 0:
        return {'result': False, 'comment': ret['stderr']}

    ret = None
    try:
        trans_tar_sha256 = salt.utils.get_hash(trans_tar, 'sha256')
        copy_to(name,
                trans_tar,
                os.path.join(trans_dest_path, 'salt_state.tgz'),
                exec_driver='nsenter',
                overwrite=True)

        # Now execute the state into the container
        ret = call(name,
                   'state.pkg',
                   os.path.join(trans_dest_path, 'salt_state.tgz'),
                   trans_tar_sha256,
                   'sha256')
    finally:
        # delete the trans dir so that it does not end in the image
        rm_trans_argv = ['rm', '-rf', trans_dest_path]
        run_all(name, subprocess.list2cmdline(rm_trans_argv))
        # delete the local version of the trans tar
        try:
            os.remove(trans_tar)
        except (IOError, OSError) as exc:
            log.error(
                'docker.sls: Unable to remove state tarball \'%s\': %s',
                trans_tar, exc
            )
    if not isinstance(ret, dict):
        __context__['retcode'] = 1
    elif not salt.utils.check_state_result(ret):
        __context__['retcode'] = 2
    else:
        __context__['retcode'] = 0
    return ret


def sls_build(name, base='opensuse/python', mods=None, saltenv='base',
              dryrun=False, **kwargs):
    '''
    Build a Docker image using the specified SLS modules on top of base image

    .. versionadded:: 2016.11.0

    The base image does not need to have Salt installed, but Python is required.

    name
        Image name to be built and committed

    base : opensuse/python
        Name or ID of the base image

    mods : None
        A string containing comma-separated list of SLS with defined states to
        apply to the base image.

    saltenv : base
        Specify the environment from which to retrieve the SLS indicated by the
        `mods` parameter.

    base
        the base image

    mods
        the state modules to execute during build

    saltenv
        the salt environment to use

    dryrun: False
        when set to True the container will not be commited at the end of
        the build. The dryrun succeed also when the state contains errors.

    **RETURN DATA**

    A dictionary with the ID of the new container. In case of a dryrun,
    the state result is returned and the container gets removed.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.sls_build imgname base=mybase mods=rails,web

    '''
    create_kwargs = salt.utils.clean_kwargs(**copy.deepcopy(kwargs))
    for key in ('image', 'name', 'cmd', 'interactive', 'tty'):
        try:
            del create_kwargs[key]
        except KeyError:
            pass

    # start a new container
    ret = create(image=base,
                 cmd='sleep infinity',
                 interactive=True, tty=True,
                 **create_kwargs)
    id_ = ret['Id']
    try:
        start(id_)

        # Now execute the state into the container
        ret = sls(id_, mods, saltenv, **kwargs)
        # fail if the state was not successful
        if not dryrun and not salt.utils.check_state_result(ret):
            raise CommandExecutionError(ret)
        if dryrun is False:
            ret = commit(id_, name)
    finally:
        stop(id_)
        rm_(id_)
    return ret
