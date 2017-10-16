# -*- coding: utf-8 -*-
"""
Docker Swarm Module using Docker's Python SDK
=============================================

:codeauthor: Tyler Jones <jonestyler806@gmail.com>

.. versionadded:: 2017.7.2

The Docker Swarm Module is used to manage and create Docker Swarms.

Dependencies
============

- Docker installed on the host
- Docker python sdk >= 2.5.1

Docker Python SDK
=================
pip install -U docker

More information: https://docker-py.readthedocs.io/en/stable/
"""
from __future__ import absolute_import
import docker
import salt.config
import salt.loader
import json
__opts__ = salt.config.minion_config('/etc/salt/minion')
__grains__ = salt.loader.grains(__opts__)
client = docker.from_env()
server_name = __grains__['id']


def swarm_tokens():
    '''
    Get the Docker Swarm Manager or Worker join tokens
    '''
    client = docker.APIClient(base_url='unix://var/run/docker.sock')
    service = client.inspect_swarm()
    return service['JoinTokens']


def swarm_init(advertise_addr=str,
               listen_addr=int,
               force_new_cluster=bool):
    '''
    Initalize Docker on Minion as a Swarm Manager
    '''
    try:
        d = {}
        client.swarm.init(advertise_addr,
                          listen_addr,
                          force_new_cluster)
        output = 'Docker swarm has been Initalized on '+ server_name + ' and the worker/manager Join token is below'
        d.update({'Comment': output,
                  'Tokens': swarm_tokens()})
        return d
    except TypeError:
        d = {}
        d.update({'Error': 'Please make sure your passing advertise_addr, listen_addr and force_new_cluster correctly.'})
        return d


def joinswarm(remote_addr=int,
              listen_addr=int,
              token=str):
    '''
    Join a Swarm Worker to the cluster
    '''
    try:
        d = {}
        client.swarm.join(remote_addrs=[remote_addr],
                          listen_addr=listen_addr,
                          join_token=token)
        output = server_name + ' has joined the Swarm'
        d.update({'Comment': output, 'Manager_Addr': remote_addr})
        return d
    except TypeError:
        d = {}
        d.update({'Error': 'Please make sure this minion is not part of a swarm and your passing remote_addr, listen_addr and token correctly.'})
        return d


def leave_swarm(force=bool):
    '''
    Will force the minion to leave the swarm
    '''
    d = {}
    client.swarm.leave(force=force)
    output = server_name + ' has left the swarm'
    d.update({'Comment': output})
    return d


def service_create(image=str,
                   name=str,
                   command=str,
                   hostname=str,
                   replicas=int,
                   target_port=int,
                   published_port=int):
    '''
    Create Docker Swarm Service Create
    '''
    try:
        d = {}
        replica_mode = docker.types.ServiceMode('replicated', replicas=replicas)
        ports = docker.types.EndpointSpec(ports={target_port: published_port})
        client.services.create(name=name,
                               image=image,
                               command=command,
                               mode=replica_mode,
                               endpoint_spec=ports)
        echoback = server_name + ' has a Docker Swarm Service running named ' + name
        d.update({'Info': echoback,
                  'Minion': server_name,
                  'Name': name,
                  'Image': image,
                  'Command': command,
                  'Hostname': hostname,
                  'Replicas': replicas,
                  'Target_Port': target_port,
                  'Published_Port': published_port})
        return d
    except TypeError:
        d = {}
        d.update({'Error': 'Please make sure your passing arguments correctly [image, name, command, hostname, replicas, target_port and published_port]'})
        return d


def swarm_service_info(service_name=str):
    '''
    Swarm Service Information
    '''
    try:
        d = {}
        client = docker.APIClient(base_url='unix://var/run/docker.sock')
        service = client.inspect_service(service=service_name)
        getdata = json.dumps(service)
        dump = json.loads(getdata)
        version = dump['Version']['Index']
        name = dump['Spec']['Name']
        network_mode = dump['Spec']['EndpointSpec']['Mode']
        ports = dump['Spec']['EndpointSpec']['Ports']
        swarm_id = dump['ID']
        create_date = dump['CreatedAt']
        update_date = dump['UpdatedAt']
        labels = dump['Spec']['Labels']
        replicas = dump['Spec']['Mode']['Replicated']['Replicas']
        network = dump['Endpoint']['VirtualIPs']
        image = dump['Spec']['TaskTemplate']['ContainerSpec']['Image']
        for items in ports:
            published_port = items['PublishedPort']
            target_port = items['TargetPort']
            published_mode = items['PublishMode']
            protocol = items['Protocol']
            d.update({'Service Name': name,
                      'Replicas': replicas,
                      'Service ID': swarm_id,
                      'Network': network,
                      'Network Mode': network_mode,
                      'Creation Date': create_date,
                      'Update Date': update_date,
                      'Published Port': published_port,
                      'Target Port': target_port,
                      'Published Mode': published_mode,
                      'Protocol': protocol,
                      'Docker Image': image,
                      'Minion Id': server_name,
                      'Version': version})
        return d
    except TypeError:
        d = {}
        d.update({'Error': 'service_name arg is missing?'})
        return d


def remove_service(service=str):
    '''
    Remove Swarm Service
    '''
    try:
        d = {}
        client = docker.APIClient(base_url='unix://var/run/docker.sock')
        service = client.remove_service(service)
        d.update({'Service Deleted': service,
                  'Minion ID': server_name})
        return d
    except TypeError:
        d = {}
        d.update({'Error': 'service arg is missing?'})
        return d


def node_ls(server=str):
    '''
    Displays Information about Swarm Nodes with passing in the server
    '''
    try:
        d = {}
        client = docker.APIClient(base_url='unix://var/run/docker.sock')
        service = client.nodes(filters=({'name': server}))
        getdata = json.dumps(service)
        dump = json.loads(getdata)
        for items in dump:
            docker_version = items['Description']['Engine']['EngineVersion']
            platform = items['Description']['Platform']
            hostnames = items['Description']['Hostname']
            ids = items['ID']
            role = items['Spec']['Role']
            availability = items['Spec']['Availability']
            status = items['Status']
            Version = items['Version']['Index']
            d.update({'Docker Version': docker_version,
                      'Platform': platform,
                      'Hostname': hostnames,
                      'ID': ids,
                      'Roles': role,
                      'Availability': availability,
                      'Status': status,
                      'Version': Version})
            return d
    except TypeError:
        d = {}
        d.update({'Error': 'The server arg is missing or you not targeting a Manager node?'})
        return d


def remove_node(node_id=str, force=bool):
    '''
    Remove a node from a swarm
    '''
    client = docker.APIClient(base_url='unix://var/run/docker.sock')
    try:
        if force == 'True':
            service = client.remove_node(node_id, force=True)
            return service
        else:
            service = client.remove_node(node_id, force=False)
            return service
    except TypeError:
        d = {}
        d.update({'Error': 'Is the node_id and/or force=True/False missing?'})


def update_node(availability=str,
                node_name=str,
                role=str,
                node_id=str,
                version=int):
    '''
    Updates docker swarm nodes
    '''
    client = docker.APIClient(base_url='unix://var/run/docker.sock')
    try:
        d = {}
        node_spec = {'Availability': availability,
                     'Name': node_name,
                     'Role': role}
        client.update_node(node_id=node_id,
                           version=version,
                           node_spec=node_spec)
        d.update({'Node Information': node_spec})
        return d
    except TypeError:
        d = {}
        d.update({'Error': 'Make sure all args are passed [availability, node_name, role, node_id, version]'})
        return d
