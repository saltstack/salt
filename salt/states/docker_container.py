# -*- coding: utf-8 -*-
"""
Management of Docker containers

.. versionadded:: 2017.7.0

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

These states were moved from the :mod:`docker <salt.states.docker>` state
module (formerly called **dockerng**) in the 2017.7.0 release. When running the
:py:func:`docker_container.running <salt.states.docker_container.running>`
state for the first time after upgrading to 2017.7.0, your container(s) may be
replaced. The changes may show diffs for certain parameters which say that the
old value was an empty string, and the new value is ``None``. This is due to
the fact that in prior releases Salt was passing empty strings for these values
when creating the container if they were undefined in the SLS file, where now
Salt simply does not pass any arguments not explicitly defined in the SLS file.
Subsequent runs of the state should not replace the container if the
configuration remains unchanged.


.. note::
    To pull from a Docker registry, authentication must be configured. See
    :ref:`here <docker-authentication>` for more information on how to
    configure access to docker registries in :ref:`Pillar <pillar>` data.
"""
from __future__ import absolute_import, print_function, unicode_literals

import copy
import logging
import os

import salt.utils.args
import salt.utils.data
import salt.utils.docker

# Import Salt libs
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext import six

# Enable proper logging
log = logging.getLogger(__name__)  # pylint: disable=invalid-name

# Define the module's virtual name
__virtualname__ = "docker_container"
__virtual_aliases__ = ("moby_container",)


def __virtual__():
    """
    Only load if the docker execution module is available
    """
    if "docker.version" in __salt__:
        return __virtualname__
    return (False, __salt__.missing_fun_string("docker.version"))


def _format_comments(ret, comments):
    """
    DRY code for joining comments together and conditionally adding a period at
    the end, and adding this comment string to the state return dict.
    """
    if isinstance(comments, six.string_types):
        ret["comment"] = comments
    else:
        ret["comment"] = ". ".join(comments)
        if len(comments) > 1:
            ret["comment"] += "."
    return ret


def _check_diff(changes):
    """
    Check the diff for signs of incorrect argument handling in previous
    releases, as discovered here:

    https://github.com/saltstack/salt/pull/39996#issuecomment-288025200
    """
    for conf_dict in changes:
        if conf_dict == "Networks":
            continue
        for item in changes[conf_dict]:
            if changes[conf_dict][item]["new"] is None:
                old = changes[conf_dict][item]["old"]
                if old == "":
                    return True
                else:
                    try:
                        if all(x == "" for x in old):
                            return True
                    except TypeError:
                        # Old value is not an iterable type
                        pass
    return False


def _parse_networks(networks):
    """
    Common logic for parsing the networks
    """
    networks = salt.utils.args.split_input(networks or [])
    if not networks:
        networks = {}
    else:
        # We don't want to recurse the repack, as the values of the kwargs
        # being passed when connecting to the network will not be dictlists.
        networks = salt.utils.data.repack_dictlist(networks)
        if not networks:
            raise CommandExecutionError(
                "Invalid network configuration (see documentation)"
            )
        for net_name, net_conf in six.iteritems(networks):
            if net_conf is None:
                networks[net_name] = {}
            else:
                networks[net_name] = salt.utils.data.repack_dictlist(net_conf)
                if not networks[net_name]:
                    raise CommandExecutionError(
                        "Invalid configuration for network '{0}' "
                        "(see documentation)".format(net_name)
                    )
                for key in ("links", "aliases"):
                    try:
                        networks[net_name][key] = salt.utils.args.split_input(
                            networks[net_name][key]
                        )
                    except KeyError:
                        continue

        # Iterate over the networks again now, looking for
        # incorrectly-formatted arguments
        errors = []
        for net_name, net_conf in six.iteritems(networks):
            if net_conf is not None:
                for key, val in six.iteritems(net_conf):
                    if val is None:
                        errors.append(
                            "Config option '{0}' for network '{1}' is "
                            "missing a value".format(key, net_name)
                        )
        if errors:
            raise CommandExecutionError("Invalid network configuration", info=errors)

    if networks:
        try:
            all_networks = [
                x["Name"] for x in __salt__["docker.networks"]() if "Name" in x
            ]
        except CommandExecutionError as exc:
            raise CommandExecutionError(
                "Failed to get list of existing networks: {0}.".format(exc)
            )
        else:
            missing_networks = [x for x in sorted(networks) if x not in all_networks]
            if missing_networks:
                raise CommandExecutionError(
                    "The following networks are not present: {0}".format(
                        ", ".join(missing_networks)
                    )
                )

    return networks


def _resolve_image(ret, image, client_timeout):
    """
    Resolve the image ID and pull the image if necessary
    """
    image_id = __salt__["docker.resolve_image_id"](image)

    if image_id is False:
        if not __opts__["test"]:
            # Image not pulled locally, so try pulling it
            try:
                pull_result = __salt__["docker.pull"](
                    image, client_timeout=client_timeout,
                )
            except Exception as exc:  # pylint: disable=broad-except
                raise CommandExecutionError(
                    "Failed to pull {0}: {1}".format(image, exc)
                )
            else:
                ret["changes"]["image"] = pull_result
                # Try resolving again now that we've pulled
                image_id = __salt__["docker.resolve_image_id"](image)
                if image_id is False:
                    # Shouldn't happen unless the pull failed
                    raise CommandExecutionError(
                        "Image '{0}' not present despite a docker pull "
                        "raising no errors".format(image)
                    )
    return image_id


