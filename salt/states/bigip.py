# -*- coding: utf-8 -*-
'''
A state module designed to enforce load-balancing configurations for F5 Big-IP entities.
    :maturity:      develop
    :platform:      f5_bigip_11.6
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.json

# Import 3rd-party libs
from salt.ext import six


#set up virtual function
def __virtual__():
    '''
    Only load if the bigip exec module is available in __salt__
    '''
    return 'bigip' if 'bigip.list_transaction' in __salt__ else False


def _load_result(response, ret):
    '''
    format the results of listing functions
    '''

    #were we able to connect?
    if response['code'] is None:
        ret['comment'] = response['content']
    #forbidden?
    elif response['code'] == 401:
        ret['comment'] = '401 Forbidden: Authentication required!'
    #Not found?
    elif response['code'] == 404:
        ret['comment'] = response['content']['message']
    #200?
    elif response['code'] == 200:
        ret['result'] = True
        ret['comment'] = 'Listing Current Configuration Only.  ' \
                         'Not action or changes occurred during the execution of this state.'
        ret['changes'] = response['content']
    #something bad
    else:
        ret['comment'] = response['content']['message']

    return ret


def _strip_key(dictionary, keyword):
    '''
    look for a certain key within a dictionary and nullify ti's contents, check within nested
    dictionaries and lists as well.  Certain attributes such as "generation" will change even
    when there were no changes made to the entity.
    '''

    for key, value in six.iteritems(dictionary):
        if key == keyword:
            dictionary[key] = None
        elif isinstance(value, dict):
            _strip_key(value, keyword)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _strip_key(item, keyword)

    return dictionary


def _check_for_changes(entity_type, ret, existing, modified):
    '''
    take an existing entity and a modified entity and check for changes.
    '''

    ret['result'] = True

    #were there any changes? generation always changes, remove it.

    if isinstance(existing, dict) and isinstance(modified, dict):
        if 'generation' in modified['content'].keys():
            del modified['content']['generation']

        if 'generation' in existing['content'].keys():
            del existing['content']['generation']

        if modified['content'] == existing['content']:
            ret['comment'] = '{entity_type} is currently enforced to the desired state.  No changes made.'.format(entity_type=entity_type)
        else:
            ret['comment'] = '{entity_type} was enforced to the desired state.  Note: Only parameters specified ' \
                             'were enforced. See changes for details.'.format(entity_type=entity_type)
            ret['changes']['old'] = existing['content']
            ret['changes']['new'] = modified['content']

    else:
        if modified == existing:
            ret['comment'] = '{entity_type} is currently enforced to the desired state.  No changes made.'.format(entity_type=entity_type)
        else:
            ret['comment'] = '{entity_type} was enforced to the desired state.  Note: Only parameters specified ' \
                             'were enforced. See changes for details.'.format(entity_type=entity_type)
            ret['changes']['old'] = existing
            ret['changes']['new'] = modified

    return ret


def _test_output(ret, action, params):
    '''
    For testing just output what the state will attempt to do without actually doing it.
    '''

    if action == 'list':
        ret['comment'] += 'The list action will just list an entity and will make no changes.\n'
    elif action == 'create' or action == 'add':
        ret['comment'] += 'The create action will attempt to create an entity if it does not already exist.\n'
    elif action == 'delete':
        ret['comment'] += 'The delete action will attempt to delete an existing entity if it exists.\n'
    elif action == 'manage':
        ret['comment'] += 'The manage action will create a new entity if it does not exist.  If it does exist, it will be enforced' \
                          'to the desired state.\n'
    elif action == 'modify':
        ret['comment'] += 'The modify action will attempt to modify an existing entity only if it exists.\n'

    ret['comment'] += 'An iControl REST Request will be made using the parameters:\n'
    ret['comment'] += salt.utils.json.dumps(params, indent=4)

    ret['changes'] = {}
    # Return ``None`` when running with ``test=true``.
    ret['result'] = None

    return ret


def list_node(hostname, username, password, name):
    '''
    A function to connect to a bigip device and list a specific node.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the node to list.
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'list', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name
        }
        )

    response = __salt__['bigip.list_node'](hostname, username, password, name)
    return _load_result(response, ret)


def create_node(hostname, username, password, name, address):
    '''
    Create a new node if it does not already exist.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the node to create
    address
        The address of the node
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'create', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name,
            'address': address
        }
        )

    #is this node currently configured?
    existing = __salt__['bigip.list_node'](hostname, username, password, name)

    # if it exists
    if existing['code'] == 200:

        ret['result'] = True
        ret['comment'] = 'A node by this name currently exists.  No change made.'

    # if it doesn't exist
    elif existing['code'] == 404:
        response = __salt__['bigip.create_node'](hostname, username, password, name, address)

        ret['result'] = True
        ret['changes']['old'] = {}
        ret['changes']['new'] = response['content']
        ret['comment'] = 'Node was successfully created.'

    # else something else was returned
    else:
        ret = _load_result(existing, ret)

    return ret


def manage_node(hostname, username, password, name, address,
                connection_limit=None,
                description=None,
                dynamic_ratio=None,
                logging=None,
                monitor=None,
                rate_limit=None,
                ratio=None,
                session=None,
                node_state=None):
    '''
    Manages a node of a given bigip device.  If the node does not exist it will be created, otherwise,
    only the properties which are different than the existing will be updated.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the node to manage.
    address
        The address of the node
    connection_limit
        [integer]
    description
        [string]
    dynam
        c_ratio:        [integer]
    logging
        [enabled | disabled]
    monitor
        [[name] | none | default]
    rate_limit
        [integer]
    ratio
        [integer]
    session
        [user-enabled | user-disabled]
    node_state (state)
        [user-down | user-up ]
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'manage', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name,
            'address': address,
            'connection_limit': connection_limit,
            'description': description,
            'dynamic_ratio': dynamic_ratio,
            'logging': logging,
            'monitor': monitor,
            'rate_limit': rate_limit,
            'ratio': ratio,
            'session': session,
            'state:': node_state
        }
        )

    #is this node currently configured?
    existing = __salt__['bigip.list_node'](hostname, username, password, name)

    # if it exists by name
    if existing['code'] == 200:

        # ensure the address is the same, we don't want to modify a different node than what
        # we think we are managing
        if existing['content']['address'] != address:
            ret['result'] = False
            ret['comment'] = 'A node with this name exists but the address does not match.'

        modified = __salt__['bigip.modify_node'](hostname=hostname,
                                                 username=username,
                                                 password=password,
                                                 name=name,
                                                 connection_limit=connection_limit,
                                                 description=description,
                                                 dynamic_ratio=dynamic_ratio,
                                                 logging=logging,
                                                 monitor=monitor,
                                                 rate_limit=rate_limit,
                                                 ratio=ratio,
                                                 session=session,
                                                 state=node_state)

        #was the modification successful?
        if modified['code'] == 200:
            ret = _check_for_changes('Node', ret, existing, modified)
        else:
            ret = _load_result(modified, ret)

    # not found, attempt to create it
    elif existing['code'] == 404:

        new = __salt__['bigip.create_node'](hostname, username, password, name, address)

        # were we able to create it?
        if new['code'] == 200:
            # try modification

            modified = __salt__['bigip.modify_node'](hostname=hostname,
                                                     username=username,
                                                     password=password,
                                                     name=name,
                                                     connection_limit=connection_limit,
                                                     description=description,
                                                     dynamic_ratio=dynamic_ratio,
                                                     logging=logging,
                                                     monitor=monitor,
                                                     rate_limit=rate_limit,
                                                     ratio=ratio,
                                                     session=session,
                                                     state=node_state)
            #was the modification successful?
            if modified['code'] == 200:

                ret['result'] = True
                ret['comment'] = 'Node was created and enforced to the desired state.  Note: Only parameters specified ' \
                                 'were enforced.  See changes for details.'
                ret['changes']['old'] = {}
                ret['changes']['new'] = modified['content']

            # roll it back
            else:

                deleted = __salt__['bigip.delete_node'](hostname, username, password, name)
                # did we get rid of it?
                if deleted['code'] == 200:
                    ret['comment'] = 'Node was successfully created but an error occurred during modification. ' \
                                     'The creation of the node has been rolled back. Message is as follows:\n' \
                                     '{message}'.format(message=modified['content']['message'])
                # something bad happened
                else:
                    ret['comment'] = 'Node was successfully created but an error occurred during modification. ' \
                                     'The creation of the node was not able to be rolled back. Message is as follows:' \
                                     '\n {message}\n{message_two}'.format(message=modified['content']['message'],
                                                                          message_two=deleted['content']['message'])

        # unable to create it
        else:
            ret = _load_result(new, ret)
    # an error occurred
    else:
        ret = _load_result(existing, ret)

    return ret


