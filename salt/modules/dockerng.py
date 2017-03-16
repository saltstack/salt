# -*- coding: utf-8 -*-
'''
Management of Docker Containers

.. versionadded:: 2015.8.0


Why Make a Second Docker Execution Module?
------------------------------------------

We have received a lot of feedback on our Docker support. In the process of
implementing recommended improvements, it became obvious that major changes
needed to be made to the functions and return data. In the end, a complete
rewrite was done.

The changes being too significant, it was decided that making a separate
execution module and state module (called ``dockerng``) would be the best
option. This will give users a couple release cycles to modify their scripts,
SLS files, etc. to use the new functionality, rather than forcing users to
change everything immediately.

In the **Nitrogen** release of Salt (due in 2017), this execution module will
take the place of the default Docker execution module, and backwards-compatible
naming will be maintained for a couple releases after that to allow users time
to replace references to ``dockerng`` with ``docker``.


Installation Prerequisites
--------------------------

This execution module requires at least version 1.4.0 of both docker-py_ and
Docker_. docker-py can easily be installed using :py:func:`pip.install
<salt.modules.pip.install>`:

.. code-block:: bash

    salt myminion pip.install docker-py>=1.4.0

.. _docker-py: https://pypi.python.org/pypi/docker-py
.. _Docker: https://www.docker.com/

.. _docker-authentication:

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
    - :py:func:`dockerng.depends <salt.modules.dockerng.depends>`
    - :py:func:`dockerng.diff <salt.modules.dockerng.diff>`
    - :py:func:`dockerng.exists <salt.modules.dockerng.exists>`
    - :py:func:`dockerng.history <salt.modules.dockerng.history>`
    - :py:func:`dockerng.images <salt.modules.dockerng.images>`
    - :py:func:`dockerng.info <salt.modules.dockerng.info>`
    - :py:func:`dockerng.inspect <salt.modules.dockerng.inspect>`
    - :py:func:`dockerng.inspect_container
      <salt.modules.dockerng.inspect_container>`
    - :py:func:`dockerng.inspect_image <salt.modules.dockerng.inspect_image>`
    - :py:func:`dockerng.list_containers
      <salt.modules.dockerng.list_containers>`
    - :py:func:`dockerng.list_tags <salt.modules.dockerng.list_tags>`
    - :py:func:`dockerng.logs <salt.modules.dockerng.logs>`
    - :py:func:`dockerng.pid <salt.modules.dockerng.pid>`
    - :py:func:`dockerng.port <salt.modules.dockerng.port>`
    - :py:func:`dockerng.ps <salt.modules.dockerng.ps>`
    - :py:func:`dockerng.state <salt.modules.dockerng.state>`
    - :py:func:`dockerng.search <salt.modules.dockerng.search>`
    - :py:func:`dockerng.top <salt.modules.dockerng.top>`
    - :py:func:`dockerng.version <salt.modules.dockerng.version>`
- Container Management
    - :py:func:`dockerng.create <salt.modules.dockerng.create>`
    - :py:func:`dockerng.copy_from <salt.modules.dockerng.copy_from>`
    - :py:func:`dockerng.copy_to <salt.modules.dockerng.copy_to>`
    - :py:func:`dockerng.export <salt.modules.dockerng.export>`
    - :py:func:`dockerng.rm <salt.modules.dockerng.rm>`
- Management of Container State
    - :py:func:`dockerng.kill <salt.modules.dockerng.kill>`
    - :py:func:`dockerng.pause <salt.modules.dockerng.pause>`
    - :py:func:`dockerng.restart <salt.modules.dockerng.restart>`
    - :py:func:`dockerng.start <salt.modules.dockerng.start>`
    - :py:func:`dockerng.stop <salt.modules.dockerng.stop>`
    - :py:func:`dockerng.unpause <salt.modules.dockerng.unpause>`
    - :py:func:`dockerng.wait <salt.modules.dockerng.wait>`
- Image Management
    - :py:func:`dockerng.build <salt.modules.dockerng.build>`
    - :py:func:`dockerng.commit <salt.modules.dockerng.commit>`
    - :py:func:`dockerng.dangling <salt.modules.dockerng.dangling>`
    - :py:func:`dockerng.import <salt.modules.dockerng.import>`
    - :py:func:`dockerng.load <salt.modules.dockerng.load>`
    - :py:func:`dockerng.pull <salt.modules.dockerng.pull>`
    - :py:func:`dockerng.push <salt.modules.dockerng.push>`
    - :py:func:`dockerng.rmi <salt.modules.dockerng.rmi>`
    - :py:func:`dockerng.save <salt.modules.dockerng.save>`
    - :py:func:`dockerng.tag <salt.modules.dockerng.tag>`
- Network Management
    - :py:func:`dockerng.networks <salt.modules.dockerng.networks>`
    - :py:func:`dockerng.create_network <salt.modules.dockerng.create_network>`
    - :py:func:`dockerng.remove_network <salt.modules.dockerng.remove_network>`
    - :py:func:`dockerng.inspect_network
      <salt.modules.dockerng.inspect_network>`
    - :py:func:`dockerng.connect_container_to_network
      <salt.modules.dockerng.connect_container_to_network>`
    - :py:func:`dockerng.disconnect_container_from_network
      <salt.modules.dockerng.disconnect_container_from_network>`



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

- :py:func:`dockerng.retcode <salt.modules.dockerng.retcode>`
- :py:func:`dockerng.run <salt.modules.dockerng.run>`
- :py:func:`dockerng.run_all <salt.modules.dockerng.run_all>`
- :py:func:`dockerng.run_stderr <salt.modules.dockerng.run_stderr>`
- :py:func:`dockerng.run_stdout <salt.modules.dockerng.run_stdout>`
- :py:func:`dockerng.script <salt.modules.dockerng.script>`
- :py:func:`dockerng.script_retcode <salt.modules.dockerng.script_retcode>`


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
import distutils.version  # pylint: disable=import-error,no-name-in-module,unused-import
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

# Import Salt libs
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.ext.six.moves import map  # pylint: disable=import-error,redefined-builtin
from salt.utils.args import get_function_argspec as _argspec
from salt.utils.decorators \
    import identical_signature_wrapper as _mimic_signature
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six

# pylint: disable=import-error
try:
    import docker
    HAS_DOCKER_PY = True
except ImportError:
    HAS_DOCKER_PY = False

# These next two imports are only necessary to have access to the needed
# functions so that we can get argspecs for the container config, host config,
# and networking config (see the get_client_args() function).
try:
    import docker.types
except ImportError:
    pass
try:
    import docker.utils
except ImportError:
    pass

try:
    PY_VERSION = sys.version_info[0]
    if PY_VERSION == 2:
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
MIN_DOCKER = (1, 4, 0)
MIN_DOCKER_PY = (1, 4, 0)

VERSION_RE = r'([\d.]+)'

# Default timeout as of docker-py 1.0.0
CLIENT_TIMEOUT = 60

# Timeout for stopping the container, before a kill is invoked
STOP_TIMEOUT = 10

NOTSET = object()

# Define the module's virtual name
__virtualname__ = 'dockerng'

'''
The below two dictionaries contain information on the kwargs which are
acceptable in the dockerng.create and dockerng.start functions, respectively.
The aim is to make adding new arguments easy, and to keep all of the various
information needed to validate the input organized nicely.

There are 6 different keys which may be present in the sub-dict for each
argument name:

1. api_name - Some parameter names used in docker-py are not clear enough in
   their naming, so Salt uses a different name. For those where the Salt
   function's parameter name differs from docker-py, include this key so that
   Salt knows to pass the value to docker-py with the appropriate name.

2. validator - The lack of this key means that a custom validation function
   named in the format _valid_<keyname> must exist within _validate_input().
   Otherwise, for simple type validation, the value should be a string, and
   there should be a function named in the format _valid_<string> (e.g.
   _valid_bool) within _validate_input().

3. path - Refers to the nested path in the dockerng.inspect_container return
   data where that value is stored. This will only be used by the _compare()
   function in salt/states/dockerng.py.

4. default - Many of the CLI options will default to None, but for booleans and
   integer values (and some others) we want to ensure that someone isn't able
   to pass ``None`` through to the docker-py function call. For these
   instances, specify the default value for a parameter using this key.

