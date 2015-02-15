'''

The following configuration defaults can be define in the pillar:

    ipmi.config:
        api_host: 127.0.0.1
        api_user: admin
        api_pass: apassword
        api_port: 623
        api_kg: None

every call can override the api connection config defaults:

ensure myipmi system is powered on:
    ipmi.power:
        - name: on
        - api_host: myipmi.hostname.com
        - api_user: root
        - api_pass: apassword

'''

def boot_device(name='default', **kwargs_conn):
    '''
    Request power state change

    :param bootdev:
        * network -- Request network boot
        * hd -- Boot from hard drive
        * safe -- Boot from hard drive, requesting 'safe mode'
        * optical -- boot from CD/DVD/BD drive
        * setup -- Boot into setup utility
        * default -- remove any IPMI directed boot device
                    request
    '''
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}
    org = __salt__['ipmi.get_bootdev'](**kwargs_conn)
    
    if 'bootdev' in org:
        org = org['bootdev']

    if org == name:
        ret['result'] = True
        ret['comment'] = 'system already in this state'
        return ret

    if __opts__['test']:
        ret['comment'] = 'would change boot device'
        ret['result'] = None
        ret['changes'] = { 'old': org, 'new': name }
        return ret

    outdddd = __salt__['ipmi.set_bootdev'](bootdev=name, **kwargs_conn)
    ret['comment'] = 'changed boot device'
    ret['result'] = True
    ret['changes'] = { 'old': org, 'new': name }
    return ret


def power(name='power_on', wait=300, **kwargs_conn):
    '''
    Request power state change

    :param name:
        * poweron -- system turn on
        * poweroff -- system turn off (without waiting for OS)
        * shutdown -- request OS proper shutdown
        * reset -- reset (without waiting for OS)
        * boot -- If system is off, then 'on', else 'reset'
    :param wait
        wait X seconds for the job to complete before forcing.
        (defaults to 300seconds)
    '''
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}
    org = __salt__['ipmi.get_power'](**kwargs_conn)

    state_map = {
        'off' : 'off',
        'on' : 'on',
        'power_off' : 'off',
        'power_on' : 'on',
        'shutdown' : 'off',
        'reset' : 'na',
        'boot': 'na'
    }

    if org == state_map[name]:
        ret['result'] = True
        ret['comment'] = 'system already in this state'
        return ret

    if __opts__['test']:
        ret['comment'] = 'would power: {0} system'.format(name)
        ret['result'] = None
        ret['changes'] = { 'old': org, 'new': name }
        return ret

    outdddd = __salt__['ipmi.set_power'](name, wait=wait, **kwargs_conn)
    ret['comment'] = 'changed system power'
    ret['result'] = True
    ret['changes'] = { 'old': org, 'new': name }
    return ret


def user_present(uid, name, password, channel=1, callback=False, 
                link_auth=True, ipmi_msg=True, privilege_level='administrator', **kwargs_conn):
    '''
    :param kwargs_conn: api_host='127.0.0.1' api_user='admin' api_pass='example' api_port=623
    
    Ensure a user
    name
    password
    channel
    uid, name, password, channel=1, callback=False, 
                link_auth=True, ipmi_msg=True, privilege_level='administrator', **kwargs_conn):
                
    privilege_level:
        * callback
        * user
        * operator
        * administrator
        * proprietary
        * no_access

    '''
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}
    org_user = __salt__['ipmi.get_user'](uid=uid, channel=channel, **kwargs_conn)

    change = False
    if org_user['access']['callback'] != callback: change = True
    if org_user['access']['link_auth'] != link_auth: change = True
    if org_user['access']['ipmi_msg'] != ipmi_msg: change = True
    if org_user['access']['privilege_level'] != privilege_level: change = True
    if __salt__['ipmi.set_user_password'](uid, mode='test_password', 
                                          password=password, **kwargs_conn) == False: change = True
    if change == False:
        ret['result'] = True
        ret['comment'] = 'user already present'
        return ret

    if __opts__['test']:
        ret['comment'] = 'would (re)create user'
        ret['result'] = None
        ret['changes'] = { 'old': org_user, 'new': current_user }
        return ret

    __salt__['ipmi.ensure_user'](uid,
                                 name, 
                                 password,
                                 channel,
                                 callback, 
                                 link_auth,
                                 ipmi_msg,
                                 privilege_level,
                                 **kwargs_conn)
    current_user = __salt__['ipmi.get_user'](uid=uid, channel=channel, **kwargs_conn)
    ret['comment'] = '(re)created user'
    ret['result'] = True
    ret['changes'] = { 'old': org_user, 'new': current_user }
    return ret


def user_absent(name):
    '''
    Remove user
    
    Removes all user records having the matching name
    '''
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}
    
    user_id_list = __salt__['ipmi.get_name_uids'](name, channel, **kwargs_conn)

    if len(user_id_list) == 0:
        ret['result'] = True
        ret['comment'] = 'user already absent'
        return ret
    
    if __opts__['test']:
        ret['comment'] = 'would delete user(s)'
        ret['result'] = None
        ret['changes'] = { 'delete': user_id_list }
        return ret
    
    for uid in user_id_list:
        __salt__['ipmi.delete_user'](uid, channel, **kwargs_conn)
    
    ret['comment'] = 'user(s) removed'
    ret['changes'] = { 'old': user_id_list, 'new': 'None' }
    return ret