def modify_node(hostname, username, password, name,
                connection_limit=None,
                description=None,
                dynamic_ratio=None,
                logging=None,
                monitor=None,
                rate_limit=None,
                ratio=None,
                session=None,
                node_state=None):
    '''
    Modify an existing node. Only a node which already exists will be modified and
    only the parameters specified will be enforced.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the node to modify
    connection_limit
        [integer]
    description
        [string]
    dynamic_ratio
        [integer]
    logging
        [enabled | disabled]
    monitor
        [[name] | none | default]
    rate_limit
        [integer]
    ratio
        [integer]
    session
        [user-enabled | user-disabled]
    node_state (state)
        [user-down | user-up ]
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'modify', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name,
            'connection_limit': connection_limit,
            'description': description,
            'dynamic_ratio': dynamic_ratio,
            'logging': logging,
            'monitor': monitor,
            'rate_limit': rate_limit,
            'ratio': ratio,
            'session': session,
            'state:': node_state
        }
        )

    #is this node currently configured?
    existing = __salt__['bigip.list_node'](hostname, username, password, name)

    # if it exists by name
    if existing['code'] == 200:

        modified = __salt__['bigip.modify_node'](hostname=hostname,
                                                 username=username,
                                                 password=password,
                                                 name=name,
                                                 connection_limit=connection_limit,
                                                 description=description,
                                                 dynamic_ratio=dynamic_ratio,
                                                 logging=logging,
                                                 monitor=monitor,
                                                 rate_limit=rate_limit,
                                                 ratio=ratio,
                                                 session=session,
                                                 state=node_state)

        #was the modification successful?
        if modified['code'] == 200:
            ret = _check_for_changes('Node', ret, existing, modified)
        else:
            ret = _load_result(modified, ret)

    # not found, attempt to create it
    elif existing['code'] == 404:
        ret['comment'] = 'A node with this name was not found.'
    # an error occurred
    else:
        ret = _load_result(existing, ret)

    return ret


def delete_node(hostname, username, password, name):
    '''
    Delete an existing node.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the node which will be deleted.
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'delete', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name,
        }
        )

    #is this node currently configured?
    existing = __salt__['bigip.list_node'](hostname, username, password, name)
    # if it exists by name
    if existing['code'] == 200:

        deleted = __salt__['bigip.delete_node'](hostname, username, password, name)
        # did we get rid of it?
        if deleted['code'] == 200:
            ret['result'] = True
            ret['comment'] = 'Node was successfully deleted.'
            ret['changes']['old'] = existing['content']
            ret['changes']['new'] = {}

        # something bad happened
        else:
            ret = _load_result(existing, ret)

    # not found
    elif existing['code'] == 404:
        ret['result'] = True
        ret['comment'] = 'This node already does not exist. No changes made.'
        ret['changes']['old'] = {}
        ret['changes']['new'] = {}

    else:
        ret = _load_result(existing, ret)

    return ret


def list_pool(hostname, username, password, name):
    '''
    A function to connect to a bigip device and list a specific pool.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the pool to list.
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'list', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name,
        }
        )

    response = __salt__['bigip.list_pool'](hostname, username, password, name)
    return _load_result(response, ret)


def create_pool(hostname, username, password, name, members=None,
                allow_nat=None,
                allow_snat=None,
                description=None,
                gateway_failsafe_device=None,
                ignore_persisted_weight=None,
                ip_tos_to_client=None,
                ip_tos_to_server=None,
                link_qos_to_client=None,
                link_qos_to_server=None,
                load_balancing_mode=None,
                min_active_members=None,
                min_up_members=None,
                min_up_members_action=None,
                min_up_members_checking=None,
                monitor=None,
                profiles=None,
                queue_depth_limit=None,
                queue_on_connection_limit=None,
                queue_time_limit=None,
                reselect_tries=None,
                service_down_action=None,
                slow_ramp_time=None):
    '''
    Create a new node if it does not already exist.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the pool to create
    members
        List of members to be added to the pool
    allow_nat
        [yes | no]
    allow_snat
        [yes | no]
    description
        [string]
    gateway_failsafe_device
        [string]
    ignore_persisted_weight
        [enabled | disabled]
    ip_tos_to_client
        [pass-through | [integer]]
    ip_tos_to_server
        [pass-through | [integer]]
    link_qos_to_client
        [pass-through | [integer]]
    link_qos_to_server
        [pass-through | [integer]]
    load_balancing_mode
        [dynamic-ratio-member | dynamic-ratio-node |
        fastest-app-response | fastest-node |
        least-connections-members |
        least-connections-node |
        least-sessions |
        observed-member | observed-node |
        predictive-member | predictive-node |
        ratio-least-connections-member |
        ratio-least-connections-node |
        ratio-member | ratio-node | ratio-session |
        round-robin | weighted-least-connections-member |
        weighted-least-connections-node]
    min_active_members
        [integer]
    min_up_members
        [integer]
    min_up_members_action
        [failover | reboot | restart-all]
    min_up_members_checking
        [enabled | disabled]
    monitor
        [name]
    profiles
        [none | profile_name]
    queue_depth_limit
        [integer]
    queue_on_connection_limit
        [enabled | disabled]
    queue_time_limit
        [integer]
    reselect_tries
        [integer]
    service_down_action
        [drop | none | reselect | reset]
    slow_ramp_time
        [integer]
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'create', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name,
            'members': members,
            'allow_nat': allow_nat,
            'allow_snat': allow_snat,
            'description': description,
            'gateway_failsafe_device': gateway_failsafe_device,
            'ignore_persisted_weight': ignore_persisted_weight,
            'ip_tos_client:': ip_tos_to_client,
            'ip_tos_server': ip_tos_to_server,
            'link_qos_to_client': link_qos_to_client,
            'link_qos_to_server': link_qos_to_server,
            'load_balancing_mode': load_balancing_mode,
            'min_active_members': min_active_members,
            'min_up_members': min_up_members,
            'min_up_members_checking': min_up_members_checking,
            'monitor': monitor,
            'profiles': profiles,
            'queue_depth_limit': queue_depth_limit,
            'queue_on_connection_limit': queue_on_connection_limit,
            'queue_time_limit': queue_time_limit,
            'reselect_tries': reselect_tries,
            'service_down_action': service_down_action,
            'slow_ramp_time': slow_ramp_time
            }
        )

    #is this pool currently configured?
    existing = __salt__['bigip.list_pool'](hostname, username, password, name)

    # if it exists
    if existing['code'] == 200:

        ret['result'] = True
        ret['comment'] = 'A pool by this name currently exists.  No change made.'

    # if it doesn't exist
    elif existing['code'] == 404:

        response = __salt__['bigip.create_pool'](hostname=hostname,
                                                 username=username,
                                                 password=password,
                                                 name=name,
                                                 members=members,
                                                 allow_nat=allow_nat,
                                                 allow_snat=allow_snat,
                                                 description=description,
                                                 gateway_failsafe_device=gateway_failsafe_device,
                                                 ignore_persisted_weight=ignore_persisted_weight,
                                                 ip_tos_to_client=ip_tos_to_client,
                                                 ip_tos_to_server=ip_tos_to_server,
                                                 link_qos_to_client=link_qos_to_client,
                                                 link_qos_to_server=link_qos_to_server,
                                                 load_balancing_mode=load_balancing_mode,
                                                 min_active_members=min_active_members,
                                                 min_up_members=min_up_members,
                                                 min_up_members_action=min_up_members_action,
                                                 min_up_members_checking=min_up_members_checking,
                                                 monitor=monitor,
                                                 profiles=profiles,
                                                 queue_depth_limit=queue_depth_limit,
                                                 queue_on_connection_limit=queue_on_connection_limit,
                                                 queue_time_limit=queue_time_limit,
                                                 reselect_tries=reselect_tries,
                                                 service_down_action=service_down_action,
                                                 slow_ramp_time=slow_ramp_time)
        if response['code'] == 200:
            ret['result'] = True
            ret['changes']['old'] = {}
            ret['changes']['new'] = response['content']
            ret['comment'] = 'Pool was successfully created.'
        else:
            ret = _load_result(existing, ret)

    # else something else was returned
    else:
        ret = _load_result(existing, ret)

    return ret