5. min_docker - As features get added to Docker, we want to be able to provide
   useful feedback in the exception if someone passes an option which isn't
   supported by the installed version of Docker. For options which are newer
   than the oldest supported Docker version (currently 1.0.0 but this is
   subject to change), this key should be set to a version_info-style tuple
   which can be used to compare against the installed version of Docker.

6. min_docker_py - Same as above for min_docker, but this refers to the version
   of docker-py itself.
'''

VALID_CREATE_OPTS = {
    'command': {
        'path': 'Config:Cmd',
        'image_path': 'Config:Cmd',
    },
    'hostname': {
        'validator': 'string',
        'path': 'Config:Hostname',
        'get_default_from_container': True,
    },
    'domainname': {
        'validator': 'string',
        'path': 'Config:Domainname',
        'get_default_from_container': True,
    },
    'interactive': {
        'api_name': 'stdin_open',
        'validator': 'bool',
        'path': 'Config:OpenStdin',
        'default': False,
    },
    'tty': {
        'validator': 'bool',
        'path': 'Config:Tty',
        'default': False,
    },
    'user': {
        'path': 'Config:User',
        'default': '',
    },
    'detach': {
        'validator': 'bool',
        'path': ('Config:AttachStdout', 'Config:AttachStderr'),
        'default': False,
    },
    'memory': {
        'api_name': 'mem_limit',
        'path': 'HostConfig:Memory',
        'default': 0,
    },
    'memory_swap': {
        'api_name': 'memswap_limit',
        'path': 'HostConfig:MemorySwap',
        'get_default_from_container': True,
    },
    'mac_address': {
        'validator': 'string',
        'path': 'NetworkSettings:MacAddress',
        'get_default_from_container': True,
    },
    'network_disabled': {
        'validator': 'bool',
        'path': 'Config:NetworkDisabled',
        'default': False,
    },
    'ports': {
        'path': 'Config:ExposedPorts',
        'image_path': 'Config:ExposedPorts',
    },
    'working_dir': {
        'path': 'Config:WorkingDir',
        'image_path': 'Config:WorkingDir',
    },
    'entrypoint': {
        'path': 'Config:Entrypoint',
        'image_path': 'Config:Entrypoint',
    },
    'environment': {
        'path': 'Config:Env',
        'default': [],
    },
    'volumes': {
        'path': 'Config:Volumes',
        'image_path': 'Config:Volumes',
    },
    'cpu_shares': {
        'validator': 'number',
        'path': 'HostConfig:CpuShares',
        'default': 0,
    },
    'cpuset': {
        'path': 'HostConfig:CpusetCpus',
        'default': '',
    },
    'labels': {
      'path': 'Config:Labels',
      'image_path': 'Config:Labels',
      'default': {},
    },
    'binds': {
        'path': 'HostConfig:Binds',
        'default': None,
    },
    'port_bindings': {
        'path': 'HostConfig:PortBindings',
        'default': None,
    },
    'lxc_conf': {
        'validator': 'dict',
        'path': 'HostConfig:LxcConf',
        'default': None,
    },
    'publish_all_ports': {
        'validator': 'bool',
        'path': 'HostConfig:PublishAllPorts',
        'default': False,
    },
    'links': {
        'path': 'HostConfig:Links',
        'default': None,
    },
    'privileged': {
        'validator': 'bool',
        'path': 'HostConfig:Privileged',
        'default': False,
    },
    'dns': {
        'path': 'HostConfig:Dns',
        'default': [],
    },
    'dns_search': {
        'validator': 'stringlist',
        'path': 'HostConfig:DnsSearch',
        'default': [],
    },
    'volumes_from': {
        'path': 'HostConfig:VolumesFrom',
        'default': None,
    },
    'network_mode': {
        'path': 'HostConfig:NetworkMode',
        'default': 'default',
    },
    'restart_policy': {
        'path': 'HostConfig:RestartPolicy',
        'min_docker': (1, 2, 0),
        'default': {'MaximumRetryCount': 0, 'Name': ''},
    },
    'cap_add': {
        'validator': 'stringlist',
        'path': 'HostConfig:CapAdd',
        'min_docker': (1, 2, 0),
        'default': None,
    },
    'cap_drop': {
        'validator': 'stringlist',
        'path': 'HostConfig:CapDrop',
        'min_docker': (1, 2, 0),
        'default': None,
    },
    'extra_hosts': {
        'path': 'HostConfig:ExtraHosts',
        'min_docker': (1, 3, 0),
        'default': None,
    },
    'pid_mode': {
        'path': 'HostConfig:PidMode',
        'min_docker': (1, 5, 0),
        'default': '',
    },
    'ulimits': {
        'path': 'HostConfig:Ulimits',
        'min_docker': (1, 6, 0),
        'min_docker_py': (1, 2, 0),
        'default': [],
    },
}


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
                    'Insufficient Docker version for dockerng (required: '
                    '{0}, installed: {1})'.format(
                        '.'.join(map(str, MIN_DOCKER)),
                        '.'.join(map(str, docker_versioninfo))))
        return (False,
            'Insufficient docker-py version for dockerng (required: '
            '{0}, installed: {1})'.format(
                '.'.join(map(str, MIN_DOCKER_PY)),
                '.'.join(map(str, docker_py_versioninfo))))
    return (False, 'Docker module could not get imported')


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
        return _mimic_signature(func, wrapper)


class _client_version(object):
    '''
    Enforce a specific Docker client version
    '''
    def __init__(self, version):
        self.version = distutils.version.StrictVersion(version)

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            '''
            Get the current client version and check it against the one passed
            '''
            _get_client()
            current_version = '.'.join(map(str, _get_docker_py_versioninfo()))
            if distutils.version.StrictVersion(current_version) < self.version:
                raise CommandExecutionError(
                    'This function requires a Docker Client version of at least '
                    '{0}. Version in use is {1}.'
                    .format(self.version, current_version)
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
        '''
        Ensure that the client is present
        '''
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
        __salt__['mine.send']('dockerng.ps', verbose=True, all=True, host=True)
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
        'docker.client', 'docker.exec_driver', 'dockerng._pull_status',
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

        try:
            # docker-py 2.0 renamed this client attribute
            __context__['docker.client'] = docker.APIClient(**client_kwargs)
        except AttributeError:
            __context__['docker.client'] = docker.Client(**client_kwargs)

    # Set a new timeout if one was passed
    if timeout is not None and __context__['docker.client'].timeout != timeout:
        __context__['docker.client'].timeout = timeout


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
    '''
    docker-exec won't be used by default until we reach a version where it
    supports running commands as a user other than the effective user of the
    container.

    See: https://groups.google.com/forum/#!topic/salt-users/i6Eq4rf5ml0

    if contextkey in __context__:
        return __context__[contextkey]

    from_config = __salt__['config.get'](contextkey, None)
    if from_config is not None:
        __context__[contextkey] = from_config
    else:
        _version = version()
        if 'VersionInfo' in _version:
            if _version['VersionInfo'] >= (1, 3, 0):
                __context__[contextkey] = 'docker-exec'
        elif distutils.version.LooseVersion(version()['Version']) \
                >= distutils.version.LooseVersion('1.3.0'):
            # LooseVersion is less preferable, but OK as a fallback.
            __context__[contextkey] = 'docker-exec'

    # If the version_info tuple revealed a version < 1.3.0, the key will yet to
    # have been set in __context__, so we'll check if it's there yet and if
    # not, proceed with detecting execution driver from the output of info().
    '''  # pylint: disable=pointless-string-statement
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
                'dockerng module for more information.'
            )
            __context__[contextkey] = 'nsenter'
        else:
            raise NotImplementedError(
                'Unknown docker ExecutionDriver \'{0}\', or didn\'t find '
                'command to attach to the container'.format(driver)
            )
    return __context__[contextkey]


def _get_repo_tag(image, default_tag='latest'):
    '''
    Resolves the docker repo:tag notation and returns repo name and tag
    '''
    if ':' in image:
        r_name, r_tag = image.rsplit(':', 1)
        if not r_tag:
            # Would happen if some wiseguy requests a tag ending in a colon
            # (e.g. 'somerepo:')
            log.warning(
                'Assuming tag \'{0}\' for repo \'{1}\''
                .format(default_tag, image)
            )
            r_tag = default_tag
    else:
        r_name = image
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


def _prep_pull():
    '''
    Populate __context__ with the current (pre-pull) image IDs (see the
    docstring for _pull_status for more information).
    '''
    __context__['dockerng._pull_status'] = \
        [x[:12] for x in images(all=True)]


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
            '{0} Docker credentials{1}. Please see the dockerng remote '
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

    if 'dockerng._pull_status' not in __context__:
        log.warning(
            '_pull_status context variable was not populated, information on '
            'downloaded layers may be inaccurate. Please report this to the '
            'SaltStack development team, and if possible include the image '
            '(and tag) that was being pulled.'
        )
        __context__['dockerng._pull_status'] = NOTSET
    status = item['status']
    if status == 'Already exists':
        _already_exists(item['id'])
    elif status in 'Pull complete':
        _new_layer(item['id'])
    elif status.startswith('Status: '):
        data['Status'] = status[8:]
    elif status == 'Download complete':
        if __context__['dockerng._pull_status'] is not NOTSET:
            id_ = item['id']
            if id_ in __context__['dockerng._pull_status']:
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
        msg = '{1}: {2}'.format(
            item['errorDetail']['code'],
            item['errorDetail']['message'],
        )
    else:
        msg = item['errorDetail']['message']
    data.append(msg)


def _validate_input(kwargs,
                    validate_ip_addrs=True):
    '''
    Perform validation on kwargs. Checks each key in kwargs against the
    VALID_CONTAINER_OPTS dict and if the value is None, looks for a local
    function named in the format _valid_<kwarg> and calls that.

    The validation functions don't need to return anything, they just need to
    raise a SaltInvocationError if the validation fails.

    Where needed, this function also performs translation on the input,
    formatting it in a way that will allow it to be passed to either
    docker.client.Client.create_container() or
    docker.client.Client.start().
    '''
    # Import here so that these modules are available when _validate_input is
    # imported into the state module.
    import os  # pylint: disable=reimported,redefined-outer-name
    import shlex

    # Simple type validation
    def _valid_bool(key):  # pylint: disable=unused-variable
        '''
        Ensure that the passed value is a boolean
        '''
        if not isinstance(kwargs[key], bool):
            raise SaltInvocationError(key + ' must be True or False')

    def _valid_dict(key):  # pylint: disable=unused-variable
        '''
        Ensure that the passed value is a dictionary
        '''
        if not isinstance(kwargs[key], dict):
            raise SaltInvocationError(key + ' must be a dictionary')

    def _valid_number(key):  # pylint: disable=unused-variable
        '''
        Ensure that the passed value is an int or float
        '''
        if not isinstance(kwargs[key], (six.integer_types, float)):
            raise SaltInvocationError(
                key + ' must be a number (integer or floating-point)'
            )

    def _valid_string(key):  # pylint: disable=unused-variable
        '''
        Ensure that the passed value is a string
        '''
        if not isinstance(kwargs[key], six.string_types):
            raise SaltInvocationError(key + ' must be a string')

    def _valid_stringlist(key):  # pylint: disable=unused-variable
        '''
        Ensure that the passed value is a list of strings
        '''
        if isinstance(kwargs[key], six.string_types):
            kwargs[key] = kwargs[key].split(',')
        if not isinstance(kwargs[key], list) \
                or not all([isinstance(x, six.string_types)
                            for x in kwargs[key]]):
            raise SaltInvocationError(key + ' must be a list of strings')

    def _valid_dictlist(key):  # pylint: disable=unused-variable
        '''
        Ensure the passed value is a list of dictionaries.
        '''
        if not salt.utils.is_dictlist(kwargs[key]):
            raise SaltInvocationError(key + ' must be a list of dictionaries.')

    # Custom validation functions for container creation options
    def _valid_command():  # pylint: disable=unused-variable
        '''
        Must be either a string or a list of strings. Value will be translated
        to a list of strings
        '''
        if kwargs.get('command') is None:
            # No need to validate
            return
        if isinstance(kwargs['command'], six.string_types):
            # Translate command into a list of strings
            try:
                kwargs['command'] = salt.utils.shlex_split(kwargs['command'])
            except AttributeError:
                pass
        try:
            _valid_stringlist('command')
        except SaltInvocationError:
            raise SaltInvocationError(
                'command/cmd must be a string or list of strings'
            )

    def _valid_user():  # pylint: disable=unused-variable
        '''
        Can be either an integer >= 0 or a string
        '''
        if kwargs.get('user') is None:
            # No need to validate
            return
        if isinstance(kwargs['user'], six.string_types) \
                or isinstance(kwargs['user'], six.integer_types) \
                and kwargs['user'] >= 0:
            # Either an int or a string int will work when creating the
            # container, so just force this to be a string.
            kwargs['user'] = str(kwargs['user'])
            return
        raise SaltInvocationError('user must be a string or a uid')

    def _valid_memory():  # pylint: disable=unused-variable
        '''
        must be a positive integer
        '''
        if __context__.pop('validation.docker.memory', False):
            # Don't perform validation again, we already did this
            return
        try:
            kwargs['memory'] = salt.utils.human_size_to_bytes(kwargs['memory'])
        except ValueError:
            raise SaltInvocationError(
                'memory must be an integer, or an integer followed by '
                'K, M, G, T, or P (example: 512M)'
            )
        if kwargs['memory'] < 0:
            raise SaltInvocationError('memory must be a positive integer')
        __context__['validation.docker.memory'] = True

    def _valid_memory_swap():  # pylint: disable=unused-variable
        '''
        memory_swap can be -1 (swap disabled) or >= memory
        '''
        # Ensure that memory was validated first, because we need the munged
        # version of it below.
        _valid_memory()
        try:
            kwargs['memory_swap'] = \
                salt.utils.human_size_to_bytes(kwargs['memory_swap'])
        except ValueError:
            if kwargs['memory_swap'] == -1:
                # memory_swap of -1 means swap is disabled
                return
            raise SaltInvocationError(
                'memory must be an integer, or an integer followed by '
                'K, M, G, T, or P (example: 512M)'
            )
        if kwargs['memory_swap'] == 0:
            # Swap of 0 means unlimited
            return
        if kwargs['memory_swap'] < kwargs['memory']:
            raise SaltInvocationError(
                'memory_swap cannot be less than memory'
            )

    def _valid_ports():  # pylint: disable=unused-variable
        '''
        Format ports in the documented way:
        http://docker-py.readthedocs.org/en/stable/port-bindings/

        It's possible to pass this as a dict, and indeed it is returned as such
        in the inspect output. Passing port configurations as a dict will work
        with docker-py, but since it is not documented, we will do it as
        documented to prevent possible breakage in the future.
        '''
        if kwargs.get('ports') is None:
            # no need to validate
            return
        if isinstance(kwargs['ports'], six.integer_types):
            kwargs['ports'] = str(kwargs['ports'])
        elif isinstance(kwargs['ports'], list):
            new_ports = [str(x) for x in kwargs['ports']]
            kwargs['ports'] = new_ports
        else:
            try:
                _valid_stringlist('ports')
            except SaltInvocationError:
                raise SaltInvocationError(
                    'ports must be a comma-separated list or Python list'
                )
        new_ports = []
        for item in kwargs['ports']:
            # Have to run str() here again in case the ports were passed in a
            # Python list instead of a string.
            port_num, _, protocol = str(item).partition('/')
            if not port_num.isdigit():
                raise SaltInvocationError(
                    'Invalid port number \'{0}\' in \'ports\' argument'
                    .format(port_num)
                )
            else:
                port_num = int(port_num)
            lc_protocol = protocol.lower()
            if lc_protocol == 'tcp':
                protocol = ''
            elif lc_protocol == 'udp':
                protocol = lc_protocol
            elif lc_protocol != '':
                raise SaltInvocationError(
                    'Invalid protocol \'{0}\' for port {1} in \'ports\' '
                    'argument'.format(protocol, port_num)
                )
            if protocol:
                new_ports.append((port_num, protocol))
            else:
                new_ports.append(port_num)
        kwargs['ports'] = new_ports

    def _valid_working_dir():  # pylint: disable=unused-variable
        '''
        Must be an absolute path
        '''
        if kwargs.get('working_dir') is None:
            # No need to validate
            return
        _valid_string('working_dir')
        if not os.path.isabs(kwargs['working_dir']):
            raise SaltInvocationError('working_dir must be an absolute path')

    def _valid_entrypoint():  # pylint: disable=unused-variable
        '''
        Must be a string or list of strings
        '''
        if kwargs.get('entrypoint') is None:
            # No need to validate
            return
        if isinstance(kwargs['entrypoint'], six.string_types):
            # Translate entrypoint into a list of strings
            try:
                kwargs['entrypoint'] = salt.utils.shlex_split(kwargs['entrypoint'])
            except AttributeError:
                pass
        try:
            _valid_stringlist('entrypoint')
        except SaltInvocationError:
            raise SaltInvocationError(
                'entrypoint must be a string or list of strings'
            )

    def _valid_environment():  # pylint: disable=unused-variable
        '''
        Can be a list of VAR=value strings, a dictionary, or a single env var
        represented as a string. Data will be munged into a dictionary.
        '''
        if kwargs.get('environment') is None:
            # No need to validate
            return
        if isinstance(kwargs['environment'], list):
            repacked_env = {}
            for env_var in kwargs['environment']:
                try:
                    key, val = env_var.split('=')
                except AttributeError:
                    raise SaltInvocationError(
                        'Invalid environment variable definition \'{0}\''
                        .format(env_var)
                    )
                else:
                    if key in repacked_env:
                        raise SaltInvocationError(
                            'Duplicate environment variable \'{0}\''
                            .format(key)
                        )
                    if not isinstance(val, six.string_types):
                        raise SaltInvocationError(
                            'Environment values must be strings {key}=\'{val}\''
                            .format(key=key, val=val))
                    repacked_env[key] = val
            kwargs['environment'] = repacked_env
        elif isinstance(kwargs['environment'], dict):
            for key, val in six.iteritems(kwargs['environment']):
                if not isinstance(val, six.string_types):
                    raise SaltInvocationError(
                        'Environment values must be strings {key}=\'{val}\''
                        .format(key=key, val=val))
        elif not isinstance(kwargs['environment'], dict):
            raise SaltInvocationError(
                'Invalid environment configuration. See the documentation for '
                'proper usage.'
            )

    def _valid_volumes():  # pylint: disable=unused-variable
        '''
        Must be a list of absolute paths
        '''
        if kwargs.get('volumes') is None:
            # No need to validate
            return
        try:
            _valid_stringlist('volumes')
            if not all(os.path.isabs(x) for x in kwargs['volumes']):
                raise SaltInvocationError()
        except SaltInvocationError:
            raise SaltInvocationError(
                'volumes must be a list of absolute paths'
            )

    def _valid_cpuset():  # pylint: disable=unused-variable
        '''
        Must be a string. If a string integer is passed, convert it to a
        string.
        '''
        if kwargs.get('cpuset') is None:
            # No need to validate
            return
        if isinstance(kwargs['cpuset'], six.integer_types):
            kwargs['cpuset'] = str(kwargs['cpuset'])
        try:
            _valid_string('cpuset')
        except SaltInvocationError:
            raise SaltInvocationError('cpuset must be a string or integer')

    # Custom validation functions for runtime options
    def _valid_binds():  # pylint: disable=unused-variable
        '''
        Must be a string or list of strings with bind mount information
        '''
        if kwargs.get('binds') is None:
            # No need to validate
            return
        err = (
            'Invalid binds configuration. See the documentation for proper '
            'usage.'
        )
        if isinstance(kwargs['binds'], six.integer_types):
            kwargs['binds'] = str(kwargs['binds'])
        try:
            _valid_stringlist('binds')
        except SaltInvocationError:
            raise SaltInvocationError(err)
        new_binds = {}
        for bind in kwargs['binds']:
            bind_parts = bind.split(':')
            num_bind_parts = len(bind_parts)
            if num_bind_parts == 2:
                host_path, container_path = bind_parts
                read_only = False
            elif num_bind_parts == 3:
                host_path, container_path, read_only = bind_parts
                if read_only == 'ro':
                    read_only = True
                elif read_only == 'rw':
                    read_only = False
                else:
                    raise SaltInvocationError(
                        'Invalid read-only configuration for bind {0}, must '
                        'be either \'ro\' or \'rw\''
                        .format(host_path + '/' + container_path)
                    )
            else:
                raise SaltInvocationError(err)

            if not os.path.isabs(host_path):
                if os.path.sep in host_path:
                    raise SaltInvocationError(
                        'Host path {0} in bind {1} is not absolute'
                        .format(container_path, bind)
                    )
                log.warn('Host path {0} in bind {1} is not absolute,'
                         ' assuming it is a docker volume.'.format(host_path,
                                                                   bind))
            if not os.path.isabs(container_path):
                raise SaltInvocationError(
                    'Container path {0} in bind {1} is not absolute'
                    .format(container_path, bind)
                )
            new_binds[host_path] = {'bind': container_path, 'ro': read_only}
        kwargs['binds'] = new_binds

    def _valid_links():  # pylint: disable=unused-variable
        '''
        Must be a list of colon-delimited mappings
        '''
        if kwargs.get('links') is None:
            # No need to validate
            return
        err = 'Invalid format for links. See documentaion for proper usage.'
        try:
            _valid_stringlist('links')
        except SaltInvocationError:
            raise SaltInvocationError(
                'links must be a comma-separated list or Python list'
            )
        new_links = []
        for item in kwargs['links']:
            try:
                link_name, link_alias = item.split(':')
            except ValueError:
                raise SaltInvocationError(err)
            else:
                if not link_name.startswith('/'):
                    # Normalize container name to make comparisons simpler
                    link_name = '/' + link_name
            new_links.append((link_name, link_alias))
        kwargs['links'] = new_links

    def _valid_dns():  # pylint: disable=unused-variable
        '''
        Must be a list of mappings or a dictionary
        '''
        if kwargs.get('dns') is None:
            # No need to validate
            return
        if isinstance(kwargs['dns'], six.string_types):
            kwargs['dns'] = kwargs['dns'].split(',')
        if not isinstance(kwargs['dns'], list):
            raise SaltInvocationError(
                'dns must be a comma-separated list or Python list'
            )
        if validate_ip_addrs:
            errors = []
            for addr in kwargs['dns']:
                try:
                    if not salt.utils.network.is_ip(addr):
                        errors.append(
                            'dns nameserver \'{0}\' is not a valid IP address'
                            .format(addr)
                        )
                except RuntimeError:
                    pass
            if errors:
                raise SaltInvocationError('; '.join(errors))

    def _valid_port_bindings():  # pylint: disable=unused-variable
        '''
        Must be a string or list of strings with port binding information
        '''
        if kwargs.get('port_bindings') is None:
            # No need to validate
            return
        err = (
            'Invalid port_bindings configuration. See the documentation for '
            'proper usage.'
        )
        if isinstance(kwargs['port_bindings'], six.integer_types):
            kwargs['port_bindings'] = str(kwargs['port_bindings'])
        try:
            _valid_stringlist('port_bindings')
        except SaltInvocationError:
            raise SaltInvocationError(err)
        new_port_bindings = {}
        for binding in kwargs['port_bindings']:
            bind_parts = binding.split(':')
            num_bind_parts = len(bind_parts)
            if num_bind_parts == 1:
                container_port = str(bind_parts[0])
                if container_port == '':
                    raise SaltInvocationError(err)
                bind_val = None
            elif num_bind_parts == 2:
                if any(x == '' for x in bind_parts):
                    raise SaltInvocationError(err)
                host_port, container_port = bind_parts
                if not host_port.isdigit():
                    raise SaltInvocationError(
                        'Invalid host port \'{0}\' for port {1} in '
                        'port_bindings'.format(host_port, container_port)
                    )
                bind_val = int(host_port)
            elif num_bind_parts == 3:
                host_ip, host_port, container_port = bind_parts
                if validate_ip_addrs:
                    try:
                        if not salt.utils.network.is_ip(host_ip):
                            raise SaltInvocationError(
                                'Host IP \'{0}\' in port_binding {1} is not a '
                                'valid IP address'.format(host_ip, binding)
                            )
                    except RuntimeError:
                        pass
                if host_port == '':
                    bind_val = (host_ip,)
                elif not host_port.isdigit():
                    raise SaltInvocationError(
                        'Invalid host port \'{0}\' for port {1} in '
                        'port_bindings'.format(host_port, container_port)
                    )
                else:
                    bind_val = (host_ip, int(host_port))
            else:
                raise SaltInvocationError(err)
            port_num, _, protocol = container_port.partition('/')
            if not port_num.isdigit():
                raise SaltInvocationError(
                    'Invalid container port number \'{0}\' in '
                    'port_bindings argument'.format(port_num)
                )
            lc_protocol = protocol.lower()
            if lc_protocol in ('', 'tcp'):
                container_port = int(port_num)
            elif lc_protocol == 'udp':
                container_port = port_num + '/' + lc_protocol
            else:
                raise SaltInvocationError(err)
            new_port_bindings.setdefault(container_port, []).append(bind_val)
        kwargs['port_bindings'] = new_port_bindings

    def _valid_volumes_from():  # pylint: disable=unused-variable
        '''
        Must be a string or list of strings
        '''
        if isinstance(kwargs['volumes_from'], six.integer_types):
            # Handle cases where a container's name is numeric
            kwargs['volumes_from'] = str(kwargs['volumes_from'])
        try:
            _valid_stringlist('volumes_from')
        except SaltInvocationError:
            raise SaltInvocationError(
                'volumes_from must be a string or list of strings'
            )

    def _valid_network_mode():  # pylint: disable=unused-variable
        '''
        Must be one of several possible string types
        '''
        if kwargs.get('network_mode') is None:
            # No need to validate
            return
        try:
            _valid_string('network_mode')
            if kwargs['network_mode'] in ('bridge', 'host'):
                return
            elif kwargs['network_mode'].startswith('container:') \
                    and kwargs['network_mode'] != 'container:':
                # Ensure that the user didn't just pass 'container:', because
                # that would be invalid.
                return
            else:
                # just a name assume it is a network
                log.info(
                    'Assuming network_mode \'{0}\' is a network.'.format(
                      kwargs['network_mode'])
                )
        except SaltInvocationError:
            raise SaltInvocationError(
                'network_mode must be one of \'bridge\', \'host\', '
                '\'container:<id or name>\' or a name of a network.'
            )

    def _valid_restart_policy():  # pylint: disable=unused-variable
        '''
        Must be one of several possible string types
        '''
        if kwargs['restart_policy'] is None:
            # No need to validate
            return
        if isinstance(kwargs['restart_policy'], six.string_types):
            try:
                pol_name, count = kwargs['restart_policy'].split(':')
            except ValueError:
                pol_name = kwargs['restart_policy']
                count = '0'
            if not count.isdigit():
                raise SaltInvocationError(
                    'Invalid retry count \'{0}\' in restart_policy, '
                    'must be an integer'.format(count)
                )
            count = int(count)
            if pol_name == 'always' and count != 0:
                log.warning(
                    'Using \'always\' restart_policy. Retry count will '
                    'be ignored.'
                )
                count = 0
            kwargs['restart_policy'] = {'Name': pol_name,
                                        'MaximumRetryCount': count}

    def _valid_extra_hosts():  # pylint: disable=unused-variable
        '''
        Must be a list of host:ip mappings
        '''
        if kwargs.get('extra_hosts') is None:
            # No need to validate
            return
        try:
            _valid_stringlist('extra_hosts')
        except SaltInvocationError:
            raise SaltInvocationError(
                'extra_hosts must be a comma-separated list or Python list'
            )
        err = (
            'Invalid format for extra_hosts. See documentaion for proper '
            'usage.'
        )
        errors = []
        new_extra_hosts = {}
        for item in kwargs['extra_hosts']:
            try:
                host_name, ip_addr = item.split(':')
            except ValueError:
                raise SaltInvocationError(err)

            if validate_ip_addrs:
                try:
                    if not salt.utils.network.is_ip(ip_addr):
                        errors.append(
                            'Address \'{0}\' for extra_host \'{0}\' is not a '
                            'valid IP address'
                        )
                except RuntimeError:
                    pass
            new_extra_hosts[host_name] = ip_addr
        if errors:
            raise SaltInvocationError('; '.join(errors))

        kwargs['extra_hosts'] = new_extra_hosts

    def _valid_pid_mode():  # pylint: disable=unused-variable
        '''
        Can either be None or 'host'
        '''
        if kwargs.get('pid_mode') not in (None, 'host'):
            raise SaltInvocationError(
                'pid_mode can only be \'host\', if set'
            )

    def _valid_labels():  # pylint: disable=unused-variable
        '''
        Must be a dict or a list of strings
        '''
        if kwargs.get('labels') is None:
            return
        try:
            _valid_stringlist('labels')
        except SaltInvocationError:
            try:
                _valid_dictlist('labels')
            except SaltInvocationError:
                try:
                    _valid_dict('labels')
                except SaltInvocationError:
                    raise SaltInvocationError(
                        'labels can only be a list of strings/dict'
                        ' or a dict containing strings')
                else:
                    new_labels = {}
                    for k, v in six.iteritems(kwargs['labels']):
                        new_labels[str(k)] = str(v)
                    kwargs['labels'] = new_labels
            else:
                kwargs['labels'] = salt.utils.repack_dictlist(kwargs['labels'])

    def _valid_ulimits():  # pylint: disable=unused-variable
        '''
        Must be a string or list of strings with bind mount information
        '''
        if kwargs.get('ulimits') is None:
            # No need to validate
            return
        err = (
            'Invalid ulimits configuration. See the documentation for proper '
            'usage.'
        )
        try:
            _valid_dictlist('ulimits')
            # If this was successful then assume the correct API value was
            # passed on on the CLI and do not proceed with validation.
            return
        except SaltInvocationError:
            pass
        try:
            _valid_stringlist('ulimits')
        except SaltInvocationError:
            raise SaltInvocationError(err)

        new_ulimits = []
        for ulimit in kwargs['ulimits']:
            ulimit_name, comps = ulimit.strip().split('=', 1)
            try:
                comps = [int(x) for x in comps.split(':', 1)]
            except ValueError:
                raise SaltInvocationError(err)
            if len(comps) == 1:
                comps *= 2
            soft_limit, hard_limit = comps
            new_ulimits.append({'Name': ulimit_name,
                                'Soft': soft_limit,
                                'Hard': hard_limit})
        kwargs['ulimits'] = new_ulimits

    # And now, the actual logic to perform the validation
    if 'docker.docker_version' not in __context__:
        # Have to call this func using the __salt__ dunder (instead of just
        # version()) because this _validate_input() will be imported into the
        # state module, and the state module won't have a version() func.
        _version = __salt__['dockerng.version']()
        if 'VersionInfo' not in _version:
            log.warning(
                'Unable to determine docker version. Feature version checking '
                'will be unavailable.'
            )
            docker_version = None
        else:
            docker_version = _version['VersionInfo']
        __context__['docker.docker_version'] = docker_version

    _locals = locals()
    for kwarg in kwargs:
        if kwarg not in VALID_CREATE_OPTS:
            raise SaltInvocationError('Invalid argument \'{0}\''.format(kwarg))

        # Check for Docker/docker-py compatibility
        compat_errors = []
        if 'min_docker' in VALID_CREATE_OPTS[kwarg]:
            min_docker = VALID_CREATE_OPTS[kwarg]['min_docker']
            if __context__['docker.docker_version'] is not None:
                if __context__['docker.docker_version'] < min_docker:
                    compat_errors.append(
                        'The \'{0}\' parameter requires at least Docker {1} '
                        '(detected version {2})'.format(
                            kwarg,
                            '.'.join(map(str, min_docker)),
                            '.'.join(__context__['docker.docker_version'])
                        )
                    )
        if 'min_docker_py' in VALID_CREATE_OPTS[kwarg]:
            cur_docker_py = _get_docker_py_versioninfo()
            if cur_docker_py is not None:
                min_docker_py = VALID_CREATE_OPTS[kwarg]['min_docker_py']
                if cur_docker_py < min_docker_py:
                    compat_errors.append(
                        'The \'{0}\' parameter requires at least docker-py '
                        '{1} (detected version {2})'.format(
                            kwarg,
                            '.'.join(map(str, min_docker_py)),
                            '.'.join(map(str, cur_docker_py))
                        )
                    )
        if compat_errors:
            raise SaltInvocationError('; '.join(compat_errors))

        default_val = VALID_CREATE_OPTS[kwarg].get('default')
        if kwargs[kwarg] is None:
            if default_val is None:
                # Passed as None and None is the default. Skip validation. This
                # catches cases where user explicitly passes a value of None.
                continue
            else:
                # User explicitly passed None for an option that cannot be
                # None, don't let them do this.
                raise SaltInvocationError(kwarg + ' cannot be None')

        validator = VALID_CREATE_OPTS[kwarg].get('validator')
        if validator is None:
            # Look for custom validation function
            validator = kwarg
            validation_arg = ()
        else:
            validation_arg = (kwarg,)
        key = '_valid_' + validator
        if key not in _locals:
            raise SaltInvocationError(
                'Validator function missing for argument \'{0}\'. Please '
                'report this.'.format(kwarg)
            )
        # Run validation function
        _locals[key](*validation_arg)

    # Clear any context variables created during validation process
    for key in list(__context__):
        try:
            if key.startswith('validation.docker.'):
                __context__.pop(key)
        except AttributeError:
            pass


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

        salt myminion dockerng.depends myimage
        salt myminion dockerng.depends 0123456789ab
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

        salt myminion dockerng.diff mycontainer
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

        salt myminion dockerng.exists mycontainer
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

            $ salt myminion dockerng.history nginx:latest quiet=True
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

        salt myminion dockerng.exists mycontainer
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

        salt myminion dockerng.images
        salt myminion dockerng.images all=True
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

        salt myminion dockerng.info
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

        salt myminion dockerng.inspect mycontainer
        salt myminion dockerng.inspect busybox
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
    Retrieves container information. Equivalent to running the ``docker
    inspect`` Docker CLI command, but will only look for container information.

    name
        Container name or ID


    **RETURN DATA**

    A dictionary of container information


    CLI Example:

    .. code-block:: bash

        salt myminion dockerng.inspect_container mycontainer
        salt myminion dockerng.inspect_container 0123456789ab
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

        salt myminion dockerng.inspect_image busybox
        salt myminion dockerng.inspect_image centos:6
        salt myminion dockerng.inspect_image 0123456789ab
    '''
    ret = _client_wrapper('inspect_image', name)
    for param in ('Size', 'VirtualSize'):
        if param in ret:
            ret['{0}_Human'.format(param)] = _size_fmt(ret[param])
    return ret


