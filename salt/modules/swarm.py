"""
Docker Swarm Module using Docker's Python SDK
=============================================

:codeauthor: Tyler Jones <jonestyler806@gmail.com>

.. versionadded:: 2018.3.0

The Docker Swarm Module is used to manage and create Docker Swarms.

Dependencies
------------

- Docker installed on the host
- Docker python sdk >= 2.5.1

Docker Python SDK
-----------------

.. code-block:: bash

    pip install -U docker

More information: https://docker-py.readthedocs.io/en/stable/
"""

import salt.utils.json


def _is_docker_module(mod):
    required_attrs = ["APIClient", "from_env"]
    return all(hasattr(mod, attr) for attr in required_attrs)


try:
    import docker

    HAS_DOCKER = _is_docker_module(docker)
except ImportError:
    HAS_DOCKER = False

__virtualname__ = "swarm"


def __virtual__():
    """
    Load this module if the docker python module is installed
    """
    if HAS_DOCKER:
        return __virtualname__
    return (
        False,
        "The swarm module failed to load: Docker python module is not available.",
    )


def __init__(self):
    if HAS_DOCKER:
        __context__["client"] = docker.from_env()
    __context__["server_name"] = __grains__["id"]


def swarm_tokens():
    """
    Get the Docker Swarm Manager or Worker join tokens

    CLI Example:

    .. code-block:: bash

        salt '*' swarm.swarm_tokens
    """
    client = docker.APIClient(base_url="unix://var/run/docker.sock")
    service = client.inspect_swarm()
    return service["JoinTokens"]


def swarm_init(advertise_addr=str, listen_addr=int, force_new_cluster=bool):
    """
    Initialize Docker on Minion as a Swarm Manager

    advertise_addr
        The ip of the manager

    listen_addr
        Listen address used for inter-manager communication,
        as well as determining the networking interface used
        for the VXLAN Tunnel Endpoint (VTEP).
        This can either be an address/port combination in
        the form 192.168.1.1:4567,
        or an interface followed by a port number,
        like eth0:4567

    force_new_cluster
        Force a new cluster if True is passed

    CLI Example:

    .. code-block:: bash

        salt '*' swarm.swarm_init advertise_addr='192.168.50.10' listen_addr='0.0.0.0' force_new_cluster=False
    """
    try:
        salt_return = {}
        __context__["client"].swarm.init(advertise_addr, listen_addr, force_new_cluster)
        output = (
            "Docker swarm has been initialized on {} "
            "and the worker/manager Join token is below".format(
                __context__["server_name"]
            )
        )
        salt_return.update({"Comment": output, "Tokens": swarm_tokens()})
    except docker.errors.APIError as err:
        salt_return = {}
        if "This node is already part of a swarm." in err.explanation:
            salt_return.update({"Comment": err.explanation, "result": False})
        else:
            salt_return.update({"Error": str(err.explanation), "result": False})
    except TypeError:
        salt_return = {}
        salt_return.update(
            {
                "Error": (
                    "Please make sure you are passing advertise_addr, "
                    "listen_addr and force_new_cluster correctly."
                )
            }
        )
    return salt_return


def joinswarm(remote_addr=int, listen_addr=int, token=str):
    """
    Join a Swarm Worker to the cluster

    remote_addr
        The manager node you want to connect to for the swarm

    listen_addr
        Listen address used for inter-manager communication if the node gets promoted to manager,
        as well as determining the networking interface used for the VXLAN Tunnel Endpoint (VTEP)

    token
        Either the manager join token or the worker join token.
        You can get the worker or manager token via ``salt '*' swarm.swarm_tokens``

    CLI Example:

    .. code-block:: bash

        salt '*' swarm.joinswarm remote_addr=192.168.50.10 listen_addr='0.0.0.0' \
            token='SWMTKN-1-64tux2g0701r84ofq93zppcih0pe081akq45owe9ts61f30x4t-06trjugdu7x2z47j938s54il'
    """
    try:
        salt_return = {}
        __context__["client"].swarm.join(
            remote_addrs=[remote_addr], listen_addr=listen_addr, join_token=token
        )
        output = __context__["server_name"] + " has joined the Swarm"
        salt_return.update({"Comment": output, "Manager_Addr": remote_addr})
    except TypeError:
        salt_return = {}
        salt_return.update(
            {
                "Error": (
                    "Please make sure this minion is not part of a swarm and you are "
                    "passing remote_addr, listen_addr and token correctly."
                )
            }
        )
    return salt_return