def manage_pool(hostname, username, password, name,
                allow_nat=None,
                allow_snat=None,
                description=None,
                gateway_failsafe_device=None,
                ignore_persisted_weight=None,
                ip_tos_to_client=None,
                ip_tos_to_server=None,
                link_qos_to_client=None,
                link_qos_to_server=None,
                load_balancing_mode=None,
                min_active_members=None,
                min_up_members=None,
                min_up_members_action=None,
                min_up_members_checking=None,
                monitor=None,
                profiles=None,
                queue_depth_limit=None,
                queue_on_connection_limit=None,
                queue_time_limit=None,
                reselect_tries=None,
                service_down_action=None,
                slow_ramp_time=None):
    '''
    Create a new pool if it does not already exist. Pool members are managed separately. Only the
    parameters specified are enforced.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the pool to create
    allow_nat
        [yes | no]
    allow_snat
        [yes | no]
    description
        [string]
    gateway_failsafe_device
        [string]
    ignore_persisted_weight
        [enabled | disabled]
    ip_tos_to_client
        [pass-through | [integer]]
    ip_tos_to_server
        [pass-through | [integer]]
    link_qos_to_client
        [pass-through | [integer]]
    link_qos_to_server
        [pass-through | [integer]]
    load_balancing_mode
        [dynamic-ratio-member | dynamic-ratio-node |
        fastest-app-response | fastest-node |
        least-connections-members |
        least-connections-node |
        least-sessions |
        observed-member | observed-node |
        predictive-member | predictive-node |
        ratio-least-connections-member |
        ratio-least-connections-node |
        ratio-member | ratio-node | ratio-session |
        round-robin | weighted-least-connections-member |
        weighted-least-connections-node]
    min_active_members
        [integer]
    min_up_members
        [integer]
    min_up_members_action
        [failover | reboot | restart-all]
    min_up_members_checking
        [enabled | disabled]
    monitor
        [name]
    profiles
        [none | profile_name]
    queue_depth_limit
        [integer]
    queue_on_connection_limit
        [enabled | disabled]
    queue_time_limit
        [integer]
    reselect_tries
        [integer]
    service_down_action
        [drop | none | reselect | reset]
    slow_ramp_time
        [integer]

    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'manage', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name,
            'allow_nat': allow_nat,
            'allow_snat': allow_snat,
            'description': description,
            'gateway_failsafe_device': gateway_failsafe_device,
            'ignore_persisted_weight': ignore_persisted_weight,
            'ip_tos_client:': ip_tos_to_client,
            'ip_tos_server': ip_tos_to_server,
            'link_qos_to_client': link_qos_to_client,
            'link_qos_to_server': link_qos_to_server,
            'load_balancing_mode': load_balancing_mode,
            'min_active_members': min_active_members,
            'min_up_members': min_up_members,
            'min_up_members_checking': min_up_members_checking,
            'monitor': monitor,
            'profiles': profiles,
            'queue_depth_limit': queue_depth_limit,
            'queue_on_connection_limit': queue_on_connection_limit,
            'queue_time_limit': queue_time_limit,
            'reselect_tries': reselect_tries,
            'service_down_action': service_down_action,
            'slow_ramp_time': slow_ramp_time
        }
        )

    #is this pool currently configured?
    existing = __salt__['bigip.list_pool'](hostname, username, password, name)

    # if it exists
    if existing['code'] == 200:

        modified = __salt__['bigip.modify_pool'](hostname=hostname,
                                                 username=username,
                                                 password=password,
                                                 name=name,
                                                 allow_nat=allow_nat,
                                                 allow_snat=allow_snat,
                                                 description=description,
                                                 gateway_failsafe_device=gateway_failsafe_device,
                                                 ignore_persisted_weight=ignore_persisted_weight,
                                                 ip_tos_to_client=ip_tos_to_client,
                                                 ip_tos_to_server=ip_tos_to_server,
                                                 link_qos_to_client=link_qos_to_client,
                                                 link_qos_to_server=link_qos_to_server,
                                                 load_balancing_mode=load_balancing_mode,
                                                 min_active_members=min_active_members,
                                                 min_up_members=min_up_members,
                                                 min_up_members_action=min_up_members_action,
                                                 min_up_members_checking=min_up_members_checking,
                                                 monitor=monitor,
                                                 profiles=profiles,
                                                 queue_depth_limit=queue_depth_limit,
                                                 queue_on_connection_limit=queue_on_connection_limit,
                                                 queue_time_limit=queue_time_limit,
                                                 reselect_tries=reselect_tries,
                                                 service_down_action=service_down_action,
                                                 slow_ramp_time=slow_ramp_time)

        #was the modification successful?
        if modified['code'] == 200:

            #remove member listings and self-links
            del existing['content']['membersReference']
            del modified['content']['membersReference']
            del existing['content']['selfLink']
            del modified['content']['selfLink']

            ret = _check_for_changes('Pool', ret, existing, modified)
        else:
            ret = _load_result(modified, ret)

    # if it doesn't exist
    elif existing['code'] == 404:

        new = __salt__['bigip.create_pool'](hostname=hostname,
                                            username=username,
                                            password=password,
                                            name=name,
                                            allow_nat=allow_nat,
                                            allow_snat=allow_snat,
                                            description=description,
                                            gateway_failsafe_device=gateway_failsafe_device,
                                            ignore_persisted_weight=ignore_persisted_weight,
                                            ip_tos_to_client=ip_tos_to_client,
                                            ip_tos_to_server=ip_tos_to_server,
                                            link_qos_to_client=link_qos_to_client,
                                            link_qos_to_server=link_qos_to_server,
                                            load_balancing_mode=load_balancing_mode,
                                            min_active_members=min_active_members,
                                            min_up_members=min_up_members,
                                            min_up_members_action=min_up_members_action,
                                            min_up_members_checking=min_up_members_checking,
                                            monitor=monitor,
                                            profiles=profiles,
                                            queue_depth_limit=queue_depth_limit,
                                            queue_on_connection_limit=queue_on_connection_limit,
                                            queue_time_limit=queue_time_limit,
                                            reselect_tries=reselect_tries,
                                            service_down_action=service_down_action,
                                            slow_ramp_time=slow_ramp_time)

        # were we able to create it?
        if new['code'] == 200:
            ret['result'] = True
            ret['comment'] = 'Pool was created and enforced to the desired state.  Note: Only parameters specified ' \
                             'were enforced.  See changes for details.'
            ret['changes']['old'] = {}
            ret['changes']['new'] = new['content']

         # unable to create it
        else:
            ret = _load_result(new, ret)

    # else something else was returned
    else:
        ret = _load_result(existing, ret)

    return ret


def modify_pool(hostname, username, password, name,
                allow_nat=None,
                allow_snat=None,
                description=None,
                gateway_failsafe_device=None,
                ignore_persisted_weight=None,
                ip_tos_to_client=None,
                ip_tos_to_server=None,
                link_qos_to_client=None,
                link_qos_to_server=None,
                load_balancing_mode=None,
                min_active_members=None,
                min_up_members=None,
                min_up_members_action=None,
                min_up_members_checking=None,
                monitor=None,
                profiles=None,
                queue_depth_limit=None,
                queue_on_connection_limit=None,
                queue_time_limit=None,
                reselect_tries=None,
                service_down_action=None,
                slow_ramp_time=None):
    '''
    Modify an existing pool. Pool members are managed separately. Only the
    parameters specified are enforced.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the pool to create
    allow_nat
        [yes | no]
    allow_snat
        [yes | no]
    description
        [string]
    gateway_failsafe_device
        [string]
    ignore_persisted_weight
        [enabled | disabled]
    ip_tos_to_client
        [pass-through | [integer]]
    ip_tos_to_server
        [pass-through | [integer]]
    link_qos_to_client
        [pass-through | [integer]]
    link_qos_to_server
        [pass-through | [integer]]
    load_balancing_mode
        [dynamic-ratio-member | dynamic-ratio-node |
        fastest-app-response | fastest-node |
        least-connections-members |
        least-connections-node |
        least-sessions |
        observed-member | observed-node |
        predictive-member | predictive-node |
        ratio-least-connections-member |
        ratio-least-connections-node |
        ratio-member | ratio-node | ratio-session |
        round-robin | weighted-least-connections-member |
        weighted-least-connections-node]
    min_active_members
        [integer]
    min_up_members
        [integer]
    min_up_members_action
        [failover | reboot | restart-all]
    min_up_members_checking
        [enabled | disabled]
    monitor
        [name]
    profiles
        [none | profile_name]
    queue_depth_limit
        [integer]
    queue_on_connection_limit
        [enabled | disabled]
    queue_time_limit
        [integer]
    reselect_tries
        [integer]
    service_down_action
        [drop | none | reselect | reset]
    slow_ramp_time
        [integer]

    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'modify', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name,
            'allow_nat': allow_nat,
            'allow_snat': allow_snat,
            'description': description,
            'gateway_failsafe_device': gateway_failsafe_device,
            'ignore_persisted_weight': ignore_persisted_weight,
            'ip_tos_client:': ip_tos_to_client,
            'ip_tos_server': ip_tos_to_server,
            'link_qos_to_client': link_qos_to_client,
            'link_qos_to_server': link_qos_to_server,
            'load_balancing_mode': load_balancing_mode,
            'min_active_members': min_active_members,
            'min_up_members': min_up_members,
            'min_up_members_checking': min_up_members_checking,
            'monitor': monitor,
            'profiles': profiles,
            'queue_depth_limit': queue_depth_limit,
            'queue_on_connection_limit': queue_on_connection_limit,
            'queue_time_limit': queue_time_limit,
            'reselect_tries': reselect_tries,
            'service_down_action': service_down_action,
            'slow_ramp_time': slow_ramp_time
        }
        )

    #is this pool currently configured?
    existing = __salt__['bigip.list_pool'](hostname, username, password, name)

    # if it exists
    if existing['code'] == 200:

        modified = __salt__['bigip.modify_pool'](hostname=hostname,
                                                 username=username,
                                                 password=password,
                                                 name=name,
                                                 allow_nat=allow_nat,
                                                 allow_snat=allow_snat,
                                                 description=description,
                                                 gateway_failsafe_device=gateway_failsafe_device,
                                                 ignore_persisted_weight=ignore_persisted_weight,
                                                 ip_tos_to_client=ip_tos_to_client,
                                                 ip_tos_to_server=ip_tos_to_server,
                                                 link_qos_to_client=link_qos_to_client,
                                                 link_qos_to_server=link_qos_to_server,
                                                 load_balancing_mode=load_balancing_mode,
                                                 min_active_members=min_active_members,
                                                 min_up_members=min_up_members,
                                                 min_up_members_action=min_up_members_action,
                                                 min_up_members_checking=min_up_members_checking,
                                                 monitor=monitor,
                                                 profiles=profiles,
                                                 queue_depth_limit=queue_depth_limit,
                                                 queue_on_connection_limit=queue_on_connection_limit,
                                                 queue_time_limit=queue_time_limit,
                                                 reselect_tries=reselect_tries,
                                                 service_down_action=service_down_action,
                                                 slow_ramp_time=slow_ramp_time)

        #was the modification successful?
        if modified['code'] == 200:

            #remove member listings and self-links
            del existing['content']['membersReference']
            del modified['content']['membersReference']
            del existing['content']['selfLink']
            del modified['content']['selfLink']

            ret = _check_for_changes('Pool', ret, existing, modified)
        else:
            ret = _load_result(modified, ret)

    # if it doesn't exist
    elif existing['code'] == 404:
        ret['comment'] = 'A pool with this name was not found.'
    # else something else was returned
    else:
        ret = _load_result(existing, ret)

    return ret


