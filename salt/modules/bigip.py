# -*- coding: utf-8 -*-
'''
An execution module which can manipulate an f5 bigip via iControl REST
    :maturity:      develop
    :platform:      f5_bigip_11.6
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import salt.utils.json

# Import third party libs
try:
    import requests
    import requests.exceptions
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

# Import 3rd-party libs
from salt.ext import six

# Import salt libs
import salt.exceptions

# Define the module's virtual name
__virtualname__ = 'bigip'


def __virtual__():
    '''
    Only return if requests is installed
    '''
    if HAS_LIBS:
        return __virtualname__
    return (False, 'The bigip execution module cannot be loaded: '
            'python requests library not available.')


BIG_IP_URL_BASE = 'https://{host}/mgmt/tm'


def _build_session(username, password, trans_label=None):
    '''
    Create a session to be used when connecting to iControl REST.
    '''

    bigip = requests.session()
    bigip.auth = (username, password)
    bigip.verify = False
    bigip.headers.update({'Content-Type': 'application/json'})

    if trans_label:
        #pull the trans id from the grain
        trans_id = __salt__['grains.get']('bigip_f5_trans:{label}'.format(label=trans_label))

        if trans_id:
            bigip.headers.update({'X-F5-REST-Coordination-Id': trans_id})
        else:
            bigip.headers.update({'X-F5-REST-Coordination-Id': None})

    return bigip


def _load_response(response):
    '''
    Load the response from json data, return the dictionary or raw text
    '''

    try:
        data = salt.utils.json.loads(response.text)
    except ValueError:
        data = response.text

    ret = {'code': response.status_code, 'content': data}

    return ret


def _load_connection_error(hostname, error):
    '''
    Format and Return a connection error
    '''

    ret = {'code': None, 'content': 'Error: Unable to connect to the bigip device: {host}\n{error}'.format(host=hostname, error=error)}

    return ret


def _loop_payload(params):
    '''
    Pass in a dictionary of parameters, loop through them and build a payload containing,
    parameters who's values are not None.
    '''

    #construct the payload
    payload = {}

    #set the payload
    for param, value in six.iteritems(params):
        if value is not None:
            payload[param] = value

    return payload


def _build_list(option_value, item_kind):
    '''
    pass in an option to check for a list of items, create a list of dictionary of items to set
    for this option
    '''
    #specify profiles if provided
    if option_value is not None:

        items = []

        #if user specified none, return an empty list
        if option_value == 'none':
            return items

        #was a list already passed in?
        if not isinstance(option_value, list):
            values = option_value.split(',')
        else:
            values = option_value

        for value in values:
            # sometimes the bigip just likes a plain ol list of items
            if item_kind is None:
                items.append(value)
            # other times it's picky and likes key value pairs...
            else:
                items.append({'kind': item_kind, 'name': value})
        return items
    return None


def _determine_toggles(payload, toggles):
    '''
    BigIP can't make up its mind if it likes yes / no or true or false.
    Figure out what it likes to hear without confusing the user.
    '''

    for toggle, definition in six.iteritems(toggles):
        #did the user specify anything?
        if definition['value'] is not None:
            #test for yes_no toggle
            if (definition['value'] is True or definition['value'] == 'yes') and definition['type'] == 'yes_no':
                payload[toggle] = 'yes'
            elif (definition['value'] is False or definition['value'] == 'no') and definition['type'] == 'yes_no':
                payload[toggle] = 'no'

            #test for true_false toggle
            if (definition['value'] is True or definition['value'] == 'yes') and definition['type'] == 'true_false':
                payload[toggle] = True
            elif (definition['value'] is False or definition['value'] == 'no') and definition['type'] == 'true_false':
                payload[toggle] = False

    return payload


def _set_value(value):
    '''
    A function to detect if user is trying to pass a dictionary or list.  parse it and return a
    dictionary list or a string
    '''
    #don't continue if already an acceptable data-type
    if isinstance(value, bool) or isinstance(value, dict) or isinstance(value, list):
        return value

    #check if json
    if value.startswith('j{') and value.endswith('}j'):

        value = value.replace('j{', '{')
        value = value.replace('}j', '}')

        try:
            return salt.utils.json.loads(value)
        except Exception:
            raise salt.exceptions.CommandExecutionError

    #detect list of dictionaries
    if '|' in value and r'\|' not in value:
        values = value.split('|')
        items = []
        for value in values:
            items.append(_set_value(value))
        return items

    #parse out dictionary if detected
    if ':' in value and r'\:' not in value:
        options = {}
        #split out pairs
        key_pairs = value.split(',')
        for key_pair in key_pairs:
            k = key_pair.split(':')[0]
            v = key_pair.split(':')[1]
            options[k] = v
        return options

    #try making a list
    elif ',' in value and r'\,' not in value:
        value_items = value.split(',')
        return value_items

    #just return a string
    else:

        #remove escape chars if added
        if r'\|' in value:
            value = value.replace(r'\|', '|')

        if r'\:' in value:
            value = value.replace(r'\:', ':')

        if r'\,' in value:
            value = value.replace(r'\,', ',')

        return value


def start_transaction(hostname, username, password, label):
    '''
    A function to connect to a bigip device and start a new transaction.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    label
        The name / alias for this transaction.  The actual transaction
        id will be stored within a grain called ``bigip_f5_trans:<label>``

    CLI Example::

        salt '*' bigip.start_transaction bigip admin admin my_transaction

    '''

    #build the session
    bigip_session = _build_session(username, password)

    payload = {}

    #post to REST to get trans id
    try:
        response = bigip_session.post(
            BIG_IP_URL_BASE.format(host=hostname) + '/transaction',
            data=salt.utils.json.dumps(payload)
        )
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    #extract the trans_id
    data = _load_response(response)

    if data['code'] == 200:

        trans_id = data['content']['transId']

        __salt__['grains.setval']('bigip_f5_trans', {label: trans_id})

        return 'Transaction: {trans_id} - has successfully been stored in the grain: bigip_f5_trans:{label}'.format(trans_id=trans_id,
                                                                                                                       label=label)
    else:
        return data


def list_transaction(hostname, username, password, label):
    '''
    A function to connect to a bigip device and list an existing transaction.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    label
        the label of this transaction stored within the grain:
        ``bigip_f5_trans:<label>``

    CLI Example::

        salt '*' bigip.list_transaction bigip admin admin my_transaction

    '''

    #build the session
    bigip_session = _build_session(username, password)

    #pull the trans id from the grain
    trans_id = __salt__['grains.get']('bigip_f5_trans:{label}'.format(label=label))

    if trans_id:

        #post to REST to get trans id
        try:
            response = bigip_session.get(BIG_IP_URL_BASE.format(host=hostname)+'/transaction/{trans_id}/commands'.format(trans_id=trans_id))
            return _load_response(response)
        except requests.exceptions.ConnectionError as e:
            return _load_connection_error(hostname, e)
    else:
        return 'Error: the label for this transaction was not defined as a grain.  Begin a new transaction using the' \
               ' bigip.start_transaction function'


def commit_transaction(hostname, username, password, label):
    '''
    A function to connect to a bigip device and commit an existing transaction.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    label
        the label of this transaction stored within the grain:
        ``bigip_f5_trans:<label>``

    CLI Example::

        salt '*' bigip.commit_transaction bigip admin admin my_transaction
    '''

    #build the session
    bigip_session = _build_session(username, password)

    #pull the trans id from the grain
    trans_id = __salt__['grains.get']('bigip_f5_trans:{label}'.format(label=label))

    if trans_id:

        payload = {}
        payload['state'] = 'VALIDATING'

        #patch to REST to get trans id
        try:
            response = bigip_session.patch(
                BIG_IP_URL_BASE.format(host=hostname) + '/transaction/{trans_id}'.format(trans_id=trans_id),
                data=salt.utils.json.dumps(payload)
            )
            return _load_response(response)
        except requests.exceptions.ConnectionError as e:
            return _load_connection_error(hostname, e)
    else:
        return 'Error: the label for this transaction was not defined as a grain.  Begin a new transaction using the' \
               ' bigip.start_transaction function'


def delete_transaction(hostname, username, password, label):
    '''
    A function to connect to a bigip device and delete an existing transaction.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    label
        The label of this transaction stored within the grain:
        ``bigip_f5_trans:<label>``

    CLI Example::

        salt '*' bigip.delete_transaction bigip admin admin my_transaction
    '''

    #build the session
    bigip_session = _build_session(username, password)

    #pull the trans id from the grain
    trans_id = __salt__['grains.get']('bigip_f5_trans:{label}'.format(label=label))

    if trans_id:

        #patch to REST to get trans id
        try:
            response = bigip_session.delete(BIG_IP_URL_BASE.format(host=hostname)+'/transaction/{trans_id}'.format(trans_id=trans_id))
            return _load_response(response)
        except requests.exceptions.ConnectionError as e:
            return _load_connection_error(hostname, e)
    else:
        return 'Error: the label for this transaction was not defined as a grain.  Begin a new transaction using the' \
               ' bigip.start_transaction function'


def list_node(hostname, username, password, name=None, trans_label=None):
    '''
    A function to connect to a bigip device and list all nodes or a specific node.


    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the node to list. If no name is specified than all nodes
        will be listed.
    trans_label
        The label of the transaction stored within the grain:
        ``bigip_f5_trans:<label>``

    CLI Example::

        salt '*' bigip.list_node bigip admin admin my-node
    '''

    #build sessions
    bigip_session = _build_session(username, password, trans_label)

    #get to REST
    try:
        if name:
            response = bigip_session.get(BIG_IP_URL_BASE.format(host=hostname)+'/ltm/node/{name}'.format(name=name))
        else:
            response = bigip_session.get(BIG_IP_URL_BASE.format(host=hostname)+'/ltm/node')
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


def create_node(hostname, username, password, name, address, trans_label=None):
    '''
    A function to connect to a bigip device and create a node.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the node
    address
        The address of the node
    trans_label
        The label of the transaction stored within the grain:
        ``bigip_f5_trans:<label>``

    CLI Example::

        salt '*' bigip.create_node bigip admin admin 10.1.1.2
    '''

    #build session
    bigip_session = _build_session(username, password, trans_label)

    #construct the payload
    payload = {}
    payload['name'] = name
    payload['address'] = address

    #post to REST
    try:
        response = bigip_session.post(
            BIG_IP_URL_BASE.format(host=hostname) + '/ltm/node',
            data=salt.utils.json.dumps(payload))
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


def modify_node(hostname, username, password, name,
                connection_limit=None,
                description=None,
                dynamic_ratio=None,
                logging=None,
                monitor=None,
                rate_limit=None,
                ratio=None,
                session=None,
                state=None,
                trans_label=None):
    '''
    A function to connect to a bigip device and modify an existing node.

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
    state
        [user-down | user-up ]
    trans_label
        The label of the transaction stored within the grain:
        ``bigip_f5_trans:<label>``

    CLI Example::

        salt '*' bigip.modify_node bigip admin admin 10.1.1.2 ratio=2 logging=enabled
    '''

    params = {
        'connection-limit': connection_limit,
        'description': description,
        'dynamic-ratio': dynamic_ratio,
        'logging': logging,
        'monitor': monitor,
        'rate-limit': rate_limit,
        'ratio': ratio,
        'session': session,
        'state': state,
    }

    #build session
    bigip_session = _build_session(username, password, trans_label)

    #build payload
    payload = _loop_payload(params)
    payload['name'] = name

    #put to REST
    try:
        response = bigip_session.put(
            BIG_IP_URL_BASE.format(host=hostname) + '/ltm/node/{name}'.format(name=name),
            data=salt.utils.json.dumps(payload)
        )
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


def delete_node(hostname, username, password, name, trans_label=None):
    '''
    A function to connect to a bigip device and delete a specific node.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the node which will be deleted.
    trans_label
        The label of the transaction stored within the grain:
        ``bigip_f5_trans:<label>``

    CLI Example::

        salt '*' bigip.delete_node bigip admin admin my-node
    '''

    #build session
    bigip_session = _build_session(username, password, trans_label)

    #delete to REST
    try:
        response = bigip_session.delete(BIG_IP_URL_BASE.format(host=hostname)+'/ltm/node/{name}'.format(name=name))
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    if _load_response(response) == '':
        return True
    else:
        return _load_response(response)


def list_pool(hostname, username, password, name=None):
    '''
    A function to connect to a bigip device and list all pools or a specific pool.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the pool to list. If no name is specified then all pools
        will be listed.

    CLI Example::

        salt '*' bigip.list_pool bigip admin admin my-pool
    '''

    #build sessions
    bigip_session = _build_session(username, password)

    #get to REST
    try:
        if name:
            response = bigip_session.get(BIG_IP_URL_BASE.format(host=hostname)+'/ltm/pool/{name}/?expandSubcollections=true'.format(name=name))
        else:
            response = bigip_session.get(BIG_IP_URL_BASE.format(host=hostname)+'/ltm/pool')
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


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
    A function to connect to a bigip device and create a pool.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the pool to create.
    members
        List of comma delimited pool members to add to the pool.
        i.e. 10.1.1.1:80,10.1.1.2:80,10.1.1.3:80
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

    CLI Example::

        salt '*' bigip.create_pool bigip admin admin my-pool 10.1.1.1:80,10.1.1.2:80,10.1.1.3:80 monitor=http
    '''

    params = {
        'description': description,
        'gateway-failsafe-device': gateway_failsafe_device,
        'ignore-persisted-weight': ignore_persisted_weight,
        'ip-tos-to-client': ip_tos_to_client,
        'ip-tos-to-server': ip_tos_to_server,
        'link-qos-to-client': link_qos_to_client,
        'link-qos-to-server': link_qos_to_server,
        'load-balancing-mode': load_balancing_mode,
        'min-active-members': min_active_members,
        'min-up-members': min_up_members,
        'min-up-members-action': min_up_members_action,
        'min-up-members-checking': min_up_members_checking,
        'monitor': monitor,
        'profiles': profiles,
        'queue-on-connection-limit': queue_on_connection_limit,
        'queue-depth-limit': queue_depth_limit,
        'queue-time-limit': queue_time_limit,
        'reselect-tries': reselect_tries,
        'service-down-action': service_down_action,
        'slow-ramp-time': slow_ramp_time
    }

    # some options take yes no others take true false.  Figure out when to use which without
    # confusing the end user
    toggles = {
        'allow-nat': {'type': 'yes_no', 'value': allow_nat},
        'allow-snat': {'type': 'yes_no', 'value': allow_snat}
    }

    #build payload
    payload = _loop_payload(params)
    payload['name'] = name

    #determine toggles
    payload = _determine_toggles(payload, toggles)

    #specify members if provided
    if members is not None:
        payload['members'] = _build_list(members, 'ltm:pool:members')

    #build session
    bigip_session = _build_session(username, password)

    #post to REST
    try:
        response = bigip_session.post(
            BIG_IP_URL_BASE.format(host=hostname) + '/ltm/pool',
            data=salt.utils.json.dumps(payload)
        )
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


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
    A function to connect to a bigip device and modify an existing pool.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the pool to modify.
    allow_nat
        [yes | no]
    allow_snat
        [yes | no]
    description
        [string]
    gateway_failsafe_device
        [string]
    ignore_persisted_weight
        [yes | no]
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
    queue_on_connection_limit
        [enabled | disabled]
    queue_depth_limit
        [integer]
    queue_time_limit
        [integer]
    reselect_tries
        [integer]
    service_down_action
        [drop | none | reselect | reset]
    slow_ramp_time
        [integer]

    CLI Example::

        salt '*' bigip.modify_pool bigip admin admin my-pool 10.1.1.1:80,10.1.1.2:80,10.1.1.3:80 min_active_members=1
    '''

    params = {
        'description': description,
        'gateway-failsafe-device': gateway_failsafe_device,
        'ignore-persisted-weight': ignore_persisted_weight,
        'ip-tos-to-client': ip_tos_to_client,
        'ip-tos-to-server': ip_tos_to_server,
        'link-qos-to-client': link_qos_to_client,
        'link-qos-to-server': link_qos_to_server,
        'load-balancing-mode': load_balancing_mode,
        'min-active-members': min_active_members,
        'min-up-members': min_up_members,
        'min-up_members-action': min_up_members_action,
        'min-up-members-checking': min_up_members_checking,
        'monitor': monitor,
        'profiles': profiles,
        'queue-on-connection-limit': queue_on_connection_limit,
        'queue-depth-limit': queue_depth_limit,
        'queue-time-limit': queue_time_limit,
        'reselect-tries': reselect_tries,
        'service-down-action': service_down_action,
        'slow-ramp-time': slow_ramp_time
    }

    # some options take yes no others take true false.  Figure out when to use which without
    # confusing the end user
    toggles = {
        'allow-nat': {'type': 'yes_no', 'value': allow_nat},
        'allow-snat': {'type': 'yes_no', 'value': allow_snat}
    }

    #build payload
    payload = _loop_payload(params)
    payload['name'] = name

    #determine toggles
    payload = _determine_toggles(payload, toggles)

    #build session
    bigip_session = _build_session(username, password)

    #post to REST
    try:
        response = bigip_session.put(
            BIG_IP_URL_BASE.format(host=hostname) + '/ltm/pool/{name}'.format(name=name),
            data=salt.utils.json.dumps(payload)
        )
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


def delete_pool(hostname, username, password, name):
    '''
    A function to connect to a bigip device and delete a specific pool.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the pool which will be deleted

    CLI Example::

        salt '*' bigip.delete_node bigip admin admin my-pool
    '''

    #build session
    bigip_session = _build_session(username, password)

    #delete to REST
    try:
        response = bigip_session.delete(BIG_IP_URL_BASE.format(host=hostname)+'/ltm/pool/{name}'.format(name=name))
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    if _load_response(response) == '':
        return True
    else:
        return _load_response(response)


def replace_pool_members(hostname, username, password, name, members):
    '''
    A function to connect to a bigip device and replace members of an existing pool with new members.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the pool to modify
    members
        List of comma delimited pool members to replace existing members with.
        i.e. 10.1.1.1:80,10.1.1.2:80,10.1.1.3:80

    CLI Example::

        salt '*' bigip.replace_pool_members bigip admin admin my-pool 10.2.2.1:80,10.2.2.2:80,10.2.2.3:80
    '''

    payload = {}
    payload['name'] = name
    #specify members if provided
    if members is not None:

        if isinstance(members, six.string_types):
            members = members.split(',')

        pool_members = []
        for member in members:

            #check to see if already a dictionary ( for states)
            if isinstance(member, dict):

                #check for state alternative name 'member_state', replace with state
                if 'member_state' in member.keys():
                    member['state'] = member.pop('member_state')

                #replace underscore with dash
                for key in member:
                    new_key = key.replace('_', '-')
                    member[new_key] = member.pop(key)

                pool_members.append(member)

            #parse string passed via execution command (for executions)
            else:
                pool_members.append({'name': member, 'address': member.split(':')[0]})

        payload['members'] = pool_members

    #build session
    bigip_session = _build_session(username, password)

    #put to REST
    try:
        response = bigip_session.put(
            BIG_IP_URL_BASE.format(host=hostname) + '/ltm/pool/{name}'.format(name=name),
            data=salt.utils.json.dumps(payload)
        )
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


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
        The name of the member to add
        i.e. 10.1.1.2:80

    CLI Example:

    .. code-block:: bash

        salt '*' bigip.add_pool_members bigip admin admin my-pool 10.2.2.1:80
    '''

    # for states
    if isinstance(member, dict):

        #check for state alternative name 'member_state', replace with state
        if 'member_state' in member.keys():
            member['state'] = member.pop('member_state')

        #replace underscore with dash
        for key in member:
            new_key = key.replace('_', '-')
            member[new_key] = member.pop(key)

        payload = member
    # for execution
    else:

        payload = {'name': member, 'address': member.split(':')[0]}

    #build session
    bigip_session = _build_session(username, password)

    #post to REST
    try:
        response = bigip_session.post(
            BIG_IP_URL_BASE.format(host=hostname) + '/ltm/pool/{name}/members'.format(name=name),
            data=salt.utils.json.dumps(payload)
        )
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


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
                       state=None):
    '''
    A function to connect to a bigip device and modify an existing member of a pool.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the pool to modify
    member
        The name of the member to modify i.e. 10.1.1.2:80
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
    state
        [ user-up | user-down ]

    CLI Example::

        salt '*' bigip.modify_pool_member bigip admin admin my-pool 10.2.2.1:80 state=use-down session=user-disabled
    '''

    params = {
        'connection-limit': connection_limit,
        'description': description,
        'dynamic-ratio': dynamic_ratio,
        'inherit-profile': inherit_profile,
        'logging': logging,
        'monitor': monitor,
        'priority-group': priority_group,
        'profiles': profiles,
        'rate-limit': rate_limit,
        'ratio': ratio,
        'session': session,
        'state': state
    }

    #build session
    bigip_session = _build_session(username, password)

    #build payload
    payload = _loop_payload(params)

    #put to REST
    try:
        response = bigip_session.put(
            BIG_IP_URL_BASE.format(host=hostname) + '/ltm/pool/{name}/members/{member}'.format(name=name, member=member),
            data=salt.utils.json.dumps(payload)
        )
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


