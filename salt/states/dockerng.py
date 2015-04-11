# -*- coding: utf-8 -*-
'''
Management of Docker containers

.. versionadded:: Beryllium


This is the state module to accompany the :mod:`docker-ng
<salt.modules.dockerng>` execution module.

.. note::

    To pull from a Docker registry, authentication must be configured. See
    :ref:`here <docker-authentication>` for more information on how to
    configure access to docker registries in :ref:`Pillar <pillar>` data.
'''

from __future__ import absolute_import
import logging
import sys
import time
import traceback

# Import salt libs
from salt.exceptions import CommandExecutionError, SaltInvocationError
# pylint: disable=no-name-in-module,import-error
from salt.modules.dockerng import (
    CLIENT_TIMEOUT,
    VALID_CREATE_OPTS,
    VALID_RUNTIME_OPTS,
    _validate_input,
    _get_repo_tag
)
# pylint: enable=no-name-in-module,import-error
import salt.utils
import salt.ext.six as six

# Enable proper logging
log = logging.getLogger(__name__)  # pylint: disable=invalid-name

# Define the module's virtual name
__virtualname__ = 'docker-ng'

NOTSET = object()


def __virtual__():
    '''
    Only load if the dockerio execution module is available
    '''
    if 'docker-ng.version' in __salt__:
        global _validate_input  # pylint: disable=global-statement
        _validate_input = salt.utils.namespaced_function(
            _validate_input, globals()
        )
        return __virtualname__
    return False


def _format_comments(comments):
    '''
    DRY code for joining comments together and conditionally adding a period at
    the end.
    '''
    ret = '. '.join(comments)
    if len(comments) > 1:
        ret += '.'
    return ret


def _api_mismatch(param):
    '''
    Raise an exception if a config value can't be found at the expected
    location in a call to docker-ng.inspect_container
    '''
    raise CommandExecutionError(
        'Unable to compare configuration for the \'{0}\' parameter. This may '
        'be due to a change in the Docker API'.format(param)
    )


def _prep_input(kwargs):
    '''
    Repack (if necessary) data that should be in a dict but is easier to
    configure in an SLS file as a dictlist. If the data type is a string, then
    skip repacking and let _validate_input() try to sort it out.
    '''
    for kwarg in ('environment', 'lxc_conf'):
        kwarg_value = kwargs.get(kwarg)
        if kwarg_value is not None \
                and not isinstance(kwarg_value, six.string_types):
            err = ('Invalid {0} configuration. See the documentation for '
                   'proper usage.'.format(kwarg))
            if salt.utils.is_dictlist(kwarg_value):
                new_kwarg_value = salt.utils.repack_dictlist(kwarg_value)
                if not kwarg_value:
                    raise SaltInvocationError(err)
                kwargs[kwarg] = new_kwarg_value
            if not isinstance(kwargs[kwarg], dict):
                raise SaltInvocationError(err)