def delete_pool(hostname, username, password, name):
    '''
    Delete an existing pool.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the pool which will be deleted
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'delete', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name,
        }
        )

    #is this pool currently configured?
    existing = __salt__['bigip.list_pool'](hostname, username, password, name)
    # if it exists by name
    if existing['code'] == 200:

        deleted = __salt__['bigip.delete_pool'](hostname, username, password, name)
        # did we get rid of it?
        if deleted['code'] == 200:
            ret['result'] = True
            ret['comment'] = 'Pool was successfully deleted.'
            ret['changes']['old'] = existing['content']
            ret['changes']['new'] = {}

        # something bad happened
        else:
            ret = _load_result(deleted, ret)

    # not found
    elif existing['code'] == 404:
        ret['result'] = True
        ret['comment'] = 'This pool already does not exist. No changes made.'
        ret['changes']['old'] = {}
        ret['changes']['new'] = {}

    else:
        ret = _load_result(existing, ret)

    return ret


def manage_pool_members(hostname, username, password, name, members):
    '''
    Manage the members of an existing pool.  This function replaces all current pool members.
    Only the parameters specified are enforced.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the pool to modify
    members
        list of pool members to manage.

    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'manage', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name,
            'members': members
        }
        )

    #is this pool currently configured?
    existing = __salt__['bigip.list_pool'](hostname, username, password, name)

    # if it exists
    if existing['code'] == 200:

        #what are the current members?
        current_members = existing['content']['membersReference']['items']

        modified = __salt__['bigip.replace_pool_members'](hostname, username, password, name, members)

        #was the modification successful?
        if modified['code'] == 200:

            #re-list the pool with new membership
            new_listing = __salt__['bigip.list_pool'](hostname, username, password, name)

            #just in case something happened...
            if new_listing['code'] != 200:
                ret = _load_result(new_listing, ret)
                ret['comment'] = 'modification of the pool was successful but an error occurred upon retrieving new' \
                                 ' listing.'
                return ret

            new_members = new_listing['content']['membersReference']['items']

            #remove generation keys and create new lists indexed by integers
            for current_member in current_members:
                del current_member['generation']

            for new_member in new_members:
                del new_member['generation']

            #anything changed?
            ret = _check_for_changes('Pool Membership', ret, current_members, new_members)

        else:
            ret = _load_result(modified, ret)

    #pool does not exists
    elif existing['code'] == 404:
        ret['comment'] = 'A pool with this name was not found.'

    else:
        ret = _load_result(existing, ret)

    return ret


def add_pool_member(hostname, username, password, name, member):
    '''
    A function to connect to a bigip device and add a new member to an existing pool.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the pool to modify
    member
        The member to add to the pool
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'add', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name,
            'members': member
        }
        )

    #is this pool member currently configured?
    existing_pool = __salt__['bigip.list_pool'](hostname, username, password, name)

    if existing_pool['code'] == 200:

        # for some reason iControl REST doesn't support listing a single pool member.
        # the response from GET for listing a member will return 200 even if it doesn't exists.
        # because of this we have to do some rather "unnecessary" searching within a pool.

        #what are the current members?
        current_members = existing_pool['content']['membersReference']['items']

        #loop through them
        exists = False
        for current_member in current_members:
            if current_member['name'] == member['name']:
                exists = True
                break

        if exists:
            ret['result'] = True
            ret['comment'] = 'Member: {name} already exists within this pool.  No changes made.'.format(name=member['name'])
            ret['changes']['old'] = {}
            ret['changes']['new'] = {}
        else:
            new_member = __salt__['bigip.add_pool_member'](hostname, username, password, name, member)

            if new_member['code'] == 200:
                ret['result'] = True
                ret['comment'] = 'Member: {name} has been successfully added to the pool.'.format(name=member['name'])
                ret['changes']['old'] = {}

                #look up the member again...
                pool_listing = __salt__['bigip.list_pool'](hostname, username, password, name)

                if pool_listing['code'] != 200:
                    ret = _load_result(new_member, ret)
                    return ret

                members = pool_listing['content']['membersReference']['items']
                #loop through them
                for current_member in members:
                    if current_member['name'] == member['name']:
                        added_member = current_member
                        break

                ret['changes']['new'] = added_member

            # member wasn't added
            else:
                ret = _load_result(new_member, ret)

    #pool does not exists
    elif existing_pool['code'] == 404:
        ret['comment'] = 'A pool with this name was not found.'
    else:
        ret = _load_result(existing_pool, ret)

    return ret


def modify_pool_member(hostname, username, password, name, member,
                       connection_limit=None,
                       description=None,
                       dynamic_ratio=None,
                       inherit_profile=None,
                       logging=None,
                       monitor=None,
                       priority_group=None,
                       profiles=None,
                       rate_limit=None,
                       ratio=None,
                       session=None,
                       member_state=None):
    '''
    A function to connect to a bigip device and modify a member of an existing pool.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the pool to modify
    member
        The member modify
    connection_limit
        [integer]
    description
        [string]
    dynamic_ratio
        [integer]
    inherit_profile
        [enabled | disabled]
    logging
        [enabled | disabled]
    monitor
        [name]
    priority_group
        [integer]
    profiles
        [none | profile_name]
    rate_limit
        [integer]
    ratio
        [integer]
    session
        [user-enabled | user-disabled]
    member_state (state)
        [ user-up | user-down ]

    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'modify', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name,
            'members': member
        }
        )

    #is this pool member currently configured?
    existing_pool = __salt__['bigip.list_pool'](hostname, username, password, name)

    if existing_pool['code'] == 200:

        # for some reason iControl REST doesn't support listing a single pool member.
        # the response from GET for listing a member will return 200 even if it doesn't exists.
        # because of this we have to do some rather "unnecessary" searching within a pool.

        #what are the current members?
        current_members = existing_pool['content']['membersReference']['items']

        #loop through them
        exists = False
        for current_member in current_members:
            if current_member['name'] == member:
                exists = True
                existing_member = current_member
                break

        if exists:

            #modify the pool member
            modified = __salt__['bigip.modify_pool_member'](hostname=hostname,
                                                            username=username,
                                                            password=password,
                                                            name=name,
                                                            member=member,
                                                            connection_limit=connection_limit,
                                                            description=description,
                                                            dynamic_ratio=dynamic_ratio,
                                                            inherit_profile=inherit_profile,
                                                            logging=logging,
                                                            monitor=monitor,
                                                            priority_group=priority_group,
                                                            profiles=profiles,
                                                            rate_limit=rate_limit,
                                                            ratio=ratio,
                                                            session=session,
                                                            state=member_state)

            #re-list the pool
            new_pool = __salt__['bigip.list_pool'](hostname, username, password, name)

            if modified['code'] == 200 and modified['code'] == 200:

                #what are the new members?
                new_members = new_pool['content']['membersReference']['items']

                #loop through them
                for new_member in new_members:
                    if new_member['name'] == member:
                        modified_member = new_member
                        break

                #check for changes
                old = {'content': existing_member}
                new = {'content': modified_member}
                ret = _check_for_changes('Pool Member: {member}'.format(member=member), ret, old, new)

            else:
                ret = _load_result(modified, ret)
        else:
            ret['comment'] = 'Member: {name} does not exists within this pool.  No changes made.'.format(name=member['name'])

    #pool does not exists
    elif existing_pool['code'] == 404:
        ret['comment'] = 'A pool with this name was not found.'
    else:
        ret = _load_result(existing_pool, ret)

    return ret