def list_containers(**kwargs):
    '''
    Returns a list of containers by name. This is different from
    :py:func:`dockerng.ps <salt.modules.dockerng.ps_>` in that
    :py:func:`dockerng.ps <salt.modules.dockerng.ps_>` returns its results
    organized by container ID.

    all : False
        If ``True``, stopped containers will be included in return data

    CLI Example:

    .. code-block:: bash

        salt myminion dockerng.inspect_image <image>
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

        salt myminion dockerng.list_tags
    '''
    ret = set()
    for item in six.itervalues(images()):
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

        salt myminion dockerng.logs mycontainer
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

        salt myminion dockerng.pid mycontainer
        salt myminion dockerng.pid 0123456789ab
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

        salt myminion dockerng.port mycontainer
        salt myminion dockerng.port mycontainer 5000
        salt myminion dockerng.port mycontainer 5000/udp
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

        salt myminion dockerng.ps
        salt myminion dockerng.ps all=True
        salt myminion dockerng.ps filters="{'label': 'role=web'}"
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

        salt myminion dockerng.state mycontainer
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

        salt myminion dockerng.search centos
        salt myminion dockerng.search centos official=True
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

        salt myminion dockerng.top mycontainer
        salt myminion dockerng.top 0123456789ab
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

        salt myminion dockerng.version
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
           validate_ip_addrs=True,
           client_timeout=CLIENT_TIMEOUT,
           **kwargs):
    '''
    Create a new container

    name
        Name for the new container. If not provided, Docker will randomly
        generate one for you.

    image
        Image from which to create the container

    command or cmd
        Command to run in the container

        Example: ``command=bash`` or ``cmd=bash``

        .. versionchanged:: 2015.8.1
            ``cmd`` is now also accepted

    hostname
        Hostname of the container. If not provided, and if a ``name`` has been
        provided, the ``hostname`` will default to the ``name`` that was
        passed.

        Example: ``hostname=web1``

        .. warning::

            If the container is started with ``network_mode=host``, the
            hostname will be overridden by the hostname of the Minion.

    domainname
        Domain name of the container

        Example: ``domainname=domain.tld``

    interactive : False
        Leave stdin open

        Example: ``interactive=True``

    tty : False
        Attach TTYs

        Example: ``tty=True``

    detach : True
        If ``True``, run ``command`` in the background (daemon mode)

        Example: ``detach=False``

    user
        User under which to run docker

        Example: ``user=foo``

    memory : 0
        Memory limit. Can be specified in bytes or using single-letter units
        (i.e. ``512M``, ``2G``, etc.). A value of ``0`` (the default) means no
        memory limit.

        Example: ``memory=512M``, ``memory=1073741824``

    memory_swap : -1
        Total memory limit (memory plus swap). Set to ``-1`` to disable swap. A
        value of ``0`` means no swap limit.

        Example: ``memory_swap=1G``, ``memory_swap=2147483648``

    mac_address
        MAC address to use for the container. If not specified, a random MAC
        address will be used.

        Example: ``mac_address=01:23:45:67:89:0a``

    network_disabled : False
        If ``True``, networking will be disabled within the container

        Example: ``network_disabled=True``

    working_dir
        Working directory inside the container

        Example: ``working_dir=/var/log/nginx``

    entrypoint
        Entrypoint for the container. Either a string (e.g. ``"mycmd --arg1
        --arg2"``) or a Python list (e.g.  ``"['mycmd', '--arg1', '--arg2']"``)

        Example: ``entrypoint="cat access.log"``

    environment
        Either a dictionary of environment variable names and their values, or
        a Python list of strings in the format ``VARNAME=value``.

        Example: ``"{'VAR1': 'value', 'VAR2': 'value'}"``,
        ``"['VAR1=value', 'VAR2=value']"``

    ports
        A list of ports to expose on the container. Can be passed as
        comma-separated list or a Python list. If the protocol is omitted, the
        port will be assumed to be a TCP port.

        Example: ``1111,2222/udp``, ``"['1111/tcp', '2222/udp']"``

    volumes : None
        List of directories to expose as volumes. Can be passed as a
        comma-separated list or a Python list.

        Example: ``volumes=/mnt/vol1,/mnt/vol2``, ``volumes="[/mnt/vol1,
        /mnt/vol2]"``

    cpu_shares
        CPU shares (relative weight)

        Example: ``cpu_shares=0.5``, ``cpu_shares=1``

    cpuset
        CPUs on which which to allow execution, specified as a string
        containing a range (e.g. ``0-3``) or a comma-separated list of CPUs
        (e.g. ``0,1``).

        Example: ``cpuset="0-3"``, ``cpuset="0,1"``

    client_timeout
        Timeout in seconds for the Docker client. This is not a timeout for
        this function, but for receiving a response from the API.

        .. note::

            This is only used if Salt needs to pull the requested image.

    labels
        Add Metadata to the container. Can be a list of strings/dictionaries
        or a dictionary of strings (keys and values).

        Example: ``labels=LABEL1,LABEL2``,
        ``labels="{'LABEL1': 'value1', 'LABEL2': 'value2'}"``

    validate_ip_addrs : True
        For parameters which accept IP addresses as input, IP address
        validation will be performed. To disable, set this to ``False``

    binds
        Files/directories to bind mount. Each bind mount should be passed in
        the format ``<host_path>:<container_path>:<read_only>``, where
        ``<read_only>`` is one of ``rw`` (for read-write access) or ``ro`` (for
        read-only access).  Optionally, the read-only information can be left
        off the end and the bind mount will be assumed to be read-write.
        Examples 2 and 3 below are equivalent.

        Example 1: ``binds=/srv/www:/var/www:ro``

        Example 2: ``binds=/srv/www:/var/www:rw``

        Example 3: ``binds=/srv/www:/var/www``

    port_bindings
        Bind exposed ports which were exposed using the ``ports`` argument to
        :py:func:`dockerng.create <salt.modules.dockerng.create>`. These
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

        Example 1: ``port_bindings="5000:5000,2123:2123/udp,8080"``

        Example 2: ``port_bindings="['5000:5000', '2123:2123/udp', '8080']"``

        .. note::

            When configuring bindings for UDP ports, the protocol must be
            passed in the ``containerPort`` value, as seen in the examples
            above.

    lxc_conf
        Additional LXC configuration parameters to set before starting the
        container.

        Example: ``lxc_conf="{lxc.utsname: docker}"``

        .. note::

            These LXC configuration parameters will only have the desired
            effect if the container is using the LXC execution driver, which
            has not been the default for some time.

    publish_all_ports : False
        Allocates a random host port for each port exposed using the ``ports``
        argument to :py:func:`dockerng.create <salt.modules.dockerng.create>`.

        Example: ``publish_all_ports=True``

    links
        Link this container to another. Links should be specified in the format
        ``<container_name_or_id>:<link_alias>``. Multiple links can be passed,
        ether as a comma separated list or a Python list.

        Example 1: ``links=mycontainer:myalias``,
        ``links=web1:link1,web2:link2``

        Example 2: ``links="['mycontainer:myalias']"``
        ``links="['web1:link1', 'web2:link2']"``

    dns
        List of DNS nameservers. Can be passed as a comma-separated list or a
        Python list.

        Example: ``dns=8.8.8.8,8.8.4.4`` or ``dns="[8.8.8.8, 8.8.4.4]"``

        .. note::

            To skip IP address validation, use ``validate_ip_addrs=False``

    dns_search
        List of DNS search domains. Can be passed as a comma-separated list
        or a Python list.

        Example: ``dns_search=foo1.domain.tld,foo2.domain.tld`` or
        ``dns_search="[foo1.domain.tld, foo2.domain.tld]"``

    volumes_from
        Container names or IDs from which the container will get volumes. Can
        be passed as a comma-separated list or a Python list.

        Example: ``volumes_from=foo``, ``volumes_from=foo,bar``,
        ``volumes_from="[foo, bar]"``

    network_mode : bridge
        One of the following:

        - ``bridge`` - Creates a new network stack for the container on the
          docker bridge
        - ``null`` - No networking (equivalent of the Docker CLI argument
          ``--net=none``)
        - ``container:<name_or_id>`` - Reuses another container's network stack
        - ``host`` - Use the host's network stack inside the container

          .. warning::

                Using ``host`` mode gives the container full access to the
                hosts system's services (such as D-bus), and is therefore
                considered insecure.

        Example: ``network_mode=null``, ``network_mode=container:web1``

    restart_policy
        Set a restart policy for the container. Must be passed as a string in
        the format ``policy[:retry_count]`` where ``policy`` is one of
        ``always`` or ``on-failure``, and ``retry_count`` is an optional limit
        to the number of retries. The retry count is ignored when using the
        ``always`` restart policy.

        Example 1: ``restart_policy=on-failure:5``

        Example 2: ``restart_policy=always``

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

    extra_hosts
        Additional hosts to add to the container's /etc/hosts file. Can be
        passed as a comma-separated list or a Python list. Requires Docker
        1.3.0 or newer.

        Example: ``extra_hosts=web1:10.9.8.7,web2:10.9.8.8``

        .. note::

            To skip IP address validation, use ``validate_ip_addrs=False``

    pid_mode
        Set to ``host`` to use the host container's PID namespace within the
        container. Requires Docker 1.5.0 or newer.

        Example: ``pid_mode=host``

    **RETURN DATA**

    A dictionary containing the following keys:

    - ``Id`` - ID of the newly-created container
    - ``Name`` - Name of the newly-created container


    CLI Example:

    .. code-block:: bash

        # Create a data-only container
        salt myminion dockerng.create myuser/mycontainer volumes="/mnt/vol1,/mnt/vol2"
        # Create a CentOS 7 container that will stay running once started
        salt myminion dockerng.create centos:7 name=mycent7 interactive=True tty=True command=bash
    '''
    if 'cmd' in kwargs:
        if 'command' in kwargs:
            raise SaltInvocationError(
                'Only one of \'command\' and \'cmd\' can be used. Both '
                'arguments are equivalent.'
            )
        kwargs['command'] = kwargs.pop('cmd')

    try:
        # Try to inspect the image, if it fails then we know we need to pull it
        # first.
        inspect_image(image)
    except Exception:
        pull(image, client_timeout=client_timeout)

    create_kwargs = salt.utils.clean_kwargs(**copy.deepcopy(kwargs))
    if create_kwargs.get('hostname') is None \
            and create_kwargs.get('name') is not None:
        create_kwargs['hostname'] = create_kwargs['name']

    if create_kwargs.pop('validate_input', False):
        _validate_input(create_kwargs, validate_ip_addrs=validate_ip_addrs)

    # Rename the kwargs whose names differ from their counterparts in the
    # docker.client.Client class member functions. Can't use iterators here
    # because we're going to be modifying the dict.
    for key in list(six.iterkeys(VALID_CREATE_OPTS)):
        if key in create_kwargs:
            val = VALID_CREATE_OPTS[key]
            if 'api_name' in val:
                create_kwargs[val['api_name']] = create_kwargs.pop(key)

    # API v1.15 introduced HostConfig parameter
    # https://docs.docker.com/engine/reference/api/docker_remote_api_v1.15/#create-a-container
    if salt.utils.version_cmp(version()['ApiVersion'], '1.15') > 0:
        client = __context__['docker.client']
        host_config_args = get_client_args()['host_config']
        create_kwargs['host_config'] = client.create_host_config(
            **dict((arg, create_kwargs.pop(arg, None)) for arg in host_config_args if arg != 'version')
        )

    log.debug(
        'dockerng.create is using the following kwargs to create '
        'container \'{0}\' from image \'{1}\': {2}'
        .format(name, image, create_kwargs)
    )
    time_started = time.time()
    response = _client_wrapper('create_container',
                               name=name,
                               image=image,
                               **create_kwargs)
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

        salt myminion dockerng.copy_from mycontainer /var/log/nginx/access.log /home/myuser
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
        log.debug('{0}:{1} and {2} are the same file, skipping copy'
                  .format(name, source, dest))
        return True

    log.debug('Copying {0} from container \'{1}\' to local path {2}'
              .format(source, name, dest))

    cmd = ['docker', 'cp', '{0}:{1}'.format(name, source), dest_dir]
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

        salt myminion dockerng.copy_to mycontainer /tmp/foo /root/foo
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

        salt myminion dockerng.export mycontainer /tmp/mycontainer.tar
        salt myminion dockerng.export mycontainer /tmp/mycontainer.tar.xz push=True
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

        salt myminion dockerng.rm mycontainer
        salt myminion dockerng.rm mycontainer force=True
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
          image=None,
          cache=True,
          rm=True,
          api_response=False,
          fileobj=None):
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

        salt myminion dockerng.build /path/to/docker/build/dir image=myimage:dev
        salt myminion dockerng.build https://github.com/myuser/myrepo.git image=myimage:latest
    '''
    _prep_pull()

    image = ':'.join(_get_repo_tag(image))
    time_started = time.time()
    response = _client_wrapper('build',
                               path=path,
                               tag=image,
                               quiet=False,
                               fileobj=fileobj,
                               rm=rm,
                               nocache=not cache)
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

        salt myminion dockerng.commit mycontainer myuser/myimage
        salt myminion dockerng.commit mycontainer myuser/myimage:mytag
    '''
    repo_name, repo_tag = _get_repo_tag(image)
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
      <salt.modules.dockerng.load>` (or the ``docker load`` Docker CLI
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

        salt myminion dockerng.dangling
        salt myminion dockerng.dangling prune=True
    '''
    all_images = images(all=True)
    dangling_images = [x[:12] for x in _get_top_level_images(all_images)
                       if '<none>:<none>' in all_images[x]['RepoTags']]
    if not prune:
        return dangling_images

    ret = {}
    for image in dangling_images:
        try:
            ret.setdefault(image, {})['Removed'] = rmi(image, force=force)
        except Exception as exc:
            err = '{0}'.format(exc)
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

        salt myminion dockerng.import /tmp/cent7-minimal.tar.xz myuser/centos
        salt myminion dockerng.import /tmp/cent7-minimal.tar.xz myuser/centos:7
        salt myminion dockerng.import salt://dockerimages/cent7-minimal.tar.xz myuser/centos:7
    '''
    repo_name, repo_tag = _get_repo_tag(image)
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
    Load a tar archive that was created using :py:func:`dockerng.save
    <salt.modules.dockerng.save>` (or via the Docker CLI using ``docker
    save``).

    path
        Path to docker tar archive. Path can be a file on the Minion, or the
        URL of a file on the Salt fileserver (i.e.
        ``salt://path/to/docker/saved/image.tar``). To load a file from a
        saltenv other than ``base`` (e.g. ``dev``), pass it at the end of the
        URL (ex. ``salt://path/to/rootfs/tarball.tar.xz?saltenv=dev``).

    image : None
        If specified, the topmost layer of the newly-loaded image will be
        tagged with the specified repo and tag using :py:func:`dockerng.tag
        <salt.modules.dockerng.tag_>`. The image name should be specified in
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

        salt myminion dockerng.load /path/to/image.tar
        salt myminion dockerng.load salt://path/to/docker/saved/image.tar image=myuser/myimage:mytag
    '''
    if image is not None:
        image = ':'.join(_get_repo_tag(image))
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

        salt myminion dockerng.layers centos:7
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
         client_timeout=CLIENT_TIMEOUT):
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

        salt myminion dockerng.pull centos
        salt myminion dockerng.pull centos:6
    '''
    _prep_pull()

    repo_name, repo_tag = _get_repo_tag(image)
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
         client_timeout=CLIENT_TIMEOUT):
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

        salt myminion dockerng.push myuser/mycontainer
        salt myminion dockerng.push myuser/mycontainer:mytag
    '''
    if ':' in image:
        repo_name, repo_tag = _get_repo_tag(image)
    else:
        repo_name = image
        repo_tag = None
        log.info('Attempting to push all tagged images matching {0}'
                 .format(repo_name))

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

        salt myminion dockerng.rmi busybox
        salt myminion dockerng.rmi busybox force=True
        salt myminion dockerng.rmi foo bar baz
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

        salt myminion dockerng.save centos:7 /tmp/cent7.tar
        salt myminion dockerng.save 0123456789ab cdef01234567 /tmp/saved.tar
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

        salt myminion dockerng.tag 0123456789ab myrepo/mycontainer
        salt myminion dockerng.tag 0123456789ab myrepo/mycontainer:mytag
    '''
    image_id = inspect_image(name)['Id']
    repo_name, repo_tag = _get_repo_tag(image)
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

        salt myminion dockerng.networks names="['network-web']"
        salt myminion dockerng.networks ids="['1f9d2454d0872b68dd9e8744c6e7a4c66b86f10abaccc21e14f7f014f729b2bc']"
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

        salt myminion dockerng.create_network web_network driver=bridge
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

        salt myminion dockerng.remove_network 1f9d2454d0872b68dd9e8744c6e7a4c66b86f10abaccc21e14f7f014f729b2bc
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

        salt myminion dockerng.inspect_network 1f9d2454d0872b68dd9e8744c6e7a4c66b86f10abaccc21e14f7f014f729b2bc
    '''
    response = _client_wrapper('inspect_network', network_id)
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response


@_api_version(1.21)
@_client_version('1.5.0')
def connect_container_to_network(container, network_id):
    '''
    Connect container to network.

    container
        Container name or ID

    network_id
        ID of network

    CLI Example:

    .. code-block:: bash

        salt myminion dockerng.connect_container_from_network web-1 1f9d2454d0872b68dd9e8744c6e7a4c66b86f10abaccc21e14f7f014f729b2bc
    '''
    response = _client_wrapper('connect_container_to_network',
                               container,
                               network_id)
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

        salt myminion dockerng.disconnect_container_from_network web-1 1f9d2454d0872b68dd9e8744c6e7a4c66b86f10abaccc21e14f7f014f729b2bc
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

        salt myminion dockerng.volumes filters="{'dangling': True}"
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

        salt myminion dockerng.create_volume my_volume driver=local
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

        salt myminion dockerng.remove_volume my_volume
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

        salt myminion dockerng.inspect_volume my_volume
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

        salt myminion dockerng.kill mycontainer
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

        salt myminion dockerng.pause mycontainer
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

        salt myminion dockerng.restart mycontainer
        salt myminion dockerng.restart mycontainer timeout=20
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

        salt myminion dockerng.signal mycontainer SIGHUP
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

        salt myminion dockerng.start mycontainer
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
def stop(name, timeout=STOP_TIMEOUT, **kwargs):
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

        salt myminion dockerng.stop mycontainer
        salt myminion dockerng.stop mycontainer unpause=True
        salt myminion dockerng.stop mycontainer timeout=20
    '''
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

        salt myminion dockerng.pause mycontainer
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

        salt myminion dockerng.wait mycontainer
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
                'cmd.script: Unable to clean tempfile \'{0}\': {1}'.format(
                    path,
                    exc
                )
            )

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

        salt myminion dockerng.retcode mycontainer 'ls -l /etc'
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

        salt myminion dockerng.run mycontainer 'ls -l /etc'
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

        salt myminion dockerng.run_all mycontainer 'ls -l /etc'
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

        salt myminion dockerng.run_stderr mycontainer 'ls -l /etc'
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

        salt myminion dockerng.run_stdout mycontainer 'ls -l /etc'
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

        salt myminion dockerng.script mycontainer salt://docker_script.py
        salt myminion dockerng.script mycontainer salt://scripts/runme.sh 'arg1 arg2 "arg 3"'
        salt myminion dockerng.script mycontainer salt://scripts/runme.sh stdin='one\\ntwo\\nthree\\nfour\\nfive\\n' output_loglevel=quiet
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

        salt myminion dockerng.script_retcode mycontainer salt://docker_script.py
        salt myminion dockerng.script_retcode mycontainer salt://scripts/runme.sh 'arg1 arg2 "arg 3"'
        salt myminion dockerng.script_retcode mycontainer salt://scripts/runme.sh stdin='one\\ntwo\\nthree\\nfour\\nfive\\n' output_loglevel=quiet
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


def get_client_args():
    '''
    .. versionadded:: 2016.3.6,2016.11.4,Nitrogen

    Returns the args for docker-py's `low-level API`_, organized by container
    config, host config, and networking config.

    .. _`low-level API`: http://docker-py.readthedocs.io/en/stable/api.html

    CLI Example:

    .. code-block:: bash

        salt myminion docker.get_client_args
    '''
    try:
        config_args = _argspec(docker.types.ContainerConfig.__init__).args
    except AttributeError:
        try:
            config_args = _argspec(docker.utils.create_container_config).args
        except AttributeError:
            raise CommandExecutionError(
                'Failed to get create_container_config argspec'
            )

    try:
        host_config_args = \
            _argspec(docker.types.HostConfig.__init__).args
    except AttributeError:
        try:
            host_config_args = _argspec(docker.utils.create_host_config).args
        except AttributeError:
            raise CommandExecutionError(
                'Failed to get create_host_config argspec'
            )

    try:
        endpoint_config_args = \
            _argspec(docker.types.EndpointConfig.__init__).args
    except AttributeError:
        try:
            endpoint_config_args = \
                _argspec(docker.utils.utils.create_endpoint_config).args
        except AttributeError:
            try:
                endpoint_config_args = \
                    _argspec(docker.utils.create_endpoint_config).args
            except AttributeError:
                raise CommandExecutionError(
                    'Failed to get create_endpoint_config argspec'
                )

    for arglist in (config_args, host_config_args, endpoint_config_args):
        try:
            # The API version is passed automagically by the API code that
            # imports these classes/functions and is not an arg that we will be
            # passing, so remove it if present.
            arglist.remove('version')
        except ValueError:
            pass

    # Remove any args in host or networking config from the main config dict.
    # This keeps us from accidentally allowing args that have been moved from
    # the container config to the host config (but are still accepted by
    # create_container_config so warnings can be issued).
    for arglist in (host_config_args, endpoint_config_args):
        for item in arglist:
            try:
                config_args.remove(item)
            except ValueError:
                # Arg is not in config_args
                pass

    return {'config': config_args,
            'host_config': host_config_args,
            'networking_config': endpoint_config_args}
