import docker
import os
import subprocess
import salt.config
import salt.loader
import json
__opts__ = salt.config.minion_config('/etc/salt/minion')
__grains__ = salt.loader.grains(__opts__)
client = docker.from_env()
server_name = __grains__['id']

def swarm_tokens():
    client = docker.APIClient(base_url='unix://var/run/docker.sock')
    service = client.inspect_swarm()
    return service['JoinTokens']


def swarm_init(advertise_addr=str,
               listen_addr=int,
               force_new_cluster=bool):
    d = {}               
    try:
        '''
        Initalize Docker on Minion as a Swarm Manager
        salt <Target> advertise_addr='ens4' listen_addr='0.0.0.0:5000' force_new_cluster=False
        '''
        client.swarm.init(advertise_addr,
                          listen_addr,
                          force_new_cluster)
        output =  'Docker swarm has been Initalized on '+   server_name  + ' and the worker/manager Join token is below'
        d.update({'Comment': output,
                  'Tokens': swarm_tokens()})
        return d
    except:
        d.update({'Error': 'Please make sure your passing advertise_addr, listen_addr and force_new_cluster correctly.'})
        return d


def joinswarm(remote_addr=int,
              listen_addr=int,
              token=str):
    d = {}          
    try:
        '''
        Join a Swarm Worker to the cluster
        *NOTE this can be use for worker or manager join
        salt <target> remote_addr='10.1.0.1' listen_addr='0.0.0.0' token='token'
        '''
        client.swarm.join(remote_addrs=[remote_addr],
                          listen_addr=listen_addr,
                          join_token=token )
        output =  server_name + ' has joined the Swarm'
        d.update({'Comment': output,
                  'Manager_Addr': remote_addr })
        return d
    except:
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
    d = {}               
    try:
        replica_mode = docker.types.ServiceMode('replicated', replicas=replicas)
        ports = docker.types.EndpointSpec(ports={ target_port: published_port })
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
    except:
        d.update({'Error': 'Please make sure your passing arguments correctly [image, name, command, hostname, replicas, target_port and published_port]'})
        return d


def swarm_service_info(service_name=str):
    d = {}
    try:
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
        replicas =  dump['Spec']['Mode']['Replicated']['Replicas']
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
    except:
        d.update({'Error': 'service_name arg is missing?'})
        return d


def remove_service(service=str):
    d = {}
    try:
        client = docker.APIClient(base_url='unix://var/run/docker.sock')
        service = client.remove_service(service)
        d.update({'Service Deleted':service,
                  'Minion ID': server_name })
        return d
    except:
        d.update({'Error': 'service arg is missing?'})
        return d


def node_ls(server=str):
    d = {}
    try:
        client = docker.APIClient(base_url='unix://var/run/docker.sock')
        service = client.nodes(filters=({'name': server }))
        getdata = json.dumps(service)
        dump = json.loads(getdata)
        for items in dump:
            docker_version = items['Description']['Engine']['EngineVersion']
            platform = items['Description']['Platform']
            hostnames = items['Description']['Hostname']
            ids = items['ID']
            role = items['Spec']['Role']
            availability = items['Spec']['Availability'] 
            status =  items['Status']
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
    except:
        d.update({'Error': 'The server arg is missing or you not targeting a Manager node?'})
        return d


def remove_node(node_id=str, force=bool):
    client = docker.APIClient(base_url='unix://var/run/docker.sock')
    d = {}
    try:
        if force == 'True':
            service = client.remove_node(node_id,force=True) 
            return service
        else:
            service = client.remove_node(node_id,force=False)
            return service
    except:
        d.update({'Error': 'Is the node_id and/or force=True/False missing?'})


def update_node(availability=str,
                node_name=str,
                role=str,
                node_id=str,
                version=int):
    client = docker.APIClient(base_url='unix://var/run/docker.sock')
    d = {}
    try:
        node_spec = {'Availability': availability,
                     'Name': node_name,
                     'Role': role}
        client.update_node(node_id=node_id, 
                           version=version,
                           node_spec=node_spec)
        d.update({'Node Information': node_spec,})
        return d
    except:
        d.update({'Error': 'Make sure all args are passed [availability, node_name, role, node_id, version]'})
        return d