def delete_pool_member(hostname, username, password, name, member):
    '''
    A function to connect to a bigip device and delete a specific pool.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the pool to modify
    member
        The name of the pool member to delete

    CLI Example::

        salt '*' bigip.delete_pool_member bigip admin admin my-pool 10.2.2.2:80
    '''

    #build session
    bigip_session = _build_session(username, password)

    #delete to REST
    try:
        response = bigip_session.delete(BIG_IP_URL_BASE.format(host=hostname)+'/ltm/pool/{name}/members/{member}'.format(name=name, member=member))
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    if _load_response(response) == '':
        return True
    else:
        return _load_response(response)


def list_virtual(hostname, username, password, name=None):
    '''
    A function to connect to a bigip device and list all virtuals or a specific virtual.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the virtual to list. If no name is specified than all
        virtuals will be listed.

    CLI Example::

        salt '*' bigip.list_virtual bigip admin admin my-virtual
    '''

    #build sessions
    bigip_session = _build_session(username, password)

    #get to REST
    try:
        if name:
            response = bigip_session.get(BIG_IP_URL_BASE.format(host=hostname)+'/ltm/virtual/{name}/?expandSubcollections=true'.format(name=name))
        else:
            response = bigip_session.get(BIG_IP_URL_BASE.format(host=hostname)+'/ltm/virtual')
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


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
                   state=None,
                   traffic_classes=None,
                   translate_address=None,
                   translate_port=None,
                   vlans=None):
    r'''
    A function to connect to a bigip device and create a virtual server.

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
        [yes | no]
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
    twelve_forward
        (12-forward)
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
        [none | profile1,profile2,profile3 ... ]
    profiles
        [none | default | profile1,profile2,profile3 ... ]
    policies
        [none | default | policy1,policy2,policy3 ... ]
    rate_class
        [name]
    rate_limit
        [integer]
    rate_limit_mode
        [destination | object | object-destination |
        object-source | object-source-destination |
        source | source-destination]
    rate_limit_dst
        [integer]
    rate_limitçsrc
        [integer]
    rules
        [none | [rule_one,rule_two ...] ]
    related_rules
        [none | [rule_one,rule_two ...] ]
    reject
        [yes | no]
    source
        { [ipv4[/prefixlen]] | [ipv6[/prefixlen]] }
    source_address_translation
        [none | snat:pool_name | lsn | automap ]
    source_port
        [change | preserve | preserve-strict]
    state
        [enabled | disabled]
    traffic_classes
        [none | default | class_one,class_two ... ]
    translate_address
        [enabled | disabled]
    translate_port
        [enabled | disabled]
    vlans
        [none | default | [enabled|disabled]:vlan1,vlan2,vlan3 ... ]

    CLI Examples::

        salt '*' bigip.create_virtual bigip admin admin my-virtual-3 26.2.2.5:80 \
            pool=my-http-pool-http profiles=http,tcp

        salt '*' bigip.create_virtual bigip admin admin my-virtual-3 43.2.2.5:80 \
            pool=test-http-pool-http profiles=http,websecurity persist=cookie,hash \
            policies=asm_auto_l7_policy__http-virtual \
            rules=_sys_APM_ExchangeSupport_helper,_sys_https_redirect \
            related_rules=_sys_APM_activesync,_sys_APM_ExchangeSupport_helper \
            source_address_translation=snat:my-snat-pool \
            translate_address=enabled translate_port=enabled \
            traffic_classes=my-class,other-class \
            vlans=enabled:external,internal

    '''

    params = {
        'pool': pool,
        'auto-lasthop': auto_lasthop,
        'bwc-policy': bwc_policy,
        'connection-limit': connection_limit,
        'description': description,
        'fallback-persistence': fallback_persistence,
        'flow-eviction-policy': flow_eviction_policy,
        'gtm-score': gtm_score,
        'ip-protocol': ip_protocol,
        'last-hop-pool': last_hop_pool,
        'mask': mask,
        'mirror': mirror,
        'nat64': nat64,
        'persist': persist,
        'rate-class': rate_class,
        'rate-limit': rate_limit,
        'rate-limit-mode': rate_limit_mode,
        'rate-limit-dst': rate_limit_dst,
        'rate-limit-src': rate_limit_src,
        'source': source,
        'source-port': source_port,
        'translate-address': translate_address,
        'translate-port': translate_port
    }

    # some options take yes no others take true false.  Figure out when to use which without
    # confusing the end user
    toggles = {
        'address-status': {'type': 'yes_no', 'value': address_status},
        'cmp-enabled': {'type': 'yes_no', 'value': cmp_enabled},
        'dhcp-relay': {'type': 'true_false', 'value': dhcp_relay},
        'reject': {'type': 'true_false', 'value': reject},
        '12-forward': {'type': 'true_false', 'value': twelve_forward},
        'internal': {'type': 'true_false', 'value': internal},
        'ip-forward': {'type': 'true_false', 'value': ip_forward}
    }

    #build session
    bigip_session = _build_session(username, password)

    #build payload
    payload = _loop_payload(params)

    payload['name'] = name
    payload['destination'] = destination

    #determine toggles
    payload = _determine_toggles(payload, toggles)

    #specify profiles if provided
    if profiles is not None:
        payload['profiles'] = _build_list(profiles, 'ltm:virtual:profile')

    #specify persist if provided
    if persist is not None:
        payload['persist'] = _build_list(persist, 'ltm:virtual:persist')

    #specify policies if provided
    if policies is not None:
        payload['policies'] = _build_list(policies, 'ltm:virtual:policy')

    #specify rules if provided
    if rules is not None:
        payload['rules'] = _build_list(rules, None)

    #specify related-rules if provided
    if related_rules is not None:
        payload['related-rules'] = _build_list(related_rules, None)

    #handle source-address-translation
    if source_address_translation is not None:

        #check to see if this is already a dictionary first
        if isinstance(source_address_translation, dict):
            payload['source-address-translation'] = source_address_translation
        elif source_address_translation == 'none':
            payload['source-address-translation'] = {'pool': 'none', 'type': 'none'}
        elif source_address_translation == 'automap':
            payload['source-address-translation'] = {'pool': 'none', 'type': 'automap'}
        elif source_address_translation == 'lsn':
            payload['source-address-translation'] = {'pool': 'none', 'type': 'lsn'}
        elif source_address_translation.startswith('snat'):
            snat_pool = source_address_translation.split(':')[1]
            payload['source-address-translation'] = {'pool': snat_pool, 'type': 'snat'}

    #specify related-rules if provided
    if traffic_classes is not None:
        payload['traffic-classes'] = _build_list(traffic_classes, None)

    #handle vlans
    if vlans is not None:
        #ceck to see if vlans is a dictionary (used when state makes use of function)
        if isinstance(vlans, dict):
            try:
                payload['vlans'] = vlans['vlan_ids']
                if vlans['enabled']:
                    payload['vlans-enabled'] = True
                elif vlans['disabled']:
                    payload['vlans-disabled'] = True
            except Exception:
                return 'Error: Unable to Parse vlans dictionary: \n\tvlans={vlans}'.format(vlans=vlans)
        elif vlans == 'none':
            payload['vlans'] = 'none'
        elif vlans == 'default':
            payload['vlans'] = 'default'
        elif isinstance(vlans, six.string_types) and (vlans.startswith('enabled') or vlans.startswith('disabled')):
            try:
                vlans_setting = vlans.split(':')[0]
                payload['vlans'] = vlans.split(':')[1].split(',')
                if vlans_setting == 'disabled':
                    payload['vlans-disabled'] = True
                elif vlans_setting == 'enabled':
                    payload['vlans-enabled'] = True
            except Exception:
                return 'Error: Unable to Parse vlans option: \n\tvlans={vlans}'.format(vlans=vlans)
        else:
            return 'Error: vlans must be a dictionary or string.'

    #determine state
    if state is not None:
        if state == 'enabled':
            payload['enabled'] = True
        elif state == 'disabled':
            payload['disabled'] = True

    #post to REST
    try:
        response = bigip_session.post(
            BIG_IP_URL_BASE.format(host=hostname) + '/ltm/virtual',
            data=salt.utils.json.dumps(payload)
        )
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