def delete_pool_member(hostname, username, password, name, member):
    '''
    Delete an existing pool member.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the pool to be modified
    member
        The name of the member to delete from the pool
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'delete', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name,
            'members': member
        }
        )

    #is this pool currently configured?
    existing = __salt__['bigip.list_pool'](hostname, username, password, name)

    # if it exists by name
    if existing['code'] == 200:

       #what are the current members?
        current_members = existing['content']['membersReference']['items']

        #loop through them
        exists = False
        for current_member in current_members:
            if current_member['name'] == member:
                exists = True
                existing_member = current_member
                break

        if exists:
            deleted = __salt__['bigip.delete_pool_member'](hostname, username, password, name, member)
            # did we get rid of it?
            if deleted['code'] == 200:
                ret['result'] = True
                ret['comment'] = 'Pool Member: {member} was successfully deleted.'.format(member=member)
                ret['changes']['old'] = existing_member
                ret['changes']['new'] = {}

        # something bad happened
        else:
            ret['result'] = True
            ret['comment'] = 'This pool member already does not exist. No changes made.'
            ret['changes']['old'] = {}
            ret['changes']['new'] = {}

    else:
        ret = _load_result(existing, ret)

    return ret


def list_virtual(hostname, username, password, name):
    '''
    A function to list a specific virtual.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the virtual to list
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'list', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name
        }
        )

    response = __salt__['bigip.list_virtual'](hostname, username, password, name)
    return _load_result(response, ret)


def create_virtual(hostname, username, password, name, destination,
                   pool=None,
                   address_status=None,
                   auto_lasthop=None,
                   bwc_policy=None,
                   cmp_enabled=None,
                   connection_limit=None,
                   dhcp_relay=None,
                   description=None,
                   fallback_persistence=None,
                   flow_eviction_policy=None,
                   gtm_score=None,
                   ip_forward=None,
                   ip_protocol=None,
                   internal=None,
                   twelve_forward=None,
                   last_hop_pool=None,
                   mask=None,
                   mirror=None,
                   nat64=None,
                   persist=None,
                   profiles=None,
                   policies=None,
                   rate_class=None,
                   rate_limit=None,
                   rate_limit_mode=None,
                   rate_limit_dst=None,
                   rate_limit_src=None,
                   rules=None,
                   related_rules=None,
                   reject=None,
                   source=None,
                   source_address_translation=None,
                   source_port=None,
                   virtual_state=None,
                   traffic_classes=None,
                   translate_address=None,
                   translate_port=None,
                   vlans=None):
    '''
    A function to connect to a bigip device and create a virtual server if it does not already exists.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the virtual to create
    destination
        [ [virtual_address_name:port] | [ipv4:port] | [ipv6.port] ]
    pool
        [ [pool_name] | none]
    address_status
        [yes | no]
    auto_lasthop
        [default | enabled | disabled ]
    bwc_policy
        [none] | string]
    cmp_enabled
        [yes | no]
    dhcp_relay
        [yes | no}
    connection_limit
        [integer]
    description
        [string]
    state
        [disabled | enabled]
    fallback_persistence
        [none | [profile name] ]
    flow_eviction_policy
        [none | [eviction policy name] ]
    gtm_score
        [integer]
    ip_forward
        [yes | no]
    ip_protocol
        [any | protocol]
    internal
        [yes | no]
    twelve_forward(12-forward)
        [yes | no]
    last_hop-pool
        [ [pool_name] | none]
    mask
        { [ipv4] | [ipv6] }
    mirror
        { [disabled | enabled | none] }
    nat64
        [enabled | disabled]
    persist
        [list]
    profiles
        [none | default | list ]
    policies
        [none | default | list ]
    rate_class
        [name]
    rate_limit
        [integer]
    rate_limit-mode
        [destination | object | object-destination |
        object-source | object-source-destination |
        source | source-destination]
    rate_limit-dst
        [integer]
    rate_limit-src
        [integer]
    rules
        [none | list ]
    related_rules
        [none | list ]
    reject
        [yes | no]
    source
        { [ipv4[/prefixlen]] | [ipv6[/prefixlen]] }
    source_address_translation
        [none | snat:pool_name | lsn | automap | dictionary ]
    source_port
        [change | preserve | preserve-strict]
    state
        [enabled | disabled]
    traffic_classes
        [none | default | list ]
    translate_address
        [enabled | disabled]
    translate_port
        [enabled | disabled]
    vlans
        [none | default | dictionary]

        vlan_ids
            [ list]
        enabled
            [ true | false ]
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'create', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name,
            'destination': destination,
            'pool': pool,
            'address_status': address_status,
            'auto_lasthop': auto_lasthop,
            'bwc_policy': bwc_policy,
            'cmp_enabled': cmp_enabled,
            'connection_limit': connection_limit,
            'dhcp_relay': dhcp_relay,
            'description': description,
            'fallback_persistence': fallback_persistence,
            'flow_eviction_policy': flow_eviction_policy,
            'gtm_score': gtm_score,
            'ip_forward': ip_forward,
            'ip_protocol': ip_protocol,
            'internal': internal,
            'twelve_forward': twelve_forward,
            'last_hop_pool': last_hop_pool,
            'mask': mask,
            'mirror': mirror,
            'nat64': nat64,
            'persist': persist,
            'profiles': profiles,
            'policies': policies,
            'rate_class': rate_class,
            'rate_limit': rate_limit,
            'rate_limit_mode': rate_limit_mode,
            'rate_limit_dst': rate_limit_dst,
            'rate_limit_src': rate_limit_src,
            'rules': rules,
            'related_rules': related_rules,
            'reject': reject,
            'source': source,
            'source_address_translation': source_address_translation,
            'source_port': source_port,
            'virtual_state': virtual_state,
            'traffic_classes': traffic_classes,
            'translate_address': translate_address,
            'translate_port': translate_port,
            'vlans': vlans
        }
        )

    existing = __salt__['bigip.list_virtual'](hostname, username, password, name)

    # does this virtual exist?
    if existing['code'] == 200:

        ret['result'] = True
        ret['comment'] = 'A virtual by this name currently exists.  No change made.'

    elif existing['code'] == 404:

        #create it
        virtual = __salt__['bigip.create_virtual'](hostname=hostname,
                                                   username=username,
                                                   password=password,
                                                   name=name,
                                                   destination=destination,
                                                   description=description,
                                                   pool=pool,
                                                   address_status=address_status,
                                                   auto_lasthop=auto_lasthop,
                                                   bwc_policy=bwc_policy,
                                                   cmp_enabled=cmp_enabled,
                                                   connection_limit=connection_limit,
                                                   dhcp_relay=dhcp_relay,
                                                   fallback_persistence=fallback_persistence,
                                                   flow_eviction_policy=flow_eviction_policy,
                                                   gtm_score=gtm_score,
                                                   ip_forward=ip_forward,
                                                   ip_protocol=ip_protocol,
                                                   internal=internal,
                                                   twelve_forward=twelve_forward,
                                                   last_hop_pool=last_hop_pool,
                                                   mask=mask,
                                                   mirror=mirror,
                                                   nat64=nat64,
                                                   persist=persist,
                                                   profiles=profiles,
                                                   policies=policies,
                                                   rate_class=rate_class,
                                                   rate_limit=rate_limit,
                                                   rate_limit_mode=rate_limit_mode,
                                                   rate_limit_dst=rate_limit_dst,
                                                   rate_limit_src=rate_limit_src,
                                                   rules=rules,
                                                   related_rules=related_rules,
                                                   reject=reject,
                                                   source=source,
                                                   source_address_translation=source_address_translation,
                                                   source_port=source_port,
                                                   state=virtual_state,
                                                   traffic_classes=traffic_classes,
                                                   translate_address=translate_address,
                                                   translate_port=translate_port,
                                                   vlans=vlans)
        if virtual['code'] == 200:
            ret['result'] = True
            ret['changes']['old'] = {}
            ret['changes']['new'] = virtual['content']
            ret['comment'] = 'Virtual was successfully created.'
        else:
            ret = _load_result(existing, ret)

    # else something else was returned
    else:
        ret = _load_result(existing, ret)

    return ret


def manage_virtual(hostname, username, password, name, destination,
                   pool=None,
                   address_status=None,
                   auto_lasthop=None,
                   bwc_policy=None,
                   cmp_enabled=None,
                   connection_limit=None,
                   dhcp_relay=None,
                   description=None,
                   fallback_persistence=None,
                   flow_eviction_policy=None,
                   gtm_score=None,
                   ip_forward=None,
                   ip_protocol=None,
                   internal=None,
                   twelve_forward=None,
                   last_hop_pool=None,
                   mask=None,
                   mirror=None,
                   nat64=None,
                   persist=None,
                   profiles=None,
                   policies=None,
                   rate_class=None,
                   rate_limit=None,
                   rate_limit_mode=None,
                   rate_limit_dst=None,
                   rate_limit_src=None,
                   rules=None,
                   related_rules=None,
                   reject=None,
                   source=None,
                   source_address_translation=None,
                   source_port=None,
                   virtual_state=None,
                   traffic_classes=None,
                   translate_address=None,
                   translate_port=None,
                   vlans=None):
    '''
    Manage a virtual server.  If a virtual does not exists it will be created, otherwise only the
    parameters specified will be enforced.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the virtual to create
    destination
        [ [virtual_address_name:port] | [ipv4:port] | [ipv6.port] ]
    pool
        [ [pool_name] | none]
    address_status
        [yes | no]
    auto_lasthop
        [default | enabled | disabled ]
    bwc_policy
        [none] | string]
    cmp_enabled
        [yes | no]
    dhcp_relay
        [yes | no}
    connection_limit
        [integer]
    description
        [string]
    state
        [disabled | enabled]
    fallback_persistence
        [none | [profile name] ]
    flow_eviction_policy
        [none | [eviction policy name] ]
    gtm_score
        [integer]
    ip_forward
        [yes | no]
    ip_protocol
        [any | protocol]
    internal
        [yes | no]
    twelve_forward(12-forward)
        [yes | no]
    last_hop-pool
        [ [pool_name] | none]
    mask
        { [ipv4] | [ipv6] }
    mirror
        { [disabled | enabled | none] }
    nat64
        [enabled | disabled]
    persist
        [list]
    profiles
        [none | default | list ]
    policies
        [none | default | list ]
    rate_class
        [name]
    rate_limit
        [integer]
    rate_limit-mode
        [destination | object | object-destination |
        object-source | object-source-destination |
        source | source-destination]
    rate_limit-dst
        [integer]
    rate_limit-src
        [integer]
    rules
        [none | list ]
    related_rules
        [none | list ]
    reject
        [yes | no]
    source
        { [ipv4[/prefixlen]] | [ipv6[/prefixlen]] }
    source_address_translation
        [none | snat:pool_name | lsn | automap | dictionary ]
    source_port
        [change | preserve | preserve-strict]
    state
        [enabled | disabled]
    traffic_classes
        [none | default | list ]
    translate_address
        [enabled | disabled]
    translate_port
        [enabled | disabled]
    vlans
        [none | default | dictionary]

        vlan_ids
            [ list]
        enabled
            [ true | false ]
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'manage', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name,
            'destination': destination,
            'pool': pool,
            'address_status': address_status,
            'auto_lasthop': auto_lasthop,
            'bwc_policy': bwc_policy,
            'cmp_enabled': cmp_enabled,
            'connection_limit': connection_limit,
            'dhcp_relay': dhcp_relay,
            'description': description,
            'fallback_persistence': fallback_persistence,
            'flow_eviction_policy': flow_eviction_policy,
            'gtm_score': gtm_score,
            'ip_forward': ip_forward,
            'ip_protocol': ip_protocol,
            'internal': internal,
            'twelve_forward': twelve_forward,
            'last_hop_pool': last_hop_pool,
            'mask': mask,
            'mirror': mirror,
            'nat64': nat64,
            'persist': persist,
            'profiles': profiles,
            'policies': policies,
            'rate_class': rate_class,
            'rate_limit': rate_limit,
            'rate_limit_mode': rate_limit_mode,
            'rate_limit_dst': rate_limit_dst,
            'rate_limit_src': rate_limit_src,
            'rules': rules,
            'related_rules': related_rules,
            'reject': reject,
            'source': source,
            'source_address_translation': source_address_translation,
            'source_port': source_port,
            'virtual_state': virtual_state,
            'traffic_classes': traffic_classes,
            'translate_address': translate_address,
            'translate_port': translate_port,
            'vlans': vlans
        }
        )

    existing = __salt__['bigip.list_virtual'](hostname, username, password, name)

    # does this virtual exist?
    if existing['code'] == 200:

        # modify
        modified = __salt__['bigip.modify_virtual'](hostname=hostname,
                                                    username=username,
                                                    password=password,
                                                    name=name,
                                                    destination=destination,
                                                    description=description,
                                                    pool=pool,
                                                    address_status=address_status,
                                                    auto_lasthop=auto_lasthop,
                                                    bwc_policy=bwc_policy,
                                                    cmp_enabled=cmp_enabled,
                                                    connection_limit=connection_limit,
                                                    dhcp_relay=dhcp_relay,
                                                    fallback_persistence=fallback_persistence,
                                                    flow_eviction_policy=flow_eviction_policy,
                                                    gtm_score=gtm_score,
                                                    ip_forward=ip_forward,
                                                    ip_protocol=ip_protocol,
                                                    internal=internal,
                                                    twelve_forward=twelve_forward,
                                                    last_hop_pool=last_hop_pool,
                                                    mask=mask,
                                                    mirror=mirror,
                                                    nat64=nat64,
                                                    persist=persist,
                                                    profiles=profiles,
                                                    policies=policies,
                                                    rate_class=rate_class,
                                                    rate_limit=rate_limit,
                                                    rate_limit_mode=rate_limit_mode,
                                                    rate_limit_dst=rate_limit_dst,
                                                    rate_limit_src=rate_limit_src,
                                                    rules=rules,
                                                    related_rules=related_rules,
                                                    reject=reject,
                                                    source=source,
                                                    source_address_translation=source_address_translation,
                                                    source_port=source_port,
                                                    state=virtual_state,
                                                    traffic_classes=traffic_classes,
                                                    translate_address=translate_address,
                                                    translate_port=translate_port,
                                                    vlans=vlans)

        #was the modification successful?
        if modified['code'] == 200:

            #relist it to compare
            relisting = __salt__['bigip.list_virtual'](hostname, username, password, name)

            if relisting['code'] == 200:

                relisting = _strip_key(relisting, 'generation')
                existing = _strip_key(existing, 'generation')

                ret = _check_for_changes('Virtual', ret, existing, relisting)
            else:
                ret = _load_result(relisting, ret)

        else:
            ret = _load_result(modified, ret)

    elif existing['code'] == 404:

        #create it
        virtual = __salt__['bigip.create_virtual'](hostname=hostname,
                                                   username=username,
                                                   password=password,
                                                   name=name,
                                                   destination=destination,
                                                   description=description,
                                                   pool=pool,
                                                   address_status=address_status,
                                                   auto_lasthop=auto_lasthop,
                                                   bwc_policy=bwc_policy,
                                                   cmp_enabled=cmp_enabled,
                                                   connection_limit=connection_limit,
                                                   dhcp_relay=dhcp_relay,
                                                   fallback_persistence=fallback_persistence,
                                                   flow_eviction_policy=flow_eviction_policy,
                                                   gtm_score=gtm_score,
                                                   ip_forward=ip_forward,
                                                   ip_protocol=ip_protocol,
                                                   internal=internal,
                                                   twelve_forward=twelve_forward,
                                                   last_hop_pool=last_hop_pool,
                                                   mask=mask,
                                                   mirror=mirror,
                                                   nat64=nat64,
                                                   persist=persist,
                                                   profiles=profiles,
                                                   policies=policies,
                                                   rate_class=rate_class,
                                                   rate_limit=rate_limit,
                                                   rate_limit_mode=rate_limit_mode,
                                                   rate_limit_dst=rate_limit_dst,
                                                   rate_limit_src=rate_limit_src,
                                                   rules=rules,
                                                   related_rules=related_rules,
                                                   reject=reject,
                                                   source=source,
                                                   source_address_translation=source_address_translation,
                                                   source_port=source_port,
                                                   state=virtual_state,
                                                   traffic_classes=traffic_classes,
                                                   translate_address=translate_address,
                                                   translate_port=translate_port,
                                                   vlans=vlans)

        #were we able to create it?
        if virtual['code'] == 200:
            ret['result'] = True
            ret['changes']['old'] = {}
            ret['changes']['new'] = virtual['content']
            ret['comment'] = 'Virtual was successfully created and enforced to the desired state.'

        else:
            ret = _load_result(virtual, ret)

    else:
        ret = _load_result(existing, ret)

    return ret