def _compare(actual, create_kwargs, runtime_kwargs):
    '''
    Compare the desired configuration against the actual configuration returned
    by docker-ng.inspect_container
    '''
    _get = lambda path: (
        salt.utils.traverse_dict(actual, path, NOTSET, delimiter=':')
    )
    ret = {}
    for desired, valid_opts in ((create_kwargs, VALID_CREATE_OPTS),
                                (runtime_kwargs, VALID_RUNTIME_OPTS)):
        for item, data, in six.iteritems(desired):
            if item not in valid_opts:
                log.error(
                    'Trying to compare \'{0}\', but it is not a valid '
                    'parameter. Skipping.'.format(item)
                )
                continue
            log.trace('docker-ng.running: comparing ' + item)
            conf_path = valid_opts[item]['path']
            if isinstance(conf_path, tuple):
                actual_data = [_get(x) for x in conf_path]
                for val in actual_data:
                    if val is NOTSET:
                        _api_mismatch(item)
            else:
                actual_data = _get(conf_path)
                if actual_data is NOTSET:
                    _api_mismatch(item)
            log.trace('docker-ng.running ({0}): desired value: {1}'
                      .format(item, data))
            log.trace('docker-ng.running ({0}): actual value: {1}'
                      .format(item, actual_data))

            if actual_data is None and data is not None \
                    or actual_data is not None and data is None:
                ret.update({item: {'old': actual_data, 'new': data}})
                continue

            # 'create' comparison params
            if item == 'detach':
                # Something unique here. Two fields to check, if both are False
                # then detach is True
                actual_detach = all(x is False for x in actual_data)
                log.trace('docker-ng.running ({0}): munged actual value: {1}'
                          .format(item, actual_detach))
                if actual_detach != data:
                    ret.update({item: {'old': actual_detach, 'new': data}})
                continue

            elif item == 'environment':
                actual_env = {}
                for env_var in actual_data:
                    try:
                        key, val = env_var.split('=', 1)
                    except (AttributeError, ValueError):
                        log.warning(
                            'Unexpected environment variable in inspect '
                            'output {0}'.format(env_var)
                        )
                        continue
                    else:
                        actual_env[key] = val
                log.trace('docker-ng.running ({0}): munged actual value: {1}'
                          .format(item, actual_env))
                env_diff = {}
                for key in data:
                    actual_val = actual_env.get(key)
                    if data[key] != actual_val:
                        env_ptr = env_diff.setdefault(item, {})
                        env_ptr.setdefault('old', {})[key] = actual_val
                        env_ptr.setdefault('new', {})[key] = data[key]
                if env_diff:
                    ret.update(env_diff)
                continue

            elif item == 'ports':
                # Munge the desired configuration instead of the actual
                # configuration here, because the desired configuration is a
                # list of ints or tuples, and that won't look as good in the
                # nested outputter as a simple comparison of lists of
                # port/protocol pairs (as found in the "actual" dict).
                actual_ports = sorted(actual_data)
                desired_ports = []
                for port_def in data:
                    if isinstance(port_def, tuple):
                        desired_ports.append('{0}/{1}'.format(*port_def))
                    else:
                        desired_ports.append('{0}/tcp'.format(port_def))
                desired_ports.sort()
                log.trace('docker-ng.running ({0}): munged actual value: {1}'
                          .format(item, actual_ports))
                log.trace('docker-ng.running ({0}): munged desired value: {1}'
                          .format(item, desired_ports))
                if actual_ports != desired_ports:
                    ret.update({item: {'old': actual_ports,
                                       'new': desired_ports}})
                continue

            # 'runtime' comparison params
            elif item == 'binds':
                actual_binds = []
                for bind in actual_data:
                    bind_parts = bind.split(':')
                    if len(bind_parts) == 2:
                        actual_binds.append(bind + ':rw')
                    else:
                        actual_binds.append(bind)
                desired_binds = []
                for host_path, bind_data in six.iteritems(data):
                    desired_binds.append(
                        '{0}:{1}:{2}'.format(
                            host_path,
                            bind_data['bind'],
                            'ro' if bind_data['ro'] else 'rw'
                        )
                    )
                actual_binds.sort()
                desired_binds.sort()
                if actual_binds != desired_binds:
                    ret.update({item: {'old': actual_binds,
                                       'new': desired_binds}})
                    continue

            elif item == 'port_bindings':
                actual_binds = []
                for container_port, bind_list in six.iteritems(actual_data):
                    if container_port.endswith('/tcp'):
                        container_port = container_port[:-4]
                    for bind_data in bind_list:
                        # Port range will have to be updated for future Docker
                        # versions (see
                        # https://github.com/docker/docker/issues/10220).  Note
                        # that Docker 1.5.0 (released a few weeks after the fix
                        # was merged) does not appear to have this fix in it,
                        # so we're probably looking at 1.6.0 for this fix.
                        if bind_data['HostPort'] == '' or \
                                49153 <= int(bind_data['HostPort']) <= 65535:
                            host_port = ''
                        else:
                            host_port = bind_data['HostPort']
                        if bind_data['HostIp'] in ('0.0.0.0', ''):
                            if host_port:
                                bind_def = (host_port, container_port)
                            else:
                                bind_def = (container_port,)
                        else:
                            bind_def = (bind_data['HostIp'],
                                        host_port,
                                        container_port)
                        actual_binds.append(':'.join(bind_def))

                desired_binds = []
                for container_port, bind_list in six.iteritems(data):
                    try:
                        if container_port.endswith('/tcp'):
                            container_port = container_port[:-4]
                    except AttributeError:
                        # The port's protocol was not specified, so it is
                        # assumed to be TCP. Thus, according to docker-py usage
                        # examples, the port was passed as an int. Convert it
                        # to a string here.
                        container_port = str(container_port)
                    for bind_data in bind_list:
                        if isinstance(bind_data, tuple):
                            try:
                                host_ip, host_port = bind_data
                                host_port = str(host_port)
                            except ValueError:
                                host_ip = bind_data[0]
                                host_port = ''
                            bind_def = '{0}:{1}:{2}'.format(
                                host_ip, host_port, container_port
                            )
                        else:
                            if bind_data is not None:
                                bind_def = '{0}:{1}'.format(
                                    bind_data, container_port
                                )
                            else:
                                bind_def = container_port
                        desired_binds.append(bind_def)
                actual_binds.sort()
                desired_binds.sort()
                log.trace('docker-ng.running ({0}): munged actual value: {1}'
                          .format(item, actual_binds))
                log.trace('docker-ng.running ({0}): munged desired value: {1}'
                          .format(item, desired_binds))
                if actual_binds != desired_binds:
                    ret.update({item: {'old': actual_binds,
                                       'new': desired_binds}})
                    continue

            elif item == 'links':
                actual_links = []
                for link in actual_data:
                    try:
                        link_name, alias_info = link.split(':')
                    except ValueError:
                        log.error(
                            'Failed to compare link {0}, unrecognized format'
                            .format(link)
                        )
                        continue
                    container_name, _, link_alias = alias_info.rpartition('/')
                    if not container_name:
                        log.error(
                            'Failed to interpret link alias from {0}, '
                            'unrecognized format'.format(alias_info)
                        )
                        continue
                    actual_links.append((link_name, link_alias))
                actual_links.sort()
                desired_links = sorted(data)
                if actual_links != desired_links:
                    ret.update({item: {'old': actual_links,
                                       'new': desired_links}})
                    continue

            elif item == 'extra_hosts':
                actual_hosts = sorted(actual_data)
                desired_hosts = sorted(
                    ['{0}:{1}'.format(x, y) for x, y in six.iteritems(data)]
                )
                if actual_hosts != desired_hosts:
                    ret.update({item: {'old': actual_hosts,
                                       'new': desired_hosts}})
                    continue

            elif isinstance(data, list):
                # Compare two sorted lists of items. Won't work for "command"
                # or "entrypoint" because those are both shell commands and the
                # original order matters. It will, however, work for "volumes"
                # because even though "volumes" is a sub-dict nested within the
                # "actual" dict sorted(somedict) still just gives you a sorted
                # list of the dictionary's keys. And we don't care about the
                # value for "volumes", just its keys.
                actual_data = sorted(actual_data)
                desired_data = sorted(data)
                log.trace('docker-ng.running ({0}): munged actual value: {1}'
                          .format(item, actual_data))
                log.trace('docker-ng.running ({0}): munged desired value: {1}'
                          .format(item, desired_data))
                if actual_data != desired_data:
                    ret.update({item: {'old': actual_data,
                                       'new': desired_data}})
                continue

            else:
                # Generic comparison, works on strings, numeric types, and
                # booleans
                if actual_data != data:
                    ret.update({item: {'old': actual_data, 'new': data}})
    return ret


