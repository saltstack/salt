"""
Management of Docker networks

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
module (formerly called **dockerng**) in the 2017.7.0 release.
"""

import copy
import logging
import random
import string

import salt.utils.dockermod.translate.network
from salt._compat import ipaddress
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "docker_network"
__virtual_aliases__ = ("moby_network",)

__deprecated__ = (
    3009,
    "docker",
    "https://github.com/saltstack/saltext-docker",
)


def __virtual__():
    """
    Only load if the docker execution module is available
    """
    if "docker.version" in __salt__:
        return __virtualname__
    return (False, __salt__.missing_fun_string("docker.version"))


def _normalize_pools(existing, desired):
    pools = {"existing": {4: None, 6: None}, "desired": {4: None, 6: None}}

    for pool in existing["Config"]:
        subnet = ipaddress.ip_network(pool.get("Subnet"))
        pools["existing"][subnet.version] = pool

    for pool in desired["Config"]:
        subnet = ipaddress.ip_network(pool.get("Subnet"))
        if pools["desired"][subnet.version] is not None:
            raise ValueError(f"Only one IPv{subnet.version} pool is permitted")
        else:
            pools["desired"][subnet.version] = pool

    if pools["desired"][6] and not pools["desired"][4]:
        raise ValueError(
            "An IPv4 pool is required when an IPv6 pool is used. See the "
            "documentation for details."
        )

    # The pools will be sorted when comparing
    existing["Config"] = [
        pools["existing"][x] for x in (4, 6) if pools["existing"][x] is not None
    ]
    desired["Config"] = [
        pools["desired"][x] for x in (4, 6) if pools["desired"][x] is not None
    ]