def leave_swarm(force=bool):
    """
    Force the minion to leave the swarm

    force
        Will force the minion/worker/manager to leave the swarm

    CLI Example:

    .. code-block:: bash

        salt '*' swarm.leave_swarm force=False
    """
    salt_return = {}
    __context__["client"].swarm.leave(force=force)
    output = __context__["server_name"] + " has left the swarm"
    salt_return.update({"Comment": output})
    return salt_return


def service_create(
    image=str,
    name=str,
    command=str,
    hostname=str,
    replicas=int,
    target_port=int,
    published_port=int,
):
    """
    Create Docker Swarm Service Create

    image
        The docker image

    name
        Is the service name

    command
        The docker command to run in the container at launch

    hostname
        The hostname of the containers

    replicas
        How many replicas you want running in the swarm

    target_port
        The target port on the container

    published_port
        port that's published on the host/os

    CLI Example:

    .. code-block:: bash

        salt '*' swarm.service_create image=httpd name=Test_Service \
            command=None hostname=salthttpd replicas=6 target_port=80 published_port=80
    """
    try:
        salt_return = {}
        replica_mode = docker.types.ServiceMode("replicated", replicas=replicas)
        ports = docker.types.EndpointSpec(ports={target_port: published_port})
        __context__["client"].services.create(
            name=name,
            image=image,
            command=command,
            mode=replica_mode,
            endpoint_spec=ports,
        )
        echoback = (
            __context__["server_name"]
            + " has a Docker Swarm Service running named "
            + name
        )
        salt_return.update(
            {
                "Info": echoback,
                "Minion": __context__["server_name"],
                "Name": name,
                "Image": image,
                "Command": command,
                "Hostname": hostname,
                "Replicas": replicas,
                "Target_Port": target_port,
                "Published_Port": published_port,
            }
        )
    except TypeError:
        salt_return = {}
        salt_return.update(
            {
                "Error": (
                    "Please make sure you are passing arguments correctly [image, name,"
                    " command, hostname, replicas, target_port and published_port]"
                )
            }
        )
    return salt_return


def swarm_service_info(service_name=str):
    """
    Swarm Service Information

    service_name
        The name of the service that you want information on about the service

    CLI Example:

    .. code-block:: bash

        salt '*' swarm.swarm_service_info service_name=Test_Service
    """
    try:
        salt_return = {}
        client = docker.APIClient(base_url="unix://var/run/docker.sock")
        service = client.inspect_service(service=service_name)
        getdata = salt.utils.json.dumps(service)
        dump = salt.utils.json.loads(getdata)
        version = dump["Version"]["Index"]
        name = dump["Spec"]["Name"]
        network_mode = dump["Spec"]["EndpointSpec"]["Mode"]
        ports = dump["Spec"]["EndpointSpec"]["Ports"]
        swarm_id = dump["ID"]
        create_date = dump["CreatedAt"]
        update_date = dump["UpdatedAt"]
        labels = dump["Spec"]["Labels"]
        replicas = dump["Spec"]["Mode"]["Replicated"]["Replicas"]
        network = dump["Endpoint"]["VirtualIPs"]
        image = dump["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"]
        for items in ports:
            published_port = items["PublishedPort"]
            target_port = items["TargetPort"]
            published_mode = items["PublishMode"]
            protocol = items["Protocol"]
            salt_return.update(
                {
                    "Service Name": name,
                    "Replicas": replicas,
                    "Service ID": swarm_id,
                    "Network": network,
                    "Network Mode": network_mode,
                    "Creation Date": create_date,
                    "Update Date": update_date,
                    "Published Port": published_port,
                    "Target Port": target_port,
                    "Published Mode": published_mode,
                    "Protocol": protocol,
                    "Docker Image": image,
                    "Minion Id": __context__["server_name"],
                    "Version": version,
                }
            )
    except TypeError:
        salt_return = {}
        salt_return.update({"Error": "service_name arg is missing?"})
    return salt_return


