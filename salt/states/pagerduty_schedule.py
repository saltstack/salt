# -*- coding: utf-8 -*-
'''
Manage PagerDuty schedules.

Example:

    .. code-block:: yaml

    ensure test schedule:
        pagerduty_schedule.present:
            - name: 'bruce test schedule level1'
            - schedule:
                name: 'bruce test schedule level1'
                time_zone: 'Pacific Time (US & Canada)'
                schedule_layers:
                    - name: 'Schedule Layer 1'
                      start: '2015-01-01T00:00:00'
                      users:
                        - user:
                            'id': 'Bruce TestUser1'
                          member_order: 1
                        - user:
                            'id': 'Bruce TestUser2'
                          member_order: 2
                        - user:
                            'id': 'bruce+test3@lyft.com'
                          member_order: 3
                        - user:
                            'id': 'bruce+test4@lyft.com'
                          member_order: 4
                      rotation_virtual_start: '2015-01-01T00:00:00'
                      priority: 1
                      rotation_turn_length_seconds: 604800

'''


def __virtual__():
    '''
    Only load if the pygerduty module is available in __salt__
    '''
    return 'pagerduty_schedule' if 'pagerduty_util.get_resource' in __salt__ else False


def present(profile='pagerduty', subdomain=None, api_key=None, **kwargs):
    '''
    Ensure that a pagerduty schedule exists.
    This method accepts as args everything defined in
    https://developer.pagerduty.com/documentation/rest/schedules/create.
    This means that most arguments are in a dict called "schedule."

    User id's can be pagerduty id, or name, or email address.
    '''
    # for convenience, we accept id, name, or email as the user id.
    kwargs['schedule']['name'] = kwargs['name']  # match PD API structure
    for schedule_layer in kwargs['schedule']['schedule_layers']:
        for user in schedule_layer['users']:
            u = __salt__['pagerduty_util.get_resource']('users',
                                                        user['user']['id'],
                                                        ['email', 'name', 'id'],
                                                        profile=profile,
                                                        subdomain=subdomain,
                                                        api_key=api_key)
            if u is None:
                raise Exception('unknown user: {0}'.format(str(user)))
            user['user']['id'] = u['id']
    r = __salt__['pagerduty_util.resource_present']('schedules',
                                                    ['name', 'id'],
                                                    _diff,
                                                    profile,
                                                    subdomain,
                                                    api_key,
                                                    **kwargs)
    return r


def absent(profile='pagerduty', subdomain=None, api_key=None, **kwargs):
    '''
    Ensure that a pagerduty schedule does not exist.
    Name can be pagerduty schedule id or pagerduty schedule name.
    '''
    r = __salt__['pagerduty_util.resource_absent']('schedules',
                                                   ['name', 'id'],
                                                   profile,
                                                   subdomain,
                                                   api_key,
                                                   **kwargs)
    return r


def _diff(state_data, resource_object):
    '''helper method to compare salt state info with the PagerDuty API json structure,
    and determine if we need to update.

    returns the dict to pass to the PD API to perform the update, or empty dict if no update.
    '''

    state_data['id'] = resource_object['schedule']['id']
    objects_differ = None

    # first check all the easy top-level properties: everything except the schedule_layers.
    for k, v in state_data['schedule'].items():
        if k == 'schedule_layers':
            continue
        if v != resource_object['schedule'][k]:
            objects_differ = '{0} {1} {2}'.format(k, v, resource_object['schedule'][k])
            break

    # check schedule_layers
    if not objects_differ:
        for layer in state_data['schedule']['schedule_layers']:
            # find matching layer name
            resource_layer = None
            for resource_layer in resource_object['schedule']['schedule_layers']:
                found = False
                if layer['name'] == resource_layer['name']:
                    found = True
                    break
            if not found:
                objects_differ = 'layer {0} missing'.format(layer['name'])
                break
            # set the id, so that we will update this layer instead of creating a new one
            layer['id'] = resource_layer['id']
            # compare contents of layer and resource_layer
            for k, v in layer.items():
                if k == 'users':
                    continue
                if k == 'start':
                    continue
                if v != resource_layer[k]:
                    objects_differ = 'layer {0} key {1} {2} != {3}'.format(layer['name'], k, v, resource_layer[k])
                    break
            if objects_differ:
                break
            # compare layer['users']
            if len(layer['users']) != len(resource_layer['users']):
                objects_differ = 'num users in layer {0} {1} != {2}'.format(layer['name'], len(layer['users']), len(resource_layer['users']))
                break

            for user1 in layer['users']:
                found = False
                user2 = None
                for user2 in resource_layer['users']:
                    # deal with PD API bug: when you submit member_order=N, you get back member_order=N+1
                    if user1['member_order'] == user2['member_order'] - 1:
                        found = True
                        break
                if not found:
                    objects_differ = 'layer {0} no one with member_order {1}'.format(layer['name'], user1['member_order'])
                    break
                if user1['user']['id'] != user2['user']['id']:
                    objects_differ = 'layer {0} user at member_order {1} {2} != {3}'.format(layer['name'],
                                                                                            user1['member_order'],
                                                                                            user1['user']['id'],
                                                                                            user2['user']['id'])
                    break
    if objects_differ:
        return state_data
    else:
        return {}
