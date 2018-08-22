# -*- coding: utf-8 -*-
'''
Consul Managemnt
===========================

The consul module is used to create and manage ACL

.. code-block:: yaml

    acl_present:
      consul.acl_present:
        - id: 38AC8470-4A83-4140-8DFD-F924CD32917F
        - name: acl_name
        - rules: node "" {policy = "write"} service "" {policy = "read"} key "_rexec" {policy = "write"}
        - type: client
        - consul_url: http://localhost:8500

    acl_delete:
       consul.acl_absent:
         - id: 38AC8470-4A83-4140-8DFD-F924CD32917F
'''

import logging
from salt.exceptions import SaltInvocationError, CommandExecutionError

log = logging.getLogger(__name__)


def _acl_changes(name, id=None, type=None, rules=None, consul_url=None, token=None):
    '''
       return True if the acl need to be update, False if it doesn't need to be update
    '''
    r = __salt__['consul.acl_info'](id=id, token=token, consul_url=consul_url)

    if r['res'] and r['data'][0]['Name'] != name:
       return True
    elif r['res'] and r['data'][0]['Rules'] != rules:
       return True
    elif r['res'] and r['data'][0]['Type'] != type:
       return True
    else:
       return False

def _acl_exists(name=None, id=None, token=None, consul_url=None):
    '''
       return True if acl exist, if False it not
    '''
    
    res = { 'result' : False, 'id': None }

    if id:
        r = __salt__['consul.acl_info'](id=id, token=token, consul_url=consul_url)
    elif name:
        r = __salt__['consul.acl_list'](token=token, consul_url=consul_url)

    if len(r['data']):
        for acl in r['data']:
            if id and acl['ID'] == id:
                res['result'] = True
                res['id'] = id
            elif name and acl['Name'] == name:
                res['result'] = True
                res['id'] = acl['ID']

    return res

def acl_present(name, id=None, token=None, type="client", rules="", consul_url='http://localhost:8500'):
    '''
    Ensure the ACL is present

    name
        Specifies a human-friendly name for the ACL token.

    id
        Specifies the ID of the ACL.

    type: client
        Specifies the type of ACL token. Valid values are: client and management.

    rules
        Specifies rules for this ACL token.

    consul_url : http://locahost:8500
        consul URL to query

    .. note::
        For more information https://www.consul.io/api/acl.html#create-acl-token, https://www.consul.io/api/acl.html#update-acl-token

    '''

    ret = {
	'name': name,
	'changes': {},
	'result': True,
	'comment': 'ACL "{0}" exists and is up to date'.format(name)}

    exists = _acl_exists(name, id, token, consul_url)

    if not exists['result']:
       if __opts__['test']:
	  ret['result'] = None
	  ret['comment'] = "the acl doesn't exist, it will be create"
          return ret
 
       r = __salt__['consul.acl_create'](name=name, id=id, token=token, type=type, rules=rules, consul_url=consul_url)
       if r['res']:
          ret['result'] = True
	  ret['comment'] = "the acl has been created"
       elif not r['res']:
          ret['result'] = False
	  ret['comment'] = "failed to create the acl"
    elif exists['result']:
        changes = _acl_changes(name=name, id=exists['id'], token=token, type=type, rules=rules, consul_url=consul_url)
        if changes:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = "the acl exist, but it need to be update"
                return ret
            
            r = __salt__['consul.acl_update'](name=name, id=exists['id'], token=token, type=type, rules=rules, consul_url=consul_url)
            if r['res']:
                ret['result'] = True
                ret['comment'] = "the acl has been updated"
            elif not r['res']:
                ret['result'] = False
                ret['comment'] = "failed to update the acl"
       
    return ret

def acl_absent(name, id=None, token=None, consul_url='http://localhost:8500'):
    '''
    Ensure the ACL is absent

    name
        Specifies a human-friendly name for the ACL token.

    id
        Specifies the ID of the ACL.
    
    token
        token to authenticate you Consul query

    consul_url : http://locahost:8500
        consul URL to query
        
    .. note::
        For more information https://www.consul.io/api/acl.html#delete-acl-token

    '''
    ret = {
	'name': id,
	'changes': {},
	'result': True,
	'comment': 'ACL "{0}" does not exist'.format(id)}

    exists = _acl_exists(name, id, token, consul_url)
    if exists['result']:
       if __opts__['test']:
	  ret['result'] = None
	  ret['comment'] = "the acl exists, it will be delete"
          return ret
 
       r = __salt__['consul.acl_delete'](id=exists['id'], token=token, consul_url=consul_url)
       if r['res']:
          ret['result'] = True
	  ret['comment'] = "the acl has been deleted"
       elif not r['res']:
          ret['result'] = False
	  ret['comment'] = "failed to delete the acl"

    return ret