def remove_service(service=str):
    """
    Remove Swarm Service

    service
        The name of the service

    CLI Example:

    .. code-block:: bash

        salt '*' swarm.remove_service service=Test_Service
    """
    try:
        salt_return = {}
        client = docker.APIClient(base_url="unix://var/run/docker.sock")
        service = client.remove_service(service)
        salt_return.update(
            {"Service Deleted": service, "Minion ID": __context__["server_name"]}
        )
    except TypeError:
        salt_return = {}
        salt_return.update({"Error": "service arg is missing?"})
    return salt_return


def node_ls(server=str):
    """
    Displays Information about Swarm Nodes with passing in the server

    server
        The minion/server name

    CLI Example:

    .. code-block:: bash

        salt '*' swarm.node_ls server=minion1
    """
    try:
        salt_return = {}
        client = docker.APIClient(base_url="unix://var/run/docker.sock")
        service = client.nodes(filters=({"name": server}))
        getdata = salt.utils.json.dumps(service)
        dump = salt.utils.json.loads(getdata)
        for items in dump:
            docker_version = items["Description"]["Engine"]["EngineVersion"]
            platform = items["Description"]["Platform"]
            hostnames = items["Description"]["Hostname"]
            ids = items["ID"]
            role = items["Spec"]["Role"]
            availability = items["Spec"]["Availability"]
            status = items["Status"]
            version = items["Version"]["Index"]
            salt_return.update(
                {
                    "Docker Version": docker_version,
                    "Platform": platform,
                    "Hostname": hostnames,
                    "ID": ids,
                    "Roles": role,
                    "Availability": availability,
                    "Status": status,
                    "Version": version,
                }
            )
    except TypeError:
        salt_return = {}
        salt_return.update(
            {"Error": "The server arg is missing or you not targeting a Manager node?"}
        )
    return salt_return


def remove_node(node_id=str, force=bool):
    """
    Remove a node from a swarm and the target needs to be a swarm manager

    node_id
        The node id from the return of swarm.node_ls

    force
        Forcefully remove the node/minion from the service

    CLI Example:

    .. code-block:: bash

        salt '*' swarm.remove_node node_id=z4gjbe9rwmqahc2a91snvolm5 force=false
    """
    client = docker.APIClient(base_url="unix://var/run/docker.sock")
    try:
        if force == "True":
            service = client.remove_node(node_id, force=True)
            return service
        else:
            service = client.remove_node(node_id, force=False)
            return service
    except TypeError:
        salt_return = {}
        salt_return.update({"Error": "Is the node_id and/or force=True/False missing?"})
        return salt_return


def update_node(availability=str, node_name=str, role=str, node_id=str, version=int):
    """
    Updates docker swarm nodes/needs to target a manager node/minion

    availability
        Drain or Active

    node_name
        minion/node

    role
        role of manager or worker

    node_id
        The Id and that can be obtained via swarm.node_ls

    version
        Is obtained by swarm.node_ls

    CLI Example:

    .. code-block:: bash

        salt '*' swarm.update_node availability=drain node_name=minion2 \
            role=worker node_id=3k9x7t8m4pel9c0nqr3iajnzp version=19
    """
    client = docker.APIClient(base_url="unix://var/run/docker.sock")
    try:
        salt_return = {}
        node_spec = {"Availability": availability, "Name": node_name, "Role": role}
        client.update_node(node_id=node_id, version=version, node_spec=node_spec)
        salt_return.update({"Node Information": node_spec})
    except TypeError:
        salt_return = {}
        salt_return.update(
            {
                "Error": (
                    "Make sure all args are passed [availability, node_name, role,"
                    " node_id, version]"
                )
            }
        )
    return salt_return