def modify_virtual(hostname, username, password, name,
                   destination=None,
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
                   state=None,
                   traffic_classes=None,
                   translate_address=None,
                   translate_port=None,
                   vlans=None):
    '''
    A function to connect to a bigip device and modify an existing virtual server.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the virtual to modify
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
    twelve_forward
        (12-forward)
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
        [none | profile1,profile2,profile3 ... ]
    profiles
        [none | default | profile1,profile2,profile3 ... ]
    policies
        [none | default | policy1,policy2,policy3 ... ]
    rate_class
        [name]
    rate_limit
        [integer]
    rate_limitr_mode
        [destination | object | object-destination |
        object-source | object-source-destination |
        source | source-destination]
    rate_limit_dst
        [integer]
    rate_limit_src
        [integer]
    rules
        [none | [rule_one,rule_two ...] ]
    related_rules
        [none | [rule_one,rule_two ...] ]
    reject
        [yes | no]
    source
        { [ipv4[/prefixlen]] | [ipv6[/prefixlen]] }
    source_address_translation
        [none | snat:pool_name | lsn | automap ]
    source_port
        [change | preserve | preserve-strict]
    state
        [enabled | disable]
    traffic_classes
        [none | default | class_one,class_two ... ]
    translate_address
        [enabled | disabled]
    translate_port
        [enabled | disabled]
    vlans
        [none | default | [enabled|disabled]:vlan1,vlan2,vlan3 ... ]

    CLI Example::

        salt '*' bigip.modify_virtual bigip admin admin my-virtual source_address_translation=none
        salt '*' bigip.modify_virtual bigip admin admin my-virtual rules=my-rule,my-other-rule
    '''

    params = {
        'destination': destination,
        'pool': pool,
        'auto-lasthop': auto_lasthop,
        'bwc-policy': bwc_policy,
        'connection-limit': connection_limit,
        'description': description,
        'fallback-persistence': fallback_persistence,
        'flow-eviction-policy': flow_eviction_policy,
        'gtm-score': gtm_score,
        'ip-protocol': ip_protocol,
        'last-hop-pool': last_hop_pool,
        'mask': mask,
        'mirror': mirror,
        'nat64': nat64,
        'persist': persist,
        'rate-class': rate_class,
        'rate-limit': rate_limit,
        'rate-limit-mode': rate_limit_mode,
        'rate-limit-dst': rate_limit_dst,
        'rate-limit-src': rate_limit_src,
        'source': source,
        'source-port': source_port,
        'translate-address': translate_address,
        'translate-port': translate_port
    }

    # some options take yes no others take true false.  Figure out when to use which without
    # confusing the end user
    toggles = {
        'address-status': {'type': 'yes_no', 'value': address_status},
        'cmp-enabled': {'type': 'yes_no', 'value': cmp_enabled},
        'dhcp-relay': {'type': 'true_false', 'value': dhcp_relay},
        'reject': {'type': 'true_false', 'value': reject},
        '12-forward': {'type': 'true_false', 'value': twelve_forward},
        'internal': {'type': 'true_false', 'value': internal},
        'ip-forward': {'type': 'true_false', 'value': ip_forward}
    }

    #build session
    bigip_session = _build_session(username, password)

    #build payload
    payload = _loop_payload(params)
    payload['name'] = name

    #determine toggles
    payload = _determine_toggles(payload, toggles)

    #specify profiles if provided
    if profiles is not None:
        payload['profiles'] = _build_list(profiles, 'ltm:virtual:profile')

    #specify persist if provided
    if persist is not None:
        payload['persist'] = _build_list(persist, 'ltm:virtual:persist')

    #specify policies if provided
    if policies is not None:
        payload['policies'] = _build_list(policies, 'ltm:virtual:policy')

    #specify rules if provided
    if rules is not None:
        payload['rules'] = _build_list(rules, None)

    #specify related-rules if provided
    if related_rules is not None:
        payload['related-rules'] = _build_list(related_rules, None)

    #handle source-address-translation
    if source_address_translation is not None:
        if source_address_translation == 'none':
            payload['source-address-translation'] = {'pool': 'none', 'type': 'none'}
        elif source_address_translation == 'automap':
            payload['source-address-translation'] = {'pool': 'none', 'type': 'automap'}
        elif source_address_translation == 'lsn':
            payload['source-address-translation'] = {'pool': 'none', 'type': 'lsn'}
        elif source_address_translation.startswith('snat'):
            snat_pool = source_address_translation.split(':')[1]
            payload['source-address-translation'] = {'pool': snat_pool, 'type': 'snat'}

    #specify related-rules if provided
    if traffic_classes is not None:
        payload['traffic-classes'] = _build_list(traffic_classes, None)

    #handle vlans
    if vlans is not None:
        #ceck to see if vlans is a dictionary (used when state makes use of function)
        if isinstance(vlans, dict):
            try:
                payload['vlans'] = vlans['vlan_ids']
                if vlans['enabled']:
                    payload['vlans-enabled'] = True
                elif vlans['disabled']:
                    payload['vlans-disabled'] = True
            except Exception:
                return 'Error: Unable to Parse vlans dictionary: \n\tvlans={vlans}'.format(vlans=vlans)
        elif vlans == 'none':
            payload['vlans'] = 'none'
        elif vlans == 'default':
            payload['vlans'] = 'default'
        elif vlans.startswith('enabled') or vlans.startswith('disabled'):
            try:
                vlans_setting = vlans.split(':')[0]
                payload['vlans'] = vlans.split(':')[1].split(',')
                if vlans_setting == 'disabled':
                    payload['vlans-disabled'] = True
                elif vlans_setting == 'enabled':
                    payload['vlans-enabled'] = True
            except Exception:
                return 'Error: Unable to Parse vlans option: \n\tvlans={vlans}'.format(vlans=vlans)

    #determine state
    if state is not None:
        if state == 'enabled':
            payload['enabled'] = True
        elif state == 'disabled':
            payload['disabled'] = True

    #put to REST
    try:
        response = bigip_session.put(
            BIG_IP_URL_BASE.format(host=hostname) + '/ltm/virtual/{name}'.format(name=name),
            data=salt.utils.json.dumps(payload)
        )
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