def running(
    name,
    image=None,
    skip_translate=None,
    ignore_collisions=False,
    validate_ip_addrs=True,
    force=False,
    watch_action="force",
    start=True,
    shutdown_timeout=None,
    client_timeout=salt.utils.docker.CLIENT_TIMEOUT,
    networks=None,
    **kwargs
):
    """
    Ensure that a container with a specific configuration is present and
    running

    name
        Name of the container

    image
        Image to use for the container

        .. note::
            This state will pull the image if it is not present. However, if
            the image needs to be built from a Dockerfile or loaded from a
            saved image, or if you would like to use requisites to trigger a
            replacement of the container when the image is updated, then the
            :py:func:`docker_image.present
            <salt.states.dockermod.image_present>` state should be used to
            manage the image.

        .. versionchanged:: 2018.3.0
            If no tag is specified in the image name, and nothing matching the
            specified image is pulled on the minion, the ``docker pull`` that
            retrieves the image will pull *all tags* for the image. A tag of
            ``latest`` is no longer implicit for the pull. For this reason, it
            is recommended to specify the image in ``repo:tag`` notation.

    .. _docker-container-running-skip-translate:

    skip_translate
        This function translates Salt CLI or SLS input into the format which
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

        For example, imagine that there is an issue with processing the
        ``port_bindings`` argument, and the following configuration no longer
        works as expected:

        .. code-block:: yaml

            mycontainer:
              docker_container.running:
                - image: 7.3.1611
                - port_bindings:
                  - 10.2.9.10:8080:80

        By using ``skip_translate``, you can forego the input translation and
        configure the port binding in the format docker-py_ needs:

        .. code-block:: yaml

            mycontainer:
              docker_container.running:
                - image: 7.3.1611
                - skip_translate: port_bindings
                - port_bindings: {8080: [('10.2.9.10', 80)], '4193/udp': 9314}

        See the following links for more information:

        - `docker-py Low-level API`_
        - `Docker Engine API`_

    .. _docker-py: https://pypi.python.org/pypi/docker-py
    .. _`docker-py Low-level API`: http://docker-py.readthedocs.io/en/stable/api.html#docker.api.container.ContainerApiMixin.create_container
    .. _`Docker Engine API`: https://docs.docker.com/engine/api/v1.33/#operation/ContainerCreate

    ignore_collisions : False
        Since many of docker-py_'s arguments differ in name from their CLI
        counterparts (with which most Docker users are more familiar), Salt
        detects usage of these and aliases them to the docker-py_ version of
        that argument so that both CLI and API versions of a given argument are
        supported. However, if both the alias and the docker-py_ version of the
        same argument (e.g. ``env`` and ``environment``) are used, an error
        will be raised. Set this argument to ``True`` to suppress these errors
        and keep the docker-py_ version of the argument.

    validate_ip_addrs : True
        For parameters which accept IP addresses as input, IP address
        validation will be performed. To disable, set this to ``False``

    force : False
        Set this parameter to ``True`` to force Salt to re-create the container
        irrespective of whether or not it is configured as desired.

    watch_action : force
        Control what type of action is taken when this state :ref:`watches
        <requisites-watch>` another state that has changes. The default action
        is ``force``, which runs the state with ``force`` set to ``True``,
        triggering a rebuild of the container.

        If any other value is passed, it will be assumed to be a kill signal.
        If the container matches the specified configuration, and is running,
        then the action will be to send that signal to the container. Kill
        signals can be either strings or numbers, and are defined in the
        **Standard Signals** section of the ``signal(7)`` manpage. Run ``man 7
        signal`` on a Linux host to browse this manpage. For example:

        .. code-block:: yaml

            mycontainer:
              docker_container.running:
                - image: busybox
                - watch_action: SIGHUP
                - watch:
                  - file: some_file

        .. note::

            If the container differs from the specified configuration, or is
            not running, then instead of sending a signal to the container, the
            container will be re-created/started and no signal will be sent.

    start : True
        Set to ``False`` to suppress starting of the container if it exists,
        matches the desired configuration, but is not running. This is useful
        for data-only containers, or for non-daemonized container processes,
        such as the Django ``migrate`` and ``collectstatic`` commands. In
        instances such as this, the container only needs to be started the
        first time.

    shutdown_timeout
        If the container needs to be replaced, the container will be stopped
        using :py:func:`docker.stop <salt.modules.dockermod.stop>`. If a
        ``shutdown_timout`` is not set, and the container was created using
        ``stop_timeout``, that timeout will be used. If neither of these values
        were set, then a timeout of 10 seconds will be used.

        .. versionchanged:: 2017.7.0
            This option was renamed from ``stop_timeout`` to
            ``shutdown_timeout`` to accommodate the ``stop_timeout`` container
            configuration setting.

    client_timeout : 60
        Timeout in seconds for the Docker client. This is not a timeout for
        this function, but for receiving a response from the API.

        .. note::
            This is only used if Salt needs to pull the requested image.

    .. _salt-states-docker-container-network-management:

    **NETWORK MANAGEMENT**

    .. versionadded:: 2018.3.0
    .. versionchanged:: 2019.2.0
        If the ``networks`` option is used, any networks (including the default
        ``bridge`` network) which are not specified will be disconnected.

    The ``networks`` argument can be used to ensure that a container is
    attached to one or more networks. Optionally, arguments can be passed to
    the networks. In the example below, ``net1`` is being configured with
    arguments, while ``net2`` and ``bridge`` are being configured *without*
    arguments:

    .. code-block:: yaml

        foo:
          docker_container.running:
            - image: myuser/myimage:foo
            - networks:
              - net1:
                - aliases:
                  - bar
                  - baz
                - ipv4_address: 10.0.20.50
              - net2
              - bridge
            - require:
              - docker_network: net1
              - docker_network: net2

    The supported arguments are the ones from the docker-py's
    `connect_container_to_network`_ function (other than ``container`` and
    ``net_id``).

    .. important::
        Unlike with the arguments described in the **CONTAINER CONFIGURATION
        PARAMETERS** section below, these network configuration parameters are
        not translated at all.  Consult the `connect_container_to_network`_
        documentation for the correct type/format of data to pass.

    .. _`connect_container_to_network`: https://docker-py.readthedocs.io/en/stable/api.html#docker.api.network.NetworkApiMixin.connect_container_to_network

    To start a container with no network connectivity (only possible in
    2019.2.0 and later) pass this option as an empty list. For example:

    .. code-block:: yaml

        foo:
          docker_container.running:
            - image: myuser/myimage:foo
            - networks: []


    **CONTAINER CONFIGURATION PARAMETERS**

    auto_remove (or *rm*) : False
        Enable auto-removal of the container on daemon side when the
        container’s process exits (analogous to running a docker container with
        ``--rm`` on the CLI).

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - auto_remove: True

    binds
        Files/directories to bind mount. Each bind mount should be passed in
        one of the following formats:

        - ``<host_path>:<container_path>`` - ``host_path`` is mounted within
          the container as ``container_path`` with read-write access.
        - ``<host_path>:<container_path>:<selinux_context>`` - ``host_path`` is
          mounted within the container as ``container_path`` with read-write
          access. Additionally, the specified selinux context will be set
          within the container.
        - ``<host_path>:<container_path>:<read_only>`` - ``host_path`` is
          mounted within the container as ``container_path``, with the
          read-only or read-write setting explicitly defined.
        - ``<host_path>:<container_path>:<read_only>,<selinux_context>`` -
          ``host_path`` is mounted within the container as ``container_path``,
          with the read-only or read-write setting explicitly defined.
          Additionally, the specified selinux context will be set within the
          container.

        ``<read_only>`` can be either ``rw`` for read-write access, or ``ro``
        for read-only access. When omitted, it is assumed to be read-write.

        ``<selinux_context>`` can be ``z`` if the volume is shared between
        multiple containers, or ``Z`` if the volume should be private.

        .. note::
            When both ``<read_only>`` and ``<selinux_context>`` are specified,
            there must be a comma before ``<selinux_context>``.

        Binds can be expressed as a comma-separated list or a YAML list. The
        below two examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - binds: /srv/www:/var/www:ro,/etc/foo.conf:/usr/local/etc/foo.conf:rw

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - binds:
                  - /srv/www:/var/www:ro
                  - /home/myuser/conf/foo.conf:/etc/foo.conf:rw

        However, in cases where both ro/rw and an selinux context are combined,
        the only option is to use a YAML list, like so:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - binds:
                  - /srv/www:/var/www:ro,Z
                  - /home/myuser/conf/foo.conf:/etc/foo.conf:rw,Z

        Since the second bind in the previous example is mounted read-write,
        the ``rw`` and comma can be dropped. For example:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - binds:
                  - /srv/www:/var/www:ro,Z
                  - /home/myuser/conf/foo.conf:/etc/foo.conf:Z

    blkio_weight
        Block IO weight (relative weight), accepts a weight value between 10
        and 1000.

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - blkio_weight: 100

    blkio_weight_device
        Block IO weight (relative device weight), specified as a list of
        expressions in the format ``PATH:RATE``

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - blkio_weight_device: /dev/sda:100

    cap_add
        List of capabilities to add within the container. Can be expressed as a
        comma-separated list or a Python list. The below two examples are
        equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - cap_add: SYS_ADMIN,MKNOD

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - cap_add:
                  - SYS_ADMIN
                  - MKNOD

        .. note::

            This option requires Docker 1.2.0 or newer.

    cap_drop
        List of capabilities to drop within the container. Can be expressed as
        a comma-separated list or a Python list. The below two examples are
        equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - cap_drop: SYS_ADMIN,MKNOD

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - cap_drop:
                  - SYS_ADMIN
                  - MKNOD

        .. note::
            This option requires Docker 1.2.0 or newer.

    command (or *cmd*)
        Command to run in the container

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - command: bash

    cpuset_cpus (or *cpuset*)
        CPUs on which which to allow execution, specified as a string
        containing a range (e.g. ``0-3``) or a comma-separated list of CPUs
        (e.g. ``0,1``).

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - cpuset_cpus: "0,1"

    cpuset_mems
        Memory nodes on which which to allow execution, specified as a string
        containing a range (e.g. ``0-3``) or a comma-separated list of MEMs
        (e.g. ``0,1``). Only effective on NUMA systems.

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - cpuset_mems: "0,1"

    cpu_group
        The length of a CPU period in microseconds

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - cpu_group: 100000

    cpu_period
        Microseconds of CPU time that the container can get in a CPU period

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - cpu_period: 50000

    cpu_shares
        CPU shares (relative weight), specified as an integer between 2 and 1024.

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - cpu_shares: 512

    detach : False
        If ``True``, run the container's command in the background (daemon
        mode)

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - detach: True

    devices
        List of host devices to expose within the container. Can be expressed
        as a comma-separated list or a YAML list. The below two examples are
        equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - devices: /dev/net/tun,/dev/xvda1:/dev/xvda1,/dev/xvdb1:/dev/xvdb1:r

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - devices:
                  - /dev/net/tun
                  - /dev/xvda1:/dev/xvda1
                  - /dev/xvdb1:/dev/xvdb1:r

    device_read_bps
        Limit read rate (bytes per second) from a device, specified as a list
        of expressions in the format ``PATH:RATE``, where ``RATE`` is either an
        integer number of bytes, or a string ending in ``kb``, ``mb``, or
        ``gb``. Can be expressed as a comma-separated list or a YAML list. The
        below two examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - devices_read_bps: /dev/sda:1mb,/dev/sdb:5mb

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - devices_read_bps:
                  - /dev/sda:1mb
                  - /dev/sdb:5mb

    device_read_iops
        Limit read rate (I/O per second) from a device, specified as a list
        of expressions in the format ``PATH:RATE``, where ``RATE`` is a number
        of I/O operations. Can be expressed as a comma-separated list or a YAML
        list. The below two examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - devices_read_iops: /dev/sda:1000,/dev/sdb:500

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - devices_read_iops:
                  - /dev/sda:1000
                  - /dev/sdb:500

    device_write_bps
        Limit write rate (bytes per second) from a device, specified as a list
        of expressions in the format ``PATH:RATE``, where ``RATE`` is either an
        integer number of bytes, or a string ending in ``kb``, ``mb``, or
        ``gb``. Can be expressed as a comma-separated list or a YAML list. The
        below two examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - devices_write_bps: /dev/sda:1mb,/dev/sdb:5mb

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - devices_write_bps:
                  - /dev/sda:1mb
                  - /dev/sdb:5mb


    device_read_iops
        Limit write rate (I/O per second) from a device, specified as a list
        of expressions in the format ``PATH:RATE``, where ``RATE`` is a number
        of I/O operations. Can be expressed as a comma-separated list or a
        YAML list. The below two examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - devices_read_iops: /dev/sda:1000,/dev/sdb:500

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - devices_read_iops:
                  - /dev/sda:1000
                  - /dev/sdb:500

    dns
        List of DNS nameservers. Can be expressed as a comma-separated list or
        a YAML list. The below two examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - dns: 8.8.8.8,8.8.4.4

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - dns:
                  - 8.8.8.8
                  - 8.8.4.4

        .. note::

            To skip IP address validation, use ``validate_ip_addrs=False``

    dns_opt
        Additional options to be added to the container’s ``resolv.conf`` file.
        Can be expressed as a comma-separated list or a YAML list. The below
        two examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - dns_opt: ndots:9

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - dns_opt:
                  - ndots:9

    dns_search
        List of DNS search domains. Can be expressed as a comma-separated list
        or a YAML list. The below two examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - dns_search: foo1.domain.tld,foo2.domain.tld

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - dns_search:
                  - foo1.domain.tld
                  - foo2.domain.tld

    domainname
        The domain name to use for the container

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - dommainname: domain.tld

    entrypoint
        Entrypoint for the container

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - entrypoint: "mycmd --arg1 --arg2"

        This argument can also be specified as a list:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - entrypoint:
                  - mycmd
                  - --arg1
                  - --arg2

    environment
        Either a list of variable/value mappings, or a list of strings in the
        format ``VARNAME=value``. The below three examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - environment:
                  - VAR1: value
                  - VAR2: value

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - environment: 'VAR1=value,VAR2=value'

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - environment:
                  - VAR1=value
                  - VAR2=value

    extra_hosts
        Additional hosts to add to the container's /etc/hosts file. Can be
        expressed as a comma-separated list or a Python list. The below two
        examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - extra_hosts: web1:10.9.8.7,web2:10.9.8.8

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - extra_hosts:
                  - web1:10.9.8.7
                  - web2:10.9.8.8

        .. note::

            To skip IP address validation, use ``validate_ip_addrs=False``

        .. note::

            This option requires Docker 1.3.0 or newer.

    group_add
        List of additional group names and/or IDs that the container process
        will run as. Can be expressed as a comma-separated list or a YAML list.
        The below two examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - group_add: web,network

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - group_add:
                  - web
                  - network

    hostname
        Hostname of the container. If not provided, the value passed as the
        container's``name`` will be used for the hostname.

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - hostname: web1

        .. warning::

            ``hostname`` cannot be set if ``network_mode`` is set to ``host``.
            The below example will result in an error:

            .. code-block:: yaml

                foo:
                  docker_container.running:
                    - image: bar/baz:latest
                    - hostname: web1
                    - network_mode: host

    interactive (or *stdin_open*) : False
        Leave stdin open, even if not attached

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - interactive: True

    ipc_mode (or *ipc*)
        Set the IPC mode for the container. The default behavior is to create a
        private IPC namespace for the container, but this option can be
        used to change that behavior:

        - ``container:<container_name_or_id>`` reuses another container shared
          memory, semaphores and message queues
        - ``host``: use the host's shared memory, semaphores and message queues

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - ipc_mode: container:foo

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - ipc_mode: host

        .. warning::
            Using ``host`` gives the container full access to local shared
            memory and is therefore considered insecure.

    isolation
        Specifies the type of isolation technology used by containers

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - isolation: hyperv

        .. note::
            The default value on Windows server is ``process``, while the
            default value on Windows client is ``hyperv``. On Linux, only
            ``default`` is supported.

    labels
        Add metadata to the container. Labels can be set both with and without
        values, and labels with values can be passed either as ``key=value`` or
        ``key: value`` pairs. For example, while the below would be very
        confusing to read, it is technically valid, and demonstrates the
        different ways in which labels can be passed:

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - labels:
                  - foo
                  - bar=baz
                  - hello: world

        The labels can also simply be passed as a YAML dictionary, though this
        can be error-prone due to some :ref:`idiosyncrasies
        <yaml-idiosyncrasies>` with how PyYAML loads nested data structures:

        .. code-block:: yaml

            foo:
              docker_network.present:
                - labels:
                    foo: ''
                    bar: baz
                    hello: world

        .. versionchanged:: 2018.3.0
            Methods for specifying labels can now be mixed. Earlier releases
            required either labels with or without values.

    links
        Link this container to another. Links can be specified as a list of
        mappings or a comma-separated or Python list of expressions in the
        format ``<container_name_or_id>:<link_alias>``. The below three
        examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - links:
                  - web1: link1
                  - web2: link2

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - links: web1:link1,web2:link2

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - links:
                  - web1:link1
                  - web2:link2

    log_driver and log_opt
        Set container's logging driver and options to configure that driver.
        Requires Docker 1.6 or newer.

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - log_driver: syslog
                - log_opt:
                  - syslog-address: tcp://192.168.0.42
                  - syslog-facility: daemon

        The ``log_opt`` can also be expressed as a comma-separated or YAML list
        of ``key=value`` pairs. The below two examples are equivalent to the
        above one:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - log_driver: syslog
                - log_opt: "syslog-address=tcp://192.168.0.42,syslog-facility=daemon"

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - log_driver: syslog
                - log_opt:
                  - syslog-address=tcp://192.168.0.42
                  - syslog-facility=daemon

        .. note::
            The logging driver feature was improved in Docker 1.13 introducing
            option name changes. Please see Docker's
            `Configure logging drivers`_ documentation for more information.

        .. _`Configure logging drivers`: https://docs.docker.com/engine/admin/logging/overview/

    lxc_conf
        Additional LXC configuration parameters to set before starting the
        container. Either a list of variable/value mappings, or a list of
        strings in the format ``VARNAME=value``. The below three examples are
        equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - lxc_conf:
                  - lxc.utsname: docker
                  - lxc.arch: x86_64

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - lxc_conf: lxc.utsname=docker,lxc.arch=x86_64

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - lxc_conf:
                  - lxc.utsname=docker
                  - lxc.arch=x86_64

        .. note::
            These LXC configuration parameters will only have the desired
            effect if the container is using the LXC execution driver, which
            has been deprecated for some time.

    mac_address
        MAC address to use for the container. If not specified, a random MAC
        address will be used.

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - mac_address: 01:23:45:67:89:0a

    mem_limit (or *memory*) : 0
        Memory limit. Can be specified in bytes or using single-letter units
        (i.e. ``512M``, ``2G``, etc.). A value of ``0`` (the default) means no
        memory limit.

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - mem_limit: 512M

    mem_swappiness
        Tune a container's memory swappiness behavior. Accepts an integer
        between 0 and 100.

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - mem_swappiness: 60

    memswap_limit (or *memory_swap*) : -1
        Total memory limit (memory plus swap). Set to ``-1`` to disable swap. A
        value of ``0`` means no swap limit.

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - memswap_limit: 1G

    network_disabled : False
        If ``True``, networking will be disabled within the container

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - network_disabled: True

    network_mode : bridge
        One of the following:

        - ``bridge`` - Creates a new network stack for the container on the
          docker bridge
        - ``none`` - No networking (equivalent of the Docker CLI argument
          ``--net=none``). Not to be confused with Python's ``None``.
        - ``container:<name_or_id>`` - Reuses another container's network stack
        - ``host`` - Use the host's network stack inside the container

          .. warning::

                Using ``host`` mode gives the container full access to the
                hosts system's services (such as D-bus), and is therefore
                considered insecure.

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - network_mode: "none"

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - network_mode: container:web1

    oom_kill_disable
        Whether to disable OOM killer

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - oom_kill_disable: False

    oom_score_adj
        An integer value containing the score given to the container in order
        to tune OOM killer preferences

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - oom_score_adj: 500

    pid_mode
        Set to ``host`` to use the host container's PID namespace within the
        container. Requires Docker 1.5.0 or newer.

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - pid_mode: host

        .. note::
            This option requires Docker 1.5.0 or newer.

    pids_limit
        Set the container's PID limit. Set to ``-1`` for unlimited.

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - pids_limit: 2000

    port_bindings (or *publish*)
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

        Multiple bindings can be separated by commas, or expressed as a YAML
        list, and port ranges can be defined using dashes. The below two
        examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - port_bindings: "4505-4506:14505-14506,2123:2123/udp,8080"

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - port_bindings:
                  - 4505-4506:14505-14506
                  - 2123:2123/udp
                  - 8080

        .. note::
            When specifying a protocol, it must be passed in the
            ``containerPort`` value, as seen in the examples above.

    ports
        A list of ports to expose on the container. Can either be a
        comma-separated list or a YAML list. If the protocol is omitted, the
        port will be assumed to be a TCP port. The below two examples are
        equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - ports: 1111,2222/udp

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - ports:
                  - 1111
                  - 2222/udp

    privileged : False
        If ``True``, runs the exec process with extended privileges

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - privileged: True

    publish_all_ports (or *publish_all*) : False
        Publish all ports to the host

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - ports: 8080
                - publish_all_ports: True

    read_only : False
        If ``True``, mount the container’s root filesystem as read only

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - read_only: True

    restart_policy (or *restart*)
        Set a restart policy for the container. Must be passed as a string in
        the format ``policy[:retry_count]`` where ``policy`` is one of
        ``always``, ``unless-stopped``, or ``on-failure``, and ``retry_count``
        is an optional limit to the number of retries. The retry count is ignored
        when using the ``always`` or ``unless-stopped`` restart policy.

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - restart_policy: on-failure:5

            bar:
              docker_container.running:
                - image: bar/baz:latest
                - restart_policy: always

    security_opt (or *security_opts*):
        Security configuration for MLS systems such as SELinux and AppArmor.
        Can be expressed as a comma-separated list or a YAML list. The below
        two examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - security_opt: apparmor:unconfined

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - security_opt:
                  - apparmor:unconfined

        .. important::
            Some security options can contain commas. In these cases, this
            argument *must* be passed as a Python list, as splitting by comma
            will result in an invalid configuration.

        .. note::
            See the documentation for security_opt at
            https://docs.docker.com/engine/reference/run/#security-configuration

    shm_size
        Size of /dev/shm

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - shm_size: 128M

    stop_signal
        Specify the signal docker will send to the container when stopping.
        Useful when running systemd as PID 1 inside the container.

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - stop_signal: SIGRTMIN+3

        .. note::

            This option requires Docker 1.9.0 or newer and docker-py 1.7.0 or
            newer.

        .. versionadded:: 2016.11.0

    stop_timeout
        Timeout to stop the container, in seconds

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - stop_timeout: 5

        .. note::
            In releases prior to 2017.7.0, this option was not set in the
            container configuration, but rather this timeout was enforced only
            when shutting down an existing container to replace it. To remove
            the ambiguity, and to allow for the container to have a stop
            timeout set for it, the old ``stop_timeout`` argument has been
            renamed to ``shutdown_timeout``, while ``stop_timeout`` now refer's
            to the container's configured stop timeout.

    storage_opt
        Storage driver options for the container. Can be either a list of
        strings in the format ``option=value``, or a list of mappings between
        option and value. The below three examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - storage_opt:
                  - dm.basesize: 40G

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - storage_opt: dm.basesize=40G

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - storage_opt:
                  - dm.basesize=40G

    sysctls (or *sysctl*)
        Set sysctl options for the container. Can be either a list of strings
        in the format ``option=value``, or a list of mappings between option
        and value. The below three examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - sysctls:
                  - fs.nr_open: 1048576
                  - kernel.pid_max: 32768

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - sysctls: fs.nr_open=1048576,kernel.pid_max=32768

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - sysctls:
                  - fs.nr_open=1048576
                  - kernel.pid_max=32768

    tmpfs
        A map of container directories which should be replaced by tmpfs mounts
        and their corresponding mount options.

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - tmpfs:
                  - /run: rw,noexec,nosuid,size=65536k

    tty : False
        Attach TTYs

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - tty: True

    ulimits
        List of ulimits. These limits should be passed in the format
        ``<ulimit_name>:<soft_limit>:<hard_limit>``, with the hard limit being
        optional. Can be expressed as a comma-separated list or a YAML list.
        The below two examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - ulimits: nofile=1024:1024,nproc=60

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - ulimits:
                  - nofile=1024:1024
                  - nproc=60

    user
        User under which to run exec process

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - user: foo

    userns_mode (or *user_ns_mode*)
        Sets the user namsepace mode, when the user namespace remapping option
        is enabled

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - userns_mode: host

    volumes (or *volume*)
        List of directories to expose as volumes. Can be expressed as a
        comma-separated list or a YAML list. The below two examples are
        equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - volumes: /mnt/vol1,/mnt/vol2

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - volumes:
                  - /mnt/vol1
                  - /mnt/vol2

    volumes_from
        Container names or IDs from which the container will get volumes. Can
        be expressed as a comma-separated list or a YAML list. The below two
        examples are equivalent:

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - volumes_from: foo

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - volumes_from:
                  - foo

    volume_driver
        sets the container's volume driver

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - volume_driver: foobar

    working_dir (or *workdir*)
        Working directory inside the container

        .. code-block:: yaml

            foo:
              docker_container.running:
                - image: bar/baz:latest
                - working_dir: /var/log/nginx
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if image is None:
        ret["result"] = False
        ret["comment"] = "The 'image' argument is required"
        return ret
    elif not isinstance(image, six.string_types):
        image = six.text_type(image)

    try:
        # Since we're rewriting the "networks" value below, save the original
        # value here.
        configured_networks = networks
        networks = _parse_networks(networks)
        if networks:
            kwargs["networks"] = networks
        image_id = _resolve_image(ret, image, client_timeout)
    except CommandExecutionError as exc:
        ret["result"] = False
        if exc.info is not None:
            return _format_comments(ret, exc.info)
        else:
            ret["comment"] = exc.__str__()
            return ret

    comments = []

    # Pop off the send_signal argument passed by the watch requisite
    send_signal = kwargs.pop("send_signal", False)

    try:
        current_image_id = __salt__["docker.inspect_container"](name)["Image"]
    except CommandExecutionError:
        current_image_id = None
    except KeyError:
        ret["result"] = False
        comments.append(
            "Unable to detect current image for container '{0}'. "
            "This might be due to a change in the Docker API.".format(name)
        )
        return _format_comments(ret, comments)

    # Shorthand to make the below code more understandable
    exists = current_image_id is not None

    pre_state = __salt__["docker.state"](name) if exists else None

    # If skip_comparison is True, we're definitely going to be using the temp
    # container as the new container (because we're forcing the change, or
    # because the image IDs differ). If False, we'll need to perform a
    # comparison between it and the new container.
    skip_comparison = force or not exists or current_image_id != image_id

    if skip_comparison and __opts__["test"]:
        ret["result"] = None
        if force:
            ret["changes"]["forced_update"] = True
        elif current_image_id != image_id:
            ret["changes"]["image"] = {"old": current_image_id, "new": image_id}
        comments.append(
            "Container '{0}' would be {1}".format(
                name, "created" if not exists else "replaced"
            )
        )
        return _format_comments(ret, comments)

    # Create temp container (or just create the named container if the
    # container does not already exist)
    try:
        temp_container = __salt__["docker.create"](
            image,
            name=name if not exists else None,
            skip_translate=skip_translate,
            ignore_collisions=ignore_collisions,
            validate_ip_addrs=validate_ip_addrs,
            client_timeout=client_timeout,
            **kwargs
        )
        temp_container_name = temp_container["Name"]
    except KeyError as exc:
        ret["result"] = False
        comments.append(
            "Key '{0}' missing from API response, this may be due to a "
            "change in the Docker Remote API. Please report this on the "
            "SaltStack issue tracker if it has not already been reported.".format(exc)
        )
        return _format_comments(ret, comments)
    except Exception as exc:  # pylint: disable=broad-except
        ret["result"] = False
        msg = exc.__str__()
        if (
            isinstance(exc, CommandExecutionError)
            and isinstance(exc.info, dict)
            and "invalid" in exc.info
        ):
            msg += (
                "\n\nIf you feel this information is incorrect, the "
                "skip_translate argument can be used to skip input "
                "translation for the argument(s) identified as invalid. See "
                "the documentation for details."
            )
        comments.append(msg)
        return _format_comments(ret, comments)

    def _replace(orig, new):
        rm_kwargs = {"stop": True}
        if shutdown_timeout is not None:
            rm_kwargs["timeout"] = shutdown_timeout
        ret["changes"].setdefault("container_id", {})["removed"] = __salt__[
            "docker.rm"
        ](name, **rm_kwargs)
        try:
            result = __salt__["docker.rename"](new, orig)
        except CommandExecutionError as exc:
            result = False
            comments.append("Failed to rename temp container: {0}".format(exc))
        if result:
            comments.append("Replaced container '{0}'".format(orig))
        else:
            comments.append("Failed to replace container '{0}'")
        return result

    def _delete_temp_container():
        log.debug("Removing temp container '%s'", temp_container_name)
        __salt__["docker.rm"](temp_container_name)

    # If we're not skipping the comparison, then the assumption is that
    # temp_container will be discarded, unless the comparison reveals
    # differences, in which case we'll set cleanup_temp = False to prevent it
    # from being cleaned.
    cleanup_temp = not skip_comparison
    try:
        pre_net_connect = __salt__["docker.inspect_container"](
            name if exists else temp_container_name
        )
        for net_name, net_conf in six.iteritems(networks):
            try:
                __salt__["docker.connect_container_to_network"](
                    temp_container_name, net_name, **net_conf
                )
            except CommandExecutionError as exc:
                # Shouldn't happen, stopped docker containers can be
                # attached to networks even if the static IP lies outside
                # of the network's subnet. An exception will be raised once
                # you try to start the container, however.
                ret["result"] = False
                comments.append(exc.__str__())
                return _format_comments(ret, comments)

        post_net_connect = __salt__["docker.inspect_container"](temp_container_name)

        if configured_networks is not None:
            # Use set arithmetic to determine the networks which are connected
            # but not explicitly defined. They will be disconnected below. Note
            # that we check configured_networks because it represents the
            # original (unparsed) network configuration. When no networks
            # argument is used, the parsed networks will be an empty list, so
            # it's not sufficient to do a boolean check on the "networks"
            # variable.
            extra_nets = set(
                post_net_connect.get("NetworkSettings", {}).get("Networks", {})
            ) - set(networks)

            if extra_nets:
                for extra_net in extra_nets:
                    __salt__["docker.disconnect_container_from_network"](
                        temp_container_name, extra_net
                    )

                # We've made changes, so we need to inspect the container again
                post_net_connect = __salt__["docker.inspect_container"](
                    temp_container_name
                )

        net_changes = __salt__["docker.compare_container_networks"](
            pre_net_connect, post_net_connect
        )

        if not skip_comparison:
            container_changes = __salt__["docker.compare_containers"](
                name, temp_container_name, ignore="Hostname",
            )
            if container_changes:
                if _check_diff(container_changes):
                    ret.setdefault("warnings", []).append(
                        "The detected changes may be due to incorrect "
                        "handling of arguments in earlier Salt releases. If "
                        "this warning persists after running the state "
                        "again{0}, and no changes were made to the SLS file, "
                        "then please report this.".format(
                            " without test=True" if __opts__["test"] else ""
                        )
                    )

                changes_ptr = ret["changes"].setdefault("container", {})
                changes_ptr.update(container_changes)
                if __opts__["test"]:
                    ret["result"] = None
                    comments.append(
                        "Container '{0}' would be {1}".format(
                            name, "created" if not exists else "replaced"
                        )
                    )
                else:
                    # We don't want to clean the temp container, we'll be
                    # replacing the existing one with it.
                    cleanup_temp = False
                    # Replace the container
                    if not _replace(name, temp_container_name):
                        ret["result"] = False
                        return _format_comments(ret, comments)
                    ret["changes"].setdefault("container_id", {})[
                        "added"
                    ] = temp_container["Id"]
            else:
                # No changes between existing container and temp container.
                # First check if a requisite is asking to send a signal to the
                # existing container.
                if send_signal:
                    if __opts__["test"]:
                        comments.append(
                            "Signal {0} would be sent to container".format(watch_action)
                        )
                    else:
                        try:
                            __salt__["docker.signal"](name, signal=watch_action)
                        except CommandExecutionError as exc:
                            ret["result"] = False
                            comments.append(
                                "Failed to signal container: {0}".format(exc)
                            )
                            return _format_comments(ret, comments)
                        else:
                            ret["changes"]["signal"] = watch_action
                            comments.append(
                                "Sent signal {0} to container".format(watch_action)
                            )
                elif container_changes:
                    if not comments:
                        log.warning(
                            "docker_container.running: detected changes without "
                            "a specific comment for container '%s'",
                            name,
                        )
                        comments.append(
                            "Container '{0}'{1} updated.".format(
                                name, " would be" if __opts__["test"] else ""
                            )
                        )
                else:
                    # Container was not replaced, no differences between the
                    # existing container and the temp container were detected,
                    # and no signal was sent to the container.
                    comments.append(
                        "Container '{0}' is already configured as specified".format(
                            name
                        )
                    )

        if net_changes:
            ret["changes"].setdefault("container", {})["Networks"] = net_changes
            if __opts__["test"]:
                ret["result"] = None
                comments.append("Network configuration would be updated")
            elif cleanup_temp:
                # We only need to make network changes if the container
                # isn't being replaced, since we would already have
                # attached all the networks for purposes of comparison.
                network_failure = False
                for net_name in sorted(net_changes):
                    errors = []
                    disconnected = connected = False
                    try:
                        if name in __salt__["docker.connected"](net_name):
                            __salt__["docker.disconnect_container_from_network"](
                                name, net_name
                            )
                            disconnected = True
                    except CommandExecutionError as exc:
                        errors.append(exc.__str__())

                    if net_name in networks:
                        try:
                            __salt__["docker.connect_container_to_network"](
                                name, net_name, **networks[net_name]
                            )
                            connected = True
                        except CommandExecutionError as exc:
                            errors.append(exc.__str__())
                            if disconnected:
                                # We succeeded in disconnecting but failed
                                # to reconnect. This can happen if the
                                # network's subnet has changed and we try
                                # to reconnect with the same IP address
                                # from the old subnet.
                                for item in list(net_changes[net_name]):
                                    if net_changes[net_name][item]["old"] is None:
                                        # Since they'd both be None, just
                                        # delete this key from the changes
                                        del net_changes[net_name][item]
                                    else:
                                        net_changes[net_name][item]["new"] = None

                    if errors:
                        comments.extend(errors)
                        network_failure = True

                    ret["changes"].setdefault("container", {}).setdefault(
                        "Networks", {}
                    )[net_name] = net_changes[net_name]

                    if disconnected and connected:
                        comments.append(
                            "Reconnected to network '{0}' with updated "
                            "configuration".format(net_name)
                        )
                    elif disconnected:
                        comments.append(
                            "Disconnected from network '{0}'".format(net_name)
                        )
                    elif connected:
                        comments.append("Connected to network '{0}'".format(net_name))

                if network_failure:
                    ret["result"] = False
                    return _format_comments(ret, comments)
    finally:
        if cleanup_temp:
            _delete_temp_container()

    if skip_comparison:
        if not exists:
            comments.append("Created container '{0}'".format(name))
        else:
            if not _replace(name, temp_container):
                ret["result"] = False
                return _format_comments(ret, comments)
        ret["changes"].setdefault("container_id", {})["added"] = temp_container["Id"]

    # "exists" means that a container by the specified name existed prior to
    #     this state being run
    # "not cleanup_temp" means that the temp container became permanent, either
    #     because the named container did not exist or changes were detected
    # "cleanup_temp" means that the container already existed and no changes
    #     were detected, so the the temp container was discarded
    if (
        not cleanup_temp
        and (not exists or (exists and start))
        or (start and cleanup_temp and pre_state != "running")
    ):
        if __opts__["test"]:
            ret["result"] = None
            comments.append("Container would be started")
            return _format_comments(ret, comments)
        else:
            try:
                post_state = __salt__["docker.start"](name)["state"]["new"]
            except Exception as exc:  # pylint: disable=broad-except
                ret["result"] = False
                comments.append(
                    "Failed to start container '{0}': '{1}'".format(name, exc)
                )
                return _format_comments(ret, comments)
    else:
        post_state = __salt__["docker.state"](name)

    if not __opts__["test"] and post_state == "running":
        # Now that we're certain the container is running, check each modified
        # network to see if the network went from static (or disconnected) to
        # automatic IP configuration. If so, grab the automatically-assigned
        # IPs and munge the changes dict to include them. Note that this can
        # only be done after the container is started bceause automatic IPs are
        # assigned at runtime.
        contextkey = ".".join((name, "docker_container.running"))

        def _get_nets():
            if contextkey not in __context__:
                new_container_info = __salt__["docker.inspect_container"](name)
                __context__[contextkey] = new_container_info.get(
                    "NetworkSettings", {}
                ).get("Networks", {})
            return __context__[contextkey]

        autoip_keys = __salt__["config.option"](
            "docker.compare_container_networks"
        ).get("automatic", [])
        for net_name, net_changes in six.iteritems(
            ret["changes"].get("container", {}).get("Networks", {})
        ):
            if (
                "IPConfiguration" in net_changes
                and net_changes["IPConfiguration"]["new"] == "automatic"
            ):
                for key in autoip_keys:
                    val = _get_nets().get(net_name, {}).get(key)
                    if val:
                        net_changes[key] = {"old": None, "new": val}
                        try:
                            net_changes.pop("IPConfiguration")
                        except KeyError:
                            pass
        __context__.pop(contextkey, None)

    if pre_state != post_state:
        ret["changes"]["state"] = {"old": pre_state, "new": post_state}
        if pre_state is not None:
            comments.append(
                "State changed from '{0}' to '{1}'".format(pre_state, post_state)
            )

    if exists and current_image_id != image_id:
        comments.append("Container has a new image")
        ret["changes"]["image"] = {"old": current_image_id, "new": image_id}

    if post_state != "running" and start:
        ret["result"] = False
        comments.append("Container is not running")

    return _format_comments(ret, comments)


def run(
    name,
    image=None,
    onlyif=None,
    unless=None,
    creates=None,
    bg=False,
    failhard=True,
    replace=False,
    force=False,
    skip_translate=None,
    ignore_collisions=False,
    validate_ip_addrs=True,
    client_timeout=salt.utils.docker.CLIENT_TIMEOUT,
    **kwargs
):
    """
    .. versionadded:: 2018.3.0

    .. note::
        If no tag is specified in the image name, and nothing matching the
        specified image is pulled on the minion, the ``docker pull`` that
        retrieves the image will pull *all tags* for the image. A tag of
        ``latest`` is not implicit for the pull. For this reason, it is
        recommended to specify the image in ``repo:tag`` notation.

    Like the :py:func:`cmd.run <salt.states.cmd.run>` state, only for Docker.
    Does the equivalent of a ``docker run`` and returns information about the
    container that was created, as well as its output.

    This state accepts the same arguments as :py:func:`docker_container.running
    <salt.states.docker_container.running>`, with the exception of
    ``watch_action``, ``start``, and ``shutdown_timeout`` (though the ``force``
    argument has a different meaning in this state).

    In addition, this state accepts the arguments from :py:func:`docker.logs
    <salt.modules.dockermod.logs>`, with the exception of ``follow``, to
    control how logs are returned.

    Additionally, the following arguments are supported:

    onlyif
        A command or list of commands to run as a check. The container will
        only run if any of the specified commands returns a zero exit status.

    unless
        A command or list of commands to run as a check. The container will
        only run if any of the specified commands returns a non-zero exit
        status.

    creates
        A path or list of paths. Only run if one or more of the specified paths
        do not exist on the minion.

    bg : False
        If ``True``, run container in background and do not await or deliver
        its results.

        .. note::
            This may not be useful in cases where other states depend on the
            results of this state. Also, the logs will be inaccessible once the
            container exits if ``auto_remove`` is set to ``True``, so keep this
            in mind.

    failhard : True
        If ``True``, the state will return a ``False`` result if the exit code
        of the container is non-zero. When this argument is set to ``False``,
        the state will return a ``True`` result regardless of the container's
        exit code.

        .. note::
            This has no effect if ``bg`` is set to ``True``.

    replace : False
        If ``True``, and if the named container already exists, this will
        remove the existing container. The default behavior is to return a
        ``False`` result when the container already exists.

    force : False
        If ``True``, and the named container already exists, *and* ``replace``
        is also set to ``True``, then the container will be forcibly removed.
        Otherwise, the state will not proceed and will return a ``False``
        result.

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.run_container myuser/myimage command=/usr/local/bin/myscript.sh

    **USAGE EXAMPLE**

    .. code-block:: jinja

        {% set pkg_version = salt.pillar.get('pkg_version', '1.0-1') %}
        build_package:
          docker_container.run:
            - image: myuser/builder:latest
            - binds: /home/myuser/builds:/build_dir
            - command: /scripts/build.sh {{ pkg_version }}
            - creates: /home/myuser/builds/myapp-{{ pkg_version }}.noarch.rpm
            - replace: True
            - networks:
              - mynet
            - require:
              - docker_network: mynet
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    for unsupported in ("watch_action", "start", "shutdown_timeout", "follow"):
        if unsupported in kwargs:
            ret["result"] = False
            ret["comment"] = "The '{0}' argument is not supported".format(unsupported)
            return ret

    if image is None:
        ret["result"] = False
        ret["comment"] = "The 'image' argument is required"
        return ret
    elif not isinstance(image, six.string_types):
        image = six.text_type(image)

    cret = mod_run_check(onlyif, unless, creates)
    if isinstance(cret, dict):
        ret.update(cret)
        return ret

    try:
        if "networks" in kwargs and kwargs["networks"] is not None:
            kwargs["networks"] = _parse_networks(kwargs["networks"])
        _resolve_image(ret, image, client_timeout)
    except CommandExecutionError as exc:
        ret["result"] = False
        if exc.info is not None:
            return _format_comments(ret, exc.info)
        else:
            ret["comment"] = exc.__str__()
            return ret

    cret = mod_run_check(onlyif, unless, creates)
    if isinstance(cret, dict):
        ret.update(cret)
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Container would be run{0}".format(
            " in the background" if bg else ""
        )
        return ret

    if bg:
        remove = False
    else:
        # We're doing a bit of a hack here, so that we can get the exit code after
        # the container exits. Since the input translation and compilation of the
        # host_config take place within a private function of the execution module,
        # we manually do the handling for auto_remove here and extract if (if
        # present) from the kwargs. This allows us to explicitly pass auto_remove
        # as False when we run the container, so it is still present upon exit (and
        # the exit code can be retrieved). We can then remove the container
        # manually if auto_remove is True.
        remove = None
        for item in ("auto_remove", "rm"):
            try:
                val = kwargs.pop(item)
            except KeyError:
                continue
            if remove is not None:
                if not ignore_collisions:
                    ret["result"] = False
                    ret["comment"] = (
                        "'rm' is an alias for 'auto_remove', they cannot "
                        "both be used"
                    )
                    return ret
            else:
                remove = bool(val)

        if remove is not None:
            # We popped off the value, so replace it with False
            kwargs["auto_remove"] = False
        else:
            remove = False

    try:
        ret["changes"] = __salt__["docker.run_container"](
            image,
            name=name,
            skip_translate=skip_translate,
            ignore_collisions=ignore_collisions,
            validate_ip_addrs=validate_ip_addrs,
            client_timeout=client_timeout,
            bg=bg,
            replace=replace,
            force=force,
            **kwargs
        )
    except Exception as exc:  # pylint: disable=broad-except
        log.exception("Encountered error running container")
        ret["result"] = False
        ret["comment"] = "Encountered error running container: {0}".format(exc)
    else:
        if bg:
            ret["comment"] = "Container was run in the background"
        else:
            try:
                retcode = ret["changes"]["ExitCode"]
            except KeyError:
                pass
            else:
                ret["result"] = False if failhard and retcode != 0 else True
                ret["comment"] = (
                    "Container ran and exited with a return code of "
                    "{0}".format(retcode)
                )

    if remove:
        id_ = ret.get("changes", {}).get("Id")
        if id_:
            try:
                __salt__["docker.rm"](ret["changes"]["Id"])
            except CommandExecutionError as exc:
                ret.setdefault("warnings", []).append(
                    "Failed to auto_remove container: {0}".format(exc)
                )

    return ret


