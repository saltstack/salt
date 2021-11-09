"""
A route is a rule that specifies how certain packets should be handled by the
virtual network. Routes are associated with virtual machine instances by tag,
and the set of routes for a particular VM is called its routing table.
For each packet leaving a virtual machine, the system searches that machine's
routing table for a single best matching route.

.. versionadded:: 2018.3.0

This module will create a route to send traffic destined to the Internet
through your gateway instance.

:codeauthor: `Pratik Bandarkar <pratik.bandarkar@gmail.com>`
:maturity:   new
:depends:    google-api-python-client
:platform:   Linux

"""

import logging

try:
    import googleapiclient.discovery
    import oauth2client.service_account

    HAS_LIB = True
except ImportError:
    HAS_LIB = False

log = logging.getLogger(__name__)

__virtualname__ = "gcp"


def __virtual__():
    """
    Check for googleapiclient api
    """
    if HAS_LIB is False:
        return (
            False,
            "Required dependencies 'googleapiclient' and/or 'oauth2client' were not"
            " found.",
        )
    return __virtualname__


def _get_network(project_id, network_name, service):
    """
    Fetch network selfLink from network name.
    """
    return service.networks().get(project=project_id, network=network_name).execute()


def _get_instance(project_id, instance_zone, name, service):
    """
    Get instance details
    """
    return (
        service.instances()
        .get(project=project_id, zone=instance_zone, instance=name)
        .execute()
    )


def route_create(
    credential_file=None,
    project_id=None,
    name=None,
    dest_range=None,
    next_hop_instance=None,
    instance_zone=None,
    tags=None,
    network=None,
    priority=None,
):
    """
    Create a route to send traffic destined to the Internet through your
    gateway instance

    credential_file : string
        File location of application default credential. For more information,
        refer: https://developers.google.com/identity/protocols/application-default-credentials
    project_id : string
        Project ID where instance and network resides.
    name : string
        name of the route to create
    next_hop_instance : string
        the name of an instance that should handle traffic matching this route.
    instance_zone : string
        zone where instance("next_hop_instance") resides
    network : string
        Specifies the network to which the route will be applied.
    dest_range : string
        The destination range of outgoing packets that the route will apply to.
    tags : list
        (optional) Identifies the set of instances that this route will apply to.
    priority : int
        (optional) Specifies the priority of this route relative to other routes.
        default=1000

    CLI Example:

    .. code-block:: bash

        salt 'salt-master.novalocal' gcp.route_create
            credential_file=/root/secret_key.json
            project_id=cp100-170315
            name=derby-db-route1
            next_hop_instance=instance-1
            instance_zone=us-central1-a
            network=default
            dest_range=0.0.0.0/0
            tags=['no-ip']
            priority=700

    In above example, the instances which are having tag "no-ip" will route the
    packet to instance "instance-1"(if packet is intended to other network)
    """

    credentials = (
        oauth2client.service_account.ServiceAccountCredentials.from_json_keyfile_name(
            credential_file
        )
    )
    service = googleapiclient.discovery.build("compute", "v1", credentials=credentials)
    routes = service.routes()

    routes_config = {
        "name": str(name),
        "network": _get_network(project_id, str(network), service=service)["selfLink"],
        "destRange": str(dest_range),
        "nextHopInstance": _get_instance(
            project_id, instance_zone, next_hop_instance, service=service
        )["selfLink"],
        "tags": tags,
        "priority": priority,
    }
    route_create_request = routes.insert(project=project_id, body=routes_config)
    return route_create_request.execute()