def delete_virtual(hostname, username, password, name):
    '''
    A function to connect to a bigip device and delete a specific virtual.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    name
        The name of the virtual to delete

    CLI Example::

        salt '*' bigip.delete_virtual bigip admin admin my-virtual
    '''

    #build session
    bigip_session = _build_session(username, password)

    #delete to REST
    try:
        response = bigip_session.delete(BIG_IP_URL_BASE.format(host=hostname)+'/ltm/virtual/{name}'.format(name=name))
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    if _load_response(response) == '':
        return True
    else:
        return _load_response(response)


def list_monitor(hostname, username, password, monitor_type, name=None, ):
    '''
    A function to connect to a bigip device and list an existing monitor.  If no name is provided than all
    monitors of the specified type will be listed.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    monitor_type
        The type of monitor(s) to list
    name
        The name of the monitor to list

    CLI Example::

        salt '*' bigip.list_monitor bigip admin admin http my-http-monitor

    '''

    #build sessions
    bigip_session = _build_session(username, password)

    #get to REST
    try:
        if name:
            response = bigip_session.get(BIG_IP_URL_BASE.format(host=hostname)+'/ltm/monitor/{type}/{name}?expandSubcollections=true'.format(type=monitor_type, name=name))
        else:
            response = bigip_session.get(BIG_IP_URL_BASE.format(host=hostname)+'/ltm/monitor/{type}'.format(type=monitor_type))
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


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
        Consult F5 BIGIP user guide for specific options for each monitor type.
        Typically, tmsh arg names are used.

    CLI Example::

        salt '*' bigip.create_monitor bigip admin admin http my-http-monitor timeout=10 interval=5
    '''

    #build session
    bigip_session = _build_session(username, password)

    #construct the payload
    payload = {}
    payload['name'] = name

    #there's a ton of different monitors and a ton of options for each type of monitor.
    #this logic relies that the end user knows which options are meant for which monitor types
    for key, value in six.iteritems(kwargs):
        if not key.startswith('__'):
            if key not in ['hostname', 'username', 'password', 'type']:
                key = key.replace('_', '-')
                payload[key] = value

    #post to REST
    try:
        response = bigip_session.post(
            BIG_IP_URL_BASE.format(host=hostname) + '/ltm/monitor/{type}'.format(type=monitor_type),
            data=salt.utils.json.dumps(payload)
        )
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


def modify_monitor(hostname, username, password, monitor_type, name, **kwargs):
    '''
    A function to connect to a bigip device and modify an existing monitor.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    monitor_type
        The type of monitor to modify
    name
        The name of the monitor to modify
    kwargs
        Consult F5 BIGIP user guide for specific options for each monitor type.
        Typically, tmsh arg names are used.

    CLI Example::

        salt '*' bigip.modify_monitor bigip admin admin http my-http-monitor  timout=16 interval=6

    '''

    #build session
    bigip_session = _build_session(username, password)

    #construct the payload
    payload = {}

    #there's a ton of different monitors and a ton of options for each type of monitor.
    #this logic relies that the end user knows which options are meant for which monitor types
    for key, value in six.iteritems(kwargs):
        if not key.startswith('__'):
            if key not in ['hostname', 'username', 'password', 'type', 'name']:
                key = key.replace('_', '-')
                payload[key] = value

    #put to REST
    try:
        response = bigip_session.put(
            BIG_IP_URL_BASE.format(host=hostname) + '/ltm/monitor/{type}/{name}'.format(type=monitor_type, name=name),
            data=salt.utils.json.dumps(payload)
        )
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


def delete_monitor(hostname, username, password, monitor_type, name):
    '''
    A function to connect to a bigip device and delete an existing monitor.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    monitor_type
        The type of monitor to delete
    name
        The name of the monitor to delete

    CLI Example::

        salt '*' bigip.delete_monitor bigip admin admin http my-http-monitor

    '''

    #build sessions
    bigip_session = _build_session(username, password)

    #delete to REST
    try:
        response = bigip_session.delete(BIG_IP_URL_BASE.format(host=hostname)+'/ltm/monitor/{type}/{name}'.format(type=monitor_type, name=name))
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    if _load_response(response) == '':
        return True
    else:
        return _load_response(response)


def list_profile(hostname, username, password, profile_type, name=None, ):
    '''
    A function to connect to a bigip device and list an existing profile.  If no name is provided than all
    profiles of the specified type will be listed.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    profile_type
        The type of profile(s) to list
    name
        The name of the profile to list

    CLI Example::

        salt '*' bigip.list_profile bigip admin admin http my-http-profile

    '''

    #build sessions
    bigip_session = _build_session(username, password)

    #get to REST
    try:
        if name:
            response = bigip_session.get(BIG_IP_URL_BASE.format(host=hostname)+'/ltm/profile/{type}/{name}?expandSubcollections=true'.format(type=profile_type, name=name))
        else:
            response = bigip_session.get(BIG_IP_URL_BASE.format(host=hostname)+'/ltm/profile/{type}'.format(type=profile_type))
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


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
        ``[ arg=val ] ... [arg=key1:val1,key2:val2] ...``

        Consult F5 BIGIP user guide for specific options for each monitor type.
        Typically, tmsh arg names are used.

    Creating Complex Args
        Profiles can get pretty complicated in terms of the amount of possible
        config options. Use the following shorthand to create complex arguments such
        as lists, dictionaries, and lists of dictionaries. An option is also
        provided to pass raw json as well.

        lists ``[i,i,i]``:
            ``param='item1,item2,item3'``

        Dictionary ``[k:v,k:v,k,v]``:
            ``param='key-1:val-1,key-2:val2,key-3:va-3'``

        List of Dictionaries ``[k:v,k:v|k:v,k:v|k:v,k:v]``:
           ``param='key-1:val-1,key-2:val-2|key-1:val-1,key-2:val-2|key-1:val-1,key-2:val-2'``

        JSON: ``'j{ ... }j'``:
           ``cert-key-chain='j{ "default": { "cert": "default.crt", "chain": "default.crt", "key": "default.key" } }j'``

        Escaping Delimiters:
            Use ``\,`` or ``\:`` or ``\|`` to escape characters which shouldn't
            be treated as delimiters i.e. ``ciphers='DEFAULT\:!SSLv3'``

    CLI Examples::

        salt '*' bigip.create_profile bigip admin admin http my-http-profile defaultsFrom='/Common/http'
        salt '*' bigip.create_profile bigip admin admin http my-http-profile defaultsFrom='/Common/http' \
            enforcement=maxHeaderCount:3200,maxRequests:10

    '''

    #build session
    bigip_session = _build_session(username, password)

    #construct the payload
    payload = {}
    payload['name'] = name

    #there's a ton of different profiles and a ton of options for each type of profile.
    #this logic relies that the end user knows which options are meant for which profile types
    for key, value in six.iteritems(kwargs):
        if not key.startswith('__'):
            if key not in ['hostname', 'username', 'password', 'profile_type']:
                key = key.replace('_', '-')

                try:
                    payload[key] = _set_value(value)
                except salt.exceptions.CommandExecutionError:
                    return 'Error: Unable to Parse JSON data for parameter: {key}\n{value}'.format(key=key, value=value)

    #post to REST
    try:
        response = bigip_session.post(
            BIG_IP_URL_BASE.format(host=hostname) + '/ltm/profile/{type}'.format(type=profile_type),
            data=salt.utils.json.dumps(payload)
        )
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