def present(
    name,
    skip_translate=None,
    ignore_collisions=False,
    validate_ip_addrs=True,
    containers=None,
    reconnect=True,
    **kwargs,
):
    """
    .. versionchanged:: 2018.3.0
        Support added for network configuration options other than ``driver``
        and ``driver_opts``, as well as IPAM configuration.

    Ensure that a network is present

    .. note::
        This state supports all arguments for network and IPAM pool
        configuration which are available for the release of docker-py
        installed on the minion. For that reason, the arguments described below
        in the :ref:`NETWORK CONFIGURATION
        <salt-states-docker-network-present-netconf>` and :ref:`IP ADDRESS
        MANAGEMENT (IPAM) <salt-states-docker-network-present-ipam>` sections
        may not accurately reflect what is available on the minion. The
        :py:func:`docker.get_client_args
        <salt.modules.dockermod.get_client_args>` function can be used to check
        the available arguments for the installed version of docker-py (they
        are found in the ``network_config`` and ``ipam_config`` sections of the
        return data), but Salt will not prevent a user from attempting to use
        an argument which is unsupported in the release of Docker which is
        installed. In those cases, network creation be attempted but will fail.

    name
        Network name

    skip_translate
        This function translates Salt SLS input into the format which
        docker-py expects. However, in the event that Salt's translation logic
        fails (due to potential changes in the Docker Remote API, or to bugs in
        the translation code), this argument can be used to exert granular
        control over which arguments are translated and which are not.

        Pass this argument as a comma-separated list (or Python list) of
        arguments, and translation for each passed argument name will be
        skipped. Alternatively, pass ``True`` and *all* translation will be
        skipped.

        Skipping tranlsation allows for arguments to be formatted directly in
        the format which docker-py expects. This allows for API changes and
        other issues to be more easily worked around. See the following links
        for more information:

        - `docker-py Low-level API`_
        - `Docker Engine API`_

        .. versionadded:: 2018.3.0

    .. _`docker-py Low-level API`: http://docker-py.readthedocs.io/en/stable/api.html#docker.api.container.ContainerApiMixin.create_container
    .. _`Docker Engine API`: https://docs.docker.com/engine/api/v1.33/#operation/ContainerCreate

    ignore_collisions : False
        Since many of docker-py's arguments differ in name from their CLI
        counterparts (with which most Docker users are more familiar), Salt
        detects usage of these and aliases them to the docker-py version of
        that argument. However, if both the alias and the docker-py version of
        the same argument (e.g. ``options`` and ``driver_opts``) are used, an error
        will be raised. Set this argument to ``True`` to suppress these errors
        and keep the docker-py version of the argument.

        .. versionadded:: 2018.3.0

    validate_ip_addrs : True
        For parameters which accept IP addresses/subnets as input, validation
        will be performed. To disable, set this to ``False``.

        .. versionadded:: 2018.3.0

    containers
        A list of containers which should be connected to this network.

        .. note::
            As of the 2018.3.0 release, this is not the recommended way of
            managing a container's membership in a network, for a couple
            reasons:

            1. It does not support setting static IPs, aliases, or links in the
               container's IP configuration.
            2. If a :py:func:`docker_container.running
               <salt.states.docker_container.running>` state replaces a
               container, it will not be reconnected to the network until the
               ``docker_network.present`` state is run again. Since containers
               often have ``require`` requisites to ensure that the network
               is present, this means that the ``docker_network.present`` state
               ends up being run *before* the :py:func:`docker_container.running
               <salt.states.docker_container.running>`, leaving the container
               unattached at the end of the Salt run.

            For these reasons, it is recommended to use
            :ref:`docker_container.running's network management support
            <salt-states-docker-container-network-management>`.

    reconnect : True
        If ``containers`` is not used, and the network is replaced, then Salt
        will keep track of the containers which were connected to the network
        and reconnect them to the network after it is replaced. Salt will first
        attempt to reconnect using the same IP the container had before the
        network was replaced. If that fails (for instance, if the network was
        replaced because the subnet was modified), then the container will be
        reconnected without an explicit IP address, and its IP will be assigned
        by Docker.

        Set this option to ``False`` to keep Salt from trying to reconnect
        containers. This can be useful in some cases when :ref:`managing static
        IPs in docker_container.running
        <salt-states-docker-container-network-management>`. For instance, if a
        network's subnet is modified, it is likely that the static IP will need
        to be updated in the ``docker_container.running`` state as well. When
        the network is replaced, the initial reconnect attempt would fail, and
        the container would be reconnected with an automatically-assigned IP
        address. Then, when the ``docker_container.running`` state executes, it
        would disconnect the network *again* and reconnect using the new static
        IP. Disabling the reconnect behavior in these cases would prevent the
        unnecessary extra reconnection.

        .. versionadded:: 2018.3.0

    .. _salt-states-docker-network-present-netconf:

    **NETWORK CONFIGURATION ARGUMENTS**

    driver
        Network driver

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - driver: macvlan

    driver_opts (or *driver_opt*, or *options*)
        Options for the network driver. Either a dictionary of option names and
        values or a Python list of strings in the format ``varname=value``. The
        below three examples are equivalent:

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - driver: macvlan
                - driver_opts: macvlan_mode=bridge,parent=eth0

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - driver: macvlan
                - driver_opts:
                  - macvlan_mode=bridge
                  - parent=eth0

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - driver: macvlan
                - driver_opts:
                  - macvlan_mode: bridge
                  - parent: eth0

        The options can also simply be passed as a dictionary, though this can
        be error-prone due to some :ref:`idiosyncrasies <yaml-idiosyncrasies>`
        with how PyYAML loads nested data structures:

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - driver: macvlan
                - driver_opts:
                    macvlan_mode: bridge
                    parent: eth0

    check_duplicate : True
        If ``True``, checks for networks with duplicate names. Since networks
        are primarily keyed based on a random ID and not on the name, and
        network name is strictly a user-friendly alias to the network which is
        uniquely identified using ID, there is no guaranteed way to check for
        duplicates. This option providess a best effort, checking for any
        networks which have the same name, but it is not guaranteed to catch
        all name collisions.

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - check_duplicate: False

    internal : False
        If ``True``, restricts external access to the network

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - internal: True

    labels
        Add metadata to the network. Labels can be set both with and without
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

    enable_ipv6 (or *ipv6*) : False
        Enable IPv6 on the network

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - enable_ipv6: True

        .. note::
            While it should go without saying, this argument must be set to
            ``True`` to :ref:`configure an IPv6 subnet
            <salt-states-docker-network-present-ipam>`. Also, if this option is
            turned on without an IPv6 subnet explicitly configured, you will
            get an error unless you have set up a fixed IPv6 subnet. Consult
            the `Docker IPv6 docs`_ for information on how to do this.

            .. _`Docker IPv6 docs`: https://docs.docker.com/v17.09/engine/userguide/networking/default_network/ipv6/

    attachable : False
        If ``True``, and the network is in the global scope, non-service
        containers on worker nodes will be able to connect to the network.

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - attachable: True

        .. note::
            This option cannot be reliably managed on CentOS 7. This is because
            while support for this option was added in API version 1.24, its
            value was not added to the inpsect results until API version 1.26.
            The version of Docker which is available for CentOS 7 runs API
            version 1.24, meaning that while Salt can pass this argument to the
            API, it has no way of knowing the value of this config option in an
            existing Docker network.

    scope
        Specify the network's scope (``local``, ``global`` or ``swarm``)

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - scope: local

    ingress : False
        If ``True``, create an ingress network which provides the routing-mesh in
        swarm mode

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - ingress: True

    .. _salt-states-docker-network-present-ipam:

    **IP ADDRESS MANAGEMENT (IPAM)**

    This state supports networks with either IPv4, or both IPv4 and IPv6. If
    configuring IPv4, then you can pass the :ref:`IPAM pool arguments
    <salt-states-docker-network-present-ipam-pool-arguments>` below as
    individual arguments. However, if configuring IPv4 and IPv6, the arguments
    must be passed as a list of dictionaries, in the ``ipam_pools`` argument
    (click :ref:`here <salt-states-docker-network-present-ipam-examples>` for
    some examples). `These docs`_ also have more information on these
    arguments.

    .. _`These docs`: http://docker-py.readthedocs.io/en/stable/api.html#docker.types.IPAMPool

    *IPAM ARGUMENTS*

    ipam_driver
        IPAM driver to use, if different from the default one

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - ipam_driver: foo

    ipam_opts
        Options for the IPAM driver. Either a dictionary of option names and
        values or a Python list of strings in the format ``varname=value``. The
        below three examples are equivalent:

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - ipam_driver: foo
                - ipam_opts: foo=bar,baz=qux

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - ipam_driver: foo
                - ipam_opts:
                  - foo=bar
                  - baz=qux

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - ipam_driver: foo
                - ipam_opts:
                  - foo: bar
                  - baz: qux

        The options can also simply be passed as a dictionary, though this can
        be error-prone due to some :ref:`idiosyncrasies <yaml-idiosyncrasies>`
        with how PyYAML loads nested data structures:

        .. code-block:: yaml

            mynet:
              docker_network.present:
                - ipam_driver: macvlan
                - ipam_opts:
                    foo: bar
                    baz: qux

    .. _salt-states-docker-network-present-ipam-pool-arguments:

    *IPAM POOL ARGUMENTS*

    subnet
        Subnet in CIDR format that represents a network segment

    iprange (or *ip_range*)
        Allocate container IP from a sub-range within the subnet

        Subnet in CIDR format that represents a network segment

    gateway
        IPv4 or IPv6 gateway for the master subnet

    aux_addresses (or *aux_address*)
        A dictionary of mapping container names to IP addresses which should be
        allocated for them should they connect to the network. Either a
        dictionary of option names and values or a Python list of strings in
        the format ``host=ipaddr``.

    .. _salt-states-docker-network-present-ipam-examples:

    *IPAM CONFIGURATION EXAMPLES*

    Below is an example of an IPv4-only network (keep in mind that ``subnet``
    is the only required argument).

    .. code-block:: yaml

        mynet:
          docker_network.present:
            - subnet: 10.0.20.0/24
            - iprange: 10.0.20.128/25
            - gateway: 10.0.20.254
            - aux_addresses:
              - foo.bar.tld: 10.0.20.50
              - hello.world.tld: 10.0.20.51

    .. note::
        The ``aux_addresses`` can be passed differently, in the same way that
        ``driver_opts`` and ``ipam_opts`` can.

    This same network could also be configured this way:

    .. code-block:: yaml

        mynet:
          docker_network.present:
            - ipam_pools:
              - subnet: 10.0.20.0/24
                iprange: 10.0.20.128/25
                gateway: 10.0.20.254
                aux_addresses:
                  foo.bar.tld: 10.0.20.50
                  hello.world.tld: 10.0.20.51

    Here is an example of a mixed IPv4/IPv6 subnet.

    .. code-block:: yaml

        mynet:
          docker_network.present:
            - ipam_pools:
              - subnet: 10.0.20.0/24
                gateway: 10.0.20.1
              - subnet: fe3f:2180:26:1::/123
                gateway: fe3f:2180:26:1::1
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    try:
        network = __salt__["docker.inspect_network"](name)
    except CommandExecutionError as exc:
        msg = str(exc)
        if "404" in msg:
            # Network not present
            network = None
        else:
            ret["comment"] = msg
            return ret

    # map container's IDs to names
    to_connect = {}
    missing_containers = []
    stopped_containers = []
    for cname in __utils__["args.split_input"](containers or []):
        try:
            cinfo = __salt__["docker.inspect_container"](cname)
        except CommandExecutionError:
            missing_containers.append(cname)
        else:
            try:
                cid = cinfo["Id"]
            except KeyError:
                missing_containers.append(cname)
            else:
                if not cinfo.get("State", {}).get("Running", False):
                    stopped_containers.append(cname)
                else:
                    to_connect[cid] = {"Name": cname}

    if missing_containers:
        ret.setdefault("warnings", []).append(
            "The following containers do not exist: {}.".format(
                ", ".join(missing_containers)
            )
        )

    if stopped_containers:
        ret.setdefault("warnings", []).append(
            "The following containers are not running: {}.".format(
                ", ".join(stopped_containers)
            )
        )

    # We might disconnect containers in the process of recreating the network,
    # we'll need to keep track these containers so we can reconnect them later.
    disconnected_containers = {}

    try:
        kwargs = __utils__["docker.translate_input"](
            salt.utils.dockermod.translate.network,
            skip_translate=skip_translate,
            ignore_collisions=ignore_collisions,
            validate_ip_addrs=validate_ip_addrs,
            **__utils__["args.clean_kwargs"](**kwargs),
        )
    except Exception as exc:  # pylint: disable=broad-except
        ret["comment"] = str(exc)
        return ret

    # Separate out the IPAM config options and build the IPAM config dict
    ipam_kwargs = {}
    ipam_kwarg_names = ["ipam", "ipam_driver", "ipam_opts", "ipam_pools"]
    ipam_kwarg_names.extend(
        __salt__["docker.get_client_args"]("ipam_config")["ipam_config"]
    )
    for key in ipam_kwarg_names:
        try:
            ipam_kwargs[key] = kwargs.pop(key)
        except KeyError:
            pass
    if "ipam" in ipam_kwargs:
        if len(ipam_kwargs) > 1:
            ret["comment"] = (
                "Cannot mix the 'ipam' argument with any of the IPAM config "
                "arguments. See documentation for details."
            )
            return ret
        ipam_config = ipam_kwargs["ipam"]
    else:
        ipam_pools = ipam_kwargs.pop("ipam_pools", ())
        try:
            ipam_config = __utils__["docker.create_ipam_config"](
                *ipam_pools, **ipam_kwargs
            )
        except Exception as exc:  # pylint: disable=broad-except
            ret["comment"] = str(exc)
            return ret

    # We'll turn this off if we decide below that creating the network is not
    # necessary.
    create_network = True

    if network is not None:
        log.debug("Docker network '%s' already exists", name)

        # Set the comment now to say that it already exists, if we need to
        # recreate the network with new config we'll update the comment later.
        ret["comment"] = (
            f"Network '{name}' already exists, and is configured as specified"
        )
        log.trace("Details of docker network '%s': %s", name, network)

        temp_net_name = "".join(
            random.choice(string.ascii_lowercase) for _ in range(20)
        )

        try:
            # When using enable_ipv6, you *must* provide a subnet. But we don't
            # care about the subnet when we make our temp network, we only care
            # about the non-IPAM values in the network. And we also do not want
            # to try some hacky workaround where we choose a small IPv6 subnet
            # to pass when creating the temp network, that may end up
            # overlapping with a large IPv6 subnet already in use by Docker.
            # So, for purposes of comparison we will create the temp network
            # with enable_ipv6=False and then munge the inspect results before
            # performing the comparison. Note that technically it is not
            # required that one specify both v4 and v6 subnets when creating a
            # network, but not specifying IPv4 makes it impossible for us to
            # reliably compare the SLS input to the existing network, as we
            # wouldng't know if the IPv4 subnet in the existing network was
            # explicitly configured or was automatically assigned by Docker.
            enable_ipv6 = kwargs.pop("enable_ipv6", None)
            kwargs_tmp = kwargs
            driver = kwargs.get(
                "driver",
            )
            driver_opts = kwargs.get("options", {})
            bridge_name = driver_opts.get("com.docker.network.bridge.name", None)

            if driver == "bridge" and bridge_name is not None:
                tmp_name = str(bridge_name) + "comp"
                kwargs_tmp["options"]["com.docker.network.bridge.name"] = tmp_name[-14:]
            __salt__["docker.create_network"](
                temp_net_name,
                skip_translate=True,  # No need to translate (already did)
                enable_ipv6=False,
                **kwargs_tmp,
            )
        except CommandExecutionError as exc:
            ret["comment"] = "Failed to create temp network for comparison: {}".format(
                str(exc)
            )
            return ret
        else:
            # Replace the value so we can use it later
            if enable_ipv6 is not None:
                kwargs["enable_ipv6"] = enable_ipv6

        try:
            try:
                temp_net_info = __salt__["docker.inspect_network"](temp_net_name)
            except CommandExecutionError as exc:
                ret["comment"] = f"Failed to inspect temp network: {str(exc)}"
                return ret
            else:
                temp_net_info["EnableIPv6"] = bool(enable_ipv6)

            # Replace the IPAM configuration in the temp network with the IPAM
            # config dict we created earlier, for comparison purposes. This is
            # necessary because we cannot create two networks that have
            # overlapping subnets (the Docker Engine will throw an error).
            temp_net_info["IPAM"] = ipam_config

            existing_pool_count = len(network["IPAM"]["Config"])
            desired_pool_count = len(temp_net_info["IPAM"]["Config"])

            def is_default_pool(x):
                return True if sorted(x) == ["Gateway", "Subnet"] else False

            if (
                desired_pool_count == 0
                and existing_pool_count == 1
                and is_default_pool(network["IPAM"]["Config"][0])
            ):
                # If we're not explicitly configuring an IPAM pool, then we
                # don't care what the subnet is. Docker networks created with
                # no explicit IPAM configuration are assigned a single IPAM
                # pool containing just a subnet and gateway. If the above if
                # statement resolves as True, then we know that both A) we
                # aren't explicitly configuring IPAM, and B) the existing
                # network appears to be one that was created without an
                # explicit IPAM configuration (since it has the default pool
                # config values). Of course, it could be possible that the
                # existing network was created with a single custom IPAM pool,
                # with just a subnet and gateway. But even if this was the
                # case, the fact that we aren't explicitly enforcing IPAM
                # configuration means we don't really care what the existing
                # IPAM configuration is. At any rate, to avoid IPAM differences
                # when comparing the existing network to the temp network, we
                # need to clear the existing network's IPAM configuration.
                network["IPAM"]["Config"] = []

            changes = __salt__["docker.compare_networks"](
                network, temp_net_info, ignore="Name,Id,Created,Containers"
            )

            if not changes:
                # No changes to the network, so we'll be keeping the existing
                # network and at most just connecting containers to it.
                create_network = False

            else:
                ret["changes"][name] = changes
                if __opts__["test"]:
                    ret["result"] = None
                    ret["comment"] = "Network would be recreated with new config"
                    return ret

                if network["Containers"]:
                    # We've removed the network, so there are now no containers
                    # attached to it. However, once we recreate the network
                    # with the new configuration we may need to reconnect the
                    # containers that were previously connected. Even if we're
                    # not reconnecting, we still need to track the containers
                    # so that we can report on which were disconnected.
                    disconnected_containers = copy.deepcopy(network["Containers"])
                    if not containers and reconnect:
                        # Grab the links and aliases from each connected
                        # container so that we have them when we attempt to
                        # reconnect later
                        for cid in disconnected_containers:
                            try:
                                cinfo = __salt__["docker.inspect_container"](cid)
                                netinfo = cinfo["NetworkSettings"]["Networks"][name]
                                # Links and Aliases will be None if not
                                # explicitly set, hence using "or" instead of
                                # placing the empty list inside the dict.get
                                net_links = netinfo.get("Links") or []
                                net_aliases = netinfo.get("Aliases") or []
                                if net_links:
                                    disconnected_containers[cid]["Links"] = net_links
                                if net_aliases:
                                    disconnected_containers[cid][
                                        "Aliases"
                                    ] = net_aliases
                            except (CommandExecutionError, KeyError, ValueError):
                                continue

                remove_result = _remove_network(network)
                if not remove_result["result"]:
                    return remove_result

                # Replace the Containers key with an empty dict so that when we
                # check for connnected containers below, we correctly see that
                # there are none connected.
                network["Containers"] = {}
        finally:
            try:
                __salt__["docker.remove_network"](temp_net_name)
            except CommandExecutionError as exc:
                ret.setdefault("warnings", []).append(
                    f"Failed to remove temp network '{temp_net_name}': {exc}."
                )

    if create_network:
        log.debug("Network '%s' will be created", name)
        if __opts__["test"]:
            # NOTE: if the container already existed and needed to be
            # recreated, and we were in test mode, we would have already exited
            # above with a comment about the network needing to be recreated.
            # So, even though the below block to create the network would be
            # executed to create the network both when it's being recreated and
            # when it's being created for the first time, the below comment is
            # still accurate.
            ret["result"] = None
            ret["comment"] = "Network will be created"
            return ret

        kwargs["ipam"] = ipam_config
        try:
            __salt__["docker.create_network"](
                name,
                skip_translate=True,  # No need to translate (already did)
                **kwargs,
            )
        except Exception as exc:  # pylint: disable=broad-except
            ret["comment"] = f"Failed to create network '{name}': {exc}"
            return ret
        else:
            action = "recreated" if network is not None else "created"
            ret["changes"][action] = True
            ret["comment"] = "Network '{}' {}".format(
                name,
                "created" if network is None else "was replaced with updated config",
            )
            # Make sure the "Containers" key exists for logic below
            network = {"Containers": {}}

    # If no containers were specified in the state but we have disconnected
    # some in the process of recreating the network, we should reconnect those
    # containers.
    if containers is None and reconnect and disconnected_containers:
        to_connect = disconnected_containers

    # Don't try to connect any containers which are already connected. If we
    # created/re-created the network, then network['Containers'] will be empty
    # and no containers will be deleted from the to_connect dict (the result
    # being that we will reconnect all containers in the to_connect dict).
    # list() is used here because we will potentially be modifying the
    # dictionary during iteration.
    for cid in list(to_connect):
        if cid in network["Containers"]:
            del to_connect[cid]

    errors = []
    if to_connect:
        for cid, connect_info in to_connect.items():
            connect_kwargs = {}
            if cid in disconnected_containers:
                for key_name, arg_name in (
                    ("IPv4Address", "ipv4_address"),
                    ("IPV6Address", "ipv6_address"),
                    ("Links", "links"),
                    ("Aliases", "aliases"),
                ):
                    try:
                        connect_kwargs[arg_name] = connect_info[key_name]
                    except (KeyError, AttributeError):
                        continue
                    else:
                        if key_name.endswith("Address"):
                            connect_kwargs[arg_name] = connect_kwargs[arg_name].rsplit(
                                "/", 1
                            )[0]
            try:
                __salt__["docker.connect_container_to_network"](
                    cid, name, **connect_kwargs
                )
            except CommandExecutionError as exc:
                if not connect_kwargs:
                    errors.append(str(exc))
                else:
                    # We failed to reconnect with the container's old IP
                    # configuration. Reconnect using automatic IP config.
                    try:
                        __salt__["docker.connect_container_to_network"](cid, name)
                    except CommandExecutionError as exc:
                        errors.append(str(exc))
                    else:
                        ret["changes"].setdefault(
                            (
                                "reconnected"
                                if cid in disconnected_containers
                                else "connected"
                            ),
                            [],
                        ).append(connect_info["Name"])
            else:
                ret["changes"].setdefault(
                    "reconnected" if cid in disconnected_containers else "connected", []
                ).append(connect_info["Name"])

    if errors:
        if ret["comment"]:
            ret["comment"] += ". "
        ret["comment"] += ". ".join(errors) + "."
    else:
        ret["result"] = True

    # Figure out if we removed any containers as a result of replacing the
    # network and did not reconnect them. We only would not have reconnected if
    # a list of containers was passed in the "containers" argument, and there
    # were containers connected to the network prior to its replacement which
    # were not part of that list.
    for cid, c_info in disconnected_containers.items():
        if cid not in to_connect:
            ret["changes"].setdefault("disconnected", []).append(c_info["Name"])

    return ret


def absent(name):
    """
    Ensure that a network is absent.

    name
        Name of the network

    Usage Example:

    .. code-block:: yaml

        network_foo:
          docker_network.absent
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    try:
        network = __salt__["docker.inspect_network"](name)
    except CommandExecutionError as exc:
        msg = str(exc)
        if "404" in msg:
            # Network not present
            network = None
        else:
            ret["comment"] = msg
            return ret

    if network is None:
        ret["result"] = True
        ret["comment"] = f"Network '{name}' already absent"
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Network '{name}' will be removed"
        return ret

    return _remove_network(network)


def _remove_network(network):
    """
    Remove network, including all connected containers
    """
    ret = {"name": network["Name"], "changes": {}, "result": False, "comment": ""}

    errors = []
    for cid in network["Containers"]:
        try:
            cinfo = __salt__["docker.inspect_container"](cid)
        except CommandExecutionError:
            # Fall back to container ID
            cname = cid
        else:
            cname = cinfo.get("Name", "").lstrip("/")

        try:
            __salt__["docker.disconnect_container_from_network"](cid, network["Name"])
        except CommandExecutionError as exc:
            errors = f"Failed to disconnect container '{cname}' : {exc}"
        else:
            ret["changes"].setdefault("disconnected", []).append(cname)

    if errors:
        ret["comment"] = "\n".join(errors)
        return ret

    try:
        __salt__["docker.remove_network"](network["Name"])
    except CommandExecutionError as exc:
        ret["comment"] = f"Failed to remove network: {exc}"
    else:
        ret["changes"]["removed"] = True
        ret["result"] = True
        ret["comment"] = "Removed network '{}'".format(network["Name"])

    return ret