def modify_virtual(hostname, username, password, name, destination,
                   pool=None,
                   address_status=None,
                   auto_lasthop=None,
                   bwc_policy=None,
                   cmp_enabled=None,
                   connection_limit=None,
                   dhcp_relay=None,
                   description=None,
                   fallback_persistence=None,
                   flow_eviction_policy=None,
                   gtm_score=None,
                   ip_forward=None,
                   ip_protocol=None,
                   internal=None,
                   twelve_forward=None,
                   last_hop_pool=None,
                   mask=None,
                   mirror=None,
                   nat64=None,
                   persist=None,
                   profiles=None,
                   policies=None,
                   rate_class=None,
                   rate_limit=None,
                   rate_limit_mode=None,
                   rate_limit_dst=None,
                   rate_limit_src=None,
                   rules=None,
                   related_rules=None,
                   reject=None,
                   source=None,
                   source_address_translation=None,
                   source_port=None,
                   virtual_state=None,
                   traffic_classes=None,
                   translate_address=None,
                   translate_port=None,
                   vlans=None):
    '''
    Modify an virtual server.  modify an existing virtual.  Only parameters specified will be enforced.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the virtual to create
    destination
        [ [virtual_address_name:port] | [ipv4:port] | [ipv6.port] ]
    pool
        [ [pool_name] | none]
    address_status
        [yes | no]
    auto_lasthop
        [default | enabled | disabled ]
    bwc_policy
        [none] | string]
    cmp_enabled
        [yes | no]
    dhcp_relay
        [yes | no}
    connection_limit
        [integer]
    description
        [string]
    state
        [disabled | enabled]
    fallback_persistence
        [none | [profile name] ]
    flow_eviction_policy
        [none | [eviction policy name] ]
    gtm_score
        [integer]
    ip_forward
        [yes | no]
    ip_protocol
        [any | protocol]
    internal
        [yes | no]
    twelve_forward(12-forward)
        [yes | no]
    last_hop-pool
        [ [pool_name] | none]
    mask
        { [ipv4] | [ipv6] }
    mirror
        { [disabled | enabled | none] }
    nat64
        [enabled | disabled]
    persist
        [list]
    profiles
        [none | default | list ]
    policies
        [none | default | list ]
    rate_class
        [name]
    rate_limit
        [integer]
    rate_limit-mode
        [destination | object | object-destination |
        object-source | object-source-destination |
        source | source-destination]
    rate_limit_dst
        [integer]
    rate_limit_src
        [integer]
    rules
        [none | list ]
    related_rules
        [none | list ]
    reject
        [yes | no]
    source
        { [ipv4[/prefixlen]] | [ipv6[/prefixlen]] }
    source_address_translation
        [none | snat:pool_name | lsn | automap | dictionary ]
    source_port
        [change | preserve | preserve-strict]
    state
        [enabled | disabled]
    traffic_classes
        [none | default | list ]
    translate_address
        [enabled | disabled]
    translate_port
        [enabled | disabled]
    vlans
        [none | default | dictionary ]

        vlan_ids
            [ list]
        enabled
            [ true | false ]

    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'modify', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name,
            'destination': destination,
            'pool': pool,
            'address_status': address_status,
            'auto_lasthop': auto_lasthop,
            'bwc_policy': bwc_policy,
            'cmp_enabled': cmp_enabled,
            'connection_limit': connection_limit,
            'dhcp_relay': dhcp_relay,
            'description': description,
            'fallback_persistence': fallback_persistence,
            'flow_eviction_policy': flow_eviction_policy,
            'gtm_score': gtm_score,
            'ip_forward': ip_forward,
            'ip_protocol': ip_protocol,
            'internal': internal,
            'twelve_forward': twelve_forward,
            'last_hop_pool': last_hop_pool,
            'mask': mask,
            'mirror': mirror,
            'nat64': nat64,
            'persist': persist,
            'profiles': profiles,
            'policies': policies,
            'rate_class': rate_class,
            'rate_limit': rate_limit,
            'rate_limit_mode': rate_limit_mode,
            'rate_limit_dst': rate_limit_dst,
            'rate_limit_src': rate_limit_src,
            'rules': rules,
            'related_rules': related_rules,
            'reject': reject,
            'source': source,
            'source_address_translation': source_address_translation,
            'source_port': source_port,
            'virtual_state': virtual_state,
            'traffic_classes': traffic_classes,
            'translate_address': translate_address,
            'translate_port': translate_port,
            'vlans': vlans
        }
        )

    existing = __salt__['bigip.list_virtual'](hostname, username, password, name)

    # does this virtual exist?
    if existing['code'] == 200:

        # modify
        modified = __salt__['bigip.modify_virtual'](hostname=hostname,
                                                    username=username,
                                                    password=password,
                                                    name=name,
                                                    destination=destination,
                                                    description=description,
                                                    pool=pool,
                                                    address_status=address_status,
                                                    auto_lasthop=auto_lasthop,
                                                    bwc_policy=bwc_policy,
                                                    cmp_enabled=cmp_enabled,
                                                    connection_limit=connection_limit,
                                                    dhcp_relay=dhcp_relay,
                                                    fallback_persistence=fallback_persistence,
                                                    flow_eviction_policy=flow_eviction_policy,
                                                    gtm_score=gtm_score,
                                                    ip_forward=ip_forward,
                                                    ip_protocol=ip_protocol,
                                                    internal=internal,
                                                    twelve_forward=twelve_forward,
                                                    last_hop_pool=last_hop_pool,
                                                    mask=mask,
                                                    mirror=mirror,
                                                    nat64=nat64,
                                                    persist=persist,
                                                    profiles=profiles,
                                                    policies=policies,
                                                    rate_class=rate_class,
                                                    rate_limit=rate_limit,
                                                    rate_limit_mode=rate_limit_mode,
                                                    rate_limit_dst=rate_limit_dst,
                                                    rate_limit_src=rate_limit_src,
                                                    rules=rules,
                                                    related_rules=related_rules,
                                                    reject=reject,
                                                    source=source,
                                                    source_address_translation=source_address_translation,
                                                    source_port=source_port,
                                                    state=virtual_state,
                                                    traffic_classes=traffic_classes,
                                                    translate_address=translate_address,
                                                    translate_port=translate_port,
                                                    vlans=vlans)

        #was the modification successful?
        if modified['code'] == 200:

            #relist it to compare
            relisting = __salt__['bigip.list_virtual'](hostname, username, password, name)

            if relisting['code'] == 200:

                relisting = _strip_key(relisting, 'generation')
                existing = _strip_key(existing, 'generation')

                ret = _check_for_changes('Virtual', ret, existing, relisting)
            else:
                ret = _load_result(relisting, ret)

        else:
            ret = _load_result(modified, ret)

    elif existing['code'] == 404:
        ret['comment'] = 'A Virtual with this name was not found.'
        # else something else was returned
    else:
        ret = _load_result(existing, ret)

    return ret


def delete_virtual(hostname, username, password, name):
    '''
    Delete an existing virtual.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the virtual which will be deleted
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'delete', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': name
        }
        )

    #is this virtual currently configured?
    existing = __salt__['bigip.list_virtual'](hostname, username, password, name)
    # if it exists by name
    if existing['code'] == 200:

        deleted = __salt__['bigip.delete_virtual'](hostname, username, password, name)
        # did we get rid of it?
        if deleted['code'] == 200:
            ret['result'] = True
            ret['comment'] = 'Virtual was successfully deleted.'
            ret['changes']['old'] = existing['content']
            ret['changes']['new'] = {}
        # something bad happened
        else:
            ret = _load_result(deleted, ret)

    # not found
    elif existing['code'] == 404:
        ret['result'] = True
        ret['comment'] = 'This virtual already does not exist. No changes made.'
        ret['changes']['old'] = {}
        ret['changes']['new'] = {}
    else:
        ret = _load_result(existing, ret)

    return ret


