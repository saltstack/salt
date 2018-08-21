# -*- coding: utf-8 -*-
'''
Consul ACL management

'''


import logging
from salt.exceptions import SaltInvocationError, CommandExecutionError

log = logging.getLogger(__name__)


def _acl_changes(name, id=None, type=None, rules=None, consul_url=None, token=None):
    '''
       return True if the acl need to be update, False if it doesn't need to be update
    '''
    r = __salt__['consul.acl_info'](id=id, token=None, consul_url=consul_url)

    if r['res'] and r['data'][0]['Name'] != name:
       return True
    elif r['res'] and r['data'][0]['Rules'] != rules:
       return True
    elif r['res'] and r['data'][0]['Type'] != type:
       return True
    else:
       return False

def _acl_exists(id=None, token=None, consul_url=None):
    '''
       return True acl exist, if False it not
    '''
    r = __salt__['consul.acl_info'](id=id, token=None, consul_url=consul_url)
    if len(r['data']) == 0:
       return False
    else:
       return True
 

def acl_present(name, id=None, token=None, type="client", rules="", consul_url='http://localhost:8500'):
    '''
      test_delete:
        consul_acl.present:
          - id: 38AC8470-4A83-4140-8DFD-F924CD32917F
          - name: yolo
          - rules: ""
          - type: client
          - consul_url: http://localhost:8500
    '''
    ret = {
	'name': name,
	'changes': {},
	'result': True,
	'comment': 'ACL "{0}" exists and is up to date'.format(name)}

    exists = _acl_exists(id, token, consul_url)
    if not exists:
       if __opts__['test']:
	  ret['result'] = None
	  ret['comment'] = "the acl doesn't exist, it will be create"
          return ret
 
       r = __salt__['consul.acl_create'](name=name, id=id, token=None, type=type, rules=rules, consul_url=consul_url)
       if r['res']:
          ret['result'] = True
	  ret['comment'] = "the acl has been created"
       elif not r['res']:
          ret['result'] = False
	  ret['comment'] = "failed to create the acl"

    changes = _acl_changes(name=name, id=id, token=None, type=type, rules=rules, consul_url=consul_url)
    if changes:
       if __opts__['test']:
	  ret['result'] = None
	  ret['comment'] = "the acl exist, but it need to be update"
          return ret

       r = __salt__['consul.acl_create'](name=name, id=id, token=None, type=type, rules=rules, consul_url=consul_url)
       if r['res']:
          ret['result'] = True
	  ret['comment'] = "the acl has been updated"
       elif r['res'] is False:
          ret['result'] = False
	  ret['comment'] = "failed to update the acl"

    return ret

def acl_absent(name, id=None, token=None, consul_url='http://localhost:8500'):
    '''
      test_delete:
        consul_acl.absent:
          - id: 38AC8470-4A83-4140-8DFD-F924CD32917F
    '''
    ret = {
	'name': id,
	'changes': {},
	'result': True,
	'comment': 'ACL "{0}" does not exist'.format(id)}

    exists = _acl_exists(id, token, consul_url)
    if exists:
       if __opts__['test']:
	  ret['result'] = None
	  ret['comment'] = "the acl exists, it will be delete"
          return ret
 
       r = __salt__['consul.acl_delete'](id=id, token=None, consul_url=consul_url)
       if r['res'] is True:
          ret['result'] = True
	  ret['comment'] = "the acl has been deleted"
       elif r['res'] is False:
          ret['result'] = False
	  ret['comment'] = "failed to delete the acl"
    return ret