def running(name,
            pull=None,
            build=None,
            load=None,
            update=False,
            force=False,
            stop_timeout=10,
            insecure_registry=False,
            validate_ip_addrs=True,
            client_timeout=CLIENT_TIMEOUT,
            **kwargs):
    '''
    Ensures that a container is running

    name
        Name of the container

    pull
        Name or ID of an image from a Docker registry. Image names can be
        specified either using ``repo:tag`` notation, or just the repo name (in
        which case a tag of ``latest`` is assumed). If the image is not
        present, it will be pulled.

        If the specified image already exists, it will not be pulled unless
        ``update`` is set to ``True``.

        .. code-block:: yaml

            mycontainer:
              docker-ng.running:
                - pull: myuser/myimage:mytag
    build
        Path to directory on the Minion containing a Dockerfile

        .. code-block:: yaml

            mycontainer:
              docker-ng.running:
                - build:
                    - myuser/myimage:mytag: /home/myuser/docker/myimage

        The image will be built using :py:func:`docker-ng.build
        <salt.modules.dockerng.build>` and the specified image name and tag
        applied to it.

        If the specified image already exists, then the build will not be
        performed unless ``update`` is set to ``True``.

    load
        Loads a tar archive created with :py:func:`docker-ng.load
        <salt.modules.dockerng.load>` (or the ``docker load`` Docker CLI
        command). Here's a usage example:

        .. code-block:: yaml

            mycontainer:
              docker-ng.running:
                - load:
                  - myuser/myimage:mytag: salt://path/to/image.tar

        The image will be loaded using :py:func:`docker-ng.load
        <salt.modules.dockerng.load>`, and then tagged.

        If the specified image already exists, then the build will not be
        performed unless ``update`` is set to ``True``.

    update : False
        Set this parameter to ``True`` to make Salt pull/build/load the image
        even if the named container exists and matches the specified image. If
        the pull/build/load results in a new ID for the image, then the
        container will be replaced with the updated image.

    force : False
        Set this parameter to ``True`` to force Salt to pull/build/load the
        image and replace the container.

        .. note::

            This option can also be overridden by Pillar data. If the Minion
            has a pillar variable named ``docker-ng.running.force`` which is
            set to ``True``, it will turn on this option. This pillar variable
            can even be set at runtime. For example:

            .. code-block:: bash

                salt myminion state.sls docker_stuff pillar="{docker-ng.running.force: True}"

            If this pillar variable is present and set to ``False``, then it
            will turn off this option.

            For more granular control, setting a pillar variable named
            ``docker-ng.running.force.container_name`` will affect only the
            named container.

    stop_timeout : 10
        If the container needs to be replaced, the container will be stopped
        using :py:func:`docker-ng.stop <salt.modules.dockerng.stop>`. The value
        of this parameter will be passed to :py:func:`docker-ng.stop
        <salt.modules.dockerng.stop>` as the ``timeout`` value, telling Docker
        how long to wait for a graceful shutdown before killing the container.

    insecure_registry : False
        If ``True``, the Docker client will permit the use of insecure
        (non-HTTPS) registries. This only applies if the ``pull`` argument is
        used.

    validate_ip_addrs : True
        For parameters which accept IP addresses as input, IP address
        validation will be performed. To disable, set this to ``False``

    client_timeout
        Timeout in seconds for the Docker client. This is not a timeout for
        the state, but for receiving a response from the API.

        .. note::

            This is only used if Salt needs to pull the requested image.


    **CONTAINER CONFIGURATION PARAMETERS**

    command
        Command to run in the container

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - command: bash

    hostname
        Hostname of the container. If not provided, and if a ``name`` has been
        provided, the ``hostname`` will default to the ``name`` that was
        passed.

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - hostname: web1

        .. warning::

            ``hostname`` cannot be set if ``network_mode`` is set to ``host``.
            The below example will result in an error:

            .. code-block:: yaml

                foo:
                  docker-ng.running:
                    - pull: bar/baz:latest
                    - hostname: web1
                    - network_mode: host

    domainname
        Domain name of the container

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - hostname: domain.tld


    interactive : False
        Leave stdin open

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - interactive: True

    tty : False
        Attach TTYs

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - tty: True

    detach : True
        If ``True``, run ``command`` in the background (daemon mode)

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - detach: False

    user
        User under which to run docker

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - user: foo

    memory : 0
        Memory limit. Can be specified in bytes or using single-letter units
        (i.e. ``512M``, ``2G``, etc.). A value of ``0`` (the default) means no
        memory limit.

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - memory: 512M

    memory_swap : -1
        Total memory limit (memory plus swap). Set to ``-1`` to disable swap. A
        value of ``0`` means no swap limit.

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - memory_swap: 1G

    mac_address
        MAC address to use for the container. If not specified, a random MAC
        address will be used.

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - mac_address: 01:23:45:67:89:0a

    network_disabled : False
        If ``True``, networking will be disabled within the container

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - network_disabled: True

    working_dir
        Working directory inside the container

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - working_dir: /var/log/nginx

    entrypoint
        Entrypoint for the container

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - entrypoint: "mycmd --arg1 --arg2"

        The entrypoint can also be specified as a list of arguments:

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - entrypoint:
                  - mycmd
                  - --arg1
                  - --arg2

    environment
        Either a list of variable/value mappings, or a list of strings in the
        format ``VARNAME=value``. The below two examples are equivalent:

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - environment:
                  - VAR1: value
                  - VAR2: value

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - environment:
                  - VAR1=value
                  - VAR2=value

    ports
        A list of ports to expose on the container. Can either be a
        comma-separated list or a YAML list. If the protocol is omitted, the
        port will be assumed to be a TCP port. The below two examples are
        equivalent:

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - ports: 1111,2222/udp

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - ports:
                  - 1111
                  - 2222/udp

    volumes : None
        List of directories to expose as volumes. Can either be a
        comma-separated list or a YAML list. The below two examples are
        equivalent:

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - volumes: /mnt/vol1,/mnt/vol2

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - volumes:
                  - /mnt/vol1
                  - /mnt/vol2

    cpu_shares
        CPU shares (relative weight)

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - cpu_shares: 0.5

    cpuset
        CPUs on which which to allow execution, specified as a string
        containing a range (e.g. ``0-3``) or a comma-separated list of CPUs
        (e.g. ``0,1``).

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - cpuset: "0,1"

    binds
        Files/directories to bind mount. Each bind mount should be passed in
        the format ``<host_path>:<container_path>:<read_only>``, where
        ``<read_only>`` is one of ``rw`` (for read-write access) or ``ro`` (for
        read-only access).

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - binds: /srv/www:/var/www:ro,/etc/foo.conf:/usr/local/etc/foo.conf:rw

        Binds can be passed as a YAML list instead of a comma-separated list:

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - binds:
                  - /srv/www:/var/www:ro
                  - /home/myuser/conf/foo.conf:/etc/foo.conf:rw

        Optionally, the read-only information can be left off the end and the
        bind mount will be assumed to be read-write. The example below is
        equivalent to the one above:

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - binds:
                  - /srv/www:/var/www:ro
                  - /home/myuser/conf/foo.conf:/etc/foo.conf

    port_bindings
        Bind exposed ports. Port bindings should be passed in the same way as
        the ``--publish`` argument to the ``docker run`` CLI command:

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

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - port_bindings: "5000:5000,2123:2123/udp,8080"

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - port_bindings:
                  - 5000:5000
                  - 2123:2123/udp
                  - 8080

        .. note::

            When configuring bindings for UDP ports, the protocol must be
            passed in the ``containerPort`` value, as seen in the examples
            above.

    lxc_conf
        Additional LXC configuration parameters to set before starting the
        container.

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - lxc_conf:
                  - lxc.utsname: docker

        .. note::

            These LXC configuration parameters will only have the desired
            effect if the container is using the LXC execution driver, which
            has not been the default for some time.

    publish_all_ports : False
        Allocates a random host port for each port exposed using the ``ports``
        parameter

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - ports: 8080
                - publish_all_ports: True

    links
        Link this container to another. Links should be specified in the format
        ``<container_name_or_id>:<link_alias>``. Multiple links can be passed,
        either as a comma separated list or a YAML list. The below two examples
        are equivalent:

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - links: web1:link1,web2:link2

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - links:
                  - web1:link1
                  - web2:link2

    dns
        List of DNS nameservers. Can be passed as a comma-separated list or a
        YAML list. The below two examples are equivalent:

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - dns: 8.8.8.8,8.8.4.4

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - dns:
                  - 8.8.8.8
                  - 8.8.4.4

        .. note::

            To skip IP address validation, use ``validate_ip_addrs=False``

    dns_search
        List of DNS search domains. Can be passed as a comma-separated list
        or a YAML list. The below two examples are equivalent:

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - dns_search: foo1.domain.tld,foo2.domain.tld

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - dns_search:
                  - foo1.domain.tld
                  - foo2.domain.tld

    volumes_from
        Container names or IDs from which the container will get volumes. Can
        be passed as a comma-separated list or a YAML list. The below two
        examples are equivalent:

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - volumes_from: foo

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - volumes_from:
                  - foo

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

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - network_mode: null

    restart_policy
        Set a restart policy for the container. Must be passed as a string in
        the format ``policy[:retry_count]`` where ``policy`` is one of
        ``always`` or ``on-failure``, and ``retry_count`` is an optional limit
        to the number of retries. The retry count is ignored when using the
        ``always`` restart policy.

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - restart_policy: on-failure:5

            bar:
              docker-ng.running:
                - pull: bar/baz:latest
                - restart_policy: always

    cap_add
        List of capabilities to add within the container. Can be passed as a
        comma-separated list or a Python list. The below two examples are
        equivalent:

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - cap_add: SYS_ADMIN,MKNOD

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - cap_add:
                  - SYS_ADMIN
                  - MKNOD

        .. note::

            This option requires Docker 1.2.0 or newer.

    cap_drop
        List of capabilities to drop within the container. Can be passed as a
        comma-separated list or a Python list. The below two examples are
        equivalent:

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - cap_drop: SYS_ADMIN,MKNOD

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - cap_drop:
                  - SYS_ADMIN
                  - MKNOD

        .. note::

            This option requires Docker 1.2.0 or newer.

    extra_hosts
        Additional hosts to add to the container's /etc/hosts file. Can be
        passed as a comma-separated list or a Python list. The below two
        exampels are equivalent:

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - extra_hosts: web1:10.9.8.7,web2:10.9.8.8

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - extra_hosts:
                  - web1:10.9.8.7
                  - web2:10.9.8.8

        .. note::

            To skip IP address validation, use ``validate_ip_addrs=False``

        .. note::

            This option requires Docker 1.3.0 or newer.

    pid_mode
        Set to ``host`` to use the host container's PID namespace within the
        container

        .. code-block:: yaml

            foo:
              docker-ng.running:
                - pull: bar/baz:latest
                - pid_mode: host

        .. note::

            This option requires Docker 1.5.0 or newer.
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}
    num_of_image_args = len([x for x in (pull, build, load) if x is not None])
    if num_of_image_args == 0:
        ret['comment'] = ('Missing required argument. One of \'pull\', '
                          '\'build\', or \'load\' is required.')
        return ret
    elif num_of_image_args > 1:
        ret['comment'] = ('Only one of \'pull\', \'build\', or \'load\' is '
                          'permitted.')
        return ret

    if name not in __salt__['docker-ng.list_containers'](all=True):
        pre_config = {}
    else:
        try:
            pre_config = __salt__['docker-ng.inspect_container'](name)
            if 'Config' in pre_config and 'Image' in pre_config['Config']:
                current_image = ':'.join(
                    _get_repo_tag(pre_config['Config']['Image'])
                )
            else:
                ret['comment'] = (
                    'Unable to detect current image for container \'{0}\'. '
                    'This might be due to a change in the Docker API.'
                    .format(name)
                )
                return ret
        except CommandExecutionError as exc:
            ret['comment'] = ('Error occurred checking for existence of '
                              'container \'{0}\': {1}'.format(name, exc))
            return ret

    if pull:
        action = 'pulled'
        # Ensure that we have repo:tag notation
        desired_image = ':'.join(_get_repo_tag(pull))
        image_path = None
    else:
        if build:
            action = 'built'
            repacked = salt.utils.repack_dictlist(build)
        elif load:
            action = 'loaded'
            repacked = salt.utils.repack_dictlist(load)
        if len(repacked) != 1:
            ret['comment'] = ('Invalid configuration for \'{0}\'. See the '
                              'documentation for proper usage.'.format(action))
            return ret
        key = next(iter(repacked))
        image_path = repacked[key]
        # Ensure that we have repo:tag notation
        desired_image = ':'.join(_get_repo_tag(key))

    # Find out if the image needs to be updated
    update_image = not pre_config or force or update or \
        desired_image not in __salt__['docker-ng.list_tags']()

    force_pillar = __pillar__.get('docker-ng.running.force.' + name, NOTSET)
    if force_pillar is not NOTSET:
        # Handles cases where pillar variable was set to 1 or 'foo'
        force = bool(force_pillar)
        log.debug(
            'Setting force={0} via Pillar item docker-ng.running.force.{1}'
            .format(force, name)
        )
    else:
        force_pillar = __pillar__.get('docker-ng.running.force', NOTSET)
        if force_pillar is not NOTSET:
            # Handles cases where pillar variable was set to 1 or 'foo'
            force = bool(force_pillar)
            log.debug(
                'Setting force={0} via Pillar item docker-ng.running.force'
                .format(force)
            )

    # If a container is using binds, don't let it also define data-only volumes
    if kwargs.get('volumes') is not None and kwargs.get('binds') is not None:
        ret['comment'] = 'Cannot mix data-only volumes and bind mounts'
        return ret

    # Don't allow conflicting options to be set
    if kwargs.get('publish_all_ports') \
            and kwargs.get('port_bindings') is not None:
        ret['comment'] = 'Cannot mix publish_all_ports=True and port_bindings'
        return ret
    if kwargs.get('hostname') is not None \
            and kwargs.get('network_mode') == 'host':
        ret['comment'] = 'Cannot mix hostname with network_mode=True'
        return ret

    # Strip __pub kwargs and divide the remaining arguments into the ones for
    # container creation and the ones for starting containers.
    invalid_kwargs = []
    create_kwargs = {}
    runtime_kwargs = {}
    for key, val in six.iteritems(salt.utils.clean_kwargs(**kwargs)):
        if key in VALID_CREATE_OPTS:
            create_kwargs[key] = val
        elif key in VALID_RUNTIME_OPTS:
            runtime_kwargs[key] = val
        else:
            invalid_kwargs.append(key)
    if invalid_kwargs:
        ret['comment'] = (
            'The following arguments are invalid: {0}'
            .format(', '.join(invalid_kwargs))
        )
        return ret

    # Input validation
    try:
        # Repack any dictlists that need it
        _prep_input(runtime_kwargs)
        _prep_input(create_kwargs)
        # Perform data type validation and, where necessary, munge
        # the data further so it is in a format that can be passed
        # to docker-ng.start.
        _validate_input('runtime',
                        runtime_kwargs,
                        validate_ip_addrs=validate_ip_addrs)

        # Add any needed contiainer creation arguments based on the validated
        # runtime arguments.
        if runtime_kwargs.get('binds') is not None:
            # Using bind mounts requries mountpoints to be specified at the
            # time the container is created, so we need to add them to the
            # create_kwargs.
            create_kwargs['volumes'] = list(runtime_kwargs['binds'])
        if runtime_kwargs.get('port_bindings') is not None \
                and create_kwargs.get('ports') is None:
            create_kwargs['ports'] = ','.join(
                [str(x) for x in runtime_kwargs['port_bindings']]
            )

        # Perform data type validation and, where necessary, munge
        # the data further so it is in a format that can be passed
        # to docker-ng.create.
        _validate_input('create',
                        create_kwargs,
                        validate_ip_addrs=validate_ip_addrs)
    except SaltInvocationError as exc:
        ret['comment'] = '{0}'.format(exc)
        return ret

    changes_needed = {}
    if force:
        # No need to check the container config if force=True, or the image was
        # updated in the block above.
        new_container = True
    else:
        # Only compare the desired configuration if the named container is
        # already present. If it is not, pre_config will be an empty dict,
        # hence "not pre_config" will tell us if the named container is
        # present.
        if not pre_config:
            new_container = True
        else:
            if current_image != desired_image:
                # Image name doesn't match, so there's no need to check the
                # container configuration.
                new_container = True
            else:
                # Container is the correct image, let's check the container
                # config and see if we need to replace the container
                try:
                    changes_needed = _compare(pre_config,
                                              create_kwargs,
                                              runtime_kwargs)
                    if changes_needed:
                        log.debug(
                            'docker-ng.running: Analysis of container \'{0}\' '
                            'reveals the following changes need to be made: '
                            '{1}'.format(name, changes_needed)
                        )
                    else:
                        log.debug(
                            'docker-ng.running: Container \'{0}\' already '
                            'matches the desired configuration'.format(name)
                        )
                except Exception as exc:
                    exc_info = ''.join(traceback.format_tb(sys.exc_info()[2]))
                    msg = (
                        'Uncaught exception "{0}" encountered while comparing '
                        'existing container against desired configuration.'
                        .format(exc)
                    )
                    log.error(msg + ' Exception info follows:\n' + exc_info)
                    ret['comment'] = \
                        msg + ' See minion log for exception info.'
                    return ret
                new_container = bool(changes_needed)

    if __opts__['test']:
        if not new_container:
            ret['comment'] = (
                'Container \'{0}\' is already configured as specified'
                .format(name)
            )
            if update:
                ret['result'] = None
                ret['comment'] += (
                    ', however image \'{0}\' will be {1} and if this results '
                    'in an updated image, the container will be replaced.'
                    .format(desired_image, action)
                )
            else:
                ret['result'] = True
            return ret
        else:
            ret['result'] = None
            if not pre_config:
                ret['comment'] = (
                    'Image \'{0}\' will be {1}, and container \'{2}\' will be '
                    'created'.format(desired_image, action, name)
                )
            else:
                if update_image:
                    ret['comment'] = (
                        'Image \'{0}\' will be {1}, and container \'{2}\' '
                        'will be replaced'.format(desired_image, action, name)
                    )
                else:
                    ret['comment'] = \
                        'Container \'{0}\' will be replaced'.format(name)
            return ret

    comments = []
    if update_image:
        if pull:
            try:
                image_update = __salt__['docker-ng.pull'](
                    desired_image,
                    insecure_registry=insecure_registry
                )
            except Exception as exc:
                ret['comment'] = (
                    'Encountered error pulling {0}: {1}'
                    .format(desired_image, exc)
                )
                return ret
            # Only add to the changes dict if layers were pulled
            if image_update.get('Layers', {}).get('Pulled'):
                ret['changes']['pull'] = image_update

        if build:
            try:
                image_update = __salt__['docker-ng.build'](
                    path=image_path,
                    image=desired_image
                )
            except Exception as exc:
                ret['comment'] = (
                    'Encountered error building {0} as {1}: {2}'
                    .format(image_path, desired_image, exc)
                )
                return ret
            if image_update['Id'] != pre_config['Id'][:12]:
                ret['changes']['build'] = image_update

        if load:
            try:
                image_update = __salt__['docker-ng.load'](
                    path=image_path,
                    image=desired_image
                )
            except Exception as exc:
                ret['comment'] = (
                    'Encountered error loading {0} as {1}: {2}'
                    .format(image_path, desired_image, exc)
                )
                return ret
            if image_update.get('Layers', []):
                ret['changes']['load'] = image_update
        comments.append('Image \'{0}\' was {1}'.format(desired_image, action))

    if not pre_config:
        pre_state = None
    else:
        pre_state = __salt__['docker-ng.state'](name)

    if new_container:
        if pre_config:
            # Container exists, stop if necessary, then remove and recreate
            if pre_state != 'stopped':
                result = __salt__['docker-ng.stop'](name,
                                                    timeout=stop_timeout,
                                                    unpause=True)['result']
                if result is not True:
                    comments.append(
                        'Container was slated to be replaced, but the '
                        'container could not be stopped.'
                    )
                    ret['comment'] = _format_comments(comments)
                    return ret

            # Remove existing container
            removed_ids = __salt__['docker-ng.rm'](name)
            if not removed_ids:
                comments.append('Failed to remove container {0}'.format(name))
                ret['comment'] = _format_comments(comments)
                return ret

            # Removal was successful, add the list of removed IDs to the
            # changes dict.
            ret['changes'].setdefault('container', {})['removed'] = removed_ids

        try:
            # Create new container
            create_result = __salt__['docker-ng.create'](
                desired_image,
                name=name,
                client_timeout=client_timeout,
                # Already validated input
                validate_input=False,
                **create_kwargs
            )
        except Exception as exc:
            comments.append('Failed to create new container: {0}'.format(exc))
            ret['comment'] = _format_comments(comments)
            return ret

        # Creation of new container was successful, add the return data to the
        # changes dict.
        ret['changes'].setdefault('container', {})['added'] = create_result

    if new_container or pre_state != 'running':
        try:
            # Start container
            __salt__['docker-ng.start'](
                name,
                # Already validated input earlier, no need to repeat it
                validate_ip_addrs=False,
                validate_input=False,
                **runtime_kwargs
            )
        except Exception as exc:
            comments.append(
                'Failed to start new container \'{0}\': {1}'
                .format(name, exc)
            )
            ret['comment'] = _format_comments(comments)
            return ret

        time.sleep(2)
        post_state = __salt__['docker-ng.state'](name)
        if pre_state != post_state:
            # If the container changed states at all, note this change in the
            # return dict.
            ret['changes'].setdefault('container', {})['state'] = {
                'old': pre_state, 'new': post_state
            }

    if changes_needed:
        try:
            post_config = __salt__['docker-ng.inspect_container'](name)
            changes_still_needed = _compare(post_config,
                                            create_kwargs,
                                            runtime_kwargs)
            if changes_still_needed:
                log.debug(
                    'docker-ng.running: Analysis of container \'{0}\' after '
                    'creation/replacement reveals the following changes still '
                    'need to be made: {1}'.format(name, changes_still_needed)
                )
            else:
                log.debug(
                    'docker-ng.running: Changes successfully applied to '
                    'container \'{0}\''.format(name)
                )
        except Exception as exc:
            exc_info = ''.join(traceback.format_tb(sys.exc_info()[2]))
            msg = (
                'Uncaught exception "{0}" encountered while comparing '
                'new container\'s configuration against desired configuration'
                .format(exc)
            )
            log.error(msg + '. Exception info follows:\n' + exc_info)
            comments.extend([msg, 'See minion log for exception info'])
            ret['comment'] = _format_comments(comments)
            return ret

        if changes_still_needed:
            diff = ret['changes'].setdefault(
                'container', {}).setdefault('diff', {})
            failed = []
            for key in changes_needed:
                if key not in changes_still_needed:
                    # Change was applied successfully
                    diff[key] = changes_needed[key]
                else:
                    # Change partially (or not at all) applied
                    old = changes_needed[key]['old']
                    new = changes_still_needed[key]['old']
                    if old != new:
                        diff[key] = {'old': old, 'new': new}
                    failed.append(key)
            comments.append(
                'Failed to apply configuration for the following parameters: '
                '{0}'.format(', '.join(failed))
            )
            ret['comment'] = _format_comments(comments)
            return ret
        else:
            # No necessary changes detected on post-container-replacement
            # check. The diffs will be the original changeset detected in
            # pre-flight check.
            ret['changes'].setdefault('container', {})['diff'] = changes_needed
            comments.append('Container \'{0}\' was replaced'.format(name))
    else:
        if not new_container:
            # Container was not replaced, and no necessary changes detected in
            # pre-flight check.
            comments.append(
                'Container \'{0}\' is already configured as specified'
                .format(name)
            )
        else:
            comments.append(
                'Container \'{0}\' was {1}'.format(
                    name,
                    'replaced' if pre_config else 'added'
                )
            )
            if desired_image != pre_config['Config']['Image']:
                diff = ret['changes'].setdefault(
                    'container', {}).setdefault('diff', {})
                diff['image'] = {'old': pre_config['Config']['Image'],
                                 'new': desired_image}
                comments.append(
                    'Image changed from \'{0}\' to \'{1}\''
                    .format(pre_config['Config']['Image'], desired_image)
                )

    ret['comment'] = _format_comments(comments)
    ret['result'] = True
    return ret