def list_monitor(hostname, username, password, monitor_type, name):
    '''
    A function to list an exsiting monitor.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    monitor_type
        The type of monitor to list
    name
        The name of the monitor to list
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'list', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'monitor_type': monitor_type,
            'name': name
        }
        )

    response = __salt__['bigip.list_monitor'](hostname, username, password, monitor_type, name)
    return _load_result(response, ret)


def create_monitor(hostname, username, password, monitor_type, name, **kwargs):
    '''
    A function to connect to a bigip device and create a monitor.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    monitor_type
        The type of monitor to create
    name
        The name of the monitor to create
    kwargs
        [ arg=val ] ...

        Consult F5 BIGIP user guide for specific options for each monitor type.
        Typically, tmsh arg names are used.
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:

        params = {
            'hostname': hostname,
            'username': username,
            'password': password,
            'monitor_type': monitor_type,
            'name': name
        }

        for key, value in six.iteritems(kwargs):
            params[key] = value

        return _test_output(ret, 'create', params)

    #is this monitor currently configured?
    existing = __salt__['bigip.list_monitor'](hostname, username, password, monitor_type, name)

    # if it exists
    if existing['code'] == 200:

        ret['result'] = True
        ret['comment'] = 'A monitor by this name currently exists.  No change made.'

    # if it doesn't exist
    elif existing['code'] == 404:

        response = __salt__['bigip.create_monitor'](hostname, username, password, monitor_type, name, **kwargs)
        if response['code'] == 200:
            ret['result'] = True
            ret['changes']['old'] = {}
            ret['changes']['new'] = response['content']
            ret['comment'] = 'Monitor was successfully created.'
        else:
            ret = _load_result(response, ret)

    # else something else was returned
    else:
        ret = _load_result(existing, ret)

    return ret