def modify_profile(hostname, username, password, profile_type, name, **kwargs):
    r'''
    A function to connect to a bigip device and create a profile.

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
        ``[ arg=val ] ... [arg=key1:val1,key2:val2] ...``

        Consult F5 BIGIP user guide for specific options for each monitor type.
        Typically, tmsh arg names are used.

    Creating Complex Args

        Profiles can get pretty complicated in terms of the amount of possible
        config options. Use the following shorthand to create complex arguments such
        as lists, dictionaries, and lists of dictionaries. An option is also
        provided to pass raw json as well.

        lists ``[i,i,i]``:
            ``param='item1,item2,item3'``

        Dictionary ``[k:v,k:v,k,v]``:
            ``param='key-1:val-1,key-2:val2,key-3:va-3'``

        List of Dictionaries ``[k:v,k:v|k:v,k:v|k:v,k:v]``:
           ``param='key-1:val-1,key-2:val-2|key-1:val-1,key-2:val-2|key-1:val-1,key-2:val-2'``

        JSON: ``'j{ ... }j'``:
           ``cert-key-chain='j{ "default": { "cert": "default.crt", "chain": "default.crt", "key": "default.key" } }j'``

        Escaping Delimiters:
            Use ``\,`` or ``\:`` or ``\|`` to escape characters which shouldn't
            be treated as delimiters i.e. ``ciphers='DEFAULT\:!SSLv3'``

    CLI Examples::

        salt '*' bigip.modify_profile bigip admin admin http my-http-profile defaultsFrom='/Common/http'

        salt '*' bigip.modify_profile bigip admin admin http my-http-profile defaultsFrom='/Common/http' \
            enforcement=maxHeaderCount:3200,maxRequests:10

        salt '*' bigip.modify_profile bigip admin admin client-ssl my-client-ssl-1 retainCertificate=false \
            ciphers='DEFAULT\:!SSLv3'
            cert_key_chain='j{ "default": { "cert": "default.crt", "chain": "default.crt", "key": "default.key" } }j'
    '''

    #build session
    bigip_session = _build_session(username, password)

    #construct the payload
    payload = {}
    payload['name'] = name

    #there's a ton of different profiles and a ton of options for each type of profile.
    #this logic relies that the end user knows which options are meant for which profile types
    for key, value in six.iteritems(kwargs):
        if not key.startswith('__'):
            if key not in ['hostname', 'username', 'password', 'profile_type']:
                key = key.replace('_', '-')

                try:
                    payload[key] = _set_value(value)
                except salt.exceptions.CommandExecutionError:
                    return 'Error: Unable to Parse JSON data for parameter: {key}\n{value}'.format(key=key, value=value)

    #put to REST
    try:
        response = bigip_session.put(
            BIG_IP_URL_BASE.format(host=hostname) + '/ltm/profile/{type}/{name}'.format(type=profile_type, name=name),
            data=salt.utils.json.dumps(payload)
        )
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    return _load_response(response)


def delete_profile(hostname, username, password, profile_type, name):
    '''
    A function to connect to a bigip device and delete an existing profile.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    profile_type
        The type of profile to delete
    name
        The name of the profile to delete

    CLI Example::

        salt '*' bigip.delete_profile bigip admin admin http my-http-profile

    '''

    #build sessions
    bigip_session = _build_session(username, password)

    #delete to REST
    try:
        response = bigip_session.delete(BIG_IP_URL_BASE.format(host=hostname)+'/ltm/profile/{type}/{name}'.format(type=profile_type, name=name))
    except requests.exceptions.ConnectionError as e:
        return _load_connection_error(hostname, e)

    if _load_response(response) == '':
        return True
    else:
        return _load_response(response)