def stopped(
    name=None,
    containers=None,
    shutdown_timeout=None,
    unpause=False,
    error_on_absent=True,
    **kwargs
):
    """
    Ensure that a container (or containers) is stopped

    name
        Name or ID of the container

    containers
        Run this state on more than one container at a time. The following two
        examples accomplish the same thing:

        .. code-block:: yaml

            stopped_containers:
              docker_container.stopped:
                - names:
                  - foo
                  - bar
                  - baz

        .. code-block:: yaml

            stopped_containers:
              docker_container.stopped:
                - containers:
                  - foo
                  - bar
                  - baz

        However, the second example will be a bit quicker since Salt will stop
        all specified containers in a single run, rather than executing the
        state separately on each image (as it would in the first example).

    shutdown_timeout
        Timeout for graceful shutdown of the container. If this timeout is
        exceeded, the container will be killed. If this value is not passed,
        then the container's configured ``stop_timeout`` will be observed. If
        ``stop_timeout`` was also unset on the container, then a timeout of 10
        seconds will be used.

    unpause : False
        Set to ``True`` to unpause any paused containers before stopping. If
        unset, then an error will be raised for any container that was paused.

    error_on_absent : True
        By default, this state will return an error if any of the specified
        containers are absent. Set this to ``False`` to suppress that error.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if not name and not containers:
        ret["comment"] = "One of 'name' and 'containers' must be provided"
        return ret
    if containers is not None:
        if not isinstance(containers, list):
            ret["comment"] = "containers must be a list"
            return ret
        targets = []
        for target in containers:
            if not isinstance(target, six.string_types):
                target = six.text_type(target)
            targets.append(target)
    elif name:
        if not isinstance(name, six.string_types):
            targets = [six.text_type(name)]
        else:
            targets = [name]

    containers = {}
    for target in targets:
        try:
            c_state = __salt__["docker.state"](target)
        except CommandExecutionError:
            containers.setdefault("absent", []).append(target)
        else:
            containers.setdefault(c_state, []).append(target)

    errors = []
    if error_on_absent and "absent" in containers:
        errors.append(
            "The following container(s) are absent: {0}".format(
                ", ".join(containers["absent"])
            )
        )

    if not unpause and "paused" in containers:
        ret["result"] = False
        errors.append(
            "The following container(s) are paused: {0}".format(
                ", ".join(containers["paused"])
            )
        )

    if errors:
        ret["result"] = False
        ret["comment"] = ". ".join(errors)
        return ret

    to_stop = containers.get("running", []) + containers.get("paused", [])

    if not to_stop:
        ret["result"] = True
        if len(targets) == 1:
            ret["comment"] = "Container '{0}' is ".format(targets[0])
        else:
            ret["comment"] = "All specified containers are "
        if "absent" in containers:
            ret["comment"] += "absent or "
        ret["comment"] += "not running"
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "The following container(s) will be stopped: {0}".format(
            ", ".join(to_stop)
        )
        return ret

    stop_errors = []
    for target in to_stop:
        stop_kwargs = {"unpause": unpause}
        if shutdown_timeout:
            stop_kwargs["timeout"] = shutdown_timeout
        changes = __salt__["docker.stop"](target, **stop_kwargs)
        if changes["result"] is True:
            ret["changes"][target] = changes
        else:
            if "comment" in changes:
                stop_errors.append(changes["comment"])
            else:
                stop_errors.append("Failed to stop container '{0}'".format(target))

    if stop_errors:
        ret["comment"] = "; ".join(stop_errors)
        return ret

    ret["result"] = True
    ret["comment"] = "The following container(s) were stopped: {0}".format(
        ", ".join(to_stop)
    )
    return ret


def absent(name, force=False):
    """
    Ensure that a container is absent

    name
        Name of the container

    force : False
        Set to ``True`` to remove the container even if it is running

    Usage Examples:

    .. code-block:: yaml

        mycontainer:
          docker_container.absent

        multiple_containers:
          docker_container.absent:
            - names:
              - foo
              - bar
              - baz
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if name not in __salt__["docker.list_containers"](all=True):
        ret["result"] = True
        ret["comment"] = "Container '{0}' does not exist".format(name)
        return ret

    pre_state = __salt__["docker.state"](name)
    if pre_state != "stopped" and not force:
        ret["comment"] = (
            "Container is running, set force to True to " "forcibly remove it"
        )
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Container '{0}' will be removed".format(name)
        return ret

    try:
        ret["changes"]["removed"] = __salt__["docker.rm"](name, force=force)
    except Exception as exc:  # pylint: disable=broad-except
        ret["comment"] = "Failed to remove container '{0}': {1}".format(name, exc)
        return ret

    if name in __salt__["docker.list_containers"](all=True):
        ret["comment"] = "Failed to remove container '{0}'".format(name)
    else:
        if force and pre_state != "stopped":
            method = "Forcibly"
        else:
            method = "Successfully"
        ret["comment"] = "{0} removed container '{1}'".format(method, name)
        ret["result"] = True
    return ret