def manage_monitor(hostname, username, password, monitor_type, name, **kwargs):
    '''
    Create a new monitor if a monitor of this type and name does not already exists.  If it does exists, only
    the parameters specified will be enforced.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    monitor_type
        The type of monitor to create
    name
        The name of the monitor to create
    kwargs
        [ arg=val ] ...

        Consult F5 BIGIP user guide for specific options for each monitor type.
        Typically, tmsh arg names are used.
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:

        params = {
            'hostname': hostname,
            'username': username,
            'password': password,
            'monitor_type': monitor_type,
            'name': name
        }

        for key, value in six.iteritems(kwargs):
            params[key] = value

        return _test_output(ret, 'manage', params)

    #is this monitor currently configured?
    existing = __salt__['bigip.list_monitor'](hostname, username, password, monitor_type, name)

    # if it exists
    if existing['code'] == 200:

        #modify the monitor
        modified = __salt__['bigip.modify_monitor'](hostname, username, password, monitor_type, name, **kwargs)

        #was the modification successful?
        if modified['code'] == 200:
            del existing['content']['selfLink']
            del modified['content']['selfLink']
            ret = _check_for_changes('Monitor', ret, existing, modified)
        else:
            ret = _load_result(modified, ret)

    # if it doesn't exist
    elif existing['code'] == 404:

        response = __salt__['bigip.create_monitor'](hostname, username, password, monitor_type, name, **kwargs)
        if response['code'] == 200:
            ret['result'] = True
            ret['changes']['old'] = {}
            ret['changes']['new'] = response['content']
            ret['comment'] = 'Monitor was successfully created.'
        else:
            ret = _load_result(response, ret)

    # else something else was returned
    else:
        ret = _load_result(existing, ret)

    return ret


def modify_monitor(hostname, username, password, monitor_type, name, **kwargs):
    '''
    Modify an existing monitor.  If it does exists, only
    the parameters specified will be enforced.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    monitor_type
        The type of monitor to create
    name
        The name of the monitor to create
    kwargs
        [ arg=val ] ...

        Consult F5 BIGIP user guide for specific options for each monitor type.
        Typically, tmsh arg names are used.
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:

        params = {
            'hostname': hostname,
            'username': username,
            'password': password,
            'monitor_type': monitor_type,
            'name': name
        }

        for key, value in six.iteritems(kwargs):
            params[key] = value

        return _test_output(ret, 'modify', params)

    #is this monitor currently configured?
    existing = __salt__['bigip.list_monitor'](hostname, username, password, monitor_type, name)

    # if it exists
    if existing['code'] == 200:

        #modify the monitor
        modified = __salt__['bigip.modify_monitor'](hostname, username, password, monitor_type, name, **kwargs)

        #was the modification successful?
        if modified['code'] == 200:
            del existing['content']['selfLink']
            del modified['content']['selfLink']
            ret = _check_for_changes('Monitor', ret, existing, modified)
        else:
            ret = _load_result(modified, ret)

    # if it doesn't exist
    elif existing['code'] == 404:
        ret['comment'] = 'A Monitor with this name was not found.'
    # else something else was returned
    else:
        ret = _load_result(existing, ret)

    return ret


def delete_monitor(hostname, username, password, monitor_type, name):
    '''
    Modify an existing monitor.  If it does exists, only
    the parameters specified will be enforced.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    monitor_type
        The type of monitor to create
    name
        The name of the monitor to create
    kwargs
        [ arg=val ] ...

        Consult F5 BIGIP user guide for specific options for each monitor type.
        Typically, tmsh arg names are used.
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'delete', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'monitor_type': monitor_type,
            'name': name
        })

    #is this profile currently configured?
    existing = __salt__['bigip.list_monitor'](hostname, username, password, monitor_type, name)
    # if it exists by name
    if existing['code'] == 200:

        deleted = __salt__['bigip.delete_monitor'](hostname, username, password, monitor_type, name)
        # did we get rid of it?
        if deleted['code'] == 200:
            ret['result'] = True
            ret['comment'] = 'Monitor was successfully deleted.'
            ret['changes']['old'] = existing['content']
            ret['changes']['new'] = {}
        # something bad happened
        else:
            ret = _load_result(deleted, ret)

    # not found
    elif existing['code'] == 404:
        ret['result'] = True
        ret['comment'] = 'This Monitor already does not exist. No changes made.'
        ret['changes']['old'] = {}
        ret['changes']['new'] = {}
    else:
        ret = _load_result(existing, ret)

    return ret


def list_profile(hostname, username, password, profile_type, name):
    '''
    A function to list an existing profile.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    profile_type
        The type of profile to list
    name
        The name of the profile to list
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'list', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'profile_type': profile_type,
            'name': name
        })

    response = __salt__['bigip.list_profile'](hostname, username, password, profile_type, name)
    return _load_result(response, ret)


def create_profile(hostname, username, password, profile_type, name, **kwargs):
    r'''
    A function to connect to a bigip device and create a profile.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    profile_type
        The type of profile to create
    name
        The name of the profile to create
    kwargs
        [ arg=val ] ...

        Consult F5 BIGIP user guide for specific options for each profile type.
        Typically, tmsh arg names are used.

    Special Characters ``|``, ``,`` and ``:`` must be escaped using ``\`` when
    used within strings.

    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'create', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'profile_type': profile_type,
            'name': name
        })

    #is this profile currently configured?
    existing = __salt__['bigip.list_profile'](hostname, username, password, profile_type, name)

    # if it exists
    if existing['code'] == 200:

        ret['result'] = True
        ret['comment'] = 'A profile by this name currently exists.  No change made.'

    # if it doesn't exist
    elif existing['code'] == 404:

        response = __salt__['bigip.create_profile'](hostname, username, password, profile_type, name, **kwargs)

        if response['code'] == 200:
            ret['result'] = True
            ret['changes']['old'] = {}
            ret['changes']['new'] = response['content']
            ret['comment'] = 'Profile was successfully created.'
        else:
            ret = _load_result(response, ret)

    # else something else was returned
    else:
        ret = _load_result(existing, ret)

    return ret


def manage_profile(hostname, username, password, profile_type, name, **kwargs):
    '''
    Create a new profile if a monitor of this type and name does not already exists.  If it does exists, only
    the parameters specified will be enforced.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    profile_type
        The type of profile to create
    name
        The name of the profile to create
    kwargs
        [ arg=val ] ...

        Consult F5 BIGIP user guide for specific options for each profile type.
        Typically, tmsh arg names are used.
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:

        params = {
            'hostname': hostname,
            'username': username,
            'password': password,
            'profile_type': profile_type,
            'name': name
        }

        for key, value in six.iteritems(kwargs):
            params[key] = value

        return _test_output(ret, 'manage', params)

    #is this profile currently configured?
    existing = __salt__['bigip.list_profile'](hostname, username, password, profile_type, name)

    # if it exists
    if existing['code'] == 200:

        #modify the profile
        modified = __salt__['bigip.modify_profile'](hostname, username, password, profile_type, name, **kwargs)

        #was the modification successful?
        if modified['code'] == 200:
            del existing['content']['selfLink']
            del modified['content']['selfLink']
            ret = _check_for_changes('Profile', ret, existing, modified)
        else:
            ret = _load_result(modified, ret)

    # if it doesn't exist
    elif existing['code'] == 404:

        response = __salt__['bigip.create_profile'](hostname, username, password, profile_type, name, **kwargs)
        if response['code'] == 200:
            ret['result'] = True
            ret['changes']['old'] = {}
            ret['changes']['new'] = response['content']
            ret['comment'] = 'Profile was successfully created.'
        else:
            ret = _load_result(existing, ret)

    # else something else was returned
    else:
        ret = _load_result(existing, ret)

    return ret


def modify_profile(hostname, username, password, profile_type, name, **kwargs):
    '''
    Modify an existing profile.  If it does exists, only
    the parameters specified will be enforced.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    profile_type
        The type of profile to create
    name
        The name of the profile to create
    kwargs
        [ arg=val ] ...

        Consult F5 BIGIP user guide for specific options for each monitor type.
        Typically, tmsh arg names are used.
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:

        params = {
            'hostname': hostname,
            'username': username,
            'password': password,
            'profile_type': profile_type,
            'name': name
        }

        for key, value in six.iteritems(kwargs):
            params[key] = value

        return _test_output(ret, 'modify', params)

    #is this profile currently configured?
    existing = __salt__['bigip.list_profile'](hostname, username, password, profile_type, name)

    # if it exists
    if existing['code'] == 200:

        #modify the profile
        modified = __salt__['bigip.modify_profile'](hostname, username, password, profile_type, name, **kwargs)

        #was the modification successful?
        if modified['code'] == 200:
            del existing['content']['selfLink']
            del modified['content']['selfLink']
            ret = _check_for_changes('Profile', ret, existing, modified)
        else:
            ret = _load_result(modified, ret)

    # if it doesn't exist
    elif existing['code'] == 404:
        ret['comment'] = 'A Profile with this name was not found.'
    # else something else was returned
    else:
        ret = _load_result(existing, ret)

    return ret


def delete_profile(hostname, username, password, profile_type, name):
    '''
    Modify an existing profile.  If it does exists, only
    the parameters specified will be enforced.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    profile_type
        The type of profile to create
    name
        The name of the profile to create
    kwargs
        [ arg=val ] ...

        Consult F5 BIGIP user guide for specific options for each profile type.
        Typically, tmsh arg names are used.
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if __opts__['test']:
        return _test_output(ret, 'delete', params={
            'hostname': hostname,
            'username': username,
            'password': password,
            'profile_type': profile_type,
            'name': name
        })

    #is this profile currently configured?
    existing = __salt__['bigip.list_profile'](hostname, username, password, profile_type, name)

    # if it exists by name
    if existing['code'] == 200:

        deleted = __salt__['bigip.delete_profile'](hostname, username, password, profile_type, name)
        # did we get rid of it?
        if deleted['code'] == 200:
            ret['result'] = True
            ret['comment'] = 'Profile was successfully deleted.'
            ret['changes']['old'] = existing['content']
            ret['changes']['new'] = {}
        # something bad happened
        else:
            ret = _load_result(deleted, ret)

    # not found
    elif existing['code'] == 404:
        ret['result'] = True
        ret['comment'] = 'This Profile already does not exist. No changes made.'
        ret['changes']['old'] = {}
        ret['changes']['new'] = {}
    else:
        ret = _load_result(existing, ret)

    return ret