def mod_run_check(onlyif, unless, creates):
    """
    Execute the onlyif/unless/creates logic. Returns a result dict if any of
    the checks fail, otherwise returns True
    """
    cmd_kwargs = {"use_vt": False, "bg": False}

    if onlyif is not None:
        if isinstance(onlyif, six.string_types):
            onlyif = [onlyif]
        if not isinstance(onlyif, list) or not all(
            isinstance(x, six.string_types) for x in onlyif
        ):
            return {
                "comment": "onlyif is not a string or list of strings",
                "skip_watch": True,
                "result": True,
            }
        for entry in onlyif:
            retcode = __salt__["cmd.retcode"](
                entry, ignore_retcode=True, python_shell=True
            )
            if retcode != 0:
                return {
                    "comment": "onlyif command {0} returned exit code of {1}".format(
                        entry, retcode
                    ),
                    "skip_watch": True,
                    "result": True,
                }

    if unless is not None:
        if isinstance(unless, six.string_types):
            unless = [unless]
        if not isinstance(unless, list) or not all(
            isinstance(x, six.string_types) for x in unless
        ):
            return {
                "comment": "unless is not a string or list of strings",
                "skip_watch": True,
                "result": True,
            }
        for entry in unless:
            retcode = __salt__["cmd.retcode"](
                entry, ignore_retcode=True, python_shell=True
            )
            if retcode == 0:
                return {
                    "comment": "unless command {0} returned exit code of {1}".format(
                        entry, retcode
                    ),
                    "skip_watch": True,
                    "result": True,
                }

    if creates is not None:
        if isinstance(creates, six.string_types):
            creates = [creates]
        if not isinstance(creates, list) or not all(
            isinstance(x, six.string_types) for x in creates
        ):
            return {
                "comment": "creates is not a string or list of strings",
                "skip_watch": True,
                "result": True,
            }
        if all(os.path.exists(x) for x in creates):
            return {
                "comment": "All specified paths in 'creates' " "argument exist",
                "result": True,
            }

    # No reason to stop, return True
    return True


def mod_watch(name, sfun=None, **kwargs):
    """
    The docker_container watcher, called to invoke the watch command.

    .. note::
        This state exists to support special handling of the ``watch``
        :ref:`requisite <requisites>`. It should not be called directly.

        Parameters for this function should be set by the state being triggered.
    """
    if sfun == "running":
        watch_kwargs = copy.deepcopy(kwargs)
        if watch_kwargs.get("watch_action", "force") == "force":
            watch_kwargs["force"] = True
        else:
            watch_kwargs["send_signal"] = True
            watch_kwargs["force"] = False
        return running(name, **watch_kwargs)

    if sfun == "stopped":
        return stopped(name, **salt.utils.args.clean_kwargs(**kwargs))

    if sfun == "run":
        return run(name, **salt.utils.args.clean_kwargs(**kwargs))

    return {
        "name": name,
        "changes": {},
        "result": False,
        "comment": ("watch requisite is not" " implemented for {0}".format(sfun)),
    